"""Tes kartu penerimaan biasa vs EUDR + filter periode RM Stock-Intake.

Data tiket contoh di template (15/10/2026):
  V999: SLAB2 6.000 kg + SLAB1 1.100 kg (biasa) | V998: SLAB2 TTSR 4.680 kg (EUDR)
"""
import pytest
from fastapi.testclient import TestClient

from app.main import buat_app


@pytest.fixture(scope="module")
def klien(engine):
    return TestClient(buat_app(engine))


def test_penerimaan_per_vendor_pisah_eudr(klien):
    r = klien.get("/api/kartu/penerimaan", params={"dimensi": "vendor"}).json()
    m = {b["kunci"]: b for b in r["baris"]}
    assert m["V999"]["kg_biasa"] == 7100 and m["V999"]["kg_eudr"] == 0
    assert m["V998"]["kg_eudr"] == 4680 and m["V998"]["kg_biasa"] == 0
    assert r["total_kg"] == 11780
    assert r["total_kg_eudr"] == 4680


def test_filter_vendor_pemasok_eudr(klien):
    """eudr=true -> hanya vendor yang memasok karet EUDR."""
    r = klien.get("/api/kartu/penerimaan",
                  params={"dimensi": "vendor", "eudr": True}).json()
    assert [b["kunci"] for b in r["baris"]] == ["V998"]
    assert r["baris"][0]["kg_eudr"] == 4680
    r = klien.get("/api/kartu/penerimaan",
                  params={"dimensi": "vendor", "eudr": False}).json()
    assert [b["kunci"] for b in r["baris"]] == ["V999"]


def test_penerimaan_wilayah_dan_drill(klien):
    r = klien.get("/api/kartu/penerimaan", params={"dimensi": "provinsi"}).json()
    m = {b["kunci"]: b for b in r["baris"]}
    assert m["SUMATERA UTARA"]["kg_biasa"] == 7100
    assert m["RIAU"]["kg_eudr"] == 4680
    assert r["drill_berikutnya"] == "kabupaten"
    # drill berantai sampai desa
    r2 = klien.get("/api/kartu/penerimaan", params={
        "dimensi": "desa", "provinsi": "RIAU"}).json()
    assert r2["baris"][0]["kg_eudr"] == 4680
    assert r2["drill_berikutnya"] is None


def test_penerimaan_filter_periode(klien):
    r = klien.get("/api/kartu/penerimaan", params={
        "dimensi": "vendor", "dari": "2026-10-01", "sampai": "2026-10-31"}).json()
    assert r["total_kg"] == 11780
    r = klien.get("/api/kartu/penerimaan", params={
        "dimensi": "vendor", "sampai": "2026-09-30"}).json()
    assert r["baris"] == [] and r["total_kg"] == 0


def test_penerimaan_dimensi_salah(klien):
    assert klien.get("/api/kartu/penerimaan",
                     params={"dimensi": "warna"}).status_code == 422


def test_elemen_filter_periode(klien):
    d = klien.get("/api/ringkasan-elemen",
                  params={"dari": "2024-01", "sampai": "2024-12"}).json()
    label = [b["label"] for b in d["baris"]]
    assert label[0] == "Jan-24" and label[-1] == "Des-24" and len(label) == 12
    r = klien.get("/api/ringkasan-elemen", params={"dari": "salah"})
    assert r.status_code == 422
    assert "YYYY-MM" in r.json()["detail"]


# -------------------------------------------------------- format Excel baku
# Mengikuti `Format_penerimaan_per_desa.xlsx`: judul/periode, header biru,
# Courier New, border tipis, format accounting/0%, dan lebar kolom tetap.
def _buku_xlsx(resp):
    import io
    import openpyxl
    assert resp.status_code == 200, resp.text
    assert "spreadsheet" in resp.headers["content-type"]
    return openpyxl.load_workbook(io.BytesIO(resp.content))


def test_ekspor_xlsx_penerimaan_format_contoh(klien):
    from app.api_analisis import FORMAT_KG_PENERIMAAN, TINT_HEADER_PENERIMAAN
    r = klien.get("/api/kartu/penerimaan", params={
        "dimensi": "desa", "format": "xlsx",
        "dari": "2026-01-01", "sampai": "2026-12-31"})
    wb = _buku_xlsx(r)
    assert wb.sheetnames == ["Sheet"]
    ws = wb.active
    assert ws["A1"].value is None and ws["A4"].value is None
    assert ws["A2"].value.startswith("Penerimaan Karet dari - [")
    assert ws["A3"].value == "Periode :  [January ~ December 2026]"
    assert [ws.cell(5, i).value for i in range(1, 7)] == [
        "Desa", "Kg biasa", "Kg EUDR", "Kg total", "Porsi", "Jumlah tiket"]
    assert ws["A2"].font.name == "Courier New" and ws["A2"].font.sz == 14
    assert ws["A2"].font.color.rgb == "FF1D2434"
    assert ws["A2"].alignment.vertical == "center"
    assert ws.row_dimensions[2].height == 18.75
    hdr = ws["A5"]
    assert hdr.font.name == "Courier New" and hdr.font.sz == 11
    assert hdr.font.color.type == "theme" and hdr.font.color.theme == 0
    assert hdr.fill.fgColor.type == "theme" and hdr.fill.fgColor.theme == 3
    assert abs(hdr.fill.fgColor.tint - TINT_HEADER_PENERIMAAN) < 1e-9
    assert hdr.border.left.style == "thin" and hdr.border.bottom.style == "thin"
    assert ws["B5"].number_format == FORMAT_KG_PENERIMAAN
    assert ws["D5"].number_format == FORMAT_KG_PENERIMAAN
    assert ws["E5"].number_format == "0%"
    assert ws["F5"].alignment.horizontal == "center"
    # Baris data pertama memakai font & border yang sama, tanpa fill header.
    data = ws["A6"]
    assert data.value is not None
    assert data.font.name == "Courier New" and data.font.sz == 11
    assert data.font.color.type == "theme" and data.font.color.theme == 1
    assert data.border.left.style == "thin" and data.border.right.style == "thin"
    assert data.fill.patternType is None
    assert ws["B6"].number_format == FORMAT_KG_PENERIMAAN
    assert ws["E6"].number_format == "0%"
    assert ws["F6"].alignment.horizontal == "center"
    assert abs(ws.column_dimensions["A"].width - 26.5703125) < 1e-6
    assert abs(ws.column_dimensions["G"].width - 9.140625) < 1e-6
    assert ws.freeze_panes is None and not list(ws.merged_cells.ranges)


def _judul_chart(ws):
    ch = ws._charts[0]
    try:
        return ch.title.tx.rich.p[0].r[0].t
    except Exception:
        return ""


def test_ekspor_xlsx_penerimaan_vendor_mengikuti_template(klien):
    # V998 punya tiket di data contoh; V1112 hanya ada di Master Vendor.
    r = klien.get("/api/kartu/penerimaan", params={
        "dimensi": "vendor", "vendor": "V998", "format": "xlsx"})
    wb = _buku_xlsx(r)
    ws = wb.active
    assert "penerimaan_per_vendor.xlsx" in r.headers["content-disposition"]
    assert "_template" not in r.headers["content-disposition"]
    assert wb.sheetnames == ["Sheet"]
    assert ws["A1"].value == "Rubber Intake - Total Periods - All Vendors"
    assert ws["A2"].value == "Purchasing - Raw Material Section"
    assert ws["A3"].value.startswith("Periode : ") and "[" not in ws["A3"].value
    assert [ws.cell(4, i).value for i in range(1, 7)] == [
        "Vendor", "Kg biasa", "Kg EUDR", "Kg total", "Porsi", "Jumlah tiket"]
    assert "V998" in str(ws["A5"].value)
    assert any("Created by dev" in str(c.value)
               for c in ws[ws.max_row])
    assert len(ws._charts) == 1
    ch = ws._charts[0]
    assert _judul_chart(ws) == "Rubber Intake - Total Periods - All Vendors"
    assert ch.type == "col" and ch.grouping == "clustered"
    assert ch.overlap == -90 and ch.legend.position == "t"
    assert len(ch.series) == 1


def test_format_baru_hanya_kartu_penerimaan(klien):
    """Kartu lain (komposisi) tetap ekspor polos: header di baris 1."""
    r = klien.get("/api/kartu/penerimaan/komposisi",
                  params={"format": "xlsx"})
    ws = _buku_xlsx(r).active
    assert ws["A1"].value == "Provinsi"
    assert ws["A2"].value != "Penerimaan Karet dari - [Semua vendor]"
