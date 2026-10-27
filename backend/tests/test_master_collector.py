"""Tes CRUD dan template/impor Master Collector."""
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import buat_app
from app.models import Base, Vendor


def _engine():
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all([Vendor(kode="V001", nama_baku="PT Vendor Satu", status="aktif"),
                   Vendor(kode="V002", nama_baku="CV Vendor Dua", status="aktif")])
        s.commit()
    return eng


@pytest.fixture
def klien(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    return TestClient(buat_app(_engine()))


def _buat(klien, **ubah):
    data = {"kode": "K001", "nama": "Budi Santoso", "nik": "1203456789012345",
            "no_hp": "081234567890", "kode_vendor": "V001",
            "provinsi": "Sumatera Utara", "kabupaten_kota": "Kabupaten Deli Serdang",
            "desa": "Tanjung Morawa", "pengisi": "tester"}
    data.update(ubah)
    return klien.post("/api/collector", json=data)


def _xlsx(rows, headers=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Master_Collector"
    ws.append(headers or ["Kode_Kolektor", "Nama_Kolektor", "NIK", "No_HP",
                          "Afiliasi_Vendor", "Provinsi", "Kabupaten_Kota", "Desa"])
    for row in rows:
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_crud_collector_dengan_affiliation_dan_wilayah(klien):
    r = _buat(klien)
    assert r.status_code == 200, r.text
    c = r.json()["collector"]
    assert (c["kode"], c["nama"], c["nama_vendor"]) == (
        "K001", "Budi Santoso", "PT Vendor Satu")
    assert c["provinsi"] == "Sumatera Utara"
    assert c["kabupaten_kota"] == "Kabupaten Deli Serdang"
    assert c["desa"] == "Tanjung Morawa"

    u = klien.put("/api/collector/K001", json={
        "nama": "Budi Santoso Baru", "nik": "1203456789012345", "no_hp": "0812",
        "kode_vendor": "v002", "provinsi": "Sumatera Utara",
        "kabupaten_kota": "Kota Medan", "desa": "Medan Baru"})
    assert u.status_code == 200, u.text
    assert u.json()["collector"]["kode_vendor"] == "V002"
    assert u.json()["collector"]["kabupaten_kota"] == "Kota Medan"

    q = klien.get("/api/collector?q=Medan").json()
    assert q["jumlah"] == 1 and q["baris"][0]["kode"] == "K001"
    assert klien.get("/api/collector?kode_vendor=V001").json()["jumlah"] == 0
    d = klien.delete("/api/collector/K001")
    assert d.status_code == 200
    assert klien.get("/api/collector").json()["jumlah"] == 0


def test_kode_dan_vendor_wajib(klien):
    assert _buat(klien, kode="bad code").status_code == 422
    assert _buat(klien, kode_vendor="V999").status_code == 422
    assert _buat(klien, nama="  ").status_code == 422


def test_nik_wajib_16_digit_jika_diisi(klien):
    assert _buat(klien, nik="12345").status_code == 422
    assert _buat(klien, nik="abc1234567890123").status_code == 422
    assert _buat(klien, nik="").status_code == 200


def test_nik_unik_dan_kode_tidak_ganda(klien):
    assert _buat(klien).status_code == 200
    assert _buat(klien, kode="K002").status_code == 409
    assert _buat(klien, kode="K002", nik="1203456789012345").status_code == 409
    assert _buat(klien, kode="K002", nik="").status_code == 200


def test_vendor_tidak_bisa_dihapus_selama_masih_afiliasi_collector(klien):
    assert _buat(klien).status_code == 200
    r = klien.delete("/api/vendor/V001?paksa=true")
    assert r.status_code == 409
    assert "1 collector" in r.json()["detail"]


def test_template_collector_memiliki_header_dan_panduan(klien):
    r = klien.get("/api/collector/template")
    assert r.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Master_Collector", "Petunjuk"]
    assert [c.value for c in wb["Master_Collector"][1]] == [
        "Kode_Kolektor", "Nama_Kolektor", "NIK", "No_HP", "Afiliasi_Vendor",
        "Provinsi", "Kabupaten_Kota", "Desa"]
    assert wb["Master_Collector"][2][4].value == "V001"
    assert "NIK" in wb["Petunjuk"][6][0].value


def test_impor_upsert_validasi_per_baris_dan_kolom_opsional(klien):
    assert _buat(klien, nik="", no_hp="0812").status_code == 200
    isi = _xlsx([
        ["K001", "Budi diperbarui", "", "", "V002", "", "Kota Medan", ""],
        ["K002", "Siti", "123", "0813", "V001", "Sumatera Utara", "Kota Medan", "Medan Baru"],
        ["K003", "Rani", "3201010101900002", "0814", "V999", "Sumatera Utara", "Kota Medan", "Medan Baru"],
    ])
    r = klien.post("/api/collector/impor", files={
        "file": ("kolektor.xlsx", isi,
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["diperbarui"], d["ditambah"], d["ditolak"]) == (1, 0, 2)
    baris = klien.get("/api/collector").json()["baris"][0]
    assert baris["nama"] == "Budi diperbarui"
    assert baris["no_hp"] == "0812"  # sel kosong pada impor tidak menghapus
    assert baris["kode_vendor"] == "V002"
    assert "16 angka" in d["peringatan"][0]["alasan"]


def test_impor_menambahkan_baris_dengan_vendor_valid(klien):
    isi = _xlsx([["K009", "Dewi", "3201010101900009", "081299", "V002",
                  "Aceh", "Kota Banda Aceh", "Lampriet"]])
    r = klien.post("/api/collector/impor", files={"file": ("kolektor.xlsx", isi)})
    assert r.status_code == 200, r.text
    c = klien.get("/api/collector").json()["baris"][0]
    assert c["kode"] == "K009" and c["nama_vendor"] == "CV Vendor Dua"


def test_database_lama_mendapat_tabel_collector_tanpa_menghapus_vendor(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    # Simulasikan database lama: baru memiliki tabel vendor, belum collector.
    Vendor.__table__.create(eng)
    with Session(eng) as s:
        s.add(Vendor(kode="VOLD", nama_baku="Vendor Lama", status="aktif"))
        s.commit()
    client = TestClient(buat_app(eng))
    assert client.get("/api/collector").json()["jumlah"] == 0
    assert client.get("/api/vendor?q=VOLD").json()["baris"][0]["nama_baku"] == "Vendor Lama"


def test_template_bisa_diunduh_dan_harus_sheet_yang_benar(klien):
    isi = _xlsx([["K001", "Budi", "", "", "V001", "", "", ""]], headers=[
        "Kode_Kolektor", "Nama_Kolektor", "NIK", "No_HP", "Afiliasi_Vendor",
        "Provinsi", "Kabupaten_Kota", "Desa"])
    r = klien.post("/api/collector/impor", files={"file": ("salah.xlsx", isi)})
    assert r.status_code == 200, r.text
    bad = openpyxl.Workbook()
    bad.active.title = "Sheet1"
    out = io.BytesIO(); bad.save(out)
    r2 = klien.post("/api/collector/impor", files={"file": ("salah.xlsx", out.getvalue())})
    assert r2.status_code == 422
