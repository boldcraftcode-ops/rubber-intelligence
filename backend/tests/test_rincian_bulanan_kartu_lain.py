"""Tes rincian PER BULAN untuk kartu Tonase dan Margin per grade/vendor.

Melengkapi `per=bulan` pada kartu Penerimaan karet: bila filter periode lebih
dari satu bulan, kedua kartu ini juga menampilkan bulan x dimensi.

Aturan yang dijaga (sama dengan kartu penerimaan):
- sumbu bulan mengikuti periode filter, bukan data;
- dimensi di luar `top` digabung menjadi "Lainnya";
- margin adalah TINGKAT (US¢/kg), jadi tidak dijumlahkan antar dimensi —
  total per bulan memakai agregat tertimbang tonase;
- tanpa `per=bulan`, bentuk jawaban lama tidak berubah.

Data sintetis dibuat di sini (template hanya punya 3 tiket satu bulan).
"""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import buat_app
from app.models import Base, Kurs, Pembelian, Sicom, TiketBaris, Vendor

KURS = 16000.0     # Rp/USD
SICOM = 200.0      # US¢/kg


def _engine():
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def _isi(session):
    session.add_all([Vendor(kode="V001", nama_baku="PT Alpha"),
                     Vendor(kode="V002", nama_baku="PT Beta"),
                     Vendor(kode="V003", nama_baku="CV Gamma")])
    session.add(Sicom(tanggal=dt.date(2025, 12, 1), usc_per_kg=SICOM))
    session.add(Kurs(berlaku_dari=dt.date(2025, 12, 1), idr_per_usd=KURS))

    n = 0
    # tonase: (vendor, bulan) -> kg kering
    tonase = {("V001", 1): 100_000, ("V001", 2): 200_000, ("V001", 3): 300_000,
              ("V002", 1): 50_000, ("V002", 3): 50_000,
              ("V003", 2): 25_000}
    for (vendor, bulan), kg in tonase.items():
        n += 1
        session.add(TiketBaris(
            ticket_no=f"T{n:03d}", line_seq=1,
            ticket_date=dt.date(2026, bulan, 10), kode_vendor=vendor,
            item_code="SIR20", dry_kg=kg, provinsi="Sumatera Utara",
            kabupaten="Deli Serdang", kecamatan="Sunggal", desa="Sei Semayang",
            tiket_nol=False))

    # pembelian rinci per grade: harga beli berbeda tiap bulan
    # margin = SICOM - harga_beli; harga_beli = amount/qty/kurs*100
    # qty 100.000 kg, amount = qty * harga_rp ; harga_usc = harga_rp/kurs*100
    for bulan, harga_usc in [(1, 190.0), (2, 195.0), (3, 180.0)]:
        for grade, qty in [("SIR20", 100_000), ("SIR10", 50_000)]:
            harga_rp = harga_usc / 100.0 * KURS
            session.add(Pembelian(
                tanggal=dt.date(2026, bulan, 10), item_code=grade,
                kode_vendor="", ticket_no="",
                qty_kering_kg=qty, amount_rp=qty * harga_rp))
    session.commit()


@pytest.fixture()
def klien(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    with sessionmaker(bind=eng, future=True)() as s:
        _isi(s)
    return TestClient(buat_app(eng))


# =============================================================== TONASE / bulan
def _tonase(klien, **params):
    dasar = {"dimensi": "vendor", "per": "bulan",
             "dari": "2026-01-01", "sampai": "2026-03-31"}
    dasar.update(params)
    r = klien.get("/api/kartu/tonase", params=dasar)
    assert r.status_code == 200, r.text
    return r.json()


def test_tonase_bulan_berurutan(klien):
    d = _tonase(klien)
    assert [b["label"] for b in d["bulan"]] == ["Jan-26", "Feb-26", "Mar-26"]
    assert d["per"] == "bulan"


def test_tonase_nilai_per_bulan(klien):
    d = _tonase(klien)
    v1 = next(b for b in d["baris"] if b["kunci"] == "V001")
    assert v1["ton_per_bulan"] == [100.0, 200.0, 300.0]
    assert v1["ton"] == 600.0


def test_tonase_bulan_kosong_nol(klien):
    v2 = next(b for b in _tonase(klien)["baris"] if b["kunci"] == "V002")
    assert v2["ton_per_bulan"] == [50.0, 0.0, 50.0]


def test_tonase_total_per_bulan(klien):
    d = _tonase(klien)
    assert d["total_per_bulan"] == [150.0, 225.0, 350.0]
    assert round(sum(d["total_per_bulan"]), 3) == d["total_ton"] == 725.0


def test_tonase_lainnya_digabung(klien):
    d = _tonase(klien, top=1)
    assert len(d["baris"]) == 2
    assert d["baris"][1]["kunci"] == "__lainnya__"
    assert d["baris"][1]["ton_per_bulan"] == [50.0, 25.0, 50.0]
    assert round(sum(d["total_per_bulan"]), 3) == d["total_ton"]


def test_tonase_bulan_mengikuti_filter_bukan_data(klien):
    """Filter Feb-Mar: sumbu 2 bulan walau V001 punya data Jan juga."""
    d = _tonase(klien, dari="2026-02-01", sampai="2026-03-31")
    assert [b["label"] for b in d["bulan"]] == ["Feb-26", "Mar-26"]
    v1 = next(b for b in d["baris"] if b["kunci"] == "V001")
    assert v1["ton_per_bulan"] == [200.0, 300.0]


def test_tonase_dimensi_wilayah(klien):
    d = _tonase(klien, dimensi="kabupaten")
    assert [b["kunci"] for b in d["baris"]] == ["Deli Serdang"]


def test_tonase_tanpa_per_bulan_tetap_lama(klien):
    r = klien.get("/api/kartu/tonase", params={"dimensi": "vendor"})
    d = r.json()
    assert "ton_per_bulan" not in d["baris"][0]
    assert d["baris"][0]["ton"] == 600.0


def test_tonase_per_tidak_dikenal(klien):
    r = klien.get("/api/kartu/tonase", params={"dimensi": "vendor", "per": "tahun"})
    assert r.status_code == 422


def test_tonase_ekspor_xlsx_per_bulan(klien):
    r = klien.get("/api/kartu/tonase", params={
        "dimensi": "vendor", "per": "bulan", "format": "xlsx",
        "dari": "2026-01-01", "sampai": "2026-03-31"})
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]
    assert "per_bulan" in r.headers.get("content-disposition", "")


# ======================================================== MARGIN-PER / bulan
def _margin(klien, **params):
    dasar = {"dimensi": "grade", "per": "bulan",
             "dari": "2026-01-01", "sampai": "2026-03-31"}
    dasar.update(params)
    r = klien.get("/api/kartu/margin-per", params=dasar)
    assert r.status_code == 200, r.text
    return r.json()


def test_margin_bulan_dan_nilai(klien):
    d = _margin(klien)
    assert [b["label"] for b in d["bulan"]] == ["Jan-26", "Feb-26", "Mar-26"]
    sir20 = next(b for b in d["baris"] if b["kunci"] == "SIR20")
    # margin = SICOM(200) - harga beli (190/195/180)
    assert sir20["margin_per_bulan"] == [10.0, 5.0, 20.0]


def test_margin_total_per_bulan_tertimbang_bukan_dijumlah(klien):
    """Margin adalah tingkat: total per bulan = 10/5/20, bukan 20/10/40."""
    d = _margin(klien)
    assert d["total_per_bulan"]["op_margin"] == [10.0, 5.0, 20.0]


def test_margin_ton_per_bulan(klien):
    d = _margin(klien)
    assert d["total_per_bulan"]["ton"] == [150.0, 150.0, 150.0]


def test_margin_dimensi_vendor_tanpa_rinci_kosong(klien):
    """Pembelian di data ini tidak punya kode_vendor -> tidak dialokasikan.

    Sistem TIDAK boleh membagi rata margin ke vendor; jawabannya harus
    'data harga belum tersedia'.
    """
    r = klien.get("/api/kartu/margin-per", params={
        "dimensi": "vendor", "per": "bulan",
        "dari": "2026-01-01", "sampai": "2026-03-31"})
    d = r.json()
    assert d["status"] == "data harga belum tersedia"
    assert d["baris"] == []


def test_margin_lainnya_digabung(klien):
    d = _margin(klien, top=1)
    assert len(d["baris"]) == 2
    assert d["baris"][1]["kunci"] == "__lainnya__"
    # SIR10 juga margin 10/5/20 -> gabungan tetap nilai yang sama
    assert d["baris"][1]["margin_per_bulan"] == [10.0, 5.0, 20.0]


def test_margin_tanpa_per_bulan_bentuk_lama(klien):
    r = klien.get("/api/kartu/margin-per", params={"dimensi": "grade",
                                                  "tahun": 2026})
    d = r.json()
    assert d["status"] == "ok"
    assert "margin_per_bulan" not in d["baris"][0]
    # urut abjad kunci: SIR10 (50 t x 3 bulan) dan SIR20 (100 t x 3 bulan)
    ton = {b["kunci"]: b["ton"] for b in d["baris"]}
    assert ton == {"SIR10": 150.0, "SIR20": 300.0}


def test_margin_tanpa_tahun_memakai_data_terakhir(klien):
    """Parameter tahun kini opsional (dipakai halaman dengan filter bulan)."""
    r = klien.get("/api/kartu/margin-per", params={"dimensi": "grade"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_margin_rentang_terbalik_ditolak(klien):
    r = klien.get("/api/kartu/margin-per", params={
        "dimensi": "grade", "dari": "2026-03-01", "sampai": "2026-01-01"})
    assert r.status_code == 422


def test_margin_ekspor_xlsx_per_bulan(klien):
    r = klien.get("/api/kartu/margin-per", params={
        "dimensi": "grade", "per": "bulan", "format": "xlsx",
        "dari": "2026-01-01", "sampai": "2026-03-31"})
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]
