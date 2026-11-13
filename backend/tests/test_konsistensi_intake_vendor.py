"""Kartu Intake Analisis: laporan Ringkasan Vendor berbasis Trip.

Mengunci keputusan pemilik untuk `Intake-2025_Ringkasan-Vendor.xlsx`:
- tiga tabel di layar (chart lama dihapus);
- metrik Total Trip / % Trip / Hari Aktif / Rata² Trip/Hari Operasional /
  Rata² Trip/Bulan / Dry (kg), peringkat memakai jumlah Trip;
- ekspor Excel 3 sheet + 3 chart native, tanpa Master Data / `Lainnya`;
- semua vendor sebagai baris detail, semua hari kalender tetap ada;
- judul, kolom bulan, dan pembagi bulan mengikuti Dari/Sampai;
- seluruh rentang data boleh dipilih, periode panjang diminimalisir di layar.
"""
from __future__ import annotations

import datetime as dt
import io
import zipfile

import openpyxl
import pytest
from fastapi.testclient import TestClient
from openpyxl.chart import BarChart, LineChart
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.ringkasan_vendor import (
    AMBANG_RINGKAS_HARI, MAKS_BULAN, MAKS_HARI, daftar_bulan, daftar_hari,
    hitung_ringkasan_vendor, label_periode_judul, ringkas_untuk_layar,
)
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


def _get(klien, **params):
    r = klien.get(URL, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _xlsx(klien, **params):
    r = klien.get(URL, params={**params, "format": "xlsx"})
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers["content-type"]
    return r.content


def _judul_chart(ch) -> str:
    return "".join(r.t or "" for p in ch.title.tx.rich.p for r in p.r)


def _isi_januari(s):
    """V001 masuk 10 hari penuh (+1 tiket ekstra), V002 hanya 3 hari."""
    for i in range(1, 11):
        _tiket(s, f"A{i:02d}", dt.date(2026, 1, i), "V001")
    _tiket(s, "A99", dt.date(2026, 1, 5), "V001", kg=50)
    for i in (1, 2, 5):
        _tiket(s, f"B{i:02d}", dt.date(2026, 1, i), "V002")
    # Tiket nol tidak boleh dihitung sebagai Trip.
    _tiket(s, "B99", dt.date(2026, 1, 9), "V002", nol=True)


def _isi_lintas_bulan(s):
    _tiket(s, "C1", dt.date(2026, 1, 15), "V001", kg=100)
    _tiket(s, "C2", dt.date(2026, 2, 1), "V002", kg=200)
    _tiket(s, "C3", dt.date(2026, 3, 10), "V001", kg=300)


def _isi_tahun_baru(s):
    _tiket(s, "T1", dt.date(2026, 1, 1), "V001", kg=100)


def _isi_panjang(s):
    """Satu vendor, tiket tiap 30 hari selama 1.096 hari."""
    awal = dt.date(2024, 1, 1)
    for i in range(0, 1096, 30):
        _tiket(s, f"P{i:04d}", awal + dt.timedelta(days=i), "V001", kg=10)


# ------------------------------------------------------- hari kalender & Trip
def test_semua_hari_kalender_dan_peringkat_trip(monkeypatch):
    d = _get(_klien(monkeypatch, _isi_januari),
             dari="2026-01-01", sampai="2026-01-10")
    assert d["status"] == "ok"
    assert d["dasar"] == {
        "hari": "kalender",
        "urutan": "jumlah_trip",
        "label_hari": "Semua hari kalender dalam rentang tetap ditampilkan",
        "label_urutan": "Jumlah Trip (Ticket No unik)",
    }
    assert d["periode"]["jumlah_hari"] == 10
    assert d["periode"]["jumlah_bulan"] == 1
    assert d["ringkasan"]["total_vendor"] == 4
    assert d["ringkasan"]["total_trip"] == 14
    assert d["ringkasan"]["total_dry_kg"] == pytest.approx(1350.0)
    assert d["ringkasan"]["hari_operasional"] == 10
    assert d["ringkasan"]["hari_kalender"] == 10

    v1, v2, v3, v4 = d["baris"]
    assert (v1["kode"], v1["peringkat"]) == ("V001", 1)
    assert v1["label"] == "PT Alpha"
    assert v1["total_trip"] == 11
    assert v1["dry_kg"] == pytest.approx(1050.0)
    assert v1["hari_aktif"] == 10
    assert v1["porsi_trip"] == pytest.approx(11 / 14)
    assert v1["rata_trip_per_hari_operasional"] == pytest.approx(1.1)
    assert v1["rata_trip_per_bulan"] == pytest.approx(11.0)
    assert (v2["kode"], v2["total_trip"], v2["hari_aktif"]) == ("V002", 3, 3)
    assert v2["dry_kg"] == pytest.approx(300.0)
    # Vendor Master tanpa tiket TETAP menjadi baris detail bernilai 0.
    assert {(v3["kode"], v3["total_trip"]),
            (v4["kode"], v4["total_trip"])} == {("V003", 0), ("V004", 0)}
    assert d["paling_sering"]["kode"] == "V001"
    assert d["seri_paling_sering"] == ["V001"]
    assert {v["kode"] for v in d["vendor_tanpa_intake"]} == {"V003", "V004"}

    assert [b["ym"] for b in d["bulan"]] == ["2026-01"]
    assert [v["trip_per_bulan"] for v in d["vendor_per_bulan"]] == [
        [11], [3], [0], [0]]
    assert d["total_per_bulan"] == [14]
    assert d["vendor_utama_bulan"] == ["PT Alpha"]
    assert d["trip_utama_bulan"] == [11]
    assert d["share_utama_bulan"] == [pytest.approx(11 / 14)]

    assert [h["tanggal"] for h in d["hari"]] == [
        f"2026-01-{i:02d}" for i in range(1, 11)]
    assert d["total_per_hari"] == [2, 2, 1, 1, 3, 1, 1, 1, 1, 1]
    assert d["hari"][9]["kategori"] == "ada_intake"
    assert d["rata_total_per_hari"] == pytest.approx(1.4)
    assert d["rata_vendor_per_hari"] == [
        pytest.approx(1.1), pytest.approx(0.3), 0.0, 0.0]
    assert d["rekap_per_bulan"][0]["ringkasan"] == "01-10"
    assert d["catatan_metode"]["minimalisir"].startswith(
        "Batas 731 hari dihapus")
    assert "pabrik tutup" in d["catatan_metode"]["sepi_pabrik"]
    assert "Trip = Ticket No unik" in d["sumber"]


def test_hari_tanpa_intake_nol_dan_di_luar_data(monkeypatch):
    d = _get(_klien(monkeypatch, _isi_lintas_bulan),
             dari="2026-01-01", sampai="2026-03-31")
    assert d["periode"]["jumlah_hari"] == 90
    assert d["batas_data"] == {
        "tersedia": True, "dari": "2026-01-15", "sampai": "2026-03-10",
        "jumlah_hari": 55,
    }
    assert [b["ym"] for b in d["bulan"]] == [
        "2026-01", "2026-02", "2026-03"]
    assert len(d["hari"]) == 90
    assert d["total_per_hari"][0] == 0
    assert d["hari"][0]["kategori"] == "di_luar_data"
    assert d["hari"][0]["di_luar_data"] is True
    assert d["total_per_hari"][14] == 1
    assert d["hari"][14]["kategori"] == "ada_intake"
    assert d["total_per_hari"][15] == 0
    assert d["hari"][15]["kategori"] == "sepi_pabrik"
    assert d["hari"][15]["sepi_pabrik"] is True
    assert d["hari"][89]["kategori"] == "di_luar_data"
    assert any("di luar rentang tiket" in p for p in d["peringatan"])

    assert [m["label"] for m in d["rekap_per_bulan"]] == [
        "Jan-26", "Feb-26", "Mar-26"]
    assert [m["total_trip"] for m in d["rekap_per_bulan"]] == [1, 1, 1]
    assert [m["jumlah_hari_kalender"] for m in d["rekap_per_bulan"]] == [
        31, 28, 31]
    assert d["vendor_per_bulan"][0]["trip_per_bulan"] == [1, 0, 1]
    assert d["vendor_per_bulan"][1]["trip_per_bulan"] == [0, 1, 0]
    assert d["baris"][0]["rata_trip_per_bulan"] == pytest.approx(2 / 3)
    assert d["baris"][0]["rata_trip_per_hari_operasional"] == \
        pytest.approx(2 / 3)
    assert d["total_per_bulan"] == [1, 1, 1]


def test_status_kosong_jujur_dan_semua_vendor_tetap_ada(monkeypatch):
    d = _get(_klien(monkeypatch, lambda s: None),
             dari="2026-01-01", sampai="2026-01-03")
    assert len(d["baris"]) == 4
    assert all(b["total_trip"] == 0 for b in d["baris"])
    assert d["ringkasan"]["total_trip"] == 0
    assert any("Tidak ada tiket intake" in p for p in d["peringatan"])
    assert "tiket_baris" in d["sumber"]
    assert len(d["hari"]) == 3
    assert d["total_per_hari"] == [0, 0, 0]


# ------------------------------------------------- periode panjang & rinci=1
def test_mode_ringkas_rinci_dan_excel_tetap_penuh(monkeypatch):
    klien = _klien(monkeypatch, _isi_panjang)
    params = {"dari": "2024-01-01", "sampai": "2026-12-31"}
    d = _get(klien, **params)
    assert d["periode"]["jumlah_hari"] == 1096
    assert d["periode"]["jumlah_bulan"] == 36
    assert d["periode"]["mode_rincian"] == "ringkas"
    assert d["periode"]["ringkas_otomatis"] is True
    assert d["hari"] == []
    assert d["vendor_harian"] == []
    assert d["total_per_hari"] == []
    assert len(d["rekap_per_bulan"]) == 36
    assert len(d["rentang_hari"]) > 1
    assert any("DIMINIMALISIR" in p for p in d["peringatan"])

    penuh = _get(klien, **params, rinci=1)
    assert len(penuh["hari"]) == 1096
    assert len(penuh["vendor_harian"]) == 4
    assert len(penuh["total_per_hari"]) == 1096
    assert penuh["hari"][0]["tanggal"] == "2024-01-01"
    assert penuh["hari"][-1]["tanggal"] == "2026-12-31"

    isi = _xlsx(klien, **params)
    wb = openpyxl.load_workbook(io.BytesIO(isi))
    assert wb.sheetnames == ["Ringkasan Vendor", "Vendor per Bulan",
                             "Vendor Harian"]
    assert wb["Vendor Harian"].max_row >= 4 + 1096 + 1
    assert wb["Vendor Harian"]["A5"].value == dt.datetime(2024, 1, 1)
    assert wb["Vendor Harian"].cell(4 + 1096, 1).value == \
        dt.datetime(2026, 12, 31)
    wb.close()


# ------------------------------------------------------------- ekspor Excel
def test_xlsx_tiga_sheet_tiga_chart_dan_dinamis(monkeypatch):
    isi = _xlsx(_klien(monkeypatch, _isi_tahun_baru),
                dari="2025-12-30", sampai="2026-01-02")
    wb = openpyxl.load_workbook(io.BytesIO(isi))
    assert wb.sheetnames == ["Ringkasan Vendor", "Vendor per Bulan",
                             "Vendor Harian"]
    assert "Master Data" not in wb.sheetnames

    # Tidak ada label "Lainnya" di seluruh workbook (termasuk XML chart).
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                assert not (isinstance(c.value, str)
                            and "Lainnya" in c.value)
    z = zipfile.ZipFile(io.BytesIO(isi))
    assert not any(
        "Lainnya".encode("utf-8") in z.read(n)
        for n in z.namelist() if n.endswith((".xml", ".rels")))
    assert any(isinstance(c.value, str) and "pabrik tutup" in c.value
               for ws in wb.worksheets for row in ws.iter_rows() for c in row)
    assert not any(isinstance(c.value, str)
                   and "pabrik sepi" in c.value.lower()
                   for ws in wb.worksheets for row in ws.iter_rows() for c in row)

    ws1, ws2, ws3 = (wb[n] for n in wb.sheetnames)
    assert [len(ws._charts) for ws in (ws1, ws2, ws3)] == [1, 1, 1]
    assert isinstance(ws1._charts[0], BarChart)
    assert isinstance(ws2._charts[0], BarChart)
    assert ws2._charts[0].grouping == "stacked"
    assert ws2._charts[0].overlap == 100
    assert isinstance(ws3._charts[0], LineChart)
    assert all(len(ws.conditional_formatting._cf_rules) >= 1
               for ws in (ws1, ws2, ws3))
    assert "2025–2026" in ws1["A1"].value
    assert "2025–2026" in _judul_chart(ws1._charts[0])
    assert ws1["A1"].font.name == "Courier New"
    assert ws1["A4"].fill.fgColor.rgb == "FF1F4E78"
    assert [ws1.cell(4, c).value for c in range(1, 9)] == [
        "Rank", "Vendor", "Total Trip", "% Trip", "Hari Aktif",
        "Rata² Trip/Hari Operasional", "Rata² Trip/Bulan", "Dry (kg)"]
    assert [ws1.cell(r, 2).value for r in range(5, 9)] == [
        "PT Alpha", "PT Beta", "PT Delta", "PT Gamma"]
    assert ws1["B9"].value == "TOTAL"
    assert ws1["C9"].value == 1
    assert ws1["H9"].value == 100
    assert ws1["K4"].value == 1     # Hari operasional
    assert ws1["M4"].value == 2     # Jumlah bulan dinamis

    assert [ws2.cell(4, c).value for c in range(1, 5)] == [
        "Vendor", "Des-25", "Jan-26", "Total"]
    assert [ws2.cell(3, c).value for c in (2, 3)] == [
        dt.datetime(2025, 12, 1), dt.datetime(2026, 1, 1)]
    assert "mmm" in ws2["B3"].number_format
    assert ws2["A9"].value == "TOTAL"
    assert [ws2.cell(9, c).value for c in range(2, 5)] == [0, 1, 1]

    assert [ws3.cell(4, c).value for c in range(1, 10)] == [
        "Tanggal", "Total Trip", "PT Alpha", "PT Beta", "PT Delta",
        "PT Gamma", "Vendor #1", "Trip #1", "Tanggal (YYYY-MM-DD)"]
    assert ws3["A5"].number_format == "yyyy-mm-dd"
    assert [ws3.cell(r, 2).value for r in range(5, 9)] == [0, 0, 1, 0]
    assert [ws3.cell(r, 3).value for r in range(5, 9)] == [0, 0, 1, 0]
    assert [ws3.cell(r, 1).fill.fgColor.rgb for r in range(5, 9)] == [
        "FFF2F2F2", "FFF2F2F2", "00000000", "FFF2F2F2"]
    assert ws3["A9"].value == "Rata² / hari"
    assert ws1.freeze_panes == "A5"
    assert ws2.freeze_panes == "B5"
    assert ws3.freeze_panes == "C5"
    wb.close()


def test_xlsx_vendor_nol_dan_tanpa_data_tetap_tiga_chart(monkeypatch):
    isi = _xlsx(_klien(monkeypatch, lambda s: None),
                dari="2026-01-01", sampai="2026-01-02")
    wb = openpyxl.load_workbook(io.BytesIO(isi))
    assert wb.sheetnames == ["Ringkasan Vendor", "Vendor per Bulan",
                             "Vendor Harian"]
    assert sum(len(ws._charts) for ws in wb.worksheets) == 3
    assert [wb["Ringkasan Vendor"].cell(r, 2).value for r in range(5, 9)] == [
        "PT Alpha", "PT Beta", "PT Delta", "PT Gamma"]
    assert wb["Ringkasan Vendor"]["C9"].value == 0
    wb.close()


# -------------------------------------------------------------- batas aman
def test_batas_ekstrem_dan_label_bulan(monkeypatch):
    klien = _klien(monkeypatch, lambda s: None)
    r = klien.get(URL, params={"dari": "1900-01-01",
                               "sampai": "2026-11-01"})
    assert r.status_code == 422
    assert "batas keamanan" in r.json()["detail"]
    r = klien.get(URL, params={"dari": "1900-01-01",
                               "sampai": "2000-01-01"})
    assert r.status_code == 422
    assert "1.201 bulan" in r.json()["detail"]

    assert MAKS_HARI == 366 * 100
    assert MAKS_HARI > 1766
    assert MAKS_BULAN == 1_200
    assert AMBANG_RINGKAS_HARI == 366
    assert [h.isoformat() for h in daftar_hari(
        dt.date(2024, 2, 28), dt.date(2024, 3, 1))] == [
        "2024-02-28", "2024-02-29", "2024-03-01"]
    assert [b["ym"] for b in daftar_bulan(
        dt.date(2025, 12, 1), dt.date(2026, 2, 1))] == [
        "2025-12", "2026-01", "2026-02"]
    assert label_periode_judul(dt.date(2025, 1, 1),
                               dt.date(2026, 12, 31)) == "2025–2026"


# ------------------------------------------------------------ modul murni
def test_hitung_murni_trip_unik_dan_normalisasi_vendor():
    hasil = hitung_ringkasan_vendor(
        [(dt.date(2026, 6, 1), " v001 ", "T1", 100.0),
         (dt.date(2026, 6, 1), "V001", "T1", 50.0),
         (dt.date(2026, 6, 2), "V001", "T2", 50.0),
         (dt.date(2026, 6, 1), "V002", "T3", 10.0)],
        dt.date(2026, 6, 1), dt.date(2026, 6, 3),
        {"v001": "Alpha", "V002": "Beta"})
    assert [b["label"] for b in hasil["baris"]] == ["Alpha", "Beta"]
    assert hasil["baris"][0]["total_trip"] == 2   # T1 + T2, bukan 3 baris
    assert hasil["baris"][0]["dry_kg"] == pytest.approx(200.0)
    assert hasil["baris"][0]["hari_aktif"] == 2
    assert hasil["baris"][1]["total_trip"] == 1
    assert hasil["ringkasan"]["total_trip"] == 3
    assert hasil["ringkasan"]["hari_operasional"] == 2
    assert hasil["total_per_hari"] == [2, 1, 0]
    assert hasil["hari"][2]["kategori"] == "sepi_pabrik"


def test_ringkas_untuk_layar_memangkas_matriks_panjang():
    hasil = hitung_ringkasan_vendor(
        [(dt.date(2024, 1, 1), "V001", "T1", 10.0)],
        dt.date(2024, 1, 1), dt.date(2026, 12, 31), {"V001": "Alpha"})
    assert hasil["periode"]["ringkas_otomatis"] is True
    r = ringkas_untuk_layar(hasil)
    assert r["hari"] == []
    assert r["vendor_harian"] == []
    assert len(r["bulan"]) == 36
    assert len(r["vendor_per_bulan"]) == 1
    assert len(r["rekap_per_bulan"]) == 36
    assert len(r["rentang_hari"]) > 1
