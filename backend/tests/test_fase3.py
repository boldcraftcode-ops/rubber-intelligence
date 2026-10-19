"""Tes Fase 3: ringkasan ala Excel, 82 bulan, rekonsiliasi, kartu query,
telusur asal angka, ekspor Excel."""
import datetime as dt
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import buat_app
from app.models import MartBulanan


@pytest.fixture(scope="module")
def klien(engine):
    """API yang membaca database berisi data awal template."""
    return TestClient(buat_app(engine))


# ----------------------------------------------------------------------------
# Kriteria 2: 82 bulan data; Apr 2022 = 4,3391 dengan catatan koreksi
# ----------------------------------------------------------------------------
def test_jumlah_bulan_data_awal(session):
    bulan = list(session.scalars(select(MartBulanan)))
    assert len(bulan) == 82  # Jan 2020 s.d. Okt 2026


def test_apr_2022_koreksi(klien):
    r = klien.get("/api/ringkasan/2022").json()
    apr = next(b for b in r["bulan"] if b["bulan"] == 4)
    assert round(apr["op_margin"], 4) == 4.3391
    assert apr["catatan_koreksi"] and "T147" in apr["catatan_koreksi"]
    assert any("5,5232" in c for c in r["catatan"])


def test_ringkasan_2026_lengkap(klien):
    r = klien.get("/api/ringkasan/2026").json()
    jan = r["bulan"][0]
    assert round(jan["sicom"], 4) == 184.2498
    assert round(jan["op_price"], 4) == 173.6773
    assert round(jan["op_margin"], 4) == 10.5725
    assert round(jan["ton"], 3) == 3885.166
    assert jan["target"] == 12.0
    assert round(jan["vs_target"], 4) == -1.4275
    assert r["avg_ytd_sederhana"] is not None
    assert r["avg_ytd_tertimbang"] is not None


def test_grafik_margin_antar_tahun(klien):
    data = klien.get("/api/grafik/margin-antar-tahun").json()
    assert [d["tahun"] for d in data] == [2020, 2021, 2022, 2023, 2024, 2025, 2026]
    assert all(len(d["data"]) == 12 for d in data)


# ----------------------------------------------------------------------------
# Kriteria 3: Jul & Agu 2026 di Rekonsiliasi, selisih 19,453 dan 6,878 ton
# ----------------------------------------------------------------------------
def test_rekonsiliasi_selisih_diketahui(klien):
    r = klien.get("/api/rekonsiliasi").json()
    jul = next(d for d in r["diketahui"] if d["bulan"] == 7)
    agu = next(d for d in r["diketahui"] if d["bulan"] == 8)
    assert jul["selisih_ton"] == 19.453
    assert agu["selisih_ton"] == 6.878
    assert "persetujuan" in jul["status"]
    assert any("19 September 2026" in c for c in r["catatan"])


# ----------------------------------------------------------------------------
# Kualitas data
# ----------------------------------------------------------------------------
def test_kualitas(klien):
    r = klien.get("/api/kualitas").json()
    assert "kpi_reject" in r and "asumsi" in r["kpi_reject"]
    assert {t["sumber"] for t in r["terlambat"]} == {"SICOM", "Kurs", "Stok",
                                                     "Tiket", "Pembelian"}
    assert isinstance(r["peringatan"], list)


# ----------------------------------------------------------------------------
# Kartu query: daftar putih, drill-down, "data harga belum tersedia"
# ----------------------------------------------------------------------------
def test_kartu_tonase_dan_drilldown(klien):
    r = klien.get("/api/kartu/tonase", params={"dimensi": "provinsi"}).json()
    assert r["drill_berikutnya"] == "kabupaten"
    assert r["total_ton"] > 0
    prov = r["baris"][0]["kunci"]
    r2 = klien.get("/api/kartu/tonase",
                   params={"dimensi": "kabupaten", "provinsi": prov}).json()
    assert r2["drill_berikutnya"] == "kecamatan"
    assert r2["total_ton"] <= r["total_ton"] + 0.001


def test_kartu_tonase_dimensi_tak_dikenal(klien):
    r = klien.get("/api/kartu/tonase", params={"dimensi": "warna"})
    assert r.status_code == 422
    assert "tidak dikenal" in r.json()["detail"]


def test_kartu_konsentrasi_vendor(klien):
    r = klien.get("/api/kartu/konsentrasi-vendor", params={"top": 5}).json()
    assert len(r["baris"]) <= 5
    assert klien.get("/api/kartu/konsentrasi-vendor",
                     params={"top": 7}).status_code == 422


def test_kartu_margin_per_tanpa_data_harga(klien):
    """Amount data awal hanya total per hari -> tidak boleh dialokasikan."""
    r = klien.get("/api/kartu/margin-per",
                  params={"dimensi": "grade", "tahun": 2026}).json()
    assert r["status"] == "data harga belum tersedia"
    assert "TIDAK dialokasikan" in r["pesan"]
    assert r["baris"] == []


def test_kartu_margin_harian(klien):
    r = klien.get("/api/kartu/margin-harian",
                  params={"tahun": 2026, "bulan": 1}).json()
    h3 = next(b for b in r["baris"] if b["tanggal"] == "2026-01-03")
    assert round(h3["margin"], 4) == 10.3364


# ----------------------------------------------------------------------------
# Kriteria 4: telusur dari angka margin ke baris & unggahan asal
# ----------------------------------------------------------------------------
def test_telusur_bulan_ke_tanggal_ke_unggahan(klien):
    bln = klien.get("/api/telusur/bulan", params={"tahun": 2026, "bulan": 1}).json()
    assert round(bln["op_margin"], 4) == 10.5725
    assert len(bln["hari"]) > 0
    tanggal = bln["hari"][0]["tanggal"]

    hari = klien.get("/api/telusur/tanggal", params={"tanggal": tanggal}).json()
    assert len(hari["pembelian"]) > 0
    asal = hari["pembelian"][0]["unggahan"]
    assert asal is not None
    assert asal["nama_file"].startswith("Template_dan_Data_Awal")
    # jejak menunjuk unggahan terakhir yang menyentuh baris itu
    assert asal["pengunggah"].startswith("pytest")
    assert hari["sicom"]["unggahan"]["id"] == asal["id"]


def test_telusur_tanggal_dengan_tiket(klien):
    """Tanggal contoh tiket di template: baris tiket + unggahan asal muncul."""
    hari = klien.get("/api/telusur/tanggal", params={"tanggal": "2026-10-15"}).json()
    assert len(hari["tiket"]) == 3
    assert hari["tiket"][0]["unggahan"]["nama_file"].startswith("Template_dan_Data_Awal")


# ----------------------------------------------------------------------------
# Ekspor Excel & Cara dihitung
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("url,params", [
    ("/api/ringkasan/2026", {"format": "xlsx"}),
    ("/api/kartu/tonase", {"dimensi": "vendor", "format": "xlsx"}),
    ("/api/kartu/margin-bulanan", {"format": "xlsx"}),
    ("/api/rekonsiliasi", {"format": "xlsx"}),
])
def test_ekspor_xlsx(klien, url, params):
    r = klien.get(url, params=params)
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.active.max_row >= 2  # header + minimal satu baris


def test_metrik_cara_dihitung(klien):
    r = klien.get("/api/metrik").json()
    assert "metrics" in r and "kartu" in r
    assert "cara_dihitung" in r["kartu"]["ringkasan"]
    assert "T147" in r["kartu"]["ringkasan"]["cara_dihitung"]
