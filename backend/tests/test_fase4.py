"""Tes Fase 4: stok/Days, aturan berversi + audit, simulasi, perencanaan,
analisis stok-margin, dan alarm."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.alarm import evaluasi_alarm
from app.importer.template import impor_template
from app.main import buat_app
from app.models import Base, Sicom

from tests.conftest import TEMPLATE


@pytest.fixture(scope="module")
def engine4(tmp_path_factory):
    """DB terpisah untuk Fase 4 (ada tes yang menulis aturan/parameter)."""
    db = tmp_path_factory.mktemp("db4") / "fase4.db"
    eng = create_engine(f"sqlite:///{db}", future=True)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, future=True)
    with Session() as s:
        impor_template(str(TEMPLATE), s, pengunggah="pytest")
    return eng


@pytest.fixture(scope="module")
def klien(engine4):
    return TestClient(buat_app(engine4))


# ----------------------------------------------------------------------------
# Kriteria 1: Days & rasio
# ----------------------------------------------------------------------------
def test_stok_days_rasio(klien):
    r = klien.get("/api/stok", params={"dari": "2023-01-31", "sampai": "2023-01-31"}).json()
    assert r["baris"][0]["days"] == 15.687
    r = klien.get("/api/stok", params={"dari": "2026-08-31", "sampai": "2026-08-31"}).json()
    b = r["baris"][0]
    assert b["days"] == 2.962
    assert b["rasio_stok"] == 0.1975
    assert b["status"] == "di bawah safety"


def test_stok_hari_di_bawah_safety(klien):
    r = klien.get("/api/stok").json()
    assert r["jumlah_hari_di_bawah_safety"] > 0
    assert r["terakhir"] is not None


# ----------------------------------------------------------------------------
# Kriteria 2: Perencanaan Jan 2027 sebelum & sesudah Effort
# ----------------------------------------------------------------------------
def test_rencana_jan_2027(klien):
    r = klien.get("/api/rencana/2027").json()
    jan = r["bulan"][0]
    assert jan["rata_rata_dasar"] == 11.6703
    assert jan["sebelum_effort"] == 9.6703   # 11,6703 - 2
    assert jan["net_margin"] == 11.7603      # + effort 2,09
    assert jan["margin_per_tahun"]["2023"] == 16.3364
    assert not jan["perkiraan"]
    nov = r["bulan"][10]
    assert nov["perkiraan"]  # Nov 2026 belum ada data


def test_rencana_simpan_dan_audit(klien):
    r = klien.post("/api/rencana", json={
        "tahun_target": 2027, "bulan": 1, "penyesuaian_manual_usc": -2,
        "effort_usc": 2.09, "alasan": "uji simpan", "pengisi": "tester"})
    assert r.status_code == 200
    audit = klien.get("/api/audit", params={"objek": "perencanaan"}).json()
    assert audit and audit[0]["siapa"] == "tester"


# ----------------------------------------------------------------------------
# Kriteria 3: perubahan aturan/parameter tidak mengubah hasil historis
# ----------------------------------------------------------------------------
def test_aturan_baru_tidak_mengubah_historis(klien):
    # Sebelum: 31 Agu 2026 memakai versi CONTOH (penyesuaian -2 utk rasio 0,1975)
    sebelum = klien.get("/api/rekomendasi", params={"tanggal": "2026-08-31"}).json()
    assert sebelum["status"] == "OK"
    assert sebelum["penyesuaian_usc"] == -2
    assert sebelum["aturan_contoh"]

    # Versi baru berlaku 1 Sep 2026 dengan angka berbeda (dari input, bukan kode)
    r = klien.post("/api/aturan", json={
        "berlaku_dari": "2026-09-01",
        "baris": [
            {"batas_bawah": 0, "batas_atas": 0.5, "penyesuaian_usc": -3,
             "keterangan": "stok tipis (resmi)"},
            {"batas_bawah": 0.5, "batas_atas": 1.2, "penyesuaian_usc": 0},
            {"batas_bawah": 1.2, "batas_atas": None, "penyesuaian_usc": 1.5},
        ],
        "alasan": "uji kebijakan baru", "pengisi": "manajer-uji"})
    assert r.status_code == 200

    # Historis 31 Agu 2026: TIDAK berubah (tetap versi lama)
    sesudah = klien.get("/api/rekomendasi", params={"tanggal": "2026-08-31"}).json()
    assert sesudah["penyesuaian_usc"] == -2
    assert sesudah["harga_beli_maks_usc"] == sebelum["harga_beli_maks_usc"]

    # Tanggal >= 1 Sep 2026: memakai versi baru (rasio < 0,5 -> -3)
    baru = klien.get("/api/rekomendasi", params={"tanggal": "2026-09-05"}).json()
    assert baru["status"] == "OK"
    assert baru["penyesuaian_usc"] == -3
    assert not baru["aturan_contoh"]

    # Tercatat di audit log
    audit = klien.get("/api/audit", params={"objek": "aturan_stok_harga"}).json()
    assert audit and audit[0]["siapa"] == "manajer-uji"
    assert audit[0]["detail"]["alasan"] == "uji kebijakan baru"


def test_parameter_baru_tidak_mengubah_historis(klien):
    r = klien.post("/api/parameter", json={
        "berlaku_dari": "2026-11-01", "kapasitas_ton_per_hari": 200,
        "safety_stock_ton": 3000, "catatan": "uji", "pengisi": "admin-uji"})
    assert r.status_code == 200
    # Days historis tidak berubah
    h = klien.get("/api/stok", params={"dari": "2023-01-31", "sampai": "2023-01-31"}).json()
    assert h["baris"][0]["days"] == 15.687
    h = klien.get("/api/stok", params={"dari": "2026-08-31", "sampai": "2026-08-31"}).json()
    assert h["baris"][0]["days"] == 2.962
    audit = klien.get("/api/audit", params={"objek": "parameter_pabrik"}).json()
    assert audit and audit[0]["siapa"] == "admin-uji"


def test_aturan_duplikat_tanggal_ditolak(klien):
    r = klien.post("/api/aturan", json={
        "berlaku_dari": "2026-09-01",
        "baris": [{"batas_bawah": 0, "batas_atas": None, "penyesuaian_usc": 0}],
        "pengisi": "x"})
    assert r.status_code == 422
    assert "Sudah ada versi" in r.json()["detail"]


def test_aturan_belum_diisi(tmp_path):
    """Aplikasi tanpa aturan sama sekali -> status ATURAN BELUM DIISI."""
    eng = create_engine(f"sqlite:///{tmp_path/'kosong.db'}", future=True)
    Base.metadata.create_all(eng)
    k = TestClient(buat_app(eng))
    k.post("/api/sicom", json={"tanggal": "2026-10-16", "usc_per_kg": 250})
    r = k.get("/api/rekomendasi").json()
    assert r["status"] in ("ATURAN BELUM DIISI", "DATA KURANG")
    r = k.get("/api/simulasi", params={"sicom": 250, "kurs": 16000, "stok_ton": 500,
                                       "tanggal": "2026-10-16"})
    # tanpa parameter pabrik -> 422; itu pun pesan jelas
    assert r.status_code == 422


# ----------------------------------------------------------------------------
# Simulasi: dampak terhitung, tidak menyimpan apa pun
# ----------------------------------------------------------------------------
def test_simulasi_tidak_menyimpan(klien, engine4):
    Session = sessionmaker(bind=engine4, future=True)
    with Session() as s:
        sicom_sebelum = s.query(Sicom).count()
    r = klien.get("/api/simulasi", params={
        "sicom": 250.0, "kurs": 16000, "stok_ton": 500, "tanggal": "2026-10-10"}).json()
    assert r["status"] == "OK"
    assert r["rasio_stok"] == round(500 / 2795.1, 4)
    assert r["days"] == round(500 / 186.34, 3)
    # versi aturan baru (1 Sep 2026) berlaku utk tanggal simulasi ini: -3
    assert r["penyesuaian_usc"] == -3
    assert r["harga_beli_maks_usc"] == round(250 - (13 + (-3)), 4)
    assert r["harga_beli_maks_rp_kg"] == round((250 - 10) * 16000 / 100, 2)
    assert "tidak ada yang disimpan" in r["catatan"].lower()
    with Session() as s:
        assert s.query(Sicom).count() == sicom_sebelum  # tidak menyimpan

    # geser stok ke atas -> penyesuaian berubah mengikuti aturan
    r2 = klien.get("/api/simulasi", params={
        "sicom": 250.0, "kurs": 16000, "stok_ton": 4000, "tanggal": "2026-10-10"}).json()
    assert r2["penyesuaian_usc"] == 1.5
    assert r2["harga_beli_maks_usc"] < r["harga_beli_maks_usc"]


# ----------------------------------------------------------------------------
# Analisis stok vs margin (informasi, bukan aturan)
# ----------------------------------------------------------------------------
def test_analisis_stok_margin(klien):
    r = klien.get("/api/analisis/stok-margin").json()
    assert r["jumlah_bulan"] >= 40  # 2023 s.d. 2026 punya data stok
    assert r["korelasi"] is not None and 0.2 < r["korelasi"] < 0.7
    assert r["margin_stok_rendah"] < r["margin_stok_tinggi"]
    assert "bukan bukti sebab-akibat" in r["catatan"]


# ----------------------------------------------------------------------------
# Kriteria 4: alarm SICOM hari ini dikosongkan
# ----------------------------------------------------------------------------
def test_alarm_sicom_kosong(engine4):
    Session = sessionmaker(bind=engine4, future=True)
    with Session() as s:
        # SICOM terakhir di data = 10 Okt 2026. "Hari ini" = 12 Okt ->
        # SICOM kemarin & hari ini kosong -> alarm menyala.
        alarm = evaluasi_alarm(s, hari_ini=dt.date(2026, 10, 12))
        kode = {a.kode for a in alarm}
        assert "SICOM_TERLAMBAT" in kode
        pesan = next(a.pesan for a in alarm if a.kode == "SICOM_TERLAMBAT")
        assert "10/10/2026" in pesan

        # Isi SICOM hari itu -> alarm padam
        s.add(Sicom(tanggal=dt.date(2026, 10, 12), usc_per_kg=260.0,
                    sumber="uji alarm"))
        s.flush()
        alarm2 = evaluasi_alarm(s, hari_ini=dt.date(2026, 10, 12))
        assert "SICOM_TERLAMBAT" not in {a.kode for a in alarm2}
        s.rollback()


def test_alarm_pengaturan_admin(klien):
    r = klien.get("/api/alarm").json()
    kode = {p["kode"] for p in r["pengaturan"]}
    assert {"STOK_DI_BAWAH_SAFETY", "MARGIN_DI_BAWAH_TARGET", "SICOM_TERLAMBAT",
            "KURS_TERLAMBAT", "STOK_TERLAMBAT", "TIKET_TERLAMBAT",
            "SELISIH_REKONSILIASI", "HARGA_DI_ATAS_MAKS"} <= kode
    # stok terakhir 551 ton << safety -> alarm stok menyala (ambang 1,0)
    assert any(a["kode"] == "STOK_DI_BAWAH_SAFETY" for a in r["alarm"])
    # rekonsiliasi: selisih diketahui Jul/Agu 2026 ikut sebagai alarm
    assert any(a["kode"] == "SELISIH_REKONSILIASI" for a in r["alarm"])

    # admin menonaktifkan -> alarm hilang; tercatat di audit
    r = klien.post("/api/alarm/pengaturan", json={
        "kode": "STOK_DI_BAWAH_SAFETY", "aktif": False, "ambang": 1.0,
        "pengisi": "admin-uji"})
    assert r.status_code == 200
    r = klien.get("/api/alarm").json()
    assert not any(a["kode"] == "STOK_DI_BAWAH_SAFETY" for a in r["alarm"])
    audit = klien.get("/api/audit", params={"objek": "pengaturan_alarm"}).json()
    assert audit and audit[0]["siapa"] == "admin-uji"
    # kembalikan
    klien.post("/api/alarm/pengaturan", json={
        "kode": "STOK_DI_BAWAH_SAFETY", "aktif": True, "ambang": 1.0,
        "pengisi": "admin-uji"})
