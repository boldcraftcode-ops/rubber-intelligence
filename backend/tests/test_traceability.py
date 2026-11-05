from app.core.traceability import (
    normalisasi_kabupaten,
    normalisasi_teks_wilayah,
    parse_asal_getah,
    persen_traceable,
    rentang_periode,
    sidik_baris_sumber,
)


def test_parse_asal_getah_menerima_empat_bagian_dan_merapikan_spasi():
    assert parse_asal_getah(
        "  Sumatera   Utara , Kota Medan, Medan Baru ,  Babura  "
    ) == ("Sumatera Utara", "Kota Medan", "Medan Baru", "Babura")


def test_parse_asal_getah_menolak_bagian_kosong_atau_jumlah_salah():
    assert parse_asal_getah("Sumatera Utara, Medan, Medan Baru") is None
    assert parse_asal_getah("Sumatera Utara, Medan,, Babura") is None
    assert parse_asal_getah(None) is None


def test_normalisasi_wilayah_case_trim_spasi_dan_prefix_kabupaten():
    assert normalisasi_teks_wilayah("  Ilir   Timur  II ") == "ILIR TIMUR II"
    assert normalisasi_kabupaten(" Kota   Medan ") == "MEDAN"
    assert normalisasi_kabupaten("Kabupaten Deli  Serdang") == "DELI SERDANG"


def test_persen_traceable_menggunakan_volume_dan_mencegah_invalid():
    assert persen_traceable(250, 1000) == 25.0
    assert persen_traceable(1500, 1000) == 100.0
    assert persen_traceable(10, 0) is None
    assert persen_traceable(-10, 100) == 0.0


def test_sidik_baris_adalah_full_row_dan_periode_tahun_semester_kuartal_bulan():
    assert sidik_baris_sumber(("T1", "Medan", 12)) != sidik_baris_sumber(("T1", "Medan", 13))
    assert rentang_periode(2026, "H1")[1].isoformat() == "2026-06-30"
    assert rentang_periode(2026, "Q4")[0].isoformat() == "2026-10-01"
    assert rentang_periode(2026, "07")[1].isoformat() == "2026-07-31"


def test_impor_hanya_membuang_duplikat_pada_seluruh_baris_sumber():
    import datetime as dt

    from openpyxl import Workbook
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.importer.tiket import KOLOM, impor_sheet_tiket
    from app.models import Base, TiketBaris

    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    wb = Workbook()
    ws = wb.active
    headers = [
        "Ticket Date", "Ticket No", "Supplier Code", "Supplier Name", "Vehicle No",
        "Item Code", "DRC Date", "Wet", "Sample", "Reject", "DRC", "Dry",
        "Asal Getah", "Provinsi", "Kabupaten/Kota", "Kecamatan", "Desa", "BIN", "Location",
    ]
    ws.append(headers)
    baris = [dt.date(2026, 1, 2), "T-1", "V1", "Supplier", "BK 123", "SIR20",
             dt.date(2026, 1, 2), 1000, 0, 0, 50, 500,
             "Sumatera Utara, Kota Medan, Medan Baru, Babura",
             "Sumatera Utara", "Kota Medan", "Medan Baru", "Babura", "BIN-1", "LOC-1"]
    ws.append(baris)
    ws.append(baris.copy())
    berbeda = baris.copy()
    berbeda[5] = "SIR10"
    ws.append(berbeda)
    with Session(eng) as session:
        warnings = []
        assert impor_sheet_tiket(ws, session, None, warnings) == 2
        session.flush()
        tersimpan = list(session.scalars(select(TiketBaris).order_by(TiketBaris.line_seq)))
        assert len(tersimpan) == 2
        assert [row.item_code for row in tersimpan] == ["SIR20", "SIR10"]
        assert len({row.source_fingerprint for row in tersimpan}) == 2
        assert any("baris sama persis" in w for w in warnings)


def test_api_agregasi_traceability_berbasis_dry_tiket_valid_dan_ref():
    import datetime as dt

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.main import buat_app
    from app.models import (Base, Collector, ReferensiWilayahTrace,
                            TiketBaris, Vendor)

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as session:
        session.add(Vendor(kode="V1", nama_baku="Supplier One", status="aktif"))
        session.add(Collector(kode="C1", nama="Collector One",
                              kode_vendor="V1"))
        session.add(ReferensiWilayahTrace(
            kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU", desa_norm="BABURA",
            kabupaten="Kota Medan", kecamatan="Medan Baru", desa="Babura", code=None))
        for no, kab, kec, desa, item, fp in (
            ("T1", "MEDAN", "MEDAN BARU", "BABURA", "SIR20", "a" * 64),
            ("T2", "WILAYAH X", "KEC X", "DESA X", "SIR10 TTSR", "b" * 64),
            ("T3", "MEDAN", "MEDAN BARU", "BABURA", "LATEX OP", "c" * 64),
        ):
            session.add(TiketBaris(
                ticket_no=no, line_seq=1, ticket_date=dt.date(2026, 2, 1),
                kode_vendor="V1", item_code=item, wet_kg=1000, drc_pct=50,
                dry_kg=500, asal_getah="Sumatera Utara, Kota Medan, Medan Baru, Babura",
                kabupaten_norm=kab, kecamatan_norm=kec, desa_norm=desa,
                asal_getah_valid=True, source_fingerprint=fp, tiket_nol=False))
        session.commit()

    client = TestClient(buat_app(eng))
    response = client.get("/api/traceability", params={"tahun": 2026})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["kpis"]["dry_mt"] == 1.0
    assert payload["kpis"]["trace_reg_pct"] == 50.0
    assert payload["kpis"]["trace_kec_pct"] == 50.0
    assert payload["kpis"]["trace_desa_pct"] == 50.0
    assert payload["wilayah"][0]["code"] == ""
    assert payload["wilayah"][0]["status_code"] == "belum termapping"
    with_latex = client.get("/api/traceability", params={"tahun": 2026, "include_latex": "true"}).json()
    assert with_latex["kpis"]["dry_mt"] == 1.5
    eudr_only = client.get("/api/traceability", params={"tahun": 2026, "eudr": "eudr"}).json()
    assert eudr_only["kpis"]["dry_mt"] == 0.5
    actor_rows = client.get("/api/traceability/actors", params={"tahun": 2026}).json()["baris"]
    assert len(actor_rows) == 1
    assert actor_rows[0]["is_direct_producer"] is False
    assert actor_rows[0]["is_collector"] is True
    assert actor_rows[0]["tier"] == "T2"
    assert actor_rows[0]["source_from"] == 2
    assert actor_rows[0]["country"] == "Indonesia"
    detail = client.get("/api/traceability/actors/V1", params={"tahun": 2026})
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["period_turnover_mt"] == 1.0
    assert detail_payload["is_collector"] is True
    assert detail_payload["tier"] == "T2"
    assert detail_payload["tickets"] == 2
    assert len(detail_payload["origins"]) == 2
    assert sum(origin["share_pct"] for origin in detail_payload["origins"]) == 100.0
    assert any(origin["matched_to_id_aux"] for origin in detail_payload["origins"])
    assert any(not origin["matched_to_id_aux"] for origin in detail_payload["origins"])
    assert detail_payload["sell_to"] == []
    assert "bukan hubungan upstream/downstream" in detail_payload["supply_chain_note"]
    changed = client.put("/api/vendor/V1", json={
        "nama_baku": "Supplier One", "is_direct_producer": True})
    assert changed.status_code == 200, changed.text
    assert client.get("/api/traceability/actors", params={"tahun": 2026}).json()["baris"][0]["is_direct_producer"] is True
    assert client.get("/api/traceability?format=xlsx&tahun=2026").status_code == 200
    assert client.get("/api/traceability/unmapped", params={"tahun": 2026}).status_code == 200
    wilayah = client.get("/api/collector/wilayah", params={
        "kabupaten_kota": "Kota Medan"}).json()
    assert wilayah["provinsi"] == []
    assert {x["value"] for x in wilayah["kabupaten_kota"]} == {"Kota Medan"}
    assert {x["value"] for x in wilayah["desa"]} == {"Babura"}
    assert "tidak menyediakan Provinsi" in wilayah["catatan"]


def test_koreksi_manual_subdistrict_updates_supplier_and_regional_traceability():
    import datetime as dt

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.main import buat_app
    from app.models import Base, ReferensiWilayahTrace, TiketBaris, Vendor

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as session:
        session.add(Vendor(kode="V1", nama_baku="Supplier One", status="aktif"))
        session.add_all([
            ReferensiWilayahTrace(
                kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU", desa_norm="BABURA",
                kabupaten="Kota Medan", kecamatan="Medan Baru", desa="Babura", code=None),
            ReferensiWilayahTrace(
                kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU", desa_norm="BABURA TIMUR",
                kabupaten="Kota Medan", kecamatan="Medan Baru", desa="Babura Timur", code=None),
        ])
        session.add(Vendor(kode="V2", nama_baku="Supplier Two", status="aktif"))
        for no, vendor, desa, dry, fp in (
            ("T1", "V1", "BABURA", 500, "a" * 64),
            ("T2", "V1", "BABURA BARU", 500, "b" * 64),
            ("T3", "V2", "BABURA BARU", 250, "c" * 64),
        ):
            session.add(TiketBaris(
                ticket_no=no, line_seq=1, ticket_date=dt.date(2026, 2, 1),
                kode_vendor=vendor, item_code="SIR20", wet_kg=dry * 2, drc_pct=50,
                dry_kg=dry, asal_getah=f"Sumatera Utara, Kota Medan, Medan Baru, {desa.title()}",
                kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU", desa_norm=desa,
                asal_getah_valid=True, source_fingerprint=fp, tiket_nol=False))
        for no, desa, dry, fp in (("T-OLD-1", "Babura", 300, "d" * 64),
                                  ("T-OLD-2", "Babura Timur", 200, "e" * 64)):
            session.add(TiketBaris(
                ticket_no=no, line_seq=1, ticket_date=dt.date(2025, 4, 1),
                kode_vendor="V1", item_code="SIR20", wet_kg=dry * 2, drc_pct=50,
                dry_kg=dry,
                asal_getah=f"Sumatera Utara, Kota Medan, Medan Baru, {desa}",
                kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU",
                desa_norm=desa.upper(), asal_getah_valid=True,
                source_fingerprint=fp, tiket_nol=False))
        session.commit()

    client = TestClient(buat_app(eng))
    params = {"tahun": 2026}
    regional = client.get("/api/traceability", params=params).json()
    assert regional["kpis"]["trace_desa_pct"] == 40.0
    detail = client.get("/api/traceability/actors/V1", params=params).json()
    unmatched = next(row for row in detail["origins"]
                     if row["source_key"]["desa_norm"] == "BABURA BARU")
    options = client.get("/api/traceability/locations/subdistricts", params={
        "kabupaten_norm": "MEDAN", "kecamatan_norm": "MEDAN BARU"}).json()
    assert options["options"] == [
        {"value": "BABURA", "label": "Babura"},
        {"value": "BABURA TIMUR", "label": "Babura Timur"},
    ]
    rekomendasi = client.get("/api/traceability/actors/V1/origin-recommendations", params={
        **params, "source_kabupaten_norm": "MEDAN",
        "source_kecamatan_norm": "MEDAN BARU"})
    assert rekomendasi.status_code == 200, rekomendasi.text
    suggestion = rekomendasi.json()["recommendations"][0]
    assert suggestion["sub_district"] == "Babura"
    assert suggestion["confidence_pct"] == 60.0
    assert suggestion["historical_dry_mt"] == 0.3
    assert suggestion["historical_years"] == 1

    saved = client.put("/api/traceability/actors/V1/origin-correction", params=params,
                       json={"source_kabupaten_norm": unmatched["source_key"]["kabupaten_norm"],
                                 "source_kecamatan_norm": unmatched["source_key"]["kecamatan_norm"],
                                 "source_desa_norm": unmatched["source_key"]["desa_norm"],
                                 "target_desa_norm": "BABURA"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["manual_correction"] is True
    assert "Semua tiket" in saved.json()["scope"]

    regional_after = client.get("/api/traceability", params=params).json()
    assert regional_after["kpis"]["trace_desa_pct"] == 100.0
    assert regional_after["kpis"]["trace_desa_mt"] == 1.25
    desa_node = regional_after["wilayah"][0]["children"][0]["children"][0]
    assert desa_node["name"] == "BABURA"
    assert desa_node["traceability_status"] == "traceable"
    detail_after = client.get("/api/traceability/actors/V1", params=params).json()
    corrected = next(row for row in detail_after["origins"]
                     if row["source_key"]["desa_norm"] == "BABURA BARU")
    assert corrected["sub_district"] == "Babura"
    assert corrected["manual_correction"] is True
    assert corrected["traceable_mt"] == 0.5
    actor_rows = client.get("/api/traceability/actors", params=params).json()["baris"]
    assert next(row for row in actor_rows if row["supplier_code"] == "V1")["traceable_mt"] == 1.0
    assert next(row for row in actor_rows if row["supplier_code"] == "V2")["traceable_mt"] == 0.25

    reset = client.put("/api/traceability/actors/V1/origin-correction", params=params,
                       json={"source_kabupaten_norm": unmatched["source_key"]["kabupaten_norm"],
                                 "source_kecamatan_norm": unmatched["source_key"]["kecamatan_norm"],
                                 "source_desa_norm": unmatched["source_key"]["desa_norm"],
                                 "target_desa_norm": None})
    assert reset.status_code == 200, reset.text
    assert client.get("/api/traceability", params=params).json()["kpis"]["trace_desa_pct"] == 40.0

def test_upload_excel_unmapped_simpan_koreksi_scdf_dan_validasi_atomik():
    import datetime as dt
    from io import BytesIO

    from fastapi.testclient import TestClient
    from openpyxl import load_workbook
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.main import buat_app
    from app.models import (Base, KoreksiWilayahTrace, ReferensiWilayahTrace,
                            TiketBaris, Vendor)

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as session:
        session.add(Vendor(kode="V1", nama_baku="Supplier One", status="aktif"))
        session.add_all([
            ReferensiWilayahTrace(
                kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU", desa_norm="BABURA TIMUR",
                kabupaten="Kota Medan", kecamatan="Medan Baru", desa="Babura Timur", code=None),
            ReferensiWilayahTrace(
                kabupaten_norm="MEDAN", kecamatan_norm="MEDAN SELATAN", desa_norm="PASAR MERAH",
                kabupaten="Kota Medan", kecamatan="Medan Selatan", desa="Pasar Merah", code=None),
        ])
        session.add(TiketBaris(
            ticket_no="T-UPLOAD", line_seq=1, ticket_date=dt.date(2026, 2, 1),
            kode_vendor="V1", item_code="SIR20", wet_kg=1000, drc_pct=50,
            dry_kg=500, asal_getah="Sumatera Utara, Kota Medan, Medan Baru, Babura Baru",
            kabupaten="Kota Medan", kecamatan="Medan Baru", desa="Babura Baru",
            kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU", desa_norm="BABURA BARU",
            asal_getah_valid=True, source_fingerprint="f" * 64, tiket_nol=False))
        session.commit()

    client = TestClient(buat_app(eng))
    download = client.get("/api/traceability/unmapped", params={"tahun": 2026})
    assert download.status_code == 200, download.text
    wb = load_workbook(BytesIO(download.content))
    ws = wb["Unmapped Records"]
    header = {cell.value: cell.column for cell in ws[1]}
    assert "SCDF District" in header and "SCDF Sub-district" in header
    assert ws.max_row == 2
    kolom_district = header["SCDF District"]
    kolom_subdistrict = header["SCDF Sub-district"]

    def unggah(nama_district: str, nama_subdistrict: str):
        ws.cell(row=2, column=kolom_district, value=nama_district)
        ws.cell(row=2, column=kolom_subdistrict, value=nama_subdistrict)
        buf = BytesIO()
        wb.save(buf)
        return client.post("/api/traceability/unmapped/import", files={
            "file": ("traceability-unmapped.xlsx", buf.getvalue(),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    invalid = unggah("Medan Selatan", "Sub-district tidak resmi")
    assert invalid.status_code == 422, invalid.text
    with Session(eng) as session:
        assert session.scalar(select(KoreksiWilayahTrace)) is None

    valid = unggah("Medan Selatan", "Pasar Merah")
    assert valid.status_code == 200, valid.text
    assert valid.json()["baris_mapping_diisi"] == 1
    assert valid.json()["lokasi_dipetakan"] == 1
    assert valid.json()["baris_direvisi"] == 1
    assert valid.json()["koreksi_baru"] == 1
    assert valid.json()["koreksi_diperbarui"] == 0
    with Session(eng) as session:
        correction = session.scalar(select(KoreksiWilayahTrace))
        assert correction is not None
        assert correction.target_ref_id is not None
    regional = client.get("/api/traceability", params={"tahun": 2026}).json()
    assert regional["kpis"]["trace_kec_pct"] == 100.0
    assert regional["kpis"]["trace_desa_pct"] == 100.0
    node_district = regional["wilayah"][0]["children"][0]
    assert node_district["name"] == "MEDAN SELATAN"
    assert node_district["children"][0]["name"] == "PASAR MERAH"
    district_options = client.get("/api/traceability/locations/districts", params={
        "kabupaten_norm": "MEDAN"}).json()
    assert {x["value"] for x in district_options["options"]} == {
        "MEDAN BARU", "MEDAN SELATAN"}

    sama = unggah("Medan Selatan", "Pasar Merah")
    assert sama.status_code == 200, sama.text
    assert sama.json()["baris_direvisi"] == 0
    assert sama.json()["koreksi_tidak_berubah"] == 1

    diperbarui = unggah("Medan Baru", "Babura Timur")
    assert diperbarui.status_code == 200, diperbarui.text
    assert diperbarui.json()["baris_direvisi"] == 1
    assert diperbarui.json()["koreksi_baru"] == 0
    assert diperbarui.json()["koreksi_diperbarui"] == 1
    wb.close()


def test_vendor_dan_collector_dari_desa_sama_satu_baris_tier():
    import datetime as dt

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.main import buat_app
    from app.models import (Base, Collector, KoreksiWilayahTrace,
                            ReferensiWilayahTrace, TiketBaris, Vendor)

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as session:
        session.add(Vendor(kode="V1", nama_baku="Supplier One", status="aktif"))
        session.add(Collector(kode="C1", nama="Collector One",
                              kode_vendor="V1", desa="Babura"))
        session.add(Collector(kode="C2", nama="Collector Two",
                              kode_vendor="V1", desa="Desa Lain"))
        session.add(ReferensiWilayahTrace(
            kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU", desa_norm="BABURA",
            kabupaten="Kota Medan", kecamatan="Medan Baru", desa="Babura",
            code=None))
        for no, desa_norm in (("T1", "BABURA"), ("T2", "DESA LAIN")):
            session.add(TiketBaris(
                ticket_no=no, line_seq=1, ticket_date=dt.date(2026, 2, 1),
                kode_vendor="V1", item_code="SIR20", wet_kg=1000, drc_pct=50,
                dry_kg=500, asal_getah=f"Sumatera Utara, Kota Medan, Medan Baru, "
                                       f"{desa_norm.title()}",
                kabupaten_norm="MEDAN", kecamatan_norm="MEDAN BARU",
                desa_norm=desa_norm, asal_getah_valid=True,
                source_fingerprint=no.ljust(64, "0"), tiket_nol=False))
        session.commit()

    client = TestClient(buat_app(eng))
    params = {"tahun": 2026}
    actor_rows = client.get("/api/traceability/actors", params=params).json()["baris"]
    assert len(actor_rows) == 1
    row = actor_rows[0]
    assert row["supplier_code"] == "V1"
    assert row["tier"] == "T2"
    assert row["collector_code"] == "C1"
    assert row["collector_name"] == "Collector One"

    detail = client.get("/api/traceability/actors/V1", params=params).json()
    assert detail["is_collector"] is True
    assert detail["tier"] == "T2"
    assert detail["collector_code"] == "C1"


def test_rute_kartu_traceability_sudah_dihapus():
    """Fitur Kartu Traceability dihapus: /cards tidak terdaftar, API utama tetap jalan."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from app.main import buat_app
    from app.models import Base

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    client = TestClient(buat_app(eng))
    assert client.get("/api/traceability/cards",
                      params={"tahun": 2026}).status_code == 404
    assert client.get("/api/traceability",
                      params={"tahun": 2026}).status_code == 200
