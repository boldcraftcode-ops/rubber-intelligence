"""Tes rincian penerimaan PER BULAN (parameter `per=bulan`).

Dipakai saat filter periode mencakup lebih dari satu bulan: yang ditampilkan
bukan total sepanjang periode, melainkan bulan x dimensi (vendor / provinsi /
kabupaten / kecamatan / desa), supaya pergerakan tiap pihak terlihat.

Data di tes ini SINTETIS (dibuat di sini, bukan dari template) karena template
hanya memuat 3 tiket pada satu bulan, sehingga tidak bisa menguji pecahan bulan.
"""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import buat_app
from app.models import Base, Grade, TiketBaris, Vendor


def _engine():
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def _isi_data(session):
    """3 vendor x 3 bulan (Jan-Mar 2026) + 1 tiket EUDR di Feb."""
    session.add_all([
        Vendor(kode="V001", nama_baku="PT Alpha"),
        Vendor(kode="V002", nama_baku="PT Beta"),
        Vendor(kode="V003", nama_baku="CV Gamma"),
        Grade(item_code="SIR20", keterangan="SIR 20", eudr=False),
        Grade(item_code="TTSR20", keterangan="TSR EUDR", eudr=True),
    ])
    session.commit()

    baris = []
    # kg kering per (vendor, bulan, tipe)
    data = {
        ("V001", 1): 1000.0, ("V001", 2): 2000.0, ("V001", 3): 3000.0,
        ("V002", 1): 500.0,  ("V002", 2): 0.0,    ("V002", 3): 500.0,
        ("V003", 2): 250.0,   # hanya satu bulan -> menguji bulan kosong
    }
    n = 0
    for (vendor, bulan), kg in data.items():
        if kg <= 0:
            continue
        n += 1
        baris.append(TiketBaris(
            ticket_no=f"T{n:03d}", line_seq=1,
            ticket_date=dt.date(2026, bulan, 10),
            kode_vendor=vendor, item_code="SIR20", dry_kg=kg,
            provinsi="Sumatera Utara",
            kabupaten="Deli Serdang" if vendor != "V003" else "Langkat",
            kecamatan="Sunggal", desa="Sei Semayang", tiket_nol=False))
    n += 1
    baris.append(TiketBaris(
        ticket_no=f"T{n:03d}", line_seq=1,
        ticket_date=dt.date(2026, 2, 20),
        kode_vendor="V001", item_code="TTSR20", dry_kg=400.0,
        provinsi="Sumatera Utara", kabupaten="Deli Serdang",
        kecamatan="Sunggal", desa="Sei Semayang", tiket_nol=False))
    session.add_all(baris)
    session.commit()


@pytest.fixture()
def klien(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    Session = sessionmaker(bind=eng, future=True)
    with Session() as s:
        _isi_data(s)
    return TestClient(buat_app(eng))


def _ambil(klien, **params):
    dasar = {"dimensi": "vendor", "per": "bulan",
             "dari": "2026-01-01", "sampai": "2026-03-31"}
    dasar.update(params)
    r = klien.get("/api/kartu/penerimaan", params=dasar)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ bentuk data
def test_tiga_bulan_dipecah_berurutan(klien):
    d = _ambil(klien)
    assert [b["label"] for b in d["bulan"]] == ["Jan-26", "Feb-26", "Mar-26"]
    assert d["jumlah_bulan"] == 3 and d["per"] == "bulan"


def test_nilai_per_bulan_benar_per_vendor(klien):
    d = _ambil(klien)
    v1 = next(b for b in d["baris"] if b["kunci"] == "V001")
    # Jan 1000 + Feb 2000 + 400 EUDR + Mar 3000
    assert v1["kg_per_bulan"] == [1000.0, 2400.0, 3000.0]
    assert v1["kg_total"] == 6400.0
    assert v1["kg_eudr_per_bulan"] == [0.0, 400.0, 0.0]


def test_bulan_kosong_tetap_muncul_sebagai_nol(klien):
    """V002 tidak ada tiket di Feb; V003 hanya ada di Feb."""
    d = _ambil(klien)
    v2 = next(b for b in d["baris"] if b["kunci"] == "V002")
    assert v2["kg_per_bulan"] == [500.0, 0.0, 500.0]
    v3 = next(b for b in d["baris"] if b["kunci"] == "V003")
    assert v3["kg_per_bulan"] == [0.0, 250.0, 0.0]


def test_total_per_bulan_sama_dengan_total_keseluruhan(klien):
    d = _ambil(klien)
    assert d["total_per_bulan"] == [1500.0, 2650.0, 3500.0]
    assert round(sum(d["total_per_bulan"]), 1) == d["total_kg"] == 7650.0


def test_label_vendor_memakai_nama_baku(klien):
    d = _ambil(klien)
    assert any("PT Alpha" in b["label"] for b in d["baris"])


def test_urutan_dari_terbesar(klien):
    d = _ambil(klien)
    total = [b["kg_total"] for b in d["baris"]]
    assert total == sorted(total, reverse=True)


# ------------------------------------------------------------------ top / Lainnya
def test_sisa_dimensi_digabung_menjadi_lainnya(klien):
    d = _ambil(klien, top=1)
    assert len(d["baris"]) == 2, d["baris"]
    assert d["baris"][0]["kunci"] == "V001"
    sisa = d["baris"][1]
    assert sisa["kunci"] == "__lainnya__" and sisa["gabungan"] is True
    assert sisa["kg_per_bulan"] == [500.0, 250.0, 500.0]
    # Jumlah tetap utuh walau dimensi digabung.
    assert round(sum(d["total_per_bulan"]), 1) == d["total_kg"]


def test_semua_dimensi_tampil_bila_top_cukup(klien):
    d = _ambil(klien, top=8)
    assert d["jumlah_dimensi"] == 3
    assert not any(b.get("gabungan") for b in d["baris"])


# ------------------------------------------------------------------ filter lain
def test_filter_eudr_hanya_menghitung_tiket_eudr(klien):
    """Sumbu bulan tetap Jan-Mar walau EUDR hanya ada di Feb."""
    d = _ambil(klien, eudr="true")
    assert [b["label"] for b in d["bulan"]] == ["Jan-26", "Feb-26", "Mar-26"]
    assert d["total_per_bulan"] == [0.0, 400.0, 0.0]
    assert len(d["baris"]) == 1 and d["baris"][0]["kunci"] == "V001"


def test_filter_vendor_membatasi_dimensi_lain(klien):
    d = _ambil(klien, dimensi="kabupaten", vendor="V003")
    assert [b["kunci"] for b in d["baris"]] == ["LANGKAT"]   # kunci UPPER/TRIM
    assert d["baris"][0]["label"] == "Langkat"
    assert d["total_kg"] == 250.0


def test_dimensi_wilayah_bekerja(klien):
    d = _ambil(klien, dimensi="kabupaten")
    kunci = {b["kunci"] for b in d["baris"]}
    # Sejak v0.9.1 kunci wilayah dibakukan UPPER/TRIM (agar "Deli Serdang" dan
    # "DELI SERDANG" tidak jadi dua baris); ejaan aslinya tetap jadi label.
    assert kunci == {"DELI SERDANG", "LANGKAT"}
    label = {b["kunci"]: b["label"] for b in d["baris"]}
    assert label["DELI SERDANG"] == "Deli Serdang"


def test_rentang_tanpa_data_tetap_mengembalikan_bulan(klien):
    """Filter 2025 (tidak ada tiket) -> bulan kosong, bukan galat 500."""
    d = _ambil(klien, dari="2025-01-01", sampai="2025-03-31")
    assert d["baris"] == [] and d["total_kg"] == 0.0
    assert len(d["bulan"]) == 3


def test_rentang_sangat_panjang_dipotong_ke_bulan_berdata(klien):
    """Filter 2020-2026 tapi data hanya Jan-Mar 2026 -> sumbu tidak 80 kolom."""
    d = _ambil(klien, dari="2020-01-01", sampai="2026-12-31")
    assert [b["label"] for b in d["bulan"]] == ["Jan-26", "Feb-26", "Mar-26"]


# ------------------------------------------------------------------ validasi
def test_per_tidak_dikenal_ditolak(klien):
    r = klien.get("/api/kartu/penerimaan", params={"dimensi": "vendor", "per": "tahun"})
    assert r.status_code == 422
    assert "per" in r.json()["detail"]


def test_top_di_luar_batas_ditolak(klien):
    r = klien.get("/api/kartu/penerimaan", params={"dimensi": "vendor", "top": 0})
    assert r.status_code == 422


def test_dimensi_tidak_dikenal_tetap_ditolak(klien):
    r = klien.get("/api/kartu/penerimaan", params={"dimensi": "warna"})
    assert r.status_code == 422


# ------------------------------------------------------------------ kompatibilitas
def test_tanpa_per_bulan_bentuk_lama_tidak_berubah(klien):
    """Pemakai lama (halaman lain, ekspor) tidak boleh rusak."""
    r = klien.get("/api/kartu/penerimaan",
                  params={"dimensi": "vendor", "dari": "2026-01-01",
                          "sampai": "2026-03-31"})
    d = r.json()
    assert set(d) >= {"dimensi", "baris", "total_kg", "total_kg_biasa",
                      "total_kg_eudr", "drill_berikutnya"}
    assert d["baris"][0]["kg_total"] == 6400.0
    assert "kg_per_bulan" not in d["baris"][0]


def test_ekspor_xlsx_mode_bulan(klien):
    r = klien.get("/api/kartu/penerimaan",
                  params={"dimensi": "vendor", "per": "bulan",
                          "dari": "2026-01-01", "sampai": "2026-03-31",
                          "format": "xlsx"})
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]
    assert "per_bulan" in r.headers.get("content-disposition", "")
