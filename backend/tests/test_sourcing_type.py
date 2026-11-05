"""Sourcing type Supplier Actors: tiga pilihan diisi langsung dari form tabel.

Yang dijaga:
- hanya Direct Smallholder / Indirect Smallholder / Own Plantation yang sah;
- nilai tersimpan sebagai kode stabil, tampil sebagai label, dan muncul di
  daftar Supplier Actors, detail supplier, serta ekspor Excel;
- `klasifikasi` Master Vendor (Small holder / Small estate / Rubber trader)
  TIDAK berubah; kalau sourcing type kosong, klasifikasi lama jadi fallback;
- kode supplier yang hanya ada di intake tetap bisa diisi (baris master
  minimal disiapkan dari nama vendor asli pada tiket).
"""
from __future__ import annotations

import datetime as dt
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.sourcing_type import (SOURCING_TYPE, bakukan, daftar_untuk_layar,
                                    label)
from app.main import buat_app
from app.models import (Base, ReferensiWilayahTrace, TiketBaris, Vendor)


def _tiket(no: str, vendor: str, nama: str, desa: str = "BABURA") -> TiketBaris:
    return TiketBaris(
        ticket_no=no, line_seq=1, ticket_date=dt.date(2026, 2, 1),
        kode_vendor=vendor, nama_vendor_asli=nama, item_code="SIR20",
        wet_kg=1000, drc_pct=50, dry_kg=500,
        asal_getah=f"Sumatera Utara, Kota Medan, Medan Baru, {desa.title()}",
        kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU", desa_norm=desa,
        asal_getah_valid=True, source_fingerprint=no.ljust(64, "0"),
        tiket_nol=False)


@pytest.fixture()
def klien():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        # Satu baris referensi mencegah seed ID_AUX (81.909 baris) saat tes.
        s.add(ReferensiWilayahTrace(
            kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU",
            desa_norm="BABURA", kabupaten="Kota Medan",
            kecamatan="Medan Baru", desa="Babura", code=None))
        s.add(Vendor(kode="V1", nama_baku="Supplier Satu", status="aktif",
                     klasifikasi="small_holder", is_direct_producer=False))
        s.add(Vendor(kode="V2", nama_baku="Supplier Dua", status="aktif"))
        s.add(_tiket("T1", "V1", "Supplier Satu"))
        s.add(_tiket("T2", "V2", "Supplier Dua"))
        s.add(_tiket("T3", "V999", "Supplier Intake Saja", desa="DESA LAIN"))
        s.commit()
    return TestClient(buat_app(eng)), eng


def test_modul_sourcing_type_hanya_menerima_tiga_pilihan():
    assert [o["kode"] for o in daftar_untuk_layar()] == [
        "direct_smallholder", "indirect_smallholder", "own_plantation"]
    assert list(SOURCING_TYPE.values()) == ["Direct Smallholder",
                                            "Indirect Smallholder",
                                            "Own Plantation"]
    assert bakukan("Direct Smallholder") == "direct_smallholder"
    assert bakukan("INDIRECT-SMALLHOLDER") == "indirect_smallholder"
    assert bakukan("own_plantation") == "own_plantation"
    assert bakukan("") is None and bakukan(None) is None
    assert label("direct_smallholder") == "Direct Smallholder"
    assert label("koperasi") is None
    with pytest.raises(ValueError, match="Direct Smallholder"):
        bakukan("koperasi besar")


def test_pilihan_diisi_dari_tabel_dan_tidak_mengubah_klasifikasi(klien):
    client, eng = klien
    params = {"tahun": 2026}
    daftar = client.get("/api/traceability/actors", params=params).json()
    assert [o["kode"] for o in daftar["sourcing_type_options"]] == [
        "direct_smallholder", "indirect_smallholder", "own_plantation"]

    for kode, nama in SOURCING_TYPE.items():
        r = client.put("/api/traceability/actors/V1/sourcing-type",
                       json={"sourcing_type": kode, "pengisi": "tes"})
        assert r.status_code == 200, r.text
        assert r.json()["sourcing_type_code"] == kode
        assert r.json()["sourcing_type_label"] == nama

        baris = client.get("/api/traceability/actors", params=params).json()["baris"]
        v1 = next(b for b in baris if b["supplier_code"] == "V1")
        assert v1["sourcing_type_code"] == kode
        assert v1["sourcing_type"] == nama
        assert v1["sourcing_type_source"] == "Supplier Actors"

        detail = client.get("/api/traceability/actors/V1", params=params).json()
        assert detail["sourcing_type_code"] == kode
        assert detail["sourcing_type_label"] == nama
        assert detail["sourcing_type_source"] == "Supplier Actors"

    # Klasifikasi lama Master Vendor tetap utuh.
    with Session(eng) as s:
        assert s.get(Vendor, "V1").klasifikasi == "small_holder"

    # Ejaan di luar tiga pilihan ditolak, bukan disimpan diam-diam.
    salah = client.put("/api/traceability/actors/V1/sourcing-type",
                       json={"sourcing_type": "koperasi besar"})
    assert salah.status_code == 422
    assert "Own Plantation" in salah.json()["detail"]

    # Ekspor Excel memuat kolom sourcing type.
    xlsx = client.get("/api/traceability", params={**params, "format": "xlsx"})
    assert xlsx.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(xlsx.content), read_only=True)
    header = [c.value for c in wb["Supplier Actors"][1]]
    assert "Sourcing type" in header and "Sourcing type source" in header
    wb.close()

    # Dikosongkan -> fallback ke klasifikasi Master Vendor.
    hapus = client.put("/api/traceability/actors/V1/sourcing-type",
                       json={"sourcing_type": "", "pengisi": "tes"})
    assert hapus.status_code == 200
    assert hapus.json()["sourcing_type_code"] is None
    baris = client.get("/api/traceability/actors", params=params).json()["baris"]
    v1 = next(b for b in baris if b["supplier_code"] == "V1")
    assert v1["sourcing_type"] == "Small holder"
    assert v1["sourcing_type_source"] == "Master Vendor"


def test_aktor_tanpa_master_vendor_tetap_bisa_diisi(klien):
    client, eng = klien
    r = client.put("/api/traceability/actors/V999/sourcing-type",
                   json={"sourcing_type": "Own Plantation", "pengisi": "tes"})
    assert r.status_code == 200, r.text
    assert r.json()["sourcing_type_code"] == "own_plantation"

    with Session(eng) as s:
        v = s.get(Vendor, "V999")
        assert v is not None
        assert v.nama_baku == "Supplier Intake Saja"
        assert v.klasifikasi is None          # tidak mengarang klasifikasi lama
        assert v.sourcing_type == "own_plantation"

    params = {"tahun": 2026}
    baris = client.get("/api/traceability/actors", params=params).json()["baris"]
    v999 = next(b for b in baris if b["supplier_code"] == "V999")
    assert v999["sourcing_type"] == "Own Plantation"
    assert v999["sourcing_type_source"] == "Supplier Actors"

    # Kode yang benar-benar tidak ada di intake/master tetap ditolak.
    assert client.put("/api/traceability/actors/V404/sourcing-type",
                      json={"sourcing_type": "own_plantation"}).status_code == 404
