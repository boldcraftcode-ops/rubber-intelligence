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
