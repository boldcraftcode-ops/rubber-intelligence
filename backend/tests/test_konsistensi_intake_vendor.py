"""Kartu baru Intake Analisis: konsistensi intake harian/bulanan per vendor.

Keputusan pemilik (ask_user):
- dasar hari = **semua hari kalender** (Sabtu/Minggu/libur tetap dihitung);
- urutan "paling sering masuk" = **jumlah tanggal unik ber-intake**;
- filter = **tanggal persis** YYYY-MM-DD;
- ekspor Excel = **beberapa sheet** dengan seluruh rincian hari/bulan kosong.
"""
from __future__ import annotations

import datetime as dt
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.konsistensi_intake import (MAKS_HARI, daftar_hari,
                                         hitung_konsistensi,
                                         kelompok_rentang_bulan,
                                         rentang_bulan_terpanjang,
                                         rentang_harian_terpanjang)
from app.main import buat_app
from app.models import Base, TiketBaris, Vendor

URL = "/api/kartu/konsistensi-intake-vendor"


def _engine():
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def _tiket(s, no, tanggal, vendor="V001", kg=100, nol=False):
    s.add(TiketBaris(
        ticket_no=no, line_seq=1, ticket_date=tanggal, kode_vendor=vendor,
        item_code="SIR20", dry_kg=kg, wet_kg=kg / 0.62,
        provinsi="SUMATERA UTARA", tiket_nol=nol))


def _klien(monkeypatch, isi):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    with Session(eng) as s:
        s.add_all([
            Vendor(kode="V001", nama_baku="PT Alpha"),
            Vendor(kode="V002", nama_baku="PT Beta"),
            Vendor(kode="V003", nama_baku="PT Gamma"),
            Vendor(kode="V004", nama_baku="PT Delta"),
        ])
        isi(s)
        s.commit()
    return TestClient(buat_app(eng))


def _isi_januari(s):
    """V001 hadir 10 hari penuh (+1 tiket ekstra di hari sama), V002 hanya 3 hari."""
    for i in range(1, 11):
        _tiket(s, f"A{i:02d}", dt.date(2026, 1, i), "V001")
    _tiket(s, "A99", dt.date(2026, 1, 5), "V001", kg=50)
    for i in (1, 2, 5):
        _tiket(s, f"B{i:02d}", dt.date(2026, 1, i), "V002")
    # Tiket nol tidak boleh dihitung sebagai kehadiran.
    _tiket(s, "B99", dt.date(2026, 1, 9), "V002", nol=True)


def _get(klien, **params):
    r = klien.get(URL, params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------- hari kalender & urutan
def test_semua_hari_kalender_dan_vendor_paling_sering_masuk(monkeypatch):
    d = _get(_klien(monkeypatch, _isi_januari),
             dari="2026-01-01", sampai="2026-01-10")
    assert d["status"] == "ok"
    assert d["dasar"] == {
        "hari": "kalender", "urutan": "jumlah_hari_masuk",
        "label_hari": "Semua hari kalender dalam rentang dihitung wajib ada intake",
        "label_urutan": "Jumlah hari ber-intake (tanggal unik)"}
    assert d["periode"]["jumlah_hari"] == 10
    assert d["periode"]["jumlah_bulan"] == 1
    assert d["ringkasan"]["total_vendor"] == 2

    v1, v2 = d["baris"]
    assert (v1["kode"], v1["peringkat"], v1["paling_sering"]) == ("V001", 1, True)
    assert v1["label"] == "V001 — PT Alpha"
    assert v1["jumlah_hari_masuk"] == 10
    assert v1["cakupan_hari_pct"] == 100.0
    assert v1["status_harian"] == "lengkap"
    assert v1["status_bulanan"] == "lengkap"
    assert v1["jumlah_hari_kosong"] == 0 and v1["hari_kosong"] == []
    assert v1["bulan_lengkap"] == [
        {"ym": "2026-01", "label": "Jan-26", "jumlah_hari": 10}]
    assert v1["rentang_harian_terpanjang"] == {
        "dari": "2026-01-01", "sampai": "2026-01-10", "jumlah_hari": 10}
    # Dua tiket di tanggal sama tetap dihitung SATU hari, tapi tiketnya 11.
    assert v1["jumlah_tiket"] == 11
    assert v1["total_kg"] == pytest.approx(1050.0)

    assert (v2["kode"], v2["peringkat"], v2["paling_sering"]) == ("V002", 2, False)
    assert v2["jumlah_hari_masuk"] == 3
    assert v2["jumlah_hari_kosong"] == 7
    assert [h["tanggal"] for h in v2["hari_kosong"]] == [
        "2026-01-03", "2026-01-04", "2026-01-06", "2026-01-07",
        "2026-01-08", "2026-01-09", "2026-01-10"]
    # 2026-01-04 adalah Minggu: tetap kosong karena dasar hari kalender.
    assert next(h for h in v2["hari_kosong"]
                if h["tanggal"] == "2026-01-04")["hari"] == "Minggu"
    # Tiket nol pada 09 Jan tidak membuat V002 hadir.
    assert v2["jumlah_tiket"] == 3
    assert v2["rentang_harian_terpanjang"]["jumlah_hari"] == 2

    assert d["paling_sering"]["kode"] == "V001"
    assert d["seri_paling_sering"] == ["V001"]
    # V003/V004 ada di Master Vendor tetapi tidak ber-intake pada periode ini.
    assert {v["kode"] for v in d["vendor_tanpa_intake"]} == {"V003", "V004"}
    assert d["ringkasan"]["vendor_tanpa_intake"] == 2


def test_hari_dan_bulan_kosong_dirinci_serta_hari_sepi_pabrik(monkeypatch):
    def isi(s):
        _tiket(s, "A1", dt.date(2026, 1, 15), "V001")
        _tiket(s, "A2", dt.date(2026, 3, 10), "V001")
        _tiket(s, "B1", dt.date(2026, 2, 1), "V002")

    d = _get(_klien(monkeypatch, isi),
             dari="2026-01-01", sampai="2026-03-31")
    assert d["periode"]["jumlah_hari"] == 90
    assert [m["ym"] for m in d["daftar_bulan"]] == [
        "2026-01", "2026-02", "2026-03"]
    v1 = next(b for b in d["baris"] if b["kode"] == "V001")
    v2 = next(b for b in d["baris"] if b["kode"] == "V002")
    assert [m["ym"] for m in v1["bulan_kosong"]] == ["2026-02"]
    assert v1["bulan_lengkap"] == []
    assert v1["rentang_bulanan_terpanjang"]["jumlah_bulan"] == 1
    assert [m["ym"] for m in v2["bulan_kosong"]] == ["2026-01", "2026-03"]
    assert d["ringkasan"]["hari_tanpa_intake_sama_sekali"] == 87
    assert any("tanpa intake dari vendor mana" in p.lower()
               for p in d["peringatan"])
    assert d["ringkasan"]["vendor_lengkap_harian"] == 0
    assert any("Belum ada vendor" in p for p in d["peringatan"])


def test_seri_paling_sering_masuk(monkeypatch):
    def isi(s):
        _tiket(s, "A1", dt.date(2026, 5, 1), "V001")
        _tiket(s, "B1", dt.date(2026, 5, 2), "V002")

    d = _get(_klien(monkeypatch, isi),
             dari="2026-05-01", sampai="2026-05-02")
    assert d["seri_paling_sering"] == ["V001", "V002"]
    assert all(b["paling_sering"] for b in d["baris"])
    assert d["ringkasan"]["total_vendor"] == 2


# ------------------------------------------------------------- ekspor Excel
def test_ekspor_excel_beberapa_sheet_dan_rincian_tidak_dipotong(monkeypatch):
    def isi(s):
        _tiket(s, "A1", dt.date(2026, 1, 1), "V001")
        _tiket(s, "B1", dt.date(2026, 1, 1), "V002")
        _tiket(s, "B2", dt.date(2026, 1, 2), "V002")

    klien = _klien(monkeypatch, isi)
    params = {"dari": "2026-01-01", "sampai": "2026-02-09"}
    d = _get(klien, **params)
    v1 = next(b for b in d["baris"] if b["kode"] == "V001")
    assert v1["jumlah_hari_kosong"] == 39
    # Layar dipangkas, Excel tidak.
    assert len(v1["hari_kosong"]) == 31
    assert v1["hari_kosong_terpotong"] is True
    assert any("Ekspor Excel memuat seluruh" in p for p in d["peringatan"])

    r = klien.get(URL, params={**params, "format": "xlsx"})
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True,
                                data_only=True)
    assert wb.sheetnames == ["Rekap vendor", "Hari kosong",
                             "Rentang hari kosong", "Bulan kosong",
                             "Bulan lengkap", "Hari sepi pabrik", "Metode"]
    assert wb["Rekap vendor"].max_row == 3  # header + 2 vendor
    # V001 39 hari kosong + V002 38 hari kosong = 77 baris rincian.
    assert wb["Hari kosong"].max_row == 78
    # Ringkasan rentang: satu rentang kosong berurutan untuk tiap vendor.
    assert wb["Rentang hari kosong"].max_row == 3
    # Februari kosong untuk kedua vendor; Januari tidak.
    assert wb["Bulan kosong"].max_row == 3
    assert wb["Bulan lengkap"].max_row == 1
    metode = [list(r) for r in wb["Metode"].iter_rows(values_only=True)]
    assert any(r[0] == "Dasar penilaian hari"
               and "Semua hari kalender" in str(r[1]) for r in metode)
    assert any(r[0] == "Dasar urutan"
               and "Jumlah hari ber-intake" in str(r[1]) for r in metode)
    wb.close()


def test_ekspor_excel_tetap_ada_saat_tidak_ada_tiket(monkeypatch):
    klien = _klien(monkeypatch, lambda s: None)
    r = klien.get(URL, params={"dari": "2026-01-01", "sampai": "2026-01-03",
                               "format": "xlsx"})
    assert r.status_code == 200, r.text
    wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True)
    assert wb["Rekap vendor"].max_row == 1
    assert wb["Hari kosong"].max_row == 1
    wb.close()


# ------------------------------------------------------- periode & validasi
def test_periode_otomatis_dari_tanggal_tiket(monkeypatch):
    def isi(s):
        _tiket(s, "A1", dt.date(2026, 2, 10), "V001")
        _tiket(s, "A2", dt.date(2026, 2, 20), "V001")

    d = _get(_klien(monkeypatch, isi))
    assert d["periode"]["dari"] == "2026-02-10"
    assert d["periode"]["sampai"] == "2026-02-20"
    assert d["periode"]["dari_otomatis"] is True
    assert d["periode"]["sampai_otomatis"] is True
    assert d["periode"]["jumlah_hari"] == 11
    assert any("diambil otomatis" in p for p in d["peringatan"])


def test_periode_terbalik_dan_format_salah_ditolak(monkeypatch):
    klien = _klien(monkeypatch, _isi_januari)
    r = klien.get(URL, params={"dari": "2026-03-10", "sampai": "2026-03-01"})
    assert r.status_code == 422 and "Periode terbalik" in r.text
    r = klien.get(URL, params={"dari": "2026/01/01"})
    assert r.status_code == 422 and "YYYY-MM-DD" in r.text
    # Rentang 1.766 hari (keluhan pemilik) sekarang HARUS diterima.
    r = klien.get(URL, params={"dari": "2021-12-15",
                               "sampai": "2026-10-15"})
    assert r.status_code == 200, r.text
    assert r.json()["periode"]["jumlah_hari"] == 1766
    assert r.json()["periode"]["mode_rincian"] == "ringkas"
    # Hanya tanggal ekstrem (±>100 tahun) yang ditolak batas keamanan.
    r = klien.get(URL, params={"dari": "1900-01-01",
                               "sampai": "2026-10-15"})
    assert r.status_code == 422 and "di luar jangkauan" in r.text


def test_rentang_1766_hari_diterima_dan_otomatis_diminimalisir(monkeypatch):
    """Keluhan pemilik: 1.766 hari tidak boleh 422, rincian tetap terbaca."""
    klien = _klien(monkeypatch, _isi_januari)
    d = _get(klien, dari="2021-12-15", sampai="2026-10-15")
    assert d["status"] == "ok"
    assert d["periode"]["jumlah_hari"] == 1766
    assert d["periode"]["jumlah_bulan"] == 59
    assert d["periode"]["mode_rincian"] == "ringkas"
    assert d["periode"]["ringkas_otomatis"] is True
    assert d["batas_data"] == {
        "tersedia": True, "dari": "2026-01-01", "sampai": "2026-01-10",
        "jumlah_hari": 10}
    assert d["ringkasan"]["hari_di_luar_rentang_data"] == 1756
    assert any("DIMINIMALISIR" in p for p in d["peringatan"])
    assert any("di luar rentang tiket" in p for p in d["peringatan"])

    v1 = next(b for b in d["baris"] if b["kode"] == "V001")
    assert v1["jumlah_hari_masuk"] == 10
    assert v1["jumlah_hari_kosong"] == 1756
    # JSON layar tetap ringan: 31 chip, 2 rentang, 59 rekap bulan.
    assert len(v1["hari_kosong"]) == 31
    assert v1["hari_kosong_terpotong"] is True
    assert len(v1["hari_kosong_rentang"]) == 2
    assert v1["hari_kosong_rentang"][0]["jumlah_hari"] == 1478
    assert v1["hari_kosong_rentang"][0]["kategori"] == "di_luar_data"
    assert len(v1["hari_kosong_per_bulan"]) == 59
    assert v1["hari_kosong_per_bulan"][0]["ringkasan"] == "15-31"
    assert v1["bulan_kosong_rentang"][0]["jumlah_bulan"] >= 48
    assert v1["hari_kosong"][0]["kategori"] == "di_luar_data"
    # Dasar lama tidak berubah.
    assert d["dasar"]["hari"] == "kalender"
    assert d["dasar"]["urutan"] == "jumlah_hari_masuk"


def test_ekspor_excel_rentang_1766_hari_tetap_lengkap(monkeypatch):
    klien = _klien(monkeypatch, _isi_januari)
    params = {"dari": "2021-12-15", "sampai": "2026-10-15"}
    d = _get(klien, **params)
    total = sum(b["jumlah_hari_kosong"] for b in d["baris"])
    r = klien.get(URL, params={**params, "format": "xlsx"})
    assert r.status_code == 200, r.text
    wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True,
                                data_only=True)
    assert wb["Hari kosong"].max_row == total + 1
    assert wb["Rentang hari kosong"].max_row > 1
    metode = [list(x) for x in wb["Metode"].iter_rows(values_only=True)]
    assert any(x[0] == "Mode rincian layar"
               and "Ringkas otomatis" in str(x[1]) for x in metode)
    assert any(x[0] == "Hari di luar rentang data" and x[1] == 1756
               for x in metode)
    wb.close()


def test_status_kosong_jujur_dan_sumber_tercantum(monkeypatch):
    d = _get(_klien(monkeypatch, lambda s: None),
             dari="2026-01-01", sampai="2026-01-03")
    assert d["baris"] == []
    assert d["paling_sering"] is None
    assert d["ringkasan"]["total_vendor"] == 0
    assert any("Tidak ada tiket intake" in p for p in d["peringatan"])
    assert "tiket_baris" in d["sumber"]


# ------------------------------------------------------- fungsi murni
def test_rentang_terpanjang_harian_dan_bulanan():
    hari = {dt.date(2026, 1, 1), dt.date(2026, 1, 2), dt.date(2026, 1, 4),
            dt.date(2026, 1, 5), dt.date(2026, 1, 6)}
    assert rentang_harian_terpanjang(hari) == {
        "dari": "2026-01-04", "sampai": "2026-01-06", "jumlah_hari": 3}
    assert rentang_harian_terpanjang(set())["jumlah_hari"] == 0
    assert rentang_bulan_terpanjang({(2026, 1), (2026, 2), (2026, 4)}) == {
        "dari": "2026-01", "sampai": "2026-02", "jumlah_bulan": 2}
    assert rentang_bulan_terpanjang({(2025, 12), (2026, 1)}) == {
        "dari": "2025-12", "sampai": "2026-01", "jumlah_bulan": 2}


def test_kelompok_rentang_bulan_untuk_tampilan_ringkas():
    bulan = [
        {"ym": "2025-11", "label": "Nov-25", "jumlah_hari": 30},
        {"ym": "2025-12", "label": "Des-25", "jumlah_hari": 31},
        {"ym": "2026-01", "label": "Jan-26", "jumlah_hari": 31},
        {"ym": "2026-03", "label": "Mar-26", "jumlah_hari": 31},
    ]
    kelompok = kelompok_rentang_bulan(bulan)
    assert [(k["dari"], k["sampai"], k["jumlah_bulan"])
            for k in kelompok] == [
        ("2025-11", "2026-01", 3), ("2026-03", "2026-03", 1)]
    assert kelompok_rentang_bulan([]) == []


def test_daftar_hari_termasuk_tahun_kabisat():
    hari = daftar_hari(dt.date(2024, 2, 28), dt.date(2024, 3, 1))
    assert [h.isoformat() for h in hari] == [
        "2024-02-28", "2024-02-29", "2024-03-01"]
    # Batas 731 hari dihapus; 1.766 hari wajib masuk, batas baru hanya
    # pengaman tanggal ekstrem ±100 tahun.
    assert MAKS_HARI == 366 * 100
    assert MAKS_HARI > 1766


def test_hitung_murni_tanpa_database():
    hasil = hitung_konsistensi(
        [(dt.date(2026, 6, 1), " v001 ", "T1", 100.0),
         (dt.date(2026, 6, 2), "V001", "T2", 50.0),
         (dt.date(2026, 6, 1), "V002", "T3", 10.0)],
        dt.date(2026, 6, 1), dt.date(2026, 6, 3),
        {"V001": "PT Alpha"})
    assert hasil["baris"][0]["kode"] == "V001"
    assert hasil["baris"][0]["nama"] == "PT Alpha"
    assert hasil["baris"][0]["jumlah_hari_masuk"] == 2
    assert [h["tanggal"] for h in hasil["baris"][0]["hari_kosong"]] == [
        "2026-06-03"]
    assert hasil["ringkasan"]["total_tiket"] == 3
