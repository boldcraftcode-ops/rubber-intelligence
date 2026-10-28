"""Tes analisa RCA 5 Why kartu RM Stock – Intake vs Pricing."""
import pytest
from fastapi.testclient import TestClient

from app.core.analisa_rca import analisa_rca
from app.main import buat_app


@pytest.fixture(scope="module")
def klien(engine):
    return TestClient(buat_app(engine))


def _data():
    return [
        {"tahun": 2026, "bulan": 1, "label": "Jan-26", "rm_stock_ton": 200,
         "intake_ton": 100, "safety_ton": 250, "sicom": 100,
         "op_price": 90, "op_margin": 10, "sumber_intake": "tiket"},
        {"tahun": 2026, "bulan": 2, "label": "Feb-26", "rm_stock_ton": 180,
         "intake_ton": 120, "safety_ton": 250, "sicom": 105,
         "op_price": 100, "op_margin": 5, "sumber_intake": "tiket"},
        {"tahun": 2026, "bulan": 3, "label": "Mar-26", "rm_stock_ton": 150,
         "intake_ton": 80, "safety_ton": 250, "sicom": 104,
         "op_price": 102, "op_margin": 2,
         "sumber_intake": "tiket (referensi rekonsiliasi)"},
    ]


def test_mom_margin_estimasi_cover_dan_gap_dihitung():
    hasil = analisa_rca(_data())
    jan, feb, mar = hasil["per_bulan"]
    assert jan["delta_intake_ton"] is None  # tidak ada bulan pembanding
    assert feb["delta_intake_ton"] == 20
    assert feb["delta_intake_ton_pct"] == 20
    assert feb["delta_sicom"] == 5
    assert feb["delta_op_price"] == 10
    assert feb["delta_op_margin"] == -5
    assert feb["estimasi_total_margin_usd"] == 6000
    assert mar["estimasi_total_margin_usd"] == 1600
    assert mar["days_of_cover"] == 56.25  # 150 / (80/30)
    assert mar["selisih_stok_safety_ton"] == -100
    assert hasil["estimasi_total_margin_usd"] == 17600
    assert any(x["jenis"] == "Intake naik, margin turun" for x in hasil["anomali"])
    assert any(x["jenis"] == "Keandalan intake lebih rendah" for x in hasil["anomali"])


def test_format_rca_memenuhi_kriteria_hipotesis_dan_target():
    hasil = analisa_rca(_data())
    assert hasil["ada_data"] is True
    assert 5 <= len(hasil["temuan_data"]) <= 7
    assert len(hasil["root_cause"]) == 5
    assert hasil["root_cause"][-1]["level"] == 5
    assert "AKAR SEMENTARA" in hasil["root_cause"][-1]["jawaban"]
    hipotesis = [x for x in hasil["root_cause"] if x["jenis"] == "HIPOTESIS"]
    assert hipotesis
    assert all(x["keyakinan"] in {"tinggi", "sedang", "rendah"} for x in hipotesis)
    assert all(x["data_dibutuhkan"] for x in hipotesis)
    assert 3 <= len(hasil["rekomendasi"]) <= 5
    assert all(x["target_angka"] and x["evaluasi"] for x in hasil["rekomendasi"])
    assert hasil["jumlah_bulan_referensi"] == 1
    assert "belum termasuk biaya olah dan logistik" in hasil["catatan_margin"]


def test_margin_selalu_diturunkan_dari_sicom_kurangi_op_price():
    data = _data()
    data[0]["op_margin"] = 999  # kolom turunan yang tidak konsisten tidak dipakai
    hasil = analisa_rca(data)
    assert hasil["per_bulan"][0]["op_margin"] == 10
    assert hasil["per_bulan"][0]["estimasi_total_margin_usd"] == 10000


def test_mom_tidak_dihitung_melompati_bulan():
    data = _data()
    data[1]["bulan"] = 3
    data[1]["label"] = "Mar-26"
    data[2]["bulan"] = 4
    data[2]["label"] = "Apr-26"
    hasil = analisa_rca(data)
    feb = hasil["per_bulan"][1]
    assert feb["moM_tersedia"] is False
    assert feb["delta_intake_ton"] is None
    apr = hasil["per_bulan"][2]
    assert apr["moM_tersedia"] is True


def test_data_kosong_ditangani():
    hasil = analisa_rca([])
    assert hasil["ada_data"] is False
    assert hasil["per_bulan"] == []
    assert "Tidak ada" in hasil["kesimpulan"]


def test_endpoint_rca_memakai_filter_periode(klien):
    r = klien.get("/api/ringkasan-elemen/rca",
                  params={"dari": "2026-01", "sampai": "2026-08"})
    assert r.status_code == 200
    hasil = r.json()
    assert hasil["ada_data"] is True
    assert hasil["periode_awal"] == "Jan-26"
    assert hasil["periode_akhir"] == "Agu-26"
    assert len(hasil["root_cause"]) == 5
    assert 5 <= len(hasil["temuan_data"]) <= 7


def test_endpoint_rca_periode_kosong(klien):
    hasil = klien.get("/api/ringkasan-elemen/rca",
                      params={"dari": "2035-01", "sampai": "2035-02"}).json()
    assert hasil["ada_data"] is False
