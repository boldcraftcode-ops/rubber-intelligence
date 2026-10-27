"""Tes penyesuaian skema untuk database yang SUDAH ADA (v0.10.0).

Masalah nyata: aplikasi dipakai di PC yang database-nya sudah berisi data.
`create_all()` tidak menambah kolom pada tabel yang sudah ada, jadi kolom baru
(alamat / kontak_person / klasifikasi pada tabel `vendor`) harus ditambahkan
lewat ALTER TABLE — tanpa menghapus satu baris pun.

Yang dijaga:
- database versi lama tetap bisa dibuka; kolom baru muncul otomatis;
- data lama (kode, nama, kategori, status, pemakaian tiket) TIDAK berubah;
- penyesuaian aman dijalankan berkali-kali (idempoten);
- vendor lama tampil di layar dengan kolom profil kosong, bukan error.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.skema import KOLOM_BARU, kolom_hilang, pastikan_kolom_baru
from app.main import buat_app
from app.models import TiketBaris, Vendor

SKEMA_LAMA = """
CREATE TABLE vendor (
    kode VARCHAR(20) NOT NULL PRIMARY KEY,
    nama_baku VARCHAR(200) NOT NULL,
    varian_nama TEXT,
    kategori VARCHAR(100),
    status VARCHAR(50)
)
"""


def _engine_lama():
    """Database 'versi lama': tabel vendor tanpa kolom profil + satu baris data."""
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    with eng.begin() as k:
        k.execute(text(SKEMA_LAMA))
        k.execute(text(
            "INSERT INTO vendor (kode, nama_baku, varian_nama, kategori, status) "
            "VALUES ('V001', 'PT Alpha', 'PT A|CV A', 'nasional', 'aktif')"))
    return eng


def test_kolom_hilang_terdeteksi():
    eng = _engine_lama()
    kurang = kolom_hilang(eng)
    assert set(kurang) == {"vendor"}
    assert [n for n, _ in kurang["vendor"]] == ["alamat", "kontak_person",
                                               "klasifikasi"]


def test_kolom_baru_ditambahkan_dan_data_lama_utuh():
    eng = _engine_lama()
    tindakan = pastikan_kolom_baru(eng)
    assert tindakan == ["vendor.alamat", "vendor.kontak_person",
                        "vendor.klasifikasi"]
    kolom = {k["name"] for k in inspect(eng).get_columns("vendor")}
    assert {"alamat", "kontak_person", "klasifikasi"} <= kolom
    with sessionmaker(bind=eng, future=True)() as s:
        v = s.get(Vendor, "V001")
        assert (v.nama_baku, v.kategori, v.status) == ("PT Alpha", "nasional", "aktif")
        assert (v.alamat, v.kontak_person, v.klasifikasi) == (None, None, None)


def test_idempoten_dijalankan_dua_kali():
    eng = _engine_lama()
    assert len(pastikan_kolom_baru(eng)) == 3
    assert pastikan_kolom_baru(eng) == []      # kedua kali: tidak ada perubahan
    kolom = [k["name"] for k in inspect(eng).get_columns("vendor")]
    assert len(kolom) == len(set(kolom))       # tidak ada kolom ganda


def test_database_baru_tidak_butuh_penyesuaian():
    from app.models import Base

    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    assert pastikan_kolom_baru(eng) == []


def test_aplikasi_menyesuaikan_sendiri_saat_start(monkeypatch):
    """Tanpa menjalankan skrip apa pun, buka aplikasi di database lama."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    from app.models import Base

    eng = _engine_lama()
    Base.metadata.create_all(eng)   # tabel lain dibuat; `vendor` lama TIDAK diubah
    with sessionmaker(bind=eng, future=True)() as s:
        s.add(TiketBaris(ticket_no="T001", line_seq=1, ticket_date=dt.date(2026, 1, 5),
                         kode_vendor="V001", item_code="SIR20", dry_kg=12_000,
                         wet_kg=20_000, tiket_nol=False))
        s.commit()

    klien = TestClient(buat_app(eng))
    daftar = klien.get("/api/vendor").json()["baris"]
    assert len(daftar) == 1
    assert daftar[0]["kode"] == "V001"
    assert daftar[0]["alamat"] is None
    assert daftar[0]["klasifikasi_label"] is None
    assert daftar[0]["jumlah_tiket"] == 1          # pemakaian lama tetap terbaca
    assert daftar[0]["ton_kering"] == 12.0

    # dan kolomnya sekarang bisa diisi seperti biasa
    r = klien.put("/api/vendor/V001", json={
        "nama_baku": "PT Alpha", "alamat": "Jl. Baru 1",
        "kontak_person": "Budi", "klasifikasi": "small_holder"})
    assert r.status_code == 200, r.text
    assert r.json()["vendor"]["klasifikasi_label"] == "Small holder"


def test_semua_tabel_di_daftar_benar_ada_di_model():
    """Jaga agar KOLOM_BARU tidak salah ketik nama tabel."""
    from app.models import Base

    assert set(KOLOM_BARU) <= set(Base.metadata.tables)
    for tabel, daftar in KOLOM_BARU.items():
        kolom_model = set(Base.metadata.tables[tabel].columns.keys())
        for nama, _tipe in daftar:
            assert nama in kolom_model, f"{tabel}.{nama} tidak ada di model"
