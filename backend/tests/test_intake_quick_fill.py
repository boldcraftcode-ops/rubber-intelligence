"""Quick-fill koreksi intake: pratinjau dulu, konfirmasi, lalu simpan atomik."""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import buat_app
from app.models import AuditLog, Base, ReferensiWilayahTrace, TiketBaris


def _engine():
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def _isi(eng):
    with sessionmaker(bind=eng, future=True)() as s:
        s.add(ReferensiWilayahTrace(
            kabupaten_norm="MANDAILING NATAL", kecamatan_norm="SIPIROK",
            desa_norm="HUTA RAJA BARU", kabupaten="Mandailing Natal",
            kecamatan="Sipirok", desa="Huta Raja Baru", code=None))
        s.add_all([
            TiketBaris(ticket_no="T-001", line_seq=1,
                       ticket_date=dt.date(2026, 3, 1), kode_vendor="V001",
                       nama_vendor_asli="CV Alpha", item_code="SLAB2",
                       wet_kg=100, dry_kg=62, drc_pct=62, bin="B1",
                       asal_getah="SUMUT_MANDAILING NATAL_SIPIROK_HUTA RAJA",
                       source_fingerprint="fp-001",
                       provinsi="SUMATERA UTARA", kabupaten="MANDAILING NATAL",
                       kecamatan="DISTRIK LAMA", desa="HUTA RAJA",
                       kabupaten_norm="MANDAILING NATAL", kecamatan_norm="DISTRIK LAMA",
                       desa_norm="HUTA RAJA", asal_getah_valid=True, tiket_nol=False),
            TiketBaris(ticket_no="T-002", line_seq=1,
                       ticket_date=dt.date(2026, 3, 2), kode_vendor="V002",
                       nama_vendor_asli="PT Beta", item_code="SLAB2",
                       wet_kg=200, dry_kg=124, drc_pct=62, bin="B2",
                       asal_getah="RIAU_KAMPAR_BANGKINANG_AIR TIRIS",
                       source_fingerprint="fp-002",
                       provinsi="RIAU", kabupaten="KAMPAR", kecamatan="BANGKINANG",
                       desa="AIR TIRIS", asal_getah_valid=True, tiket_nol=False),
            TiketBaris(ticket_no="T-003", line_seq=1,
                       ticket_date=dt.date(2026, 3, 3), kode_vendor="V003",
                       nama_vendor_asli="CV Gamma", item_code="SLAB2",
                       wet_kg=150, dry_kg=93, drc_pct=62, bin="B3",
                       asal_getah="SUMUT_ASAHAN_KISARAN_RAWANG",
                       source_fingerprint="fp-003",
                       provinsi="SUMATERA UTARA", kabupaten="ASAHAN",
                       kecamatan="KISARAN", desa="RAWANG",
                       asal_getah_valid=True, tiket_nol=False),
        ])
        s.commit()


@pytest.fixture()
def data(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    _isi(eng)
    return TestClient(buat_app(eng)), eng


def _ids(klien):
    r = klien.get("/api/intake", params={"tahun": 2026})
    assert r.status_code == 200, r.text
    return [b["id"] for b in r.json()["baris"]]


def _pratinjau(klien, ids, kolom, nilai=None, kosongkan=False):
    return klien.post("/api/intake/quick-fill/pratinjau", json={
        "ids": ids, "kolom": kolom, "nilai": nilai, "kosongkan": kosongkan,
    })


def test_pratinjau_tidak_mengubah_data(data):
    klien, eng = data
    ids = _ids(klien)[:2]
    r = _pratinjau(klien, ids, "kode_vendor", "V009")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "siap" and d["token"]
    assert d["jumlah"] == 2 and d["berubah"] == 2
    assert all(b["sesudah"] == "V009" for b in d["baris"])
    with sessionmaker(bind=eng, future=True)() as s:
        assert all(s.get(TiketBaris, i).kode_vendor != "V009" for i in ids)
        assert s.scalar(select(AuditLog.id).where(AuditLog.aksi == "ubah_massal").limit(1)) is None


def test_terapkan_menyimpan_semua_baris_dan_audit(data):
    klien, eng = data
    ids = _ids(klien)[:2]
    token = _pratinjau(klien, ids, "kode_vendor", " v009 ").json()["token"]
    r = klien.post("/api/intake/quick-fill/terapkan", json={"token": token})
    assert r.status_code == 200, r.text
    assert r.json()["jumlah"] == 2
    with sessionmaker(bind=eng, future=True)() as s:
        for i in ids:
            row = s.get(TiketBaris, i)
            assert row.kode_vendor == "V009"
            assert row.ticket_no.startswith("T-")
            assert row.asal_getah and row.source_fingerprint
        audit = list(s.scalars(select(AuditLog).where(
            AuditLog.objek == "intake_tiket", AuditLog.aksi == "ubah_massal")))
        assert len(audit) == 2
        assert all('"kolom": "kode_vendor"' in a.detail for a in audit)
    # Token sekali pakai.
    lagi = klien.post("/api/intake/quick-fill/terapkan", json={"token": token})
    assert lagi.status_code == 404


def test_data_berubah_sejak_pratinjau_ditolak(data):
    klien, eng = data
    ids = _ids(klien)[:1]
    token = _pratinjau(klien, ids, "kode_vendor", "V009").json()["token"]
    with sessionmaker(bind=eng, future=True)() as s:
        s.get(TiketBaris, ids[0]).kode_vendor = "V777"
        s.commit()
    r = klien.post("/api/intake/quick-fill/terapkan", json={"token": token})
    assert r.status_code == 409
    assert "berubah sejak pratinjau" in r.text


def test_batalkan_pratinjau(data):
    klien, _ = data
    ids = _ids(klien)[:1]
    token = _pratinjau(klien, ids, "bin", "B9").json()["token"]
    r = klien.delete(f"/api/intake/quick-fill/pratinjau/{token}")
    assert r.status_code == 200
    assert r.json()["status"] == "dibatalkan"
    assert klien.post("/api/intake/quick-fill/terapkan",
                      json={"token": token}).status_code == 404


def test_kosongkan_kolom_opsional(data):
    klien, eng = data
    ids = _ids(klien)[:2]
    token = _pratinjau(klien, ids, "bin", kosongkan=True).json()["token"]
    r = klien.post("/api/intake/quick-fill/terapkan", json={"token": token})
    assert r.status_code == 200, r.text
    with sessionmaker(bind=eng, future=True)() as s:
        assert all(s.get(TiketBaris, i).bin is None for i in ids)


def test_wet_nol_memperbarui_flag_tiket_nol(data):
    klien, eng = data
    ids = _ids(klien)[:2]
    token = _pratinjau(klien, ids, "wet_kg", "0").json()["token"]
    assert klien.post("/api/intake/quick-fill/terapkan",
                      json={"token": token}).status_code == 200
    with sessionmaker(bind=eng, future=True)() as s:
        assert all(s.get(TiketBaris, i).tiket_nol is True for i in ids)


def test_nilai_dan_kolom_tidak_valid(data):
    klien, _ = data
    ids = _ids(klien)[:2]
    assert _pratinjau(klien, ids, "drc_pct", "140").status_code == 422
    assert _pratinjau(klien, ids, "ticket_no", "X").status_code == 422
    assert _pratinjau(klien, ids, "kode_vendor", kosongkan=True).status_code == 422
    assert _pratinjau(klien, ids, "bin").status_code == 422
    assert klien.post("/api/intake/quick-fill/pratinjau", json={
        "ids": [], "kolom": "bin", "nilai": "B9"}).status_code == 422


def test_galat_wilayah_per_baris_tanpa_token(data):
    klien, eng = data
    ids = _ids(klien)
    r = _pratinjau(klien, ids, "desa", "DESA FIKTIF")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "ada_galat" and d["token"] is None
    assert d["galat"]
    with sessionmaker(bind=eng, future=True)() as s:
        assert all(s.get(TiketBaris, i).desa != "DESA FIKTIF" for i in ids)


def test_health_menyebut_fitur_quick_fill(data):
    klien, _ = data
    assert "intake-quick-fill" in klien.get("/api/health").json()["fitur"]


def test_quick_fill_hanya_admin(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("CF_ACCESS_AUD", raising=False)
    monkeypatch.delenv("AUTH_MODE", raising=False)
    eng = _engine()
    _isi(eng)
    klien = TestClient(buat_app(eng))
    assert klien.post("/api/auth/login", json={
        "username": "admin", "sandi": "admin123"}).status_code == 200
    assert klien.post("/api/auth/pengguna", json={
        "username": "pegawai", "nama": "Pegawai",
        "sandi": "pegawai123", "peran": "pengguna"}).status_code == 200
    assert klien.post("/api/auth/logout").status_code == 200
    assert klien.post("/api/auth/login", json={
        "username": "pegawai", "sandi": "pegawai123"}).status_code == 200
    ids = _ids(klien)
    r = _pratinjau(klien, ids, "kode_vendor", "V009")
    assert r.status_code == 403
    assert "Hanya admin" in r.text
