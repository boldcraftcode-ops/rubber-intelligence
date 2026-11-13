"""Daftar/pencarian dan koreksi baris per baris pada menu Data Intake."""
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


@pytest.fixture()
def data_intake(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    eng = _engine()
    with sessionmaker(bind=eng, future=True)() as session:
        session.add(ReferensiWilayahTrace(
            provinsi_norm="SUMATERA UTARA", provinsi="SUMATERA UTARA",
            kabupaten_norm="MANDAILING NATAL", kecamatan_norm="SIPIROK",
            desa_norm="HUTA RAJA BARU", kabupaten="Mandailing Natal",
            kecamatan="Sipirok", desa="Huta Raja Baru", code=None))
        session.add_all([
            TiketBaris(ticket_no="T-001", line_seq=1,
                       ticket_date=dt.date(2026, 3, 1), kode_vendor="V001",
                       nama_vendor_asli="CV Alpha", item_code="SLAB2",
                       wet_kg=100, dry_kg=62, drc_pct=62,
                       provinsi="SUMATERA UTARA", kabupaten="MANDAILING NATAL",
                       kecamatan="DISTRIK LAMA", desa="HUTA RAJA",
                       kabupaten_norm="MANDAILING NATAL", kecamatan_norm="DISTRIK LAMA",
                       desa_norm="HUTA RAJA", asal_getah_valid=True, tiket_nol=False),
            TiketBaris(ticket_no="T-002", line_seq=1,
                       ticket_date=dt.date(2026, 3, 2), kode_vendor="V002",
                       nama_vendor_asli="PT Beta", item_code="SLAB2",
                       wet_kg=200, dry_kg=124, drc_pct=62,
                       provinsi="RIAU", kabupaten="KAMPAR", kecamatan="BANGKINANG",
                       desa="AIR TIRIS", asal_getah_valid=True, tiket_nol=False),
            TiketBaris(ticket_no="T-003", line_seq=1,
                       ticket_date=dt.date(2026, 3, 3), kode_vendor="V003",
                       nama_vendor_asli="CV Gamma", item_code="SLAB2",
                       wet_kg=150, dry_kg=93, drc_pct=62,
                       provinsi="SUMATERA UTARA", kabupaten="ASAHAN",
                       kecamatan="KISARAN", desa="RAWANG",
                       asal_getah_valid=True, tiket_nol=False),
        ])
        session.commit()
    return TestClient(buat_app(eng)), eng


def _row_id(client, ticket_no="T-001"):
    return client.get("/api/intake", params={
        "tahun": 2026, "provinsi": "Sumatera Utara", "supplier": "CV Alpha",
        "q": ticket_no,
    }).json()["baris"][0]["id"]


def test_filter_wajib_cari_dan_paginasi_baris_intake(data_intake):
    client, _ = data_intake
    r = client.get("/api/intake")
    assert r.status_code == 422  # tidak boleh memuat semua baris tanpa filter

    r = client.get("/api/intake", params={
        "tahun": 2026, "provinsi": "sumatera utara", "supplier": "CV Alpha",
        "q": "T-001", "page": 1, "page_size": 1,
    })
    assert r.status_code == 200, r.text
    hasil = r.json()
    assert hasil["total"] == 1
    assert hasil["pages"] == 1
    assert hasil["baris"][0]["ticket_no"] == "T-001"

    params = {"tahun": 2026, "provinsi": "Sumatera Utara",
              "page": 1, "page_size": 1}
    r = client.get("/api/intake", params=params)
    assert r.status_code == 200
    assert r.json()["total"] == 2
    assert r.json()["pages"] == 2
    assert r.json()["baris"][0]["ticket_no"] == "T-003"

    params["page"] = 2
    r = client.get("/api/intake", params=params)
    assert r.status_code == 200
    assert r.json()["baris"][0]["ticket_no"] == "T-001"

    # Supplier saja juga merupakan filter sah.
    r = client.get("/api/intake", params={"supplier": "CV Gamma"})
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["baris"][0]["ticket_no"] == "T-003"


def test_opsi_dropdown_provinsi_dan_supplier_berasal_dari_database(data_intake):
    client, _ = data_intake
    provinsi = client.get("/api/intake/options/provinsi").json()["options"]
    assert provinsi == ["RIAU", "SUMATERA UTARA"]

    supplier = client.get("/api/intake/options/supplier", params={"q": "CV"}).json()
    assert supplier["options"] == ["CV Alpha", "CV Gamma"]
    assert supplier["has_more"] is False


def test_dropdown_wilayah_edit_hanya_menggunakan_referensi_scdf(data_intake):
    client, _ = data_intake
    provinsi = client.get("/api/intake/options/scdf/provinsi").json()
    # Opsi berasal dari crosswalk resmi pada SCDF, bukan nilai intake.
    assert provinsi["options"] == [
        {"value": "SUMATERA UTARA", "label": "SUMATERA UTARA"}]
    assert provinsi["available"] is True
    assert provinsi["catatan"] is None

    kabupaten = client.get("/api/intake/options/scdf/kabupaten").json()
    assert kabupaten["options"] == [{"value": "Mandailing Natal", "label": "Mandailing Natal"}]
    assert kabupaten["province_linked"] is True
    # Hierarki tetap terikat: Provinsi lain tidak menawarkan kabupaten ini.
    assert client.get("/api/intake/options/scdf/kabupaten", params={
        "provinsi": "RIAU"}).json()["options"] == []
    kecamatan = client.get("/api/intake/options/scdf/kecamatan", params={
        "kabupaten": "Kabupaten Mandailing Natal",
        "provinsi": "SUMATERA UTARA"}).json()["options"]
    assert kecamatan == [{"value": "Sipirok", "label": "Sipirok"}]
    desa = client.get("/api/intake/options/scdf/desa", params={
        "kabupaten": "MANDAILING NATAL", "kecamatan": "SIPIROK",
        "provinsi": "SUMATERA UTARA"}).json()["options"]
    assert desa == [{"value": "Huta Raja Baru", "label": "Huta Raja Baru"}]


def test_edit_intake_menyimpan_audit_dan_memperbarui_kunci_wilayah(data_intake):
    client, eng = data_intake
    row_id = _row_id(client)

    r = client.put(f"/api/intake/{row_id}", json={
        "kode_vendor": " v009 ",
        "kecamatan": "SIPIROK",
        "desa": "HUTA RAJA BARU",
        "dry_kg": 61.5,
        "ticket_date": "2026-03-01",
    })
    assert r.status_code == 200, r.text
    updated = r.json()["baris"]
    assert updated["kode_vendor"] == "V009"
    assert updated["kecamatan"] == "SIPIROK"
    assert updated["desa"] == "HUTA RAJA BARU"
    assert updated["dry_kg"] == pytest.approx(61.5)

    with sessionmaker(bind=eng, future=True)() as session:
        saved = session.get(TiketBaris, row_id)
        assert saved.kecamatan_norm == "SIPIROK"
        assert saved.desa_norm == "HUTA RAJA BARU"
        assert saved.ticket_no == "T-001"  # identitas sumber tidak berubah
        audit = session.scalar(select(AuditLog).where(AuditLog.objek == "intake_tiket"))
        assert audit is not None
        assert '"kecamatan": "SIPIROK"' in audit.detail

    trace = client.get("/api/traceability", params={"tahun": 2026}).json()
    kabupaten = next(x for x in trace["wilayah"] if x["name"] == "MANDAILING NATAL")
    assert kabupaten["traceability_status"] == "traceable"
    assert kabupaten["children"][0]["name"] == "SIPIROK"


def test_edit_wilayah_menolak_nilai_yang_tidak_ada_di_scdf(data_intake):
    client, _ = data_intake
    row_id = _row_id(client)
    response = client.put(f"/api/intake/{row_id}", json={"desa": "DESA FIKTIF"})
    assert response.status_code == 422
    assert "referensi SCDF" in response.text


def test_edit_kualitas_menyegarkan_flag_tiket_nol(data_intake):
    client, _ = data_intake
    row_id = _row_id(client)
    r = client.put(f"/api/intake/{row_id}", json={"wet_kg": 0})
    assert r.status_code == 200, r.text

    # Wet=0 membuatnya menjadi tiket nol sehingga tidak dihitung pada penerimaan.
    from app.models import TiketBaris
    with sessionmaker(bind=data_intake[1], future=True)() as session:
        assert session.get(TiketBaris, row_id).tiket_nol is True


def test_edit_menolak_drc_di_luar_rentang(data_intake):
    client, _ = data_intake
    row_id = _row_id(client)
    r = client.put(f"/api/intake/{row_id}", json={"drc_pct": 140})
    assert r.status_code == 422


def test_edit_id_tidak_ditemukan(data_intake):
    client, _ = data_intake
    r = client.put("/api/intake/99999", json={"kecamatan": "SIPIROK"})
    assert r.status_code == 404


def test_hapus_satu_baris_intake_mencatat_audit_dan_menyegarkan_data(data_intake):
    client, eng = data_intake
    row_id = _row_id(client)
    response = client.delete(f"/api/intake/{row_id}")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "dihapus"
    assert "T-001" in response.json()["pesan"]

    remaining = client.get("/api/intake", params={
        "tahun": 2026, "provinsi": "Sumatera Utara", "supplier": "CV Alpha"})
    assert remaining.status_code == 200
    assert remaining.json()["total"] == 0

    with sessionmaker(bind=eng, future=True)() as session:
        assert session.get(TiketBaris, row_id) is None
        audit = session.scalar(select(AuditLog).where(
            AuditLog.objek == "intake_tiket", AuditLog.aksi == "hapus"))
        assert audit is not None
        assert '"ticket_no": "T-001"' in audit.detail


def test_hapus_intake_id_tidak_ditemukan(data_intake):
    client, _ = data_intake
    response = client.delete("/api/intake/99999")
    assert response.status_code == 404
