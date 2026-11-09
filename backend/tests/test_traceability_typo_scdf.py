"""Deteksi potensi salah ketik SCDF pada Sourcing locations Supplier Actors.

Deteksi ini pelengkap rekomendasi intake tahun sebelumnya. Ia membandingkan
ejaan District/Sub-district dengan referensi SCDF, tidak menyimpan apa pun,
dan kandidat yang dipakai tetap menunggu klik Simpan.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import api_traceability
from app.core.deteksi_salah_ketik import (
    ambang_untuk, indeks_kandidat, norma_mirip, padatkan,
    skor_kemiripan, varian_padat,
)
from app.main import buat_app
from app.models import (AuditLog, Base, KoreksiWilayahTrace,
                        ReferensiWilayahTrace, TiketBaris)


def _ref(kab: str, kec: str, desa: str) -> ReferensiWilayahTrace:
    return ReferensiWilayahTrace(
        kabupaten_norm=kab, kecamatan_norm=kec, desa_norm=desa,
        kabupaten=kab.title(), kecamatan=kec.title(), desa=desa.title(),
        code=None)


def _tiket(kab: str, kec: str, desa: str) -> TiketBaris:
    return TiketBaris(
        ticket_no="T-TYPO", line_seq=1, ticket_date=dt.date(2026, 2, 1),
        kode_vendor="V1", nama_vendor_asli="Supplier Uji", item_code="SIR20",
        wet_kg=1000, drc_pct=50, dry_kg=500,
        asal_getah=f"Indonesia, {kab}, {kec}, {desa}",
        kabupaten=kab.title(), kecamatan=kec.title(), desa=desa.title(),
        kabupaten_norm=kab, kecamatan_norm=kec, desa_norm=desa,
        asal_getah_valid=True, source_fingerprint="t" * 64, tiket_nol=False)


def _klien(refs: list[ReferensiWilayahTrace],
           tiket: TiketBaris | None = None) -> tuple[TestClient, object]:
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as session:
        session.add_all(refs)
        if tiket is not None:
            session.add(tiket)
        session.commit()
    return TestClient(buat_app(eng)), eng


@pytest.fixture()
def klien(engine):
    return TestClient(buat_app(engine))


def test_normalisasi_menangkap_spasi_tanda_baca_dan_awalan():
    assert padatkan("D U M A I") == "DUMAI"
    assert padatkan("GAM[PONG REUSAK") == "GAMPONGREUSAK"
    assert "REUSAK" in varian_padat("GAM[PONG REUSAK")
    assert skor_kemiripan("GAM[PONG REUSAK", "Reusak") == 100.0
    assert skor_kemiripan("PEUNARAON BARU", "Peunaron Baru") >= 95.0
    assert skor_kemiripan("BABURA", "BABURA") == 100.0


def test_nama_pendek_butuh_ambang_lebih_tinggi():
    indeks = indeks_kandidat([("JAAN", "Jaan"), ("JALAN", "Jalan")])
    assert ambang_untuk("JALAN") == 90.0
    assert skor_kemiripan("JALAN", "JAAN") < 90.0
    assert norma_mirip("JAAN", indeks) == {"JAAN": 100.0}
    assert norma_mirip("JALAN", indeks) == {"JALAN": 100.0}


def test_status_cocok_tidak_memunculkan_peringatan_salah_ketik():
    klien, _ = _klien([_ref("KAB B", "KEC X", "BABURA")],
                      _tiket("KAB B", "KEC X", "BABURA"))
    r = klien.get("/api/traceability/actors/V1/origin-typo-check", params={
        "source_kabupaten_norm": "KAB B", "source_kecamatan_norm": "KEC X",
        "source_desa_norm": "BABURA"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "cocok"
    assert d["candidates"] == []
    assert d["checks"]["district"]["exact"] is True
    assert d["checks"]["subdistrict"]["exact"] is True
    assert "bukan rekomendasi" in d["basis"]


def test_deteksi_salah_ketik_subdistrict_dan_awalan_gampong():
    klien, _ = _klien([
        _ref("KAB C", "SAMATIGA", "REUSAK"),
        _ref("KAB C", "SAMATIGA", "DESA JAUH"),
    ], _tiket("KAB C", "SAMATIGA", "GAM[PONG REUSAK"))
    r = klien.get("/api/traceability/actors/V1/origin-typo-check", params={
        "source_kabupaten_norm": "KAB C", "source_kecamatan_norm": "SAMATIGA",
        "source_desa_norm": "GAM[PONG REUSAK",
        "source_kecamatan": "Samatiga", "source_desa": "Gam[pong Reusak"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "potensi_salah_ketik"
    assert d["source"]["desa"] == "Gam[pong Reusak"
    assert d["checks"]["district"]["exact"] is True
    assert d["checks"]["subdistrict"]["exact"] is False
    terbaik = next(c for c in d["candidates"] if c["desa_norm"] == "REUSAK")
    assert terbaik["subdistrict_score_pct"] == 100.0
    assert terbaik["same_regency"] is True
    assert terbaik["dapat_dipakai"] is True
    assert "Simpan" in d["catatan"]


def test_deteksi_tidak_mengubah_data_dan_lintas_induk_bisa_dipetakan():
    sumber = _tiket("KAB A", "KEC X", "BABURAA")
    klien, eng = _klien([
        _ref("KAB B", "KEC X", "BABURA"),
        _ref("KAB A", "KEC Y", "DESA JAUH"),
    ], sumber)
    params = {
        "source_kabupaten_norm": "KAB A", "source_kecamatan_norm": "KEC X",
        "source_desa_norm": "BABURAA"}
    r = klien.get("/api/traceability/actors/V1/origin-typo-check", params=params)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "potensi_salah_ketik"
    kandidat = next(c for c in d["candidates"] if c["desa_norm"] == "BABURA")
    assert kandidat["kabupaten_norm"] == "KAB B"
    assert kandidat["same_regency"] is False
    assert kandidat["dapat_dipakai"] is True
    with Session(eng) as session:
        assert session.scalar(select(KoreksiWilayahTrace)) is None

    simpan = klien.put("/api/traceability/actors/V1/origin-correction",
                       params={"tahun": 2026}, json={
                           **params,
                           "target_kabupaten_norm": kandidat["kabupaten_norm"],
                           "target_kecamatan_norm": kandidat["kecamatan_norm"],
                           "target_desa_norm": kandidat["desa_norm"],
                       })
    assert simpan.status_code == 200, simpan.text
    assert simpan.json()["manual_correction"] is True
    assert simpan.json()["induk_scdf"]["berbeda_dari_sumber"] is True
    with Session(eng) as session:
        koreksi = session.scalar(select(KoreksiWilayahTrace))
        assert koreksi is not None
        assert koreksi.target_ref_id == kandidat["ref_id"]
        baris = session.scalar(select(TiketBaris))
        assert (baris.kabupaten_norm, baris.kecamatan_norm, baris.desa_norm) == (
            "KAB A", "KEC X", "BABURAA")
        audit = session.scalar(select(AuditLog).where(
            AuditLog.objek == "traceability_wilayah_koreksi"))
        assert audit is not None
        detail = json.loads(audit.detail)
        assert detail["target"]["kabupaten_norm"] == "KAB B"
        assert detail["target"]["berbeda_dari_induk_sumber"] is True

    detail = klien.get("/api/traceability/actors/V1", params={"tahun": 2026})
    assert detail.status_code == 200, detail.text
    asal = detail.json()["origins"][0]
    assert asal["source_regency"] == "Kab A"
    assert asal["sub_district"] == "Babura"
    assert asal["manual_correction"] is True

    reset = klien.put("/api/traceability/actors/V1/origin-correction",
                      params={"tahun": 2026},
                      json={**params, "target_desa_norm": None})
    assert reset.status_code == 200, reset.text
    with Session(eng) as session:
        assert session.scalar(select(KoreksiWilayahTrace)) is None


def test_status_sumber_tidak_lengkap_dan_referensi_kosong(tmp_path, monkeypatch):
    klien, _ = _klien([_ref("KAB B", "KEC X", "BABURA")])
    r = klien.get("/api/traceability/actors/V1/origin-typo-check", params={
        "source_kabupaten_norm": "KAB B", "source_kecamatan_norm": "",
        "source_desa_norm": ""})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sumber_tidak_lengkap"

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    monkeypatch.setattr(api_traceability, "NAMA_FILE_REFERENSI",
                        tmp_path / "tidak-ada.xlsx")
    klien_kosong = TestClient(buat_app(eng))
    r2 = klien_kosong.get("/api/traceability/actors/V1/origin-typo-check", params={
        "source_kabupaten_norm": "KAB B", "source_kecamatan_norm": "KEC X",
        "source_desa_norm": "BABURA"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "referensi_kosong"


def test_health_menyebut_fitur_deteksi_typo_scdf(klien):
    assert "traceability-scdf-typo" in klien.get("/api/health").json()["fitur"]
