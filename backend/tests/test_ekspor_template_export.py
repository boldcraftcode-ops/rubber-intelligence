"""Ekspor Excel mengikuti folder `Template Export` (nama + format workbook)."""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import openpyxl
import pytest
import yaml
from fastapi.testclient import TestClient
from openpyxl.drawing.spreadsheet_drawing import TwoCellAnchor
from starlette.requests import Request

from app.api_analisis import _nama_pengguna_export
from app.main import buat_app

AKAR = Path(__file__).resolve().parents[2]
API = (AKAR / "backend/app/api_analisis.py").read_text(encoding="utf-8")
MAIN = (AKAR / "backend/app/main.py").read_text(encoding="utf-8")
METRIK = (AKAR / "backend/semantic/metrics.yaml").read_text(encoding="utf-8")
DOK = (AKAR / "docs/CARA_MENJALANKAN.md").read_text(encoding="utf-8")
RIWAYAT = (AKAR / "docs/SERAH_TERIMA.md").read_text(encoding="utf-8")
FOLDER_TEMPLATE = AKAR / "Template Export"


@pytest.fixture(scope="module")
def klien(engine):
    return TestClient(buat_app(engine))


def _buku(resp):
    assert resp.status_code == 200, resp.text
    assert "spreadsheet" in resp.headers["content-type"]
    with zipfile.ZipFile(io.BytesIO(resp.content)) as paket:
        xml = paket.read("xl/worksheets/sheet1.xml")
    tag = re.search(rb"<worksheet\b[^>]*>", xml).group(0)
    ignorable = re.search(rb'mc:Ignorable="([^"]*)"', tag)
    if ignorable:
        prefixes = set(ignorable.group(1).decode().split())
        declarations = set(re.findall(rb"xmlns:([\w.-]+)=", tag))
        assert prefixes <= {p.decode() for p in declarations}
    return openpyxl.load_workbook(io.BytesIO(resp.content))


def _judul_chart(ws) -> str:
    try:
        return ws._charts[0].title.tx.rich.p[0].r[0].t
    except Exception:
        return ""


def _footer(ws) -> str:
    return " ".join(str(c.value or "") for c in ws[ws.max_row])


def test_template_dan_konfigurasi_terdaftar():
    for nama in (
        "penerimaan_per_vendor_template.xlsx",
        "penerimaan_per_vendor_per_bulan_template.xlsx",
        "rm_stock_intake_vs_pricing_template.xlsx",
    ):
        assert (FOLDER_TEMPLATE / nama).is_file()
        assert nama in API
    assert "def respon_xlsx_template" in API
    assert "_nama_ekspor_template" in API
    assert 'replace("_template.xlsx", ".xlsx")' in API
    assert "ekspor-template-export" in MAIN
    assert "  ekspor_template_export:" in METRIK
    assert "Kolom pencarian GET" in METRIK  # metrik sebelumnya tetap ada
    assert "## 3r." in DOK or "### Format Excel sesuai folder" in DOK
    assert "### Format Excel sesuai folder `Template Export`" in DOK
    assert "nama + format workbook" in RIWAYAT
    assert "tanpa akhiran `_template`" in RIWAYAT
    assert "saya sudah upload di github dalam folder Template Export" in RIWAYAT
    data = yaml.safe_load(METRIK)
    assert "ekspor_template_export" in data["kartu"]
    assert "Template Export" in data["kartu"]["ekspor_template_export"]["cara_dihitung"]


def test_footer_export_memakai_username_login():
    request = Request({"type": "http", "state": {"pengguna": {"sub": "Admin"}}})
    assert _nama_pengguna_export(request) == "Admin"


def test_ketiga_ekspor_memakai_username_sesi(monkeypatch, klien):
    monkeypatch.setattr("app.api_analisis.info_pengguna",
                        lambda request: {"sub": "Admin"})
    urls = (
        "/api/kartu/penerimaan?dimensi=vendor&format=xlsx",
        "/api/kartu/penerimaan?dimensi=vendor&per=bulan&format=xlsx&dari=2026-01-01&sampai=2026-12-31",
        "/api/ringkasan-elemen?format=xlsx",
    )
    for url in urls:
        ws = _buku(klien.get(url)).active
        assert "Created by Admin Raw Material Big Data" in _footer(ws)


def test_health_dan_jelaskan(klien):
    assert "ekspor-template-export" in klien.get("/api/health").json()["fitur"]
    j = klien.get("/api/jelaskan/ekspor_template_export")
    assert j.status_code == 200, j.text
    assert "Template Export" in j.json()["judul"] or "Ekspor" in j.json()["judul"]
    assert "penerimaan_per_vendor.xlsx" in j.json()["rumus"]


def test_penerimaan_vendor_total_sesuai_template(klien):
    r = klien.get("/api/kartu/penerimaan", params={
        "dimensi": "vendor", "format": "xlsx"})
    assert "penerimaan_per_vendor.xlsx" in r.headers["content-disposition"]
    assert "_template" not in r.headers["content-disposition"]
    wb = _buku(r)
    ws = wb.active
    assert wb.sheetnames == ["Sheet"]
    assert ws["A1"].value == "Rubber Intake - Total Periods - All Vendors"
    assert ws["A2"].value == "Purchasing - Raw Material Section"
    assert ws["A3"].value.startswith("Periode : ")
    assert "[" not in ws["A3"].value and "~" not in ws["A3"].value
    assert [ws.cell(4, i).value for i in range(1, 7)] == [
        "Vendor", "Kg biasa", "Kg EUDR", "Kg total", "Porsi", "Jumlah tiket"]
    assert ws["A5"].value is not None
    assert "Created by dev Raw Material Big Data" in _footer(ws)
    assert len(ws._charts) == 1
    ch = ws._charts[0]
    assert _judul_chart(ws) == "Rubber Intake - Total Periods - All Vendors"
    assert ch.type == "col" and ch.grouping == "clustered"
    assert ch.overlap == -90 and ch.legend.position == "t"
    assert isinstance(ch.anchor, TwoCellAnchor)
    assert len(ch.series) == 1
    assert ch.series[0].tx.strRef.f == "Sheet!$D$4"
    assert ch.series[0].val.numRef.f.startswith("Sheet!$D$5:$D$")


def test_penerimaan_vendor_per_bulan_sesuai_template(klien):
    r = klien.get("/api/kartu/penerimaan", params={
        "dimensi": "vendor", "per": "bulan", "format": "xlsx",
        "dari": "2026-01-01", "sampai": "2026-12-31"})
    assert "penerimaan_per_vendor_per_bulan.xlsx" in r.headers["content-disposition"]
    assert "_template" not in r.headers["content-disposition"]
    wb = _buku(r)
    ws = wb.active
    assert wb.sheetnames == ["Data Sheet"]
    assert ws["A1"].value == "Rubber Intake - Monthly Details"
    assert ws["A2"].value == "Purchasing - Raw Material Section"
    assert ws["A3"].value.startswith("Periode : ")
    assert "[" not in ws["A3"].value
    header = [ws.cell(4, i).value for i in range(1, ws.max_column + 1)]
    assert header[0] == "Vendor"
    assert header[1] == "Jan-26" and header[12] == "Des-26"
    assert header[-2:] == ["Total kg", "%tage"]
    assert "Porsi" not in header
    assert ws["A5"].value is not None
    assert any(str(c.value) == "TOTAL" for c in ws[ws.max_row - 1])
    assert "Created by dev Raw Material Big Data" in _footer(ws)
    assert len(ws._charts) == 1
    ch = ws._charts[0]
    assert _judul_chart(ws) == "Rubber Intake - Monthly Details"
    assert ch.type == "col" and ch.grouping == "stacked"
    assert ch.overlap == 100 and ch.legend.position == "b"
    assert isinstance(ch.anchor, TwoCellAnchor)
    assert len(ch.series) >= 1
    assert ch.series[0].tx.strRef.f == "'Data Sheet'!$A$5"
    assert ch.series[0].val.numRef.f == "'Data Sheet'!$B$5:$M$5"
    # Template asli menyimpan label bulan sebagai kategori teks (strRef).
    assert ch.series[0].cat.strRef.f == "'Data Sheet'!$B$4:$M$4"


def test_rm_stock_intake_vs_pricing_sesuai_template(klien):
    r = klien.get("/api/ringkasan-elemen", params={"format": "xlsx"})
    assert "rm_stock_intake_vs_pricing.xlsx" in r.headers["content-disposition"]
    assert "_template" not in r.headers["content-disposition"]
    wb = _buku(r)
    ws = wb.active
    assert wb.sheetnames == ["Sheet"]
    assert ws["A1"].value == "RM Stock – Intake vs Pricing"
    assert ws["A2"].value == "Purchasing - Raw Material Section"
    assert ws["A3"].value.startswith("Periode : ")
    assert "[" not in ws["A3"].value
    header = [ws.cell(4, i).value for i in range(1, ws.max_column + 1)]
    assert header == [
        "Date", "RM Stock (MT)", "Intake (MT)", "Safety Level Stock (MT)",
        "SICOM (US¢/kg)", "OP Price (US¢/kg)", "OP Margin (US¢/kg)"]
    assert "Sumber intake" not in header and "RM Stock (kg)" not in header
    assert ws["A5"].value is not None
    assert "Created by dev Raw Material Big Data" in _footer(ws)
    assert len(ws._charts) == 1
    ch = ws._charts[0]
    assert _judul_chart(ws) == "RM Stock – Intake vs Pricing"
    assert ch.type == "col" and ch.grouping == "clustered"
    assert ch.overlap == -5 and ch.legend.position == "b"
    assert isinstance(ch.anchor, TwoCellAnchor)
    assert len(ch.series) == 2
    assert ch.series[0].tx.strRef.f == "Sheet!$B$4"
    assert ch.series[1].tx.strRef.f == "Sheet!$C$4"


def test_payload_json_dan_ekspor_dimensi_lain_tidak_berubah(klien):
    d = klien.get("/api/ringkasan-elemen").json()
    jan = next(b for b in d["baris"] if b["label"] == "Jan-23")
    assert jan["rm_stock_kg"] == round(jan["rm_stock_ton"] * 1000, 3)

    # Dimensi selain vendor tetap memakai format lama Format_penerimaan_per_desa.
    r = klien.get("/api/kartu/penerimaan", params={
        "dimensi": "desa", "format": "xlsx"})
    ws = _buku(r).active
    assert ws["A1"].value is None
    assert ws["A2"].value.startswith("Penerimaan Karet dari - [")
    assert ws["A5"].value == "Desa"
    assert len(ws._charts) == 0

    r2 = klien.get("/api/kartu/penerimaan", params={
        "dimensi": "grade", "per": "bulan", "format": "xlsx",
        "dari": "2026-01-01", "sampai": "2026-03-31"})
    assert "penerimaan_per_grade_per_bulan.xlsx" in r2.headers["content-disposition"]
    ws2 = _buku(r2).active
    assert ws2["A1"].value is None
    assert ws2["A5"].value == "Grade"
