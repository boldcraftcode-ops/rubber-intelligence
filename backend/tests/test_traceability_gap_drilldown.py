"""Drill-down gap Traceability: ticket rows + koreksi SCDF per kunci sumber."""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import buat_app
from app.models import (Base, KoreksiWilayahTrace, ReferensiWilayahTrace,
                        TiketBaris, Vendor)


PARAMS = {"tahun": 2026, "tingkat": "Desa/Kelurahan",
          "name": "BABURA BARU", "parent_path": "MEDAN / MEDAN BARU"}


@pytest.fixture()
def client_gap():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all([
            Vendor(kode="V1", nama_baku="Supplier One", status="aktif"),
            Vendor(kode="V2", nama_baku="Supplier Two", status="aktif"),
            ReferensiWilayahTrace(
                kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU",
                desa_norm="BABURA", kabupaten="Kota Medan",
                kecamatan="Medan Baru", desa="Babura"),
            ReferensiWilayahTrace(
                kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU",
                desa_norm="BABURA TIMUR", kabupaten="Kota Medan",
                kecamatan="Medan Baru", desa="Babura Timur"),
            ReferensiWilayahTrace(
                kabupaten_norm="BANDUNG", kecamatan_norm="BANDUNG BARU",
                desa_norm="CIHAMPELAS", kabupaten="Kota Bandung",
                kecamatan="Bandung Baru", desa="Cihampelas"),
        ])
        baris = (
            ("T-1", "V1", "BABURA BARU", True, 500, "a" * 64),
            ("T-2", "V1", "BABURA BARU", False, 250, "b" * 64),
            ("T-3", "V2", "BABURA BARU", True, 300, "c" * 64),
            ("T-4", "V1", "BABURA", True, 400, "d" * 64),
        )
        for i, (no, vendor, desa, valid, dry, fp) in enumerate(baris, 1):
            s.add(TiketBaris(
                ticket_no=no, line_seq=1, ticket_date=dt.date(2026, 2, i),
                kode_vendor=vendor, nama_vendor_asli=f"Supplier {vendor}",
                item_code="SIR20", wet_kg=dry * 2, drc_pct=50,
                dry_kg=dry,
                asal_getah=("Sumatera Utara, Kota Medan, Medan Baru, "
                            f"{desa.title()}"),
                kabupaten="Kota Medan", kecamatan="Medan Baru",
                desa=desa.title(), kabupaten_norm="MEDAN",
                kecamatan_norm="MEDAN BARU", desa_norm=desa,
                asal_getah_valid=valid, source_fingerprint=fp,
                tiket_nol=False))
        s.commit()
    klien = TestClient(buat_app(eng))
    yield klien, eng
    eng.dispose()


def _body(**ubah):
    data = {
        "tingkat": PARAMS["tingkat"], "name": PARAMS["name"],
        "parent_path": PARAMS["parent_path"],
        "source_kabupaten_norm": "MEDAN",
        "source_kecamatan_norm": "MEDAN BARU",
        "source_desa_norm": "BABURA BARU",
        "target_kabupaten_norm": "MEDAN",
        "target_kecamatan_norm": "MEDAN BARU",
        "target_desa_norm": "BABURA",
    }
    data.update(ubah)
    return data


def test_detail_gap_memakai_filter_dan_tidak_menulis_koreksi(client_gap):
    klien, eng = client_gap
    sebelum = klien.get("/api/traceability", params={"tahun": 2026}).json()
    assert sebelum["kpis"]["trace_desa_mt"] == 0.4

    r = klien.get("/api/traceability/gap-details", params=PARAMS)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["path"] == ["MEDAN", "MEDAN BARU", "BABURA BARU"]
    assert data["filters"]["supplier"] is None
    assert data["dry_kg"] == 1050.0
    assert data["ticket_lines"] == 3
    assert data["tickets"] == 3
    assert data["jumlah_kelompok"] == 1
    group = data["kelompok"][0]
    assert group["source_key"] == {
        "kabupaten_norm": "MEDAN", "kecamatan_norm": "MEDAN BARU",
        "desa_norm": "BABURA BARU"}
    assert group["dry_kg"] == 1050.0
    assert "Asal Getah tidak valid" in group["alasan"]
    assert "Desa/Kelurahan tidak cocok dengan referensi SCDF" in group["alasan"]
    assert {t["ticket_no"] for t in group["tiket"]} == {"T-1", "T-2", "T-3"}
    contoh = next(t for t in group["tiket"] if t["ticket_no"] == "T-1")
    assert {k for k in ("ticket_date", "supplier_code", "item_code",
                        "asal_getah", "kabupaten", "kecamatan", "desa",
                        "dry_kg", "reason")} <= set(contoh)
    assert contoh["reason"] == "Desa/Kelurahan tidak cocok dengan referensi SCDF"

    filter_v1 = klien.get("/api/traceability/gap-details",
                          params={**PARAMS, "supplier": "V1"}).json()
    assert filter_v1["filters"]["supplier"] == "V1"
    assert filter_v1["ticket_lines"] == 2
    assert filter_v1["dry_kg"] == 750.0
    assert {t["ticket_no"] for t in filter_v1["kelompok"][0]["tiket"]} == {
        "T-1", "T-2"}
    with Session(eng) as s:
        assert s.scalar(select(KoreksiWilayahTrace)) is None


def test_validasi_path_dan_batas_tiket(client_gap):
    klien, _ = client_gap
    assert klien.get("/api/traceability/gap-details", params={
        **PARAMS, "parent_path": "MEDAN"}).status_code == 422
    assert klien.get("/api/traceability/gap-details", params={
        **PARAMS, "tingkat": "Provinsi"}).status_code == 422
    assert klien.get("/api/traceability/gap-details", params={
        **PARAMS, "batas_tiket": 0}).status_code == 422
    assert klien.get("/api/traceability/gap-details", params={
        **PARAMS, "batas_tiket": 501}).status_code == 422
    akar = klien.get("/api/traceability/gap-details", params={
        "tahun": 2026, "tingkat": "Kabupaten/Kota", "name": "MEDAN",
        "parent_path": "—"})
    assert akar.status_code == 200, akar.text
    assert akar.json()["path"] == ["MEDAN"]


def test_koreksi_gap_satu_kunci_sumber_tanpa_mengubah_intake(client_gap):
    klien, eng = client_gap
    salah_induk = klien.put("/api/traceability/gap-correction",
                            params={"tahun": 2026}, json=_body(
                                target_kabupaten_norm="BANDUNG",
                                target_kecamatan_norm="BANDUNG BARU",
                                target_desa_norm="CIHAMPELAS"))
    assert salah_induk.status_code == 422, salah_induk.text
    assert "Kabupaten/Kota sumber" in salah_induk.json()["detail"]
    target_tidak_resmi = klien.put("/api/traceability/gap-correction",
                                   params={"tahun": 2026}, json=_body(
                                       target_desa_norm="DESA TIDAK ADA"))
    assert target_tidak_resmi.status_code == 422, target_tidak_resmi.text
    sumber_bukan_gap = klien.put("/api/traceability/gap-correction",
                                 params={"tahun": 2026}, json=_body(
                                     source_desa_norm="BABURA"))
    assert sumber_bukan_gap.status_code == 404, sumber_bukan_gap.text
    with Session(eng) as s:
        assert s.scalar(select(KoreksiWilayahTrace)) is None

    simpan = klien.put("/api/traceability/gap-correction",
                       params={"tahun": 2026}, json=_body())
    assert simpan.status_code == 200, simpan.text
    assert simpan.json()["manual_correction"] is True
    assert "Semua tiket" in simpan.json()["scope"]
    assert simpan.json()["target"]["desa"] == "Babura"

    sesudah = klien.get("/api/traceability", params={"tahun": 2026}).json()
    assert sesudah["kpis"]["trace_desa_mt"] == 1.45
    assert sesudah["kpis"]["trace_desa_pct"] == 100.0
    rincian = klien.get("/api/traceability/gap-details", params=PARAMS).json()
    assert rincian["jumlah_kelompok"] == 0
    assert rincian["ticket_lines"] == 0

    with Session(eng) as s:
        koreksi = s.scalar(select(KoreksiWilayahTrace))
        assert koreksi is not None
        assert koreksi.source_desa_norm == "BABURA BARU"
        asli = s.scalars(select(TiketBaris).where(
            TiketBaris.ticket_no.in_(["T-1", "T-3"]))).all()
        assert {t.desa_norm for t in asli} == {"BABURA BARU"}
        assert all(t.asal_getah and "Babura Baru" in t.asal_getah
                   for t in asli)
