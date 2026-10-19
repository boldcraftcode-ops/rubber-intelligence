"""Tes Fase 6: unggah file data lewat web (format mengikuti file pengguna)."""
import datetime as dt
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import buat_app


@pytest.fixture()
def klien(tmp_path, monkeypatch):
    monkeypatch.setenv("UNGGAH_DIR", str(tmp_path / "unggahan"))
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    return TestClient(buat_app(eng))


def _xlsx_berkala() -> bytes:
    """File kecil format template: stok + pembelian + sicom + kurs."""
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Stok_Harian"
    ws.append(["Tanggal", "Stok_Kg", "Item_Code", "Catatan"])
    ws.append([dt.date(2026, 10, 16), 600000, None, None])
    ws2 = wb.create_sheet("Pembelian_Harian")
    ws2.append(["Tanggal", "Item_Code", "Kode_Vendor", "Ticket_No",
                "Qty_Kering_Kg", "Amount_Rp"])
    ws2.append([dt.date(2026, 10, 16), "ALL", None, None, 1000, 30_000_000])
    ws3 = wb.create_sheet("SICOM_Harian")
    ws3.append(["Tanggal", "SICOM_USc_per_kg"])
    ws3.append([dt.date(2026, 10, 16), 250.0])
    ws4 = wb.create_sheet("Kurs")
    ws4.append(["Berlaku_Dari", "Kurs_IDR_per_USD"])
    ws4.append([dt.date(2026, 10, 1), 16500])
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def _xlsx_master_data() -> bytes:
    """File kecil meniru ekspor Master Data: judul 4 baris, header baris 7."""
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Master Data 2026"
    for _ in range(6):
        ws.append(["LAPORAN MASTER DATA"])  # judul/pengisi baris 1-6
    ws.append(["Ticket Date", "Ticket No", "Supplier Code", "Supplier Name",
               "Vehicle No", "Item Code", "DRC Date", "Wet", "Sample", "Reject",
               "DRC", "Dry", "Asal Getah", "Provinsi", "Kabupaten/Kota",
               "Kecamatan", "Desa", "BIN", "Location"])
    ws.append([])  # baris 8 (bekas sel digabung)
    t = dt.date(2026, 10, 16)
    ws.append([t, "T900", "V5", "VENDOR LIMA", "BK 5", "SLAB2", t,
               5000, 5, 10, 60, 3000, "SUMUT, A, B, C", "SUMUT", "A", "B", "C",
               "BIN1", "L1"])
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def _kirim(klien, nama, isi, pengisi="tester"):
    return klien.post("/api/unggah",
                      files={"file": (nama, isi,
                             "application/vnd.openxmlformats-officedocument"
                             ".spreadsheetml.sheet")},
                      data={"pengisi": pengisi})


def test_unggah_berkala(klien):
    r = _kirim(klien, "data harian.xlsx", _xlsx_berkala())
    assert r.status_code == 200
    j = r.json()
    assert j["jenis"].startswith("Data berkala")
    assert j["jumlah"]["stok"] == 1
    assert j["jumlah"]["pembelian"] == 1
    assert j["jumlah"]["sicom"] == 1
    assert j["jumlah"]["kurs"] == 1
    assert not j["duplikat_file"]
    # mart langsung terhitung
    h = klien.get("/api/kartu/margin-harian",
                  params={"tahun": 2026, "bulan": 10}).json()
    assert len(h["baris"]) == 1


def test_unggah_ulang_tidak_menggandakan(klien):
    isi = _xlsx_berkala()
    _kirim(klien, "a.xlsx", isi)
    r = _kirim(klien, "a.xlsx", isi)
    assert r.json()["duplikat_file"]
    h = klien.get("/api/kartu/margin-harian",
                  params={"tahun": 2026, "bulan": 10}).json()
    assert len(h["baris"]) == 1  # tetap satu hari, tidak ganda


def test_unggah_master_data_tiket(klien):
    r = _kirim(klien, "Master Data Okt.xlsx", _xlsx_master_data())
    assert r.status_code == 200
    j = r.json()
    assert j["jenis"].startswith("Tiket intake")
    assert j["jumlah"]["tiket_baris"] == 1
    assert j["jumlah_peringatan"] >= 1  # vendor V5 tak ada di master -> peringatan
    t = klien.get("/api/telusur/tanggal", params={"tanggal": "2026-10-16"}).json()
    assert len(t["tiket"]) == 1 and t["tiket"][0]["ticket_no"] == "T900"


def test_tolak_bukan_xlsx(klien):
    r = _kirim(klien, "data.csv", b"a;b;c")
    assert r.status_code == 422
    assert ".xlsx" in r.json()["detail"]


def test_tolak_terlalu_besar(klien, monkeypatch):
    monkeypatch.setenv("UNGGAH_MAKS_MB", "0.001")  # ~1 KB
    r = _kirim(klien, "besar.xlsx", _xlsx_berkala())
    assert r.status_code == 413
    assert "melebihi" in r.json()["detail"]


def test_tolak_format_tak_dikenal(klien):
    wb = openpyxl.Workbook()
    wb.active.append(["kolom aneh", "lain"])
    buf = io.BytesIO(); wb.save(buf)
    r = _kirim(klien, "aneh.xlsx", buf.getvalue())
    assert r.status_code == 422
    assert "tidak dikenal" in r.json()["detail"]


def test_unggah_tercatat_di_audit(klien):
    _kirim(klien, "data harian.xlsx", _xlsx_berkala(), pengisi="staf-gudang")
    audit = klien.get("/api/audit", params={"objek": "file"}).json()
    assert audit and audit[0]["siapa"] == "staf-gudang"
    assert audit[0]["aksi"] == "unggah"
    assert audit[0]["detail"]["jenis"] == "template"
