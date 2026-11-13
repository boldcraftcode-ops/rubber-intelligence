"""Tes kartu "Daftar intake terakhir" dan batas 12 bulan pada kartu KPI Reject.

Permintaan pemilik:
1. Di halaman Intake Analisis perlu daftar intake supaya kelihatan kapan
   intake terakhir masuk.
2. Kartu KPI Reject % hanya menampilkan 12 bulan, tidak seluruh riwayat.

Yang dijaga di sini:
- satu baris daftar = satu TIKET (baris line_seq dengan nomor tiket sama
  digabung, bukan ditampilkan berulang);
- urutan selalu dari yang paling baru, dan ringkasan `terakhir` sama dengan
  baris pertama daftar;
- `limit` membatasi jumlah baris, tapi `jumlah_tiket_total` tetap total;
- angka KPI reject dihitung dari bulan yang benar-benar ditampilkan, supaya
  ringkasan tidak bertentangan dengan tabel di bawahnya;
- `bulan=12` adalah bawaan, `bulan=0` mengembalikan semua bulan.
"""
import datetime as dt
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.traceability import (normalisasi_kabupaten,
                                   normalisasi_teks_wilayah)
from app.main import buat_app
from app.models import (Base, KoreksiWilayahTrace, ReferensiWilayahTrace,
                        TiketBaris, Vendor)

AKAR = Path(__file__).resolve().parents[2]


def _teks(rel: str) -> str:
    return (AKAR / rel).read_text(encoding="utf-8")


def _engine():
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def _tiket(session, no, tanggal, vendor, dry_kg, line_seq=1, grade="SIR20",
           wet_kg=None, reject_kg=0, tiket_nol=False,
           provinsi="Sumatera Utara", kabupaten="Deli Serdang",
           kecamatan="Kecamatan Contoh", desa="Desa Contoh",
           nama_vendor_asli=None, kabupaten_norm=None,
           kecamatan_norm=None, desa_norm=None):
    session.add(TiketBaris(
        ticket_no=no, line_seq=line_seq, ticket_date=tanggal,
        kode_vendor=vendor, nama_vendor_asli=nama_vendor_asli, item_code=grade,
        wet_kg=wet_kg if wet_kg is not None else dry_kg / 0.62,
        dry_kg=dry_kg, reject_kg=reject_kg,
        provinsi=provinsi, kabupaten=kabupaten,
        kecamatan=kecamatan, desa=desa,
        kabupaten_norm=kabupaten_norm or normalisasi_kabupaten(kabupaten),
        kecamatan_norm=kecamatan_norm or normalisasi_teks_wilayah(kecamatan),
        desa_norm=desa_norm or normalisasi_teks_wilayah(desa),
        tiket_nol=tiket_nol))


def _isi_intake(session):
    session.add_all([Vendor(kode="V001", nama_baku="PT Alpha"),
                     Vendor(kode="V002", nama_baku="PT Beta")])
    # tiket lama
    _tiket(session, "T001", dt.date(2026, 1, 5), "V001", 10_000)
    # tiket 2 baris (dua grade, satu kendaraan) -> harus jadi SATU baris daftar
    _tiket(session, "T002", dt.date(2026, 3, 10), "V001", 6_000,
           line_seq=1, grade="SIR20")
    _tiket(session, "T002", dt.date(2026, 3, 10), "V001", 4_000,
           line_seq=2, grade="SIR10")
    # tiket terbaru
    _tiket(session, "T003", dt.date(2026, 5, 20), "V002", 8_000,
           provinsi="Riau", kabupaten="Kampar")
    # tiket nol tidak boleh muncul di daftar intake
    _tiket(session, "T000", dt.date(2026, 6, 1), "V002", 99_000, tiket_nol=True)
    session.commit()


def _isi_reject(session):
    """30 bulan berurutan, Jan 2023 .. Jun 2025, reject 1% tiap bulan."""
    for i in range(30):
        tahun, bulan = 2023 + i // 12, i % 12 + 1
        _tiket(session, f"R{i:03d}", dt.date(tahun, bulan, 10), "V001",
               dry_kg=100_000, wet_kg=100_000, reject_kg=1_000)
    session.commit()


@pytest.fixture()
def klien_intake(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    with sessionmaker(bind=eng, future=True)() as s:
        _isi_intake(s)
    return TestClient(buat_app(eng))


@pytest.fixture()
def klien_intake_lengkap(monkeypatch):
    """Data + referensi SCDF untuk filter records dan breakdown wilayah."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    with sessionmaker(bind=eng, future=True)() as s:
        _isi_intake(s)
        s.add(Vendor(kode="V003", nama_baku="PT Gamma"))
        # Kode yang hanya ada di tiket belum terdaftar di Master Vendor.
        _tiket(s, "T004", dt.date(2026, 6, 1), "V999", 4_000,
               nama_vendor_asli="Toko Delta", provinsi="JAMBI",
               kabupaten="KABUPATEN BATANGHARI", kecamatan="KECAMATAN C",
               desa="DESA C")
        ref_sumatra = ReferensiWilayahTrace(
            provinsi_norm="SUMATERA UTARA", provinsi="Sumatera Utara",
            kabupaten_norm="DELI SERDANG",
            kecamatan_norm="KECAMATAN CONTOH", desa_norm="DESA CONTOH",
            kabupaten="Deli Serdang", kecamatan="Sinembah Tanjung Muda",
            desa="Durian Jangak")
        ref_kampar_lama = ReferensiWilayahTrace(
            provinsi_norm="RIAU", provinsi="Riau", kabupaten_norm="KAMPAR",
            kecamatan_norm="KECAMATAN CONTOH", desa_norm="DESA CONTOH",
            kabupaten="Kampar", kecamatan="Kecamatan Lama", desa="Desa Lama")
        ref_kampar_baru = ReferensiWilayahTrace(
            provinsi_norm="RIAU", provinsi="Riau", kabupaten_norm="KAMPAR",
            kecamatan_norm="KECAMATAN B", desa_norm="DESA B RESMI",
            kabupaten="Kampar", kecamatan="Kampar Kiri", desa="Desa B Resmi")
        s.add_all([ref_sumatra, ref_kampar_lama, ref_kampar_baru])
        s.flush()
        # Koreksi terkontrol mengalahkan padanan langsung untuk T003.
        s.add(KoreksiWilayahTrace(
            source_kabupaten_norm="KAMPAR",
            source_kecamatan_norm="KECAMATAN CONTOH",
            source_desa_norm="DESA CONTOH",
            target_ref_id=ref_kampar_baru.id))
        s.commit()
    return TestClient(buat_app(eng))


@pytest.fixture()
def klien_reject(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    with sessionmaker(bind=eng, future=True)() as s:
        _isi_reject(s)
    return TestClient(buat_app(eng))


# ============================================================ daftar intake
def _intake(klien, **params):
    r = klien.get("/api/kartu/intake-terakhir", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_intake_satu_baris_per_tiket(klien_intake):
    d = _intake(klien_intake)
    nomor = [b["ticket_no"] for b in d["baris"]]
    assert nomor == ["T003", "T002", "T001"]      # T002 tidak dobel
    t2 = next(b for b in d["baris"] if b["ticket_no"] == "T002")
    assert t2["dry_ton"] == pytest.approx(10.0)   # 6.000 + 4.000 kg
    assert t2["jumlah_baris"] == 2
    assert t2["grade"] == "SIR10, SIR20"          # digabung & diurut


def test_intake_urut_terbaru_dulu(klien_intake):
    d = _intake(klien_intake)
    assert [b["tanggal"] for b in d["baris"]] == ["2026-05-20", "2026-03-10",
                                                 "2026-01-05"]


def test_intake_ringkasan_terakhir_sama_dengan_baris_pertama(klien_intake):
    d = _intake(klien_intake)
    t = d["terakhir"]
    assert t["tanggal"] == d["baris"][0]["tanggal"] == "2026-05-20"
    assert t["ticket_no"] == "T003"
    assert t["label_vendor"] == "V002 — PT Beta"
    assert t["dry_ton"] == pytest.approx(8.0)
    assert t["jumlah_tiket_hari_itu"] == 1
    tanggal = dt.date.fromisoformat(t["tanggal"])
    assert t["umur_hari"] == (dt.date.today() - tanggal).days


def test_intake_tiket_nol_tidak_masuk_daftar(klien_intake):
    d = _intake(klien_intake)
    assert "T000" not in [b["ticket_no"] for b in d["baris"]]
    assert d["jumlah_tiket_total"] == 3
    assert d["tanggal_pertama"] == "2026-01-05"


def test_intake_limit_membatasi_baris_bukan_total(klien_intake):
    d = _intake(klien_intake, limit=2)
    assert len(d["baris"]) == 2
    assert d["jumlah_tiket_total"] == 3
    assert d["baris"][0]["ticket_no"] == "T003"


def test_intake_label_vendor_jatuh_ke_nama_asli(klien_intake):
    d = _intake(klien_intake)
    t1 = next(b for b in d["baris"] if b["kode_vendor"] == "V001")
    assert t1["label_vendor"] == "V001 — PT Alpha"


def test_intake_limit_tidak_sah_422(klien_intake):
    assert klien_intake.get("/api/kartu/intake-terakhir",
                            params={"limit": 0}).status_code == 422
    assert klien_intake.get("/api/kartu/intake-terakhir",
                            params={"limit": 201}).status_code == 422


def test_intake_ekspor_xlsx(klien_intake):
    r = klien_intake.get("/api/kartu/intake-terakhir",
                         params={"limit": 5, "format": "xlsx"})
    assert r.status_code == 200
    assert "intake_terakhir.xlsx" in r.headers["content-disposition"]


def test_intake_kosong_tidak_galat(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    klien = TestClient(buat_app(eng))
    d = klien.get("/api/kartu/intake-terakhir").json()
    assert d["baris"] == [] and d["terakhir"] is None
    assert d["jumlah_tiket_total"] == 0


# ============================================================ reject 12 bulan
def _reject(klien, **params):
    r = klien.get("/api/kartu/reject", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_reject_bawaan_hanya_12_bulan(klien_reject):
    d = _reject(klien_reject)
    assert d["bulan_ditampilkan"] == 12
    assert d["jumlah_bulan_tampil"] == 12
    assert d["jumlah_bulan_total"] == 30
    assert len(d["baris"]) == 12
    assert d["terpotong"] is True


def test_reject_bulan_terakhir_yang_ditampilkan(klien_reject):
    d = _reject(klien_reject)
    assert (d["baris"][0]["tahun"], d["baris"][0]["bulan"]) == (2024, 7)
    assert (d["baris"][-1]["tahun"], d["baris"][-1]["bulan"]) == (2025, 6)


def test_reject_kpi_periode_mengikuti_bulan_tampil(klien_reject):
    d = _reject(klien_reject)
    kp = d["kpi"]["kpi_periode"]
    assert kp["jumlah_bulan"] == 12
    assert kp["bulan_pertama"] == "2024-07"
    assert kp["bulan_terakhir"] == "2025-06"
    assert kp["wet_kg"] == pytest.approx(12 * 100_000)
    assert kp["reject_pct"] == pytest.approx(1.0)


def test_reject_bulan_0_semua(klien_reject):
    d = _reject(klien_reject, bulan=0)
    assert d["jumlah_bulan_tampil"] == 30
    assert len(d["baris"]) == 30
    assert d["terpotong"] is False


def test_reject_lima_bulan(klien_reject):
    d = _reject(klien_reject, bulan=5)
    assert len(d["baris"]) == 5
    assert d["kpi"]["kpi_periode"]["jumlah_bulan"] == 5


def test_reject_tidak_terpotong_bila_data_kurang(klien_intake):
    d = _reject(klien_intake)
    assert d["jumlah_bulan_total"] == 3      # Jan, Mar, Mei 2026
    assert d["jumlah_bulan_tampil"] == 3
    assert d["terpotong"] is False


def test_reject_bulan_tidak_sah_422(klien_reject):
    assert klien_reject.get("/api/kartu/reject",
                            params={"bulan": 121}).status_code == 422
    assert klien_reject.get("/api/kartu/reject",
                            params={"bulan": -1}).status_code == 422


def test_reject_filter_tahun_tetap_jalan(klien_reject):
    d = _reject(klien_reject, tahun=2025)
    assert d["jumlah_bulan_total"] == 6
    assert {b["tahun"] for b in d["baris"]} == {2025}


# ============================ breakdown wilayah & filter records
def test_opsi_intake_terakhir_master_plus_kode_tiket(klien_intake_lengkap):
    r = klien_intake_lengkap.get("/api/kartu/intake-terakhir/opsi")
    assert r.status_code == 200
    d = r.json()
    assert [p["kode"] for p in d["pilihan_vendor"]] == [
        "V001", "V002", "V003", "V999"]
    assert {p["kode"]: p["sumber"] for p in d["pilihan_vendor"]} == {
        "V001": "master", "V002": "master", "V003": "master",
        "V999": "tiket"}
    assert d["pilihan_vendor"][-1]["label"] == "V999 — Toko Delta"
    assert d["batas_data"] == {"tersedia": True, "dari": "2026-01-05",
                               "sampai": "2026-06-01"}


def test_intake_terakhir_empat_kolom_wilayah_dan_ejaan_scdf(
        klien_intake_lengkap):
    d = _intake(klien_intake_lengkap)
    assert d["jumlah_tiket_total"] == 4
    assert d["filter"] == {"dari": None, "sampai": None, "vendor": None,
                           "limit": 20}
    assert "tanpa menebak Provinsi" in d["catatan_wilayah"]
    assert [p["kode"] for p in d["pilihan_vendor"]] == [
        "V001", "V002", "V003", "V999"]

    t1 = next(b for b in d["baris"] if b["ticket_no"] == "T001")
    assert (t1["provinsi"], t1["kabupaten"], t1["kecamatan"],
            t1["desa"]) == ("Sumatera Utara", "Deli Serdang",
                            "Sinembah Tanjung Muda", "Durian Jangak")
    assert t1["sumber_wilayah"] == "SCDF"

    t3 = next(b for b in d["baris"] if b["ticket_no"] == "T003")
    # Koreksi terkontrol mengalahkan padanan langsung "Kecamatan Lama".
    assert (t3["provinsi"], t3["kabupaten"], t3["kecamatan"],
            t3["desa"]) == ("Riau", "Kampar", "Kampar Kiri", "Desa B Resmi")
    assert t3["sumber_wilayah"] == "SCDF"

    t4 = next(b for b in d["baris"] if b["ticket_no"] == "T004")
    # Tanpa padanan pasti: nilai tiket apa adanya, Provinsi tidak ditebak.
    assert (t4["provinsi"], t4["kabupaten"], t4["kecamatan"],
            t4["desa"]) == ("JAMBI", "KABUPATEN BATANGHARI",
                            "KECAMATAN C", "DESA C")
    assert t4["sumber_wilayah"] == "intake"
    assert d["terakhir"]["ticket_no"] == "T004"
    assert d["terakhir"]["desa"] == "DESA C"
    assert d["terakhir"]["sumber_wilayah"] == "intake"


def test_intake_terakhir_filter_vendor_dan_periode_mengikat_semua_output(
        klien_intake_lengkap):
    d = _intake(klien_intake_lengkap, vendor="v001",
                dari="2026-03-01", sampai="2026-03-31")
    assert d["filter"] == {"dari": "2026-03-01", "sampai": "2026-03-31",
                           "vendor": "V001", "limit": 20}
    assert [b["ticket_no"] for b in d["baris"]] == ["T002"]
    assert d["jumlah_tiket_total"] == 1
    assert d["tanggal_pertama"] == "2026-03-10"
    assert d["terakhir"]["ticket_no"] == "T002"
    assert d["terakhir"]["provinsi"] == "Sumatera Utara"
    # Dropdown tidak ikut menyusut saat periode/vendor berubah.
    assert [p["kode"] for p in d["pilihan_vendor"]] == [
        "V001", "V002", "V003", "V999"]
    assert d["batas_data"]["tersedia"] is True


def test_intake_terakhir_filter_vendor_kode_khusus_tiket(
        klien_intake_lengkap):
    d = _intake(klien_intake_lengkap, vendor="V999")
    assert [b["ticket_no"] for b in d["baris"]] == ["T004"]
    assert d["terakhir"]["label_vendor"] == "Toko Delta"


def test_intake_terakhir_filter_periode_saja(klien_intake_lengkap):
    d = _intake(klien_intake_lengkap, dari="2026-05-01",
                sampai="2026-05-31")
    assert [b["ticket_no"] for b in d["baris"]] == ["T003"]
    assert d["terakhir"]["ticket_no"] == "T003"


def test_intake_terakhir_xlsx_empat_kolom_mengikuti_filter(
        klien_intake_lengkap):
    r = klien_intake_lengkap.get(
        "/api/kartu/intake-terakhir",
        params={"format": "xlsx", "vendor": "V001",
                "dari": "2026-03-01", "sampai": "2026-03-31"})
    assert r.status_code == 200
    assert "intake_terakhir.xlsx" in r.headers["content-disposition"]
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws.max_column == 12
    assert [c.value for c in ws[1]][-4:] == [
        "Provinsi", "Kabupaten/Kota", "Kecamatan", "Desa"]
    assert ws.max_row == 2
    assert ws.cell(row=2, column=2).value == "T002"
    assert ws.cell(row=2, column=9).value == "Sumatera Utara"
    assert ws.cell(row=2, column=10).value == "Deli Serdang"


def test_intake_terakhir_filter_tidak_sah_422(klien_intake_lengkap):
    k = klien_intake_lengkap
    assert k.get("/api/kartu/intake-terakhir",
                 params={"vendor": "NOPE"}).status_code == 422
    assert k.get("/api/kartu/intake-terakhir",
                 params={"dari": "2026-05-20",
                         "sampai": "2026-01-01"}).status_code == 422
    assert k.get("/api/kartu/intake-terakhir",
                 params={"dari": "2026/01/01"}).status_code == 422
    assert k.get("/api/kartu/intake-terakhir",
                 params={"dari": "1900-01-01",
                         "sampai": "2026-11-01"}).status_code == 422


def test_intake_terakhir_opsi_saat_database_kosong(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    klien = TestClient(buat_app(_engine()))
    d = klien.get("/api/kartu/intake-terakhir/opsi").json()
    assert d["pilihan_vendor"] == []
    assert d["batas_data"] == {"tersedia": False, "dari": None,
                               "sampai": None}


def test_sumber_ui_intake_terakhir_breakdown_dan_filter():
    s = _teks("frontend/src/pages/Analisis.tsx")
    blok = s[s.index("export function KartuIntakeTerakhir()"):
             s.index("/* ---------- reject%")]
    assert 'idMetrik="daftar_intake_terakhir"' in blok
    assert 'data-uji="filter-intake-terakhir"' in blok
    assert 'data-uji="tabel-intake-terakhir"' in blok
    for label in ("Provinsi", "Kabupaten/Kota", "Kecamatan", "Desa"):
        assert f">{label}<" in blok
    assert "const wilayah = [b.kabupaten" not in blok
    assert ">Wilayah</th>" not in blok
    assert "params.set(\"limit\", String(limit))" in blok
    assert "params.set(\"dari\", dari)" in blok
    assert "params.set(\"sampai\", sampai)" in blok
    assert "params.set(\"vendor\", vendor)" in blok
    assert 'queryKey: ["intake-terakhir-opsi"]' in blok
    assert "/api/kartu/intake-terakhir/opsi" in blok
    assert "Semua vendor" in blok
    assert "Periode records" in blok
    assert "PilihRentangTanggal" in blok
    assert "TombolRefreshKartu" in blok
    assert "colSpan={11}" in blok
    assert "b.sumber_wilayah" in blok
    assert "b.provinsi" in blok and "b.kabupaten" in blok
    assert "b.kecamatan" in blok and "b.desa" in blok
    assert "urlEkspor={url}" in blok
    assert "qsJelaskan={qsJelaskan}" in blok
    assert "keterangan=\"Laporan tiga tabel" not in blok


def test_sumber_backend_dan_dokumentasi_intake_terakhir():
    api = _teks("backend/app/api_analisis.py")
    assert '@router.get("/kartu/intake-terakhir/opsi")' in api
    assert "def _opsi_intake_terakhir(" in api
    assert "def _peta_wilayah_scdf(" in api
    assert "CATATAN_WILAYAH_INTAKE_TERAKHIR" in api
    assert '"Kabupaten/Kota", "Kecamatan", "Desa"' in api
    assert "func.upper(func.trim(" in api

    health = _teks("backend/app/main.py")
    assert '"kartu-intake-terakhir-wilayah-vendor-periode"' in health

    metrik = _teks("backend/semantic/metrics.yaml")
    assert "daftar_intake_terakhir:" in metrik
    assert "Provinsi, Kabupaten/Kota, Kecamatan, dan Desa" in metrik

    cara = _teks("docs/CARA_MENJALANKAN.md")
    assert "## 3p. Daftar intake terakhir" in cara
    assert "GET /api/kartu/intake-terakhir/opsi" in cara
    serah = _teks("docs/SERAH_TERIMA.md")
    assert "Breakdown wilayah mengikuti SCDF" in serah
    assert "Periode records" in serah

    kamus = _teks("frontend/src/i18n.tsx")
    assert '"Kabupaten/Kota": "Regency/City"' in kamus
    assert '"Periode records": "Record period"' in kamus
