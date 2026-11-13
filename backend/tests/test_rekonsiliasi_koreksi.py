"""Revisi terkontrol pada halaman Rekonsiliasi.

Yang dijaga:
- dua kartu (selisih diketahui + pemeriksaan harian) memberi pilihan sumber;
- keputusan menutup selisih efektif, tetapi data sumber asli tidak berubah;
- keputusan bulanan Jul/Agu 2026 juga menentukan intake di kartu
  `RM Stock – Intake vs Pricing` dan menjernihkan alarm;
- hanya admin yang boleh menyimpan/membatalkan;
- keputusan bisa diubah, dibatalkan, dan tercatat di audit log.
"""
from __future__ import annotations

import datetime as dt
import io
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.alarm import evaluasi_alarm
from app.main import buat_app
from app.importer.template import impor_template
from app.models import (AuditLog, Base, KoreksiRekonsiliasi, Pembelian,
                        TiketBaris)

TEMPLATE = (Path(__file__).resolve().parents[2] / "sample_data" /
            "Template_dan_Data_Awal_OP_Margin_v3.xlsx")
TANGGAL = dt.date(2019, 12, 31)
KUNCI_HARIAN = TANGGAL.isoformat()


@pytest.fixture(scope="module")
def klien(tmp_path_factory):
    """Database templat terpisah supaya tes ini tidak mengotori fixture bersama."""
    db = tmp_path_factory.mktemp("rekonsiliasi") / "rek.db"
    eng = create_engine(f"sqlite:///{db}", future=True)
    Base.metadata.create_all(eng)
    Sesi = sessionmaker(bind=eng, future=True)
    with Sesi() as s:
        impor_template(str(TEMPLATE), s, pengunggah="pytest")
    dengan_klien = TestClient(buat_app(eng))
    return dengan_klien, Sesi


@pytest.fixture(autouse=True)
def bersih(klien):
    """Satu baris harian berselisih + bersihkan keputusan sebelum/sesudah tes."""
    _, Sesi = klien

    def _siapkan():
        with Sesi() as s:
            s.execute(delete(KoreksiRekonsiliasi))
            s.execute(delete(TiketBaris).where(
                TiketBaris.ticket_no.like("TEST-REK-%")))
            s.execute(delete(Pembelian).where(Pembelian.tanggal == TANGGAL))
            s.add(TiketBaris(
                ticket_no="TEST-REK-1", line_seq=1, ticket_date=TANGGAL,
                kode_vendor="VTEST", wet_kg=Decimal("2000"), drc_pct=50.0,
                dry_kg=Decimal("1000"), tiket_nol=False))
            s.add(Pembelian(
                tanggal=TANGGAL, item_code="ALL", kode_vendor="", ticket_no="",
                qty_kering_kg=Decimal("800"), amount_rp=Decimal("1000000")))
            s.commit()
            evaluasi_alarm(s)
            s.commit()

    _siapkan()
    yield
    _siapkan()


def _harian(k, kunci=KUNCI_HARIAN):
    data = k.get("/api/rekonsiliasi").json()
    return next(h for h in data["harian"] if h["kunci"] == kunci)


def _diketahui(k, kunci):
    data = k.get("/api/rekonsiliasi").json()
    return next(d for d in data["diketahui"] if d["kunci"] == kunci)


def _baris_elemen(k, label):
    data = k.get("/api/ringkasan-elemen").json()
    return next(b for b in data["baris"] if b["label"] == label)


def test_get_menyediakan_pilihan_sumber_dan_status_awal(klien):
    k, _ = klien
    r = k.get("/api/rekonsiliasi")
    assert r.status_code == 200
    data = r.json()
    assert data["bisa_revisi"] is True

    jul = _diketahui(k, "2026-07")
    assert jul["selisih_ton"] == 19.453  # nilai lama tetap dipertahankan
    assert jul["selisih_efektif_ton"] == 19.453
    assert "persetujuan" in jul["status"]
    assert jul["direvisi"] is False
    assert [o["kode"] for o in jul["pilihan_sumber"]] == ["tiket", "excel"]

    h = _harian(k)
    assert h["selisih_kg"] == 200.0
    assert h["selisih_efektif_kg"] == 200.0
    assert h["cocok"] is False and h["cocok_asli"] is False
    assert [o["kode"] for o in h["pilihan_sumber"]] == ["tiket", "pembelian"]


def test_keputusan_harian_menutup_selisih_tanpa_mengubah_data_sumber(klien):
    k, Sesi = klien
    r = k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "harian", "kunci": KUNCI_HARIAN,
        "sumber_benar": "pembelian", "alasan": "Sesuai buku pembelian",
    })
    assert r.status_code == 200, r.text
    assert r.json()["nilai_dipakai"] == 800.0

    h = _harian(k)
    assert h["direvisi"] is True
    assert h["sumber_dipakai"] == "pembelian"
    assert h["nilai_dipakai_kg"] == 800.0
    assert h["selisih_kg"] == 200.0            # selisih asli tetap transparan
    assert h["selisih_efektif_kg"] == 0.0
    assert h["cocok"] is True
    assert "Qty pembelian" in h["status"]
    assert h["koreksi"]["alasan"] == "Sesuai buku pembelian"

    with Sesi() as s:  # data transaksi tidak boleh berubah
        t = s.scalar(select(TiketBaris).where(
            TiketBaris.ticket_no == "TEST-REK-1"))
        p = s.scalar(select(Pembelian).where(Pembelian.tanggal == TANGGAL))
        assert float(t.dry_kg) == 1000.0
        assert float(p.qty_kering_kg) == 800.0
        assert s.scalar(select(AuditLog).where(
            AuditLog.objek == "rekonsiliasi_koreksi").limit(1)) is not None


def test_keputusan_bisa_diubah_dan_dibatalkan(klien):
    k, Sesi = klien
    assert k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "harian", "kunci": KUNCI_HARIAN,
        "sumber_benar": "tiket",
    }).status_code == 200
    assert _harian(k)["nilai_dipakai_kg"] == 1000.0

    ubah = k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "harian", "kunci": KUNCI_HARIAN,
        "sumber_benar": "pembelian", "alasan": "Koreksi buku",
    })
    assert ubah.status_code == 200
    assert ubah.json()["status"] == "tersimpan"
    assert _harian(k)["nilai_dipakai_kg"] == 800.0

    hapus = k.delete("/api/rekonsiliasi/keputusan", params={
        "jenis": "harian", "kunci": KUNCI_HARIAN})
    assert hapus.status_code == 200
    h = _harian(k)
    assert h["direvisi"] is False
    assert h["selisih_efektif_kg"] == 200.0
    assert h["cocok"] is False

    with Sesi() as s:
        aksi = [a.aksi for a in s.scalars(select(AuditLog).where(
            AuditLog.objek == "rekonsiliasi_koreksi"))]
        assert {"tambah", "ubah", "hapus"} <= set(aksi)


def test_keputusan_bulanan_mengubah_intake_dan_alarm(klien):
    k, _ = klien
    sebelum = _baris_elemen(k, "Agu-26")
    assert sebelum["intake_ton"] == 4759.827
    assert "tiket" in sebelum["sumber_intake"]
    pesan_awal = [a["pesan"] for a in k.get("/api/alarm").json()["alarm"]]
    assert any("Agustus 2026" in p for p in pesan_awal)

    r = k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "diketahui", "kunci": "2026-08",
        "sumber_benar": "excel", "alasan": "Excel sudah diverifikasi",
    })
    assert r.status_code == 200, r.text
    d = _diketahui(k, "2026-08")
    assert d["selisih_ton"] == 6.878             # tes lama tetap aman
    assert d["selisih_efektif_ton"] == 0.0
    assert d["nilai_dipakai_ton"] == 4752.949
    assert "Excel lama" in d["status"]
    assert d["direvisi"] is True

    sesudah = _baris_elemen(k, "Agu-26")
    assert sesudah["intake_ton"] == 4752.949
    assert "excel" in sesudah["sumber_intake"]
    pesan = [a["pesan"] for a in k.get("/api/alarm").json()["alarm"]]
    assert not any("Agustus 2026" in p for p in pesan)
    assert any("Juli 2026" in p for p in pesan)  # bulan lain belum direvisi

    assert k.delete("/api/rekonsiliasi/keputusan", params={
        "jenis": "diketahui", "kunci": "2026-08"}).status_code == 200
    assert _baris_elemen(k, "Agu-26")["intake_ton"] == 4759.827


def test_validasi_sumber_kunci_dan_baris_sudah_cocok(klien):
    k, Sesi = klien
    assert k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "harian", "kunci": KUNCI_HARIAN,
        "sumber_benar": "excel"}).status_code == 422
    assert k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "diketahui", "kunci": "2026-08",
        "sumber_benar": "pembelian"}).status_code == 422
    assert k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "diketahui", "kunci": "2026-09",
        "sumber_benar": "tiket"}).status_code == 422
    assert k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "harian", "kunci": "2026-02-30",
        "sumber_benar": "tiket"}).status_code == 422
    assert k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "harian", "kunci": "2020-01-01",
        "sumber_benar": "tiket"}).status_code == 422

    cocok = dt.date(2019, 12, 30)
    with Sesi() as s:
        s.add(TiketBaris(
            ticket_no="TEST-REK-COCOK", line_seq=1, ticket_date=cocok,
            kode_vendor="VTEST", wet_kg=Decimal("1000"), drc_pct=50.0,
            dry_kg=Decimal("500"), tiket_nol=False))
        s.add(Pembelian(
            tanggal=cocok, item_code="ALL", kode_vendor="", ticket_no="",
            qty_kering_kg=Decimal("500"), amount_rp=Decimal("500000")))
        s.commit()
    try:
        r = k.post("/api/rekonsiliasi/keputusan", json={
            "jenis": "harian", "kunci": cocok.isoformat(),
            "sumber_benar": "tiket"})
        assert r.status_code == 422
        assert "sudah cocok" in r.json()["detail"]
    finally:
        with Sesi() as s:
            s.execute(delete(TiketBaris).where(
                TiketBaris.ticket_no == "TEST-REK-COCOK"))
            s.execute(delete(Pembelian).where(Pembelian.tanggal == cocok))
            s.commit()


def test_pengguna_bukan_admin_tidak_bisa_menyimpan(monkeypatch, klien):
    k, _ = klien
    monkeypatch.setattr("app.auth_lokal.info_pengguna",
                        lambda request: {"sub": "pegawai", "peran": "pengguna"})
    assert k.get("/api/rekonsiliasi").json()["bisa_revisi"] is False
    assert k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "diketahui", "kunci": "2026-07",
        "sumber_benar": "tiket"}).status_code == 403
    assert k.delete("/api/rekonsiliasi/keputusan", params={
        "jenis": "diketahui", "kunci": "2026-07"}).status_code == 403


def test_ekspor_xlsx_memuat_keputusan(klien):
    k, _ = klien
    assert k.post("/api/rekonsiliasi/keputusan", json={
        "jenis": "diketahui", "kunci": "2026-08",
        "sumber_benar": "excel"}).status_code == 200
    r = k.get("/api/rekonsiliasi?format=xlsx")
    assert r.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    ws = wb.active
    judul = [c.value for c in ws[1]]
    assert "Sumber dipakai" in judul
    assert "Selisih setelah revisi (ton)" in judul
    baris_agu = next(row for row in ws.iter_rows(min_row=2, values_only=True)
                     if row[0] == "Agustus 2026")
    assert baris_agu[judul.index("Sumber dipakai")] == "excel"
    assert baris_agu[judul.index("Selisih setelah revisi (ton)")] == 0
