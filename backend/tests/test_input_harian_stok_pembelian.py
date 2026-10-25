"""Tes input harian tambahan: stok & pembelian (v0.9.7).

Latar belakang: dua sumber data yang paling cepat basi (Stok, Pembelian) dulu
hanya bisa masuk lewat unggah Excel. Sekarang bisa diisi langsung dari menu
Input Harian, dengan syarat:

- penulisan ganda pada tanggal+jenis yang sama MENIMPA (koreksi), bukan
  menambah baris baru;
- "total" dan "per grade" tidak boleh dicampur pada tanggal yang sama, karena
  mart menjumlahkan semua baris stok (bisa terhitung dua kali);
- begitu juga pembelian: baris TOTAL tidak boleh dicampur baris rinci;
- setiap simpanan berjejak (raw + audit) dan langsung membangun ulang mart;
- panel kesegaran memberi tahu tanggal mana yang belum punya data.
"""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.main import buat_app
from app.importer.template import impor_template
from app.models import Base, MartHarian, Pembelian, RawUnggahan, Stok

from tests.conftest import TEMPLATE


@pytest.fixture(scope="module")
def engine_input(tmp_path_factory):
    db = tmp_path_factory.mktemp("dbinput") / "input.db"
    eng = create_engine(f"sqlite:///{db}", future=True)
    Base.metadata.create_all(eng)
    with sessionmaker(bind=eng, future=True)() as s:
        impor_template(str(TEMPLATE), s, pengunggah="pytest")
    return eng


@pytest.fixture(scope="module")
def klien(engine_input):
    return TestClient(buat_app(engine_input))


@pytest.fixture()
def sesi(engine_input):
    """Sesi terpisah untuk memeriksa isi database setelah POST."""
    with sessionmaker(bind=engine_input, future=True)() as s:
        yield s


TGL = "2026-10-15"
GRADE = "SLAB1"   # grade yang memang ada di template


def test_panel_kesegaran_berisi_lima_sumber(klien):
    d = klien.get("/api/input-harian").json()
    nama = [x["sumber"] for x in d["sumber"]]
    assert nama == ["SICOM", "Kurs", "Stok", "Tiket", "Pembelian"]
    assert d["hari_dicek"] == 7
    assert len(d["tanggal_kosong"]["stok"]) <= 7
    assert len(d["tanggal_kosong"]["pembelian"]) <= 7
    # Kurs tidak wajib harian, sumber lain wajib
    wajib = {x["sumber"]: x["wajib_harian"] for x in d["sumber"]}
    assert wajib["Kurs"] is False and wajib["Stok"] is True
    assert d["sicom_terakhir"]["usc_per_kg"] > 0
    assert d["kurs_terakhir"]["idr_per_usd"] > 0
    assert d["stok_terakhir"]["stok_ton"] > 0


def test_health_menyebut_fitur_input_baru(klien):
    fitur = klien.get("/api/health").json()["fitur"]
    for nama in ("input-harian", "input-stok", "input-pembelian"):
        assert nama in fitur


def test_simpan_stok_lalu_mart_ikut_segar(klien, sesi):
    r = klien.post("/api/stok", json={"tanggal": TGL, "item_code": "",
                                      "stok_kg": 500_000, "pengisi": "uji"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "tersimpan" and d["nilai_sebelumnya"] is None
    assert d["ringkasan"]["stok_ton"] == pytest.approx(500.0, abs=0.001)
    # Days & rasio terisi karena parameter pabrik ada di template
    assert d["ringkasan"]["days"] is not None
    assert d["ringkasan"]["rasio_stok"] is not None

    m = sesi.scalar(select(MartHarian).where(
        MartHarian.tanggal == dt.date(2026, 10, 15)))
    assert m is not None and m.stok_ton == pytest.approx(500.0, abs=0.001)

    # tersimpan di panel kesegaran: tanggal itu tidak lagi "kosong" untuk stok
    panel = klien.get("/api/input-harian").json()
    assert panel["riwayat_stok"][0]["tanggal"] == TGL


def test_simpan_stok_lagi_menimpa_bukan_menambah(klien, sesi):
    r = klien.post("/api/stok", json={"tanggal": TGL, "item_code": "",
                                      "stok_kg": 420_000, "pengisi": "uji"})
    d = r.json()
    assert d["nilai_sebelumnya"] == pytest.approx(500_000)
    assert "diperbarui" in d["pesan"]
    baris = list(sesi.scalars(select(Stok).where(Stok.tanggal == dt.date(2026, 10, 15))))
    assert len(baris) == 1
    assert float(baris[0].stok_kg) == pytest.approx(420_000)
    m = sesi.scalar(select(MartHarian).where(
        MartHarian.tanggal == dt.date(2026, 10, 15)))
    assert m.stok_ton == pytest.approx(420.0, abs=0.001)


def test_stok_total_dan_per_grade_tidak_boleh_dicampur(klien):
    r = klien.post("/api/stok", json={"tanggal": TGL, "item_code": "SLAB1",
                                      "stok_kg": 100_000, "pengisi": "uji"})
    assert r.status_code == 422
    assert "terhitung dua kali" in r.json()["detail"]


def test_stok_grade_tak_dikenal_ditolak(klien):
    r = klien.post("/api/stok", json={"tanggal": "2026-10-14",
                                      "item_code": "GRADE_ASAL", "stok_kg": 1000})
    assert r.status_code == 422
    assert "belum ada di Master Grade" in r.json()["detail"]


def test_stok_tanggal_jauh_di_masa_depan_ditolak(klien):
    jauh = (dt.date.today() + dt.timedelta(days=30)).isoformat()
    r = klien.post("/api/stok", json={"tanggal": jauh, "stok_kg": 1000})
    assert r.status_code == 422
    assert "masa depan" in r.json()["detail"]


def test_stok_nol_ditolak(klien):
    r = klien.post("/api/stok", json={"tanggal": "2026-10-13", "stok_kg": 0})
    assert r.status_code == 422


def test_simpan_pembelian_menghitung_harga_dan_margin(klien, sesi):
    # Pakai tanggal yang belum punya pembelian rinci
    tgl = "2026-09-08"
    r = klien.post("/api/pembelian", json={
        "tanggal": tgl, "item_code": "ALL", "qty_kering_kg": 10_000,
        "amount_rp": 250_000_000, "pengisi": "uji"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["harga_rp_per_kg"] == pytest.approx(25_000)
    assert d["kurs"] > 0
    # US¢/kg = Rp/kg : kurs : 100
    # dibulatkan 4 desimal oleh API
    assert d["harga_usc_per_kg"] == pytest.approx(
        d["harga_rp_per_kg"] / d["kurs"] / 100, abs=1e-4)
    assert d["margin_usc"] == pytest.approx(d["sicom_usc"] - d["harga_usc_per_kg"],
                                            abs=1e-3)

    m = sesi.scalar(select(MartHarian).where(
        MartHarian.tanggal == dt.date(2026, 9, 8)))
    assert m is not None and m.harga_rp_per_kg == pytest.approx(25_000, abs=0.01)


def test_pembelian_menimpa_baris_yang_sama(klien, sesi):
    r = klien.post("/api/pembelian", json={
        "tanggal": "2026-09-08", "item_code": "ALL", "qty_kering_kg": 10_000,
        "amount_rp": 260_000_000, "pengisi": "uji"})
    d = r.json()
    assert d["nilai_sebelumnya"]["amount_rp"] == pytest.approx(250_000_000)
    assert "diperbarui" in d["pesan"]
    baris = list(sesi.scalars(select(Pembelian).where(
        Pembelian.tanggal == dt.date(2026, 9, 8), Pembelian.item_code == "ALL")))
    assert len(baris) == 1
    assert float(baris[0].amount_rp) == pytest.approx(260_000_000)


def test_pembelian_total_dan_rinci_tidak_boleh_dicampur(klien):
    r = klien.post("/api/pembelian", json={
        "tanggal": "2026-09-08", "item_code": "SLAB1", "qty_kering_kg": 1000,
        "amount_rp": 10_000_000})
    assert r.status_code == 422
    assert "TOTAL" in r.json()["detail"]


def test_pembelian_vendor_tak_dikenal_ditolak(klien):
    r = klien.post("/api/pembelian", json={
        "tanggal": "2026-10-12", "item_code": "SLAB1", "kode_vendor": "V999",
        "qty_kering_kg": 1000, "amount_rp": 10_000_000})
    assert r.status_code == 422
    assert "Master Vendor" in r.json()["detail"]


def test_setiap_simpanan_berjejak(klien, sesi):
    """Input manual tercatat di lapisan raw: siapa, kapan, apa isinya."""
    nama = {r.nama_file for r in sesi.scalars(select(RawUnggahan))}
    assert "input-manual:stok" in nama
    assert "input-manual:pembelian" in nama
    assert any(r.pengunggah == "uji" for r in sesi.scalars(select(RawUnggahan)))
