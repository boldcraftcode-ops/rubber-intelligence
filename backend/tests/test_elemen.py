"""Tes kartu 'RM Stock-Intake VS Pricing' (disamakan dengan Excel lampiran)."""
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.main import buat_app


@pytest.fixture(scope="module")
def klien(engine):
    return TestClient(buat_app(engine))


def _baris(data, label):
    return next(b for b in data["baris"] if b["label"] == label)


def test_cocok_dengan_excel_lampiran(klien):
    d = klien.get("/api/ringkasan-elemen").json()

    jan23 = _baris(d, "Jan-23")
    assert jan23["rm_stock_ton"] == 4313.93
    assert jan23["intake_ton"] == 7894.32
    assert jan23["safety_ton"] == 3850
    assert round(jan23["sicom"], 4) == 138.6176
    assert round(jan23["op_price"], 4) == 122.2813

    mei24 = _baris(d, "Mei-24")
    assert mei24["rm_stock_ton"] == 2915.551
    assert mei24["safety_ton"] == 2795.1  # safety berubah per Mei-24

    agu26 = _baris(d, "Agu-26")
    assert agu26["rm_stock_ton"] == 551.947
    # Intake = tonase tiket (sumber resmi) dari referensi rekonsiliasi
    assert agu26["intake_ton"] == 4759.827
    assert "tiket" in agu26["sumber_intake"]
    jul26 = _baris(d, "Jul-26")
    assert jul26["intake_ton"] == 5269.319


def test_jun25_memakai_data_harian_bukan_excel(klien):
    """Excel lampiran menulis 2.795,1 (sama persis dengan safety) — diduga
    salah isi; sistem memakai stok harian 30/06/2025 dan memberi catatan."""
    d = klien.get("/api/ringkasan-elemen").json()
    jun25 = _baris(d, "Jun-25")
    assert jun25["rm_stock_ton"] == 2038.681
    assert any("Jun-25" in c for c in d["catatan"])


def test_tanpa_baris_proyeksi(klien):
    """Baris proyeksi Sep-Des 26 di Excel tidak direplikasi; bulan berjalan
    dengan data stok belum penuh ditandai 'sebagian'."""
    d = klien.get("/api/ringkasan-elemen").json()
    sep26 = _baris(d, "Sep-26")
    assert sep26["stok_sebagian"]  # stok terakhir 08/09, bukan akhir bulan
    assert all(not b["label"].endswith("Nov-26") for b in d["baris"]
               if b["rm_stock_ton"] is None and b["intake_ton"] is None)


def test_tonase_tersedia_dalam_mt_dan_kg(klien):
    """Payload menyediakan MT dan kg sekaligus; kunci lama *_ton tetap ada."""
    d = klien.get("/api/ringkasan-elemen").json()
    jan23 = _baris(d, "Jan-23")
    for kunci in ("rm_stock", "intake", "safety"):
        assert jan23[f"{kunci}_ton"] is not None
        assert jan23[f"{kunci}_kg"] == round(jan23[f"{kunci}_ton"] * 1000, 3)
    assert any("1 MT = 1.000 kg" in c for c in d["catatan"])


def _judul_chart(ws):
    try:
        return ws._charts[0].title.tx.rich.p[0].r[0].t
    except Exception:
        return ""


def test_ekspor_xlsx(klien):
    r = klien.get("/api/ringkasan-elemen", params={"format": "xlsx"})
    assert r.status_code == 200
    assert "rm_stock_intake_vs_pricing.xlsx" in r.headers["content-disposition"]
    assert "_template" not in r.headers["content-disposition"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    ws = wb.active
    assert wb.sheetnames == ["Sheet"]
    assert ws["A1"].value == "RM Stock – Intake vs Pricing"
    assert ws["A2"].value == "Purchasing - Raw Material Section"
    assert ws["A3"].value.startswith("Periode : ") and "[" not in ws["A3"].value
    judul = [c.value for c in ws[4]]
    assert judul == [
        "Date", "RM Stock (MT)", "Intake (MT)", "Safety Level Stock (MT)",
        "SICOM (US¢/kg)", "OP Price (US¢/kg)", "OP Margin (US¢/kg)"]
    assert "RM Stock (kg)" not in judul and "Sumber intake" not in judul
    # Data mulai baris 5; payload JSON tetap menyediakan satuan kg.
    assert ws["A5"].value is not None and ws["B5"].value is not None
    assert any("Created by [user login]" in str(c.value)
               for c in ws[ws.max_row])
    assert len(ws._charts) == 1
    ch = ws._charts[0]
    assert _judul_chart(ws) == "RM Stock – Intake vs Pricing"
    assert ch.type == "col" and ch.grouping == "clustered"
    assert ch.overlap == -5 and ch.legend.position == "b"
    assert len(ch.series) == 2
    assert ws.max_row >= 44


def test_payload_json_tetap_punya_satuan_kg(klien):
    """Format Excel berubah, tetapi JSON kartu tidak boleh kehilangan kg."""
    d = klien.get("/api/ringkasan-elemen").json()
    jan23 = _baris(d, "Jan-23")
    assert jan23["rm_stock_kg"] == round(jan23["rm_stock_ton"] * 1000, 3)
    assert jan23["intake_kg"] == round(jan23["intake_ton"] * 1000, 3)
