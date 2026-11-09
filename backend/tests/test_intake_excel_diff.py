"""Alur Excel diff pada Data Intake Details: unduh → pratinjau → konfirmasi.

Pratinjau tidak menyimpan apa pun. Konfirmasi memakai token sekali pakai,
admin-only, dan menyimpan semua perubahan dalam satu transaksi dengan audit
per baris. Sumber identitas tiket tidak ikut diubah.
"""
from __future__ import annotations

import datetime as dt
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api_intake import _KOLOM_UBAH, _LABEL_EXCEL
from app.main import buat_app
from app.models import AuditLog, Base, ReferensiWilayahTrace, TiketBaris

MEDIA_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADER = ["ID", "Ticket No", "Baris"] + [_LABEL_EXCEL[k] for k in _KOLOM_UBAH]
KUNCI_HEADER = {"ID": "id", "Ticket No": "ticket_no", "Baris": "line_seq"}
KUNCI_HEADER.update({_LABEL_EXCEL[k]: k for k in _KOLOM_UBAH})


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
                       nama_vendor_asli="CV Alpha", vehicle_no="B 1",
                       item_code="SLAB2", wet_kg=100, sample_kg=10,
                       reject_kg=2, drc_pct=62, dry_kg=62, bin="B1",
                       location="L1", peringatan="W1",
                       asal_getah="SUMUT_MANDAILING NATAL_SIPIROK_HUTA RAJA",
                       source_fingerprint="fp-001",
                       provinsi="SUMATERA UTARA", kabupaten="MANDAILING NATAL",
                       kecamatan="DISTRIK LAMA", desa="HUTA RAJA",
                       kabupaten_norm="MANDAILING NATAL",
                       kecamatan_norm="DISTRIK LAMA", desa_norm="HUTA RAJA",
                       asal_getah_valid=True, tiket_nol=False),
            TiketBaris(ticket_no="T-002", line_seq=1,
                       ticket_date=dt.date(2026, 3, 2), kode_vendor="V002",
                       nama_vendor_asli="PT Beta", vehicle_no="B 2",
                       item_code="SLAB2", wet_kg=200, sample_kg=20,
                       reject_kg=4, drc_pct=62, dry_kg=124, bin="B2",
                       location="L2", peringatan="W2",
                       asal_getah="RIAU_KAMPAR_BANGKINANG_AIR TIRIS",
                       source_fingerprint="fp-002",
                       provinsi="RIAU", kabupaten="KAMPAR",
                       kecamatan="BANGKINANG", desa="AIR TIRIS",
                       asal_getah_valid=True, tiket_nol=False),
            TiketBaris(ticket_no="T-003", line_seq=1,
                       ticket_date=dt.date(2026, 3, 3), kode_vendor="V003",
                       nama_vendor_asli="CV Gamma", vehicle_no="B 3",
                       item_code="SLAB2", wet_kg=150, sample_kg=15,
                       reject_kg=3, drc_pct=62, dry_kg=93, bin="B3",
                       location="L3", peringatan="W3",
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


def _buku(headers, rows) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Koreksi"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _rekaman(klien):
    r = klien.get("/api/intake", params={"tahun": 2026})
    assert r.status_code == 200, r.text
    hasil = []
    for b in sorted(r.json()["baris"], key=lambda x: x["ticket_no"]):
        rek = {"id": b["id"], "ticket_no": b["ticket_no"], "line_seq": b["line_seq"]}
        rek.update({k: b[k] for k in _KOLOM_UBAH})
        hasil.append(rek)
    return hasil


def _xlsx_rekaman(rekaman, headers=HEADER) -> bytes:
    return _buku(headers, [[rek.get(KUNCI_HEADER.get(h)) for h in headers]
                           for rek in rekaman])


def _unggah(klien, isi, nama="koreksi.xlsx"):
    return klien.post("/api/intake/excel-diff/pratinjau",
                      files={"file": (nama, isi, MEDIA_XLSX)})


def test_template_berisi_baris_filter_dan_template_kosong(data):
    klien, _ = data
    r = klien.get("/api/intake/excel-diff/template", params={"tahun": 2026})
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True, data_only=True)
    ws = wb["Koreksi"]
    assert ws.max_row == 4  # header + 3 baris
    assert [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))][:3] == [
        "ID", "Ticket No", "Baris"]
    wb.close()

    kosong = klien.get("/api/intake/excel-diff/template", params={"kosong": "true"})
    assert kosong.status_code == 200
    wb2 = openpyxl.load_workbook(io.BytesIO(kosong.content), read_only=True, data_only=True)
    assert wb2["Koreksi"].max_row == 1
    wb2.close()

    assert klien.get("/api/intake/excel-diff/template").status_code == 422


def test_pratinjau_tidak_mengubah_data(data):
    klien, eng = data
    rekaman = _rekaman(klien)
    rekaman[0]["kode_vendor"] = "V009"
    rekaman[0]["wet_kg"] = 111
    rekaman[1]["bin"] = "B9"
    rekaman[2]["location"] = "L9"
    r = _unggah(klien, _xlsx_rekaman(rekaman))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "siap" and d["token"]
    assert d["jumlah"] == 3 and d["berubah"] == 3 and d["jumlah_perubahan"] == 4
    assert d["nama_file"] == "koreksi.xlsx"
    kolom = {p["kolom"] for b in d["baris"] for p in b["perubahan"]}
    assert kolom == {"kode_vendor", "wet_kg", "bin", "location"}
    with sessionmaker(bind=eng, future=True)() as s:
        assert s.get(TiketBaris, rekaman[0]["id"]).kode_vendor == "V001"
        assert s.scalar(select(AuditLog.id).where(AuditLog.aksi == "ubah_massal").limit(1)) is None


def test_terapkan_menyimpan_semua_dan_audit_sumber_excel(data):
    klien, eng = data
    rekaman = _rekaman(klien)
    with sessionmaker(bind=eng, future=True)() as s:
        identitas = {
            r.id: (r.ticket_no, r.line_seq, r.asal_getah,
                   r.source_fingerprint, r.peringatan)
            for r in s.scalars(select(TiketBaris))
        }
    rekaman[0]["kode_vendor"] = " v009 "
    rekaman[0]["wet_kg"] = 111
    rekaman[1]["bin"] = "B9"
    rekaman[2]["location"] = "L9"
    token = _unggah(klien, _xlsx_rekaman(rekaman)).json()["token"]
    r = klien.post("/api/intake/excel-diff/terapkan", json={"token": token})
    assert r.status_code == 200, r.text
    assert r.json()["jumlah"] == 3 and r.json()["jumlah_perubahan"] == 4

    with sessionmaker(bind=eng, future=True)() as s:
        for row_id, lama in identitas.items():
            row = s.get(TiketBaris, row_id)
            assert (row.ticket_no, row.line_seq, row.asal_getah,
                    row.source_fingerprint, row.peringatan) == lama
        assert s.get(TiketBaris, rekaman[0]["id"]).kode_vendor == "V009"
        assert float(s.get(TiketBaris, rekaman[0]["id"]).wet_kg) == 111
        assert s.get(TiketBaris, rekaman[1]["id"]).bin == "B9"
        assert s.get(TiketBaris, rekaman[2]["id"]).location == "L9"
        audit = list(s.scalars(select(AuditLog).where(
            AuditLog.objek == "intake_tiket", AuditLog.aksi == "ubah_massal")))
        assert len(audit) == 3
        assert all('"sumber": "excel"' in a.detail for a in audit)
    assert klien.post("/api/intake/excel-diff/terapkan",
                      json={"token": token}).status_code == 404


def test_status_kosong_saat_tidak_ada_nilai_berubah(data):
    klien, _ = data
    r = _unggah(klien, _xlsx_rekaman(_rekaman(klien)))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "kosong" and d["token"] is None
    assert d["jumlah_perubahan"] == 0


def test_galat_validasi_per_baris_tanpa_token(data):
    klien, eng = data
    rekaman = _rekaman(klien)
    rekaman[0]["drc_pct"] = 140
    r = _unggah(klien, _xlsx_rekaman(rekaman))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "ada_galat" and d["token"] is None
    assert d["galat"]
    with sessionmaker(bind=eng, future=True)() as s:
        assert s.get(TiketBaris, rekaman[0]["id"]).drc_pct == 62


def test_galat_scdf_desa_tanpa_token(data):
    klien, eng = data
    rekaman = _rekaman(klien)
    rekaman[1]["desa"] = "DESA FIKTIF"
    r = _unggah(klien, _xlsx_rekaman(rekaman))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "ada_galat" and d["token"] is None
    with sessionmaker(bind=eng, future=True)() as s:
        assert s.get(TiketBaris, rekaman[1]["id"]).desa != "DESA FIKTIF"


def test_data_berubah_sejak_pratinjau_ditolak_dan_token_habis(data):
    klien, eng = data
    rekaman = _rekaman(klien)
    rekaman[0]["bin"] = "B9"
    token = _unggah(klien, _xlsx_rekaman(rekaman)).json()["token"]
    with sessionmaker(bind=eng, future=True)() as s:
        s.get(TiketBaris, rekaman[0]["id"]).bin = "B777"
        s.commit()
    r = klien.post("/api/intake/excel-diff/terapkan", json={"token": token})
    assert r.status_code == 409
    assert "berubah sejak pratinjau" in r.text
    assert klien.post("/api/intake/excel-diff/terapkan",
                      json={"token": token}).status_code == 404


def test_batalkan_pratinjau(data):
    klien, _ = data
    rekaman = _rekaman(klien)
    rekaman[0]["bin"] = "B9"
    token = _unggah(klien, _xlsx_rekaman(rekaman)).json()["token"]
    r = klien.delete(f"/api/intake/excel-diff/pratinjau/{token}")
    assert r.status_code == 200
    assert r.json()["status"] == "dibatalkan"
    assert klien.post("/api/intake/excel-diff/terapkan",
                      json={"token": token}).status_code == 404


def test_wet_nol_memperbarui_flag_tiket_nol(data):
    klien, eng = data
    rekaman = _rekaman(klien)
    rekaman[0]["wet_kg"] = 0
    token = _unggah(klien, _xlsx_rekaman(rekaman)).json()["token"]
    assert klien.post("/api/intake/excel-diff/terapkan",
                      json={"token": token}).status_code == 200
    with sessionmaker(bind=eng, future=True)() as s:
        assert s.get(TiketBaris, rekaman[0]["id"]).tiket_nol is True


def test_file_tidak_valid_ditolak(data):
    klien, _ = data
    ids = [r["id"] for r in _rekaman(klien)]
    assert _unggah(klien, b"bukan excel", "koreksi.txt").status_code == 422
    assert _unggah(klien, b"", "koreksi.xlsx").status_code == 422
    assert klien.post("/api/intake/excel-diff/pratinjau", files={
        "file": ("koreksi.xlsx", _buku(["Bin"], [["B9"]]), MEDIA_XLSX),
    }).status_code == 422  # tanpa ID
    assert klien.post("/api/intake/excel-diff/pratinjau", files={
        "file": ("koreksi.xlsx", _buku(["ID", "Bin", "Kolom Aneh"],
                                       [[ids[0], "B9", "X"]]), MEDIA_XLSX),
    }).status_code == 422  # kolom asing
    assert klien.post("/api/intake/excel-diff/pratinjau", files={
        "file": ("koreksi.xlsx", _buku(["ID", "Bin"],
                                       [[i, "B9"] for i in range(1, 502)]), MEDIA_XLSX),
    }).status_code == 422  # lebih dari 500 baris


def test_id_duplikat_dan_identitas_tidak_cocok(data):
    klien, _ = data
    ids = [r["id"] for r in _rekaman(klien)]
    duplikat = klien.post("/api/intake/excel-diff/pratinjau", files={
        "file": ("koreksi.xlsx", _buku(["ID", "Bin"], [[ids[0], "B9"], [ids[0], "B8"]]), MEDIA_XLSX),
    })
    assert duplikat.status_code == 200
    assert duplikat.json()["status"] == "ada_galat"
    assert any("lebih dari sekali" in g["alasan"] for g in duplikat.json()["galat"])

    salah = klien.post("/api/intake/excel-diff/pratinjau", files={
        "file": ("koreksi.xlsx", _buku(["ID", "Ticket No", "Baris", "Bin"],
                                       [[ids[0], "SALAH", 1, "B9"]]), MEDIA_XLSX),
    })
    assert salah.status_code == 200
    assert salah.json()["status"] == "ada_galat"
    assert any("tidak cocok" in g["alasan"] for g in salah.json()["galat"])


def test_health_menyebut_fitur_excel_diff(data):
    klien, _ = data
    assert "intake-excel-diff" in klien.get("/api/health").json()["fitur"]


def test_excel_diff_hanya_admin(monkeypatch):
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
    r = klien.post("/api/intake/excel-diff/pratinjau", files={
        "file": ("koreksi.xlsx", _buku(["ID", "Bin"], [[1, "B9"]]), MEDIA_XLSX),
    })
    assert r.status_code == 403
    assert "Hanya admin" in r.text
