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

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import buat_app
from app.models import Base, TiketBaris, Vendor


def _engine():
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def _tiket(session, no, tanggal, vendor, dry_kg, line_seq=1, grade="SIR20",
           wet_kg=None, reject_kg=0, tiket_nol=False,
           provinsi="Sumatera Utara", kabupaten="Deli Serdang"):
    session.add(TiketBaris(
        ticket_no=no, line_seq=line_seq, ticket_date=tanggal,
        kode_vendor=vendor, item_code=grade,
        wet_kg=wet_kg if wet_kg is not None else dry_kg / 0.62,
        dry_kg=dry_kg, reject_kg=reject_kg,
        provinsi=provinsi, kabupaten=kabupaten, tiket_nol=tiket_nol))


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
