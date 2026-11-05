"""Kelas supplier berbasis Dry (MT) per supplier per bulan.

Batas (tanda ≥): SS 1.500, S 1.000, A 500, B 250, C 100, dan D < 100 MT.
Yang dijaga: batas inklusif, nilai tanpa pembulatan, distribusi supplier-bulan
hanya untuk vendor yang terdaftar di Master Vendor (kode intake tanpa master
dilaporkan terpisah), kelas tertinggi pada Kpi detail, serta field lama
(klasifikasi, sourcing type, supply chain) yang tidak berubah.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.kelas_intake import (batas_untuk_layar, distribusi, kelas,
                                   kelas_tertinggi)
from app.main import buat_app
from app.models import (Base, ReferensiWilayahTrace, TiketBaris, Vendor)


@pytest.mark.parametrize("mt,harapan", [
    (1600, "SS"), (1500, "SS"), (1499.9999, "S"),
    (1000, "S"), (999.9999, "A"),
    (500, "A"), (499.9999, "B"),
    (250, "B"), (249.9999, "C"),
    (100, "C"), (99.9999, "D"), (0, "D"), (-5, "D"),
])
def test_batas_kelas_inklusif_tanpa_pembulatan(mt, harapan):
    assert kelas(mt) == harapan


def test_urutan_dan_legenda():
    assert kelas_tertinggi(["C", "A", "D"]) == "A"
    assert kelas_tertinggi([]) is None
    assert kelas_tertinggi([None, "bukan_kelas"]) is None
    assert [b["kelas"] for b in batas_untuk_layar()] == \
        ["SS", "S", "A", "B", "C", "D"]
    assert batas_untuk_layar()[-1]["label"] == "< 100 MT"
    assert [d["jumlah"] for d in distribusi(["SS", "D", "D", "A"])] == \
        [1, 0, 1, 0, 0, 2]


def _tiket(no: str, vendor: str, nama: str, bulan: int, dry_mt: float) -> TiketBaris:
    dry_kg = dry_mt * 1000
    return TiketBaris(
        ticket_no=no, line_seq=1, ticket_date=dt.date(2026, bulan, 5),
        kode_vendor=vendor, nama_vendor_asli=nama, item_code="SIR20",
        wet_kg=dry_kg * 2, drc_pct=50, dry_kg=dry_kg,
        asal_getah="Sumatera Utara, Kota Medan, Medan Baru, Babura",
        kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU",
        desa_norm="BABURA", asal_getah_valid=True,
        source_fingerprint=no.ljust(64, "0"), tiket_nol=False)


@pytest.fixture()
def klien():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        # Cegah seed ID_AUX (81.909 baris) saat tes.
        s.add(ReferensiWilayahTrace(
            kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU",
            desa_norm="BABURA", kabupaten="Kota Medan",
            kecamatan="Medan Baru", desa="Babura", code=None))
        s.add(Vendor(kode="V1", nama_baku="Supplier Satu", status="aktif",
                     klasifikasi="small_holder"))
        s.add(Vendor(kode="V2", nama_baku="Supplier Dua", status="aktif"))
        # V1: enam bulan, masing-masing satu kelas.
        for i, (bulan, mt) in enumerate([
                (1, 1600), (2, 1000), (3, 500), (4, 250), (5, 100), (6, 99)]):
            s.add(_tiket(f"T1-{i}", "V1", "Supplier Satu", bulan, mt))
        s.add(_tiket("T2-0", "V2", "Supplier Dua", 1, 1200))   # S
        s.add(_tiket("T9-0", "V9", "Intake Saja", 1, 5))        # tanpa master
        s.commit()
    return TestClient(buat_app(eng))


def test_distribusi_dan_field_baru_tidak_mengubah_data_lama(klien):
    r = klien.get("/api/traceability/kelas-intake", params={"tahun": 2026})
    assert r.status_code == 200, r.text
    d = r.json()
    assert [(x["kelas"], x["jumlah"]) for x in d["distribusi"]] == [
        ("SS", 1), ("S", 2), ("A", 1), ("B", 1), ("C", 1), ("D", 1)]
    assert d["total_supplier_bulan"] == 7
    assert d["supplier_bulan_tanpa_master"] == 1
    assert d["kode_tanpa_master"] == ["V9"]
    assert d["bulan_tersedia"] == ["2026-01", "2026-02", "2026-03",
                                   "2026-04", "2026-05", "2026-06"]
    assert [b["batas_mt"] for b in d["batas"]] == \
        [1500.0, 1000.0, 500.0, 250.0, 100.0, None]

    detail = klien.get("/api/traceability/actors/V1",
                       params={"tahun": 2026}).json()
    assert detail["supplier_class"] == "SS"       # kelas tertinggi
    assert [b["kelas"] for b in detail["class_by_month"]] == \
        ["SS", "S", "A", "B", "C", "D"]
    assert detail["class_by_month"][0]["dry_mt"] == 1600.0
    assert "≥" in detail["class_basis"] or "tanda" in detail["class_basis"]
    assert len(detail["class_thresholds"]) == 6

    # Field lama tetap utuh.
    assert detail["classification"] == "Small holder"
    assert detail["sourcing_type_code"] is None
    assert detail["supply_chain"]["lane_count"] >= 1
    assert detail["tier"] == "T1"


def test_kelas_mengikuti_filter_periode(klien):
    d = klien.get("/api/traceability/kelas-intake",
                  params={"tahun": 2026, "periode": "Q1"}).json()
    assert [(x["kelas"], x["jumlah"]) for x in d["distribusi"]] == [
        ("SS", 1), ("S", 2), ("A", 1), ("B", 0), ("C", 0), ("D", 0)]
    assert d["total_supplier_bulan"] == 4
    detail = klien.get("/api/traceability/actors/V1",
                       params={"tahun": 2026, "periode": "Q1"}).json()
    assert [b["bulan"] for b in detail["class_by_month"]] == \
        ["2026-01", "2026-02", "2026-03"]
    assert detail["supplier_class"] == "SS"

    # Supplier tanpa intake pada periode tertentu tidak punya kelas.
    kosong = klien.get("/api/traceability/actors/V1",
                       params={"tahun": 2026, "periode": "12"}).json()
    assert kosong["supplier_class"] is None
    assert kosong["class_by_month"] == []


def test_kode_tanpa_master_tetap_punya_kelas_di_detail(klien):
    detail = klien.get("/api/traceability/actors/V9",
                       params={"tahun": 2026}).json()
    assert detail["supplier_class"] == "D"
    assert detail["class_by_month"][0]["dry_mt"] == 5.0
    assert detail["classification"] is None
