"""Endpoint /api/traceability/tree: pohon dari data intake + master asli."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import buat_app
from app.models import Collector, TiketBaris, Vendor


@pytest.fixture()
def klien(engine):
    return TestClient(buat_app(engine))


def _siapkan_kolektor(session):
    """Tambah satu kolektor wildcard untuk vendor yang punya baris tiket."""
    kode = session.execute(
        select(TiketBaris.kode_vendor).limit(1)).scalar()
    assert kode, "Template uji harus punya baris tiket."
    vendor_baru = False
    if session.get(Vendor, kode) is None:
        session.add(Vendor(kode=kode, nama_baku=f"Vendor Uji {kode}"))
        vendor_baru = True
    ck = "C-UJI-TREE"
    if session.get(Collector, ck) is None:
        session.add(Collector(kode=ck, nama="Kolektor Uji Tree",
                              kode_vendor=kode, desa=None))
    session.commit()
    return kode, ck, vendor_baru


def _bersihkan(session, kode, ck, vendor_baru):
    kolektor = session.get(Collector, ck)
    if kolektor:
        session.delete(kolektor)
    if vendor_baru:
        vendor = session.get(Vendor, kode)
        if vendor:
            session.delete(vendor)
    session.commit()


def test_tree_memakai_data_asli_dan_kode_tier_benar(klien, session, engine):
    kode, ck, vendor_baru = _siapkan_kolektor(session)
    try:
        r = klien.get(
            f"/api/traceability/tree?periode=ALL&eudr=all&supplier={kode}&batas=0")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sumber"] == "tiket_baris + Master Vendor + Master Collector"
        assert d["kode_tier"] == {"PABRIK": "Pabrik", "T1": "Vendor", "T2": "Kolektor"}
        assert d["filters"]["supplier"] == kode

        kode_node = {n["kode"] for n in d["nodes"]}
        assert "V1" not in kode_node and "K1" not in kode_node
        assert "PABRIK" in kode_node
        assert kode in kode_node
        assert ck in kode_node

        t1 = [n for n in d["nodes"] if n["tier"] == "T1"]
        t2 = [n for n in d["nodes"] if n["tier"] == "T2"]
        assert len(t1) == 1 and t1[0]["kode"] == kode
        assert len(t2) == 1 and t2[0]["kode"] == ck
        assert t1[0]["volume_kg"] > 0
        assert t2[0]["volume_kg"] > 0
        assert t1[0]["volume_kg"] >= t2[0]["volume_kg"]

        assert {"dari": "PABRIK", "ke": kode} in [
            {"dari": e["dari"], "ke": e["ke"]} for e in d["edges"]]
        assert any(e["dari"] == kode and e["ke"] == ck for e in d["edges"])
        assert d["anak_t1"].get(kode, []) == [ck]
        assert d["meta"]["volume_pabrik_kg"] > 0
        assert "T1 tetap vendor, T2 tetap kolektor" in d["catatan"]
    finally:
        _bersihkan(session, kode, ck, vendor_baru)


def test_batas_dan_alias_pohon(klien, session, engine):
    kode, ck, vendor_baru = _siapkan_kolektor(session)
    try:
        r = klien.get("/api/traceability/tree?periode=ALL&batas=1")
        assert r.status_code == 200
        d = r.json()
        assert d["meta"]["total_t1"] <= 1
        assert d["filters"]["batas"] == 1

        alias = klien.get("/api/traceability/pohon?periode=ALL&batas=1")
        assert alias.status_code == 200
        assert alias.json()["kode_tier"] == d["kode_tier"]
    finally:
        _bersihkan(session, kode, ck, vendor_baru)


def test_health_menyebut_fitur_tree(klien):
    assert "traceability-tree" in klien.get("/api/health").json()["fitur"]
