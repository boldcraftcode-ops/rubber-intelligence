"""Tes data peta potensi karet dan pemisahan definisi tonase."""
from fastapi.testclient import TestClient

from app import api_potensi
from app.main import buat_app


def test_feed_lampung_mengagregasi_seri_dari_api_dan_membedakan_wujud(monkeypatch):
    api_potensi._lampung_cache = None
    payload = {"result": [
        {"tahun_2022": 100, "tahun_2023": 120, "satuan": "Ton", "bentuk_hasil": "slab"},
        {"tahun_2022": 50, "tahun_2023": 80, "satuan": "Ton", "bentuk_hasil": "slab"},
    ]}
    hasil = api_potensi._ambil_lampung(lambda _url: payload)
    assert hasil["status"] == "tersedia"
    assert hasil["tahun"] == 2023
    assert hasil["produksi_ton_slab"] == 200
    assert hasil["jumlah_kabupaten_kota"] == 2
    assert hasil["satuan"] == "ton slab"


def test_intake_internal_dirata_ratakan_per_tahun_dari_dry(session):
    hasil = api_potensi._intake_tahunan(session)
    # Data template mencakup tiket contoh dengan provinsi eksplisit; data
    # tersebut hanya ada pada fixture/test sandbox, tidak memutasi produksi.
    riau = next((row for row in hasil if row["provinsi"] == "RIAU"), None)
    assert riau is not None
    assert riau["jumlah_tahun"] >= 1
    assert riau["rata_rata_kg_per_tahun"] > 0
    assert riau["rata_rata_kg_per_tahun"] == sum(riau["kg_per_tahun"].values()) / riau["jumlah_tahun"]


def test_sentra_produksi_tidak_disamakan_dengan_penjualan():
    assert len(api_potensi.PRODUKSI_SENTRA_2024) == 10
    assert all(row["ton"] > 0 for row in api_potensi.PRODUKSI_SENTRA_2024)
    assert any("bukan penjualan per provinsi" in row["cakupan"] for row in api_potensi.SUMBER)


def test_endpoint_peta_mengembalikan_dua_metrik_yang_terpisah(engine, monkeypatch):
    monkeypatch.setattr(api_potensi, "_ambil_lampung", lambda: {
        "status": "tersedia", "tahun": 2023, "produksi_ton_slab": 200,
        "jumlah_kabupaten_kota": 2, "satuan": "ton slab",
        "diperiksa_pada": "2026-11-02T00:00:00+00:00", "url": api_potensi.URL_HALAMAN_LAMPUNG,
    })
    response = TestClient(buat_app(engine)).get("/api/kartu/potensi-karet")
    assert response.status_code == 200
    payload = response.json()
    assert payload["tahun_produksi"] == 2024
    assert payload["produksi_sentra"][0]["provinsi"] == "Sumatera Selatan"
    assert "RIAU" in {row["provinsi"] for row in payload["rata_rata_intake_tahunan"]}
    assert payload["seri_lampung"]["satuan"] == "ton slab"
    assert "bukan seluruh penjualan pasar" in payload["definisi"]["intake"]
