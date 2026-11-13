"""Modul Kepatuhan vendor sampling: workbook GitHub, API, ekspor, dan menu.

Tes ini menjaga agar laporan tetap dibaca apa adanya dari workbook: angka
TOTAL, jumlah baris log, dan perbedaan formula Agu/Sep vs Okt/Nov tidak boleh
berubah tanpa disengaja.
"""
from __future__ import annotations

import io
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.main import buat_app

AKAR = Path(__file__).resolve().parents[2]


@pytest.fixture()
def klien(engine):
    return TestClient(buat_app(engine))


def _teks(rel: str) -> str:
    return (AKAR / rel).read_text(encoding="utf-8")


def test_menu_dan_rute_terpasang():
    app = _teks("frontend/src/App.tsx")
    assert 'import KepatuhanVendorSampling from "./pages/KepatuhanVendorSampling";' in app
    assert '{ id: "kepatuhan", label: "Kepatuhan vendor sampling", ikon: "☑", grup: "pantau" }' in app
    assert '{tab === "kepatuhan" && <KepatuhanVendorSampling />}' in app

    kamus = _teks("frontend/src/i18n.tsx")
    assert '"Kepatuhan vendor sampling": "Vendor Sampling Compliance"' in kamus

    utama = _teks("backend/app/main.py")
    assert "from .api_kepatuhan_vendor import pasang_router_kepatuhan" in utama
    assert '"kepatuhan-vendor-sampling"' in utama


def test_get_bawaan_memakai_bulan_terbaru(klien):
    r = klien.get("/api/kepatuhan-vendor-sampling")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["kunci"] == "2026-11"
    assert d["sumber"]["nama_file"] == "Laporan_Monitoring_Vendor_RM_Purchasing (1).xlsx"
    assert d["sumber"]["jumlah_lembar"] == 8
    assert any("Min. 30 menit" in x for x in d["catatan_aturan"])
    assert [x["kunci"] for x in d["daftar_periode"]] == [
        "2026-08", "2026-09", "2026-10", "2026-11"]
    assert [x["ringkasan"]["total_kunjungan"] for x in d["daftar_periode"]] == [
        82, 167, 148, 24]


def test_periode_agustus_mempertahankan_nilai_workbook(klien):
    d = klien.get("/api/kepatuhan-vendor-sampling?bulan=2026-08").json()
    p = d["periode"]
    assert p["label"] == "Agustus 2026"
    assert len(p["kolom_log"]) == 16
    assert len(p["log"]) == 82
    assert len(p["summary"]) == 10
    assert p["log"][0][:7] == [
        1, "PT Purba Jaya Persada", "2026-08-13", "09:30", "09:00", 30,
        "Terlambat"]
    assert p["total"]["tepat"] == 70
    assert p["total"]["terlambat"] == 10
    assert p["total"]["tanpa_data"] == 2
    assert p["total"]["total"] == 82
    assert p["total"]["persen"] == pytest.approx(0.875)
    assert "Tepat Waktu" in p["aturan"]
    assert "≥ 40 menit" in p["aturan"]


def test_periode_oktober_memakai_kolom_baru(klien):
    d = klien.get("/api/kepatuhan-vendor-sampling?bulan=2026-10").json()
    p = d["periode"]
    assert len(p["kolom_log"]) == 19
    assert len(p["log"]) == 155
    assert "Tiket" in p["kolom_log"]
    assert p["log"][0][2] == "2026-10-01"
    assert p["log"][0][3] == "26XO0012"
    assert p["ringkasan"]["terlambat"] == 63
    assert "Terlambat" in p["aturan"]


def test_ekspor_xlsx_memiliki_dua_lembar(klien):
    r = klien.get("/api/kepatuhan-vendor-sampling?bulan=2026-09&format=xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert "Kepatuhan_vendor_sampling_2026-09.xlsx" in r.headers["content-disposition"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Summary", "Log Monitoring"]
    assert wb["Summary"].cell(1, 2).value == "Nama Vendor"
    assert wb["Summary"].max_row == 19       # header + 17 vendor + TOTAL
    assert wb["Log Monitoring"].max_row == 168  # header + 167 log
    assert wb["Log Monitoring"].cell(2, 3).value == "2026-09-01"


def test_validasi_periode(klien):
    assert klien.get("/api/kepatuhan-vendor-sampling?bulan=2026-99").status_code == 404
    assert klien.get("/api/kepatuhan-vendor-sampling?bulan=2026-1").status_code == 422
    assert klien.get("/api/kepatuhan-vendor-sampling?format=pdf").status_code == 422


def test_health_menyebut_fitur_baru(klien):
    assert "kepatuhan-vendor-sampling" in klien.get("/api/health").json()["fitur"]
