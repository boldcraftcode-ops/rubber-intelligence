"""Crosswalk Provinsi resmi untuk ID_AUX/SCDF.

Sumber Provinsi bukan nilai intake: `kabupaten_norm` pada `traceability_wilayah`
dihubungkan ke Kepmendagri lewat CSV yang dapat diaudit. Backfill bersifat
idempoten dan tidak menimpa nilai yang sudah ada.
"""
from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import api_traceability
from app.api_intake import _KOLOM_UBAH, _LABEL_EXCEL
from app.api_traceability import (NAMA_FILE_CROSSWALK, baca_crosswalk_provinsi,
                                  kabupaten_memiliki_provinsi,
                                  muat_referensi_bawaan,
                                  terapkan_crosswalk_provinsi)
from app.main import buat_app
from app.models import Base, ReferensiWilayahTrace, TiketBaris

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


def _tiket(no: str, urutan: int, tanggal: dt.date, vendor: str, nama: str,
           provinsi: str, kabupaten: str, kecamatan: str, desa: str,
           **norm) -> TiketBaris:
    return TiketBaris(
        ticket_no=no, line_seq=1, ticket_date=tanggal, kode_vendor=vendor,
        nama_vendor_asli=nama, item_code="SLAB2", wet_kg=100, dry_kg=62,
        drc_pct=62, provinsi=provinsi, kabupaten=kabupaten,
        kecamatan=kecamatan, desa=desa,
        kabupaten_norm=norm.get("kabupaten_norm", kabupaten),
        kecamatan_norm=norm.get("kecamatan_norm", kecamatan),
        desa_norm=norm.get("desa_norm", desa),
        asal_getah_valid=True, tiket_nol=False)


def _isi_crosswalk(eng, dengan_crosswalk: bool = True):
    p = "SUMATERA UTARA" if dengan_crosswalk else None
    r = "RIAU" if dengan_crosswalk else None
    with Session(eng) as s:
        s.add_all([
            ReferensiWilayahTrace(
                provinsi_norm=p, provinsi=p,
                kabupaten_norm="MANDAILING NATAL", kecamatan_norm="SIPIROK",
                desa_norm="HUTA RAJA BARU", kabupaten="Mandailing Natal",
                kecamatan="Sipirok", desa="Huta Raja Baru", code=None),
            ReferensiWilayahTrace(
                provinsi_norm=r, provinsi=r,
                kabupaten_norm="KAMPAR", kecamatan_norm="BANGKINANG",
                desa_norm="AIR TIRIS", kabupaten="Kampar",
                kecamatan="Bangkinang", desa="Air Tiris", code=None),
            # Sengaja tanpa pemetaan resmi: BANJAR ambigu di sumber Kemendagri.
            ReferensiWilayahTrace(
                provinsi_norm=None, provinsi=None,
                kabupaten_norm="BANJAR", kecamatan_norm="SUNGAI TABUK",
                desa_norm="SUNGAI TABUK", kabupaten="Banjar",
                kecamatan="Sungai Tabuk", desa="Sungai Tabuk", code=None),
        ])
        s.add_all([
            _tiket("T-001", 1, dt.date(2026, 3, 1), "V001", "CV Alpha",
                   "SUMATERA UTARA", "MANDAILING NATAL", "SIPIROK",
                   "HUTA RAJA BARU"),
            # Provinsi lama salah; koreksi harus memakai crosswalk, bukan intake.
            _tiket("T-002", 1, dt.date(2026, 3, 2), "V002", "PT Beta",
                   "ACEH", "MANDAILING NATAL", "SIPIROK", "HUTA RAJA BARU"),
            _tiket("T-003", 1, dt.date(2026, 3, 3), "V003", "CV Gamma",
                   "RIAU", "KAMPAR", "BANGKINANG", "AIR TIRIS"),
            _tiket("T-004", 1, dt.date(2026, 3, 4), "V004", "PT Delta",
                   "KALIMANTAN SELATAN", "BANJAR", "SUNGAI TABUK",
                   "SUNGAI TABUK"),
        ])
        s.commit()


@pytest.fixture()
def klien_crosswalk(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    _isi_crosswalk(eng, dengan_crosswalk=True)
    return TestClient(buat_app(eng)), eng


def _id_tiket(klien):
    r = klien.get("/api/intake", params={"tahun": 2026})
    assert r.status_code == 200, r.text
    return {b["ticket_no"]: b["id"] for b in r.json()["baris"]}


def _rekaman(klien):
    r = klien.get("/api/intake", params={"tahun": 2026})
    assert r.status_code == 200, r.text
    hasil = []
    for b in sorted(r.json()["baris"], key=lambda x: x["ticket_no"]):
        rek = {"id": b["id"], "ticket_no": b["ticket_no"],
               "line_seq": b["line_seq"]}
        rek.update({k: b[k] for k in _KOLOM_UBAH})
        hasil.append(rek)
    return hasil


def _xlsx(rekaman) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Koreksi"
    ws.append(HEADER)
    for rek in rekaman:
        ws.append([rek.get(KUNCI_HEADER.get(h)) for h in HEADER])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _unggah(klien, isi):
    return klien.post("/api/intake/excel-diff/pratinjau", files={
        "file": ("koreksi.xlsx", isi, MEDIA_XLSX)})


def _csv_sementara(tmp_path, baris: list[tuple[str, str]]) -> Path:
    p = tmp_path / "crosswalk.csv"
    p.write_text(
        "kabupaten_norm,provinsi,kode_provinsi,kode_kabupaten,nama_referensi,dasar,sumber\n"
        + "".join(f"{k},{v},11,1101,KAB. {k},exact,uji\n" for k, v in baris),
        encoding="utf-8")
    return p


def test_baca_crosswalk_resmi_dan_abaikan_peta_ambigu(tmp_path):
    peta = baca_crosswalk_provinsi()
    assert len(peta) == 487
    assert peta["ACEH BARAT"] == ("ACEH", "ACEH")
    assert peta["JAKARTA BARAT"] == ("DKI JAKARTA", "DKI JAKARTA")
    assert peta["MAMUJU UTARA"] == ("SULAWESI BARAT", "SULAWESI BARAT")
    assert "BANJAR" not in peta
    assert "DANAU" not in peta
    assert NAMA_FILE_CROSSWALK.exists()

    ambigu = _csv_sementara(tmp_path, [
        ("BANJAR", "JAWA BARAT"), ("BANJAR", "KALIMANTAN SELATAN"),
        ("KAMPAR", "RIAU")])
    assert baca_crosswalk_provinsi(ambigu) == {
        "KAMPAR": ("RIAU", "RIAU")}


def test_terapkan_crosswalk_idempoten_dan_tidak_menimpa(tmp_path):
    eng = _engine()
    with Session(eng) as s:
        s.add_all([
            ReferensiWilayahTrace(kabupaten_norm="MANDAILING NATAL",
                kecamatan_norm="SIPIROK", desa_norm="HUTA RAJA BARU",
                kabupaten="Mandailing Natal", kecamatan="Sipirok",
                desa="Huta Raja Baru"),
            ReferensiWilayahTrace(kabupaten_norm="KAMPAR",
                kecamatan_norm="BANGKINANG", desa_norm="AIR TIRIS",
                kabupaten="Kampar", kecamatan="Bangkinang", desa="Air Tiris"),
            ReferensiWilayahTrace(provinsi_norm="ACEH", provinsi="ACEH",
                kabupaten_norm="ACEH BESAR", kecamatan_norm="INGIN JAYA",
                desa_norm="LAMBARO", kabupaten="Aceh Besar",
                kecamatan="Ingin Jaya", desa="Lambaro"),
            ReferensiWilayahTrace(kabupaten_norm="DANAU",
                kecamatan_norm="DANAU", desa_norm="DANAU",
                kabupaten="Danau", kecamatan="Danau", desa="Danau"),
        ])
        s.commit()
    path = _csv_sementara(tmp_path, [
        ("MANDAILING NATAL", "SUMATERA UTARA"), ("KAMPAR", "RIAU"),
        ("ACEH BESAR", "SUMATERA UTARA")])

    with Session(eng) as s:
        assert terapkan_crosswalk_provinsi(s, path) == 2
        assert terapkan_crosswalk_provinsi(s, path) == 0
        rows = {r.kabupaten_norm: (r.provinsi, r.provinsi_norm)
                for r in s.scalars(select(ReferensiWilayahTrace))}
        assert rows["MANDAILING NATAL"] == ("SUMATERA UTARA", "SUMATERA UTARA")
        assert rows["KAMPAR"] == ("RIAU", "RIAU")
        # Nilai lama tidak ditimpa walaupun CSV berisi provinsi lain.
        assert rows["ACEH BESAR"] == ("ACEH", "ACEH")
        # Kunci tanpa pemetaan pasti tetap NULL.
        assert rows["DANAU"] == (None, None)
        assert kabupaten_memiliki_provinsi(s, "MANDAILING NATAL") is True
        assert kabupaten_memiliki_provinsi(s, "DANAU") is False


def test_muat_referensi_bawaan_backfill_tabel_yang_sudah_ada(tmp_path, monkeypatch):
    """Seeder lama langsung return saat tabel berisi; crosswalk tetap dipasang."""
    eng = _engine()
    with Session(eng) as s:
        s.add(ReferensiWilayahTrace(kabupaten_norm="MANDAILING NATAL",
              kecamatan_norm="SIPIROK", desa_norm="HUTA RAJA BARU",
              kabupaten="Mandailing Natal", kecamatan="Sipirok",
              desa="Huta Raja Baru"))
        s.commit()
    path = _csv_sementara(tmp_path, [("MANDAILING NATAL", "SUMATERA UTARA")])
    monkeypatch.setattr(api_traceability, "NAMA_FILE_CROSSWALK", path)
    monkeypatch.setattr(api_traceability, "BATAS_REFERENSI_RES", 0)

    with Session(eng) as s:
        assert muat_referensi_bawaan(s) == 0  # tidak import ulang ID_AUX
        row = s.scalar(select(ReferensiWilayahTrace))
        assert (row.provinsi, row.provinsi_norm) == (
            "SUMATERA UTARA", "SUMATERA UTARA")


def test_tanpa_crosswalk_tetap_tidak_menebak_provinsi(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    _isi_crosswalk(eng, dengan_crosswalk=False)
    klien = TestClient(buat_app(eng))
    d = klien.get("/api/intake/options/scdf/provinsi").json()
    assert d["options"] == [] and d["available"] is False
    assert "belum menyediakan Provinsi" in d["catatan"]
    ids = _id_tiket(klien)
    r = klien.put(f"/api/intake/{ids['T-001']}",
                  json={"provinsi": "ACEH"})
    assert r.status_code == 422
    assert "belum menyediakan Provinsi" in r.json()["detail"]


def test_opsi_scdf_provinsi_dan_hirarki_terikat_crosswalk(klien_crosswalk):
    klien, _ = klien_crosswalk
    d = klien.get("/api/intake/options/scdf/provinsi").json()
    assert d["available"] is True and d["catatan"] is None
    assert d["options"] == [
        {"value": "RIAU", "label": "RIAU"},
        {"value": "SUMATERA UTARA", "label": "SUMATERA UTARA"}]

    sumut = {x["value"] for x in klien.get(
        "/api/intake/options/scdf/kabupaten",
        params={"provinsi": "SUMATERA UTARA"}).json()["options"]}
    riau = {x["value"] for x in klien.get(
        "/api/intake/options/scdf/kabupaten",
        params={"provinsi": "RIAU"}).json()["options"]}
    assert "Mandailing Natal" in sumut and "Kampar" not in sumut
    assert "Kampar" in riau and "Mandailing Natal" not in riau
    # Baris tanpa pemetaan resmi tidak hilang, tetapi tidak ditebak provinsinya.
    assert "Banjar" in sumut and "Banjar" in riau

    assert klien.get("/api/intake/options/scdf/kecamatan", params={
        "provinsi": "SUMATERA UTARA", "kabupaten": "MANDAILING NATAL"}
    ).json()["options"] == [{"value": "Sipirok", "label": "Sipirok"}]
    assert klien.get("/api/intake/options/scdf/kecamatan", params={
        "provinsi": "RIAU", "kabupaten": "MANDAILING NATAL"}
    ).json()["options"] == []
    assert klien.get("/api/intake/options/scdf/desa", params={
        "provinsi": "SUMATERA UTARA", "kabupaten": "MANDAILING NATAL",
        "kecamatan": "SIPIROK"}).json()["options"] == [
            {"value": "Huta Raja Baru", "label": "Huta Raja Baru"}]


def test_edit_provinsi_memakai_crosswalk_bukan_tebakan(klien_crosswalk):
    klien, eng = klien_crosswalk
    ids = _id_tiket(klien)

    # Koreksi nilai lama yang salah ke nama resmi pada crosswalk.
    r = klien.put(f"/api/intake/{ids['T-002']}",
                  json={"provinsi": "SUMATERA UTARA"})
    assert r.status_code == 200, r.text
    assert r.json()["baris"]["provinsi"] == "SUMATERA UTARA"

    # Provinsi resmi, tetapi kabupaten ini bukan anaknya.
    r = klien.put(f"/api/intake/{ids['T-001']}", json={"provinsi": "RIAU"})
    assert r.status_code == 422
    assert "untuk Provinsi tersebut" in r.json()["detail"]

    # Nama yang tidak ada pada crosswalk tetap ditolak.
    r = klien.put(f"/api/intake/{ids['T-001']}", json={"provinsi": "ACEH"})
    assert r.status_code == 422
    assert "Provinsi tidak ditemukan pada referensi SCDF" in r.json()["detail"]

    # BANJAR ambigu: jangan pilih salah satu provinsi secara otomatis.
    r = klien.put(f"/api/intake/{ids['T-004']}",
                  json={"provinsi": "SUMATERA UTARA"})
    assert r.status_code == 422
    assert "belum memiliki pemetaan Provinsi" in r.json()["detail"]

    with Session(eng) as s:
        assert s.get(TiketBaris, ids["T-001"]).provinsi == "SUMATERA UTARA"
        assert s.get(TiketBaris, ids["T-004"]).provinsi == "KALIMANTAN SELATAN"


def test_quick_fill_provinsi_validasi_dan_terapkan(klien_crosswalk):
    klien, eng = klien_crosswalk
    ids = _id_tiket(klien)

    salah = klien.post("/api/intake/quick-fill/pratinjau", json={
        "ids": [ids["T-001"]], "kolom": "provinsi", "nilai": "RIAU"})
    assert salah.status_code == 200, salah.text
    assert salah.json()["status"] == "ada_galat"
    assert salah.json()["token"] is None
    assert "referensi SCDF" in salah.json()["galat"][0]["alasan"]

    benar = klien.post("/api/intake/quick-fill/pratinjau", json={
        "ids": [ids["T-002"]], "kolom": "provinsi",
        "nilai": "SUMATERA UTARA"})
    assert benar.status_code == 200, benar.text
    assert benar.json()["status"] == "siap"
    assert benar.json()["berubah"] == 1
    token = benar.json()["token"]
    with Session(eng) as s:
        assert s.get(TiketBaris, ids["T-002"]).provinsi == "ACEH"  # belum simpan

    r = klien.post("/api/intake/quick-fill/terapkan", json={"token": token})
    assert r.status_code == 200, r.text
    with Session(eng) as s:
        assert s.get(TiketBaris, ids["T-002"]).provinsi == "SUMATERA UTARA"


def test_excel_diff_provinsi_validasi_dan_terapkan(klien_crosswalk):
    klien, eng = klien_crosswalk
    ids = _id_tiket(klien)

    rekaman = _rekaman(klien)
    for rek in rekaman:
        if rek["ticket_no"] == "T-001":
            rek["provinsi"] = "RIAU"
    salah = _unggah(klien, _xlsx(rekaman))
    assert salah.status_code == 200, salah.text
    assert salah.json()["status"] == "ada_galat"
    assert salah.json()["token"] is None
    assert "referensi SCDF" in salah.json()["galat"][0]["alasan"]

    rekaman = _rekaman(klien)
    for rek in rekaman:
        if rek["ticket_no"] == "T-002":
            rek["provinsi"] = "SUMATERA UTARA"
    benar = _unggah(klien, _xlsx(rekaman))
    assert benar.status_code == 200, benar.text
    assert benar.json()["status"] == "siap"
    assert benar.json()["jumlah_perubahan"] == 1
    token = benar.json()["token"]
    with Session(eng) as s:
        assert s.get(TiketBaris, ids["T-002"]).provinsi == "ACEH"  # belum simpan

    r = klien.post("/api/intake/excel-diff/terapkan", json={"token": token})
    assert r.status_code == 200, r.text
    with Session(eng) as s:
        assert s.get(TiketBaris, ids["T-002"]).provinsi == "SUMATERA UTARA"
        assert s.get(TiketBaris, ids["T-002"]).ticket_no == "T-002"
