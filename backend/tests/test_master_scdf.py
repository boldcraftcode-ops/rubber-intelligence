"""Master Data → SCDF: katalog hierarki lokasi, baca saja."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import buat_app
from app.models import Base, ReferensiWilayahTrace


@pytest.fixture()
def client_scdf():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        baris = (
            ("ACEH", "ACEH", "ACEH BARAT", "ACEH BARAT", "MEUREUBO",
             "MEUREUBO", "GAMPONG PASI ACEH BAROH", "GAMPONG PASI ACEH BAROH"),
            ("ACEH", "ACEH", "ACEH BARAT", "ACEH BARAT", "MEUREUBO",
             "MEUREUBO", "MEULABOH", "MEULABOH"),
            ("SUMATERA UTARA", "SUMATERA UTARA", "MEDAN", "MEDAN",
             "MEDAN BARU", "MEDAN BARU", "BABURA", "BABURA"),
            (None, None, "BANJAR", "BANJAR", "BANJAR BARU", "BANJAR BARU",
             "DESA X", "DESA X"),
            (None, None, "HUTAN", "HUTAN", "HUTAN", "HUTAN",
             "DESA HUTAN", "DESA HUTAN"),
        )
        for p, pn, k, kn, kec, kecn, d, dn in baris:
            s.add(ReferensiWilayahTrace(
                provinsi=p, provinsi_norm=pn, kabupaten=k, kabupaten_norm=kn,
                kecamatan=kec, kecamatan_norm=kecn, desa=d, desa_norm=dn,
                code=None))
        s.commit()
    klien = TestClient(buat_app(eng))
    yield klien, eng
    eng.dispose()


def _snapshot_referensi(eng):
    R = ReferensiWilayahTrace
    with Session(eng) as s:
        rows = s.execute(select(
            R.id, R.provinsi, R.provinsi_norm, R.kabupaten,
            R.kabupaten_norm, R.kecamatan, R.kecamatan_norm,
            R.desa, R.desa_norm).order_by(R.id)).all()
    return [tuple(r) for r in rows]


def test_ringkasan_dan_health_tanpa_mengubah_referensi(client_scdf):
    klien, eng = client_scdf
    sebelum = _snapshot_referensi(eng)
    r = klien.get("/api/master/scdf/ringkasan")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["provinsi"] == 2
    assert d["kabupaten_kota"] == 4
    assert d["kecamatan"] == 4
    assert d["desa_kelurahan"] == 5
    assert d["baris"] == 5
    assert d["baris_tanpa_provinsi"] == 2
    assert d["kunci_tanpa_provinsi"] == 2
    assert "baca saja" in d["catatan"]
    assert "master-scdf-hierarki" in klien.get("/api/health").json()["fitur"]
    j = klien.get("/api/jelaskan/master_scdf")
    assert j.status_code == 200, j.text
    assert "SCDF" in j.json()["judul"]
    assert "traceability_wilayah" in j.json()["rumus"]
    assert _snapshot_referensi(eng) == sebelum


def test_get_tidak_memanggil_seed_pada_katalog_sudah_siap(client_scdf,
                                                          monkeypatch):
    from app import api_master_scdf as mod

    def gagal(*_a, **_k):
        raise AssertionError("Seed tidak boleh dipanggil pada data siap.")

    monkeypatch.setattr(mod, "muat_referensi_bawaan", gagal)
    klien, eng = client_scdf
    sebelum = _snapshot_referensi(eng)
    for url, params in (
        ("/api/master/scdf/ringkasan", {}),
        ("/api/master/scdf/pohon", {"tingkat": "provinsi"}),
        ("/api/master/scdf/detail", {
            "tingkat": "provinsi", "provinsi_norm": "ACEH"}),
    ):
        assert klien.get(url, params=params).status_code == 200
    assert _snapshot_referensi(eng) == sebelum


def test_pohon_empat_tingkat_termasuk_belum_dipetakan(client_scdf):
    klien, _ = client_scdf
    akar = klien.get("/api/master/scdf/pohon", params={"tingkat": "provinsi"})
    assert akar.status_code == 200, akar.text
    d = akar.json()
    assert d["tingkat_anak"] == "kabupaten"
    assert d["jumlah_node"] == 3
    assert {n["name"] for n in d["nodes"]} == {
        "ACEH", "SUMATERA UTARA", "Belum dipetakan"}
    tanpa = next(n for n in d["nodes"] if n["name"] == "Belum dipetakan")
    assert tanpa["norm"] == ""
    assert tanpa["status_provinsi"] == "belum_dipetakan"
    assert tanpa["jumlah_anak"] == 2

    kab = klien.get("/api/master/scdf/pohon", params={
        "tingkat": "kabupaten", "provinsi_norm": "ACEH"}).json()
    assert kab["jumlah_node"] == 1
    assert kab["nodes"][0]["name"] == "ACEH BARAT"
    assert kab["nodes"][0]["jumlah_anak"] == 1
    assert kab["nodes"][0]["jumlah_baris"] == 2
    assert kab["nodes"][0]["status_provinsi"] == "terpetakan"

    kab_kosong = klien.get("/api/master/scdf/pohon", params={
        "tingkat": "kabupaten", "provinsi_norm": ""}).json()
    assert {n["name"] for n in kab_kosong["nodes"]} == {"BANJAR", "HUTAN"}
    assert all(n["status_provinsi"] == "belum_dipetakan"
               for n in kab_kosong["nodes"])

    kec = klien.get("/api/master/scdf/pohon", params={
        "tingkat": "kecamatan", "provinsi_norm": "ACEH",
        "kabupaten_norm": "ACEH BARAT"}).json()
    assert kec["jumlah_node"] == 1
    assert kec["nodes"][0]["name"] == "MEUREUBO"
    assert kec["nodes"][0]["jumlah_anak"] == 2

    desa = klien.get("/api/master/scdf/pohon", params={
        "tingkat": "desa", "provinsi_norm": "ACEH",
        "kabupaten_norm": "ACEH BARAT", "kecamatan_norm": "MEUREUBO"}).json()
    assert desa["tingkat_anak"] is None
    assert {n["name"] for n in desa["nodes"]} == {
        "GAMPONG PASI ACEH BAROH", "MEULABOH"}
    assert all(n["jumlah_anak"] == 0 for n in desa["nodes"])


def test_rincian_nama_normalized_status_dan_paginasi(client_scdf):
    klien, _ = client_scdf
    r = klien.get("/api/master/scdf/detail", params={
        "tingkat": "provinsi", "provinsi_norm": "ACEH",
        "limit": 1, "offset": 1})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total"] == 2
    assert d["halaman"] == 2
    assert d["jumlah_halaman"] == 2
    assert len(d["baris"]) == 1
    b = d["baris"][0]
    assert {"provinsi", "kabupaten", "kecamatan", "desa",
            "provinsi_norm", "kabupaten_norm", "kecamatan_norm",
            "desa_norm", "status_provinsi"} <= set(b)
    assert b["status_provinsi"] == "terpetakan"

    tanpa = klien.get("/api/master/scdf/detail", params={
        "tingkat": "provinsi", "provinsi_norm": ""}).json()
    assert tanpa["total"] == 2
    assert all(b["provinsi"] == "Belum dipetakan"
               and b["provinsi_norm"] == ""
               and b["status_provinsi"] == "belum_dipetakan"
               for b in tanpa["baris"])

    desa = klien.get("/api/master/scdf/detail", params={
        "tingkat": "desa", "provinsi_norm": "ACEH",
        "kabupaten_norm": "ACEH BARAT", "kecamatan_norm": "MEUREUBO",
        "desa_norm": "MEULABOH"})
    assert desa.status_code == 200, desa.text
    assert desa.json()["total"] == 1
    assert desa.json()["baris"][0]["desa"] == "MEULABOH"


def test_validasi_induk_batas_dan_hanya_endpoint_get(client_scdf):
    klien, _ = client_scdf
    assert klien.get("/api/master/scdf/pohon", params={
        "tingkat": "kabupaten"}).status_code == 422
    assert klien.get("/api/master/scdf/pohon", params={
        "tingkat": "kecamatan", "provinsi_norm": "ACEH"}).status_code == 422
    assert klien.get("/api/master/scdf/detail", params={
        "tingkat": "kabupaten", "provinsi_norm": "ACEH"}).status_code == 422
    assert klien.get("/api/master/scdf/detail", params={
        "tingkat": "kecamatan", "provinsi_norm": "ACEH",
        "kabupaten_norm": "ACEH BARAT"}).status_code == 422
    assert klien.get("/api/master/scdf/detail", params={
        "tingkat": "desa", "provinsi_norm": "ACEH",
        "kabupaten_norm": "ACEH BARAT",
        "kecamatan_norm": "MEUREUBO"}).status_code == 422
    assert klien.get("/api/master/scdf/detail", params={
        "tingkat": "provinsi", "provinsi_norm": "ACEH",
        "limit": 0}).status_code == 422
    assert klien.get("/api/master/scdf/detail", params={
        "tingkat": "provinsi", "provinsi_norm": "ACEH",
        "limit": 201}).status_code == 422
    assert klien.get("/api/master/scdf/detail", params={
        "tingkat": "provinsi", "provinsi_norm": "ACEH",
        "offset": -1}).status_code == 422
    spesifikasi = klien.get("/openapi.json").json()["paths"]
    rute = {p: m for p, m in spesifikasi.items()
            if p.startswith("/api/master/scdf")}
    assert rute
    assert all(set(m) == {"get"} for m in rute.values())
