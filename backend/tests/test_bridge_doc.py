"""Tes kartu Ringkasan: Margin Bridge & Days of Cover.

Spesifikasi yang diuji (sama dengan definisi pengguna):
- Margin bridge: ΔM = ΔSICOM − ΔOP Price, hanya dua penyebab; OP Price turun
  menolong margin, SICOM turun menekan margin. Angka ujung = angka resmi.
- Days of cover: pemakaian implisit dari neraca stok
  (stok awal + intake − stok akhir), DoC = stok akhir ÷ (pemakaian ÷ hari),
  dan safety dibandingkan dalam HARI (bukan ton).
Kasus emas 2025 yang sudah dikonfirmasi pengguna dipakai sebagai jangkar.
"""
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.main import buat_app


@pytest.fixture(scope="module")
def klien(engine):
    return TestClient(buat_app(engine))


def _bridge(klien, dari, sampai):
    r = klien.get("/api/margin-bridge", params={"dari": dari, "sampai": sampai})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- margin bridge
def test_bridge_dua_penyebab_saja(klien):
    d = _bridge(klien, "2025-01", "2025-12")
    assert [l["kode"] for l in d["langkah"]] == ["sicom", "op_price"]
    assert d["langkah"][0]["jenis"] == "eksternal"
    assert d["langkah"][1]["jenis"] == "keputusan"
    # ΔM = ΔSICOM − ΔOP Price
    assert d["delta_margin"] == pytest.approx(-6.23, abs=0.01)
    assert d["passthrough"]["delta_sicom"] == pytest.approx(-18.39, abs=0.01)
    assert d["passthrough"]["delta_op"] == pytest.approx(-12.16, abs=0.01)


def test_bridge_kasus_emas_jan_des_2025(klien):
    """Jan 15,00 -> Des 8,77 (−6,23); SICOM −18,39 menekan, OP −12,16 menolong."""
    d = _bridge(klien, "2025-01", "2025-12")
    assert d["awal"] == pytest.approx(15.00, abs=0.01)
    assert d["akhir"] == pytest.approx(8.77, abs=0.01)
    kontribusi = {l["kode"]: l["nilai"] for l in d["langkah"]}
    assert kontribusi["sicom"] == pytest.approx(-18.39, abs=0.01)   # menekan
    assert kontribusi["op_price"] == pytest.approx(+12.16, abs=0.01)  # menolong
    assert abs(d["penutupan_selisih"]) < 1e-9
    # OP Price mengikuti ~66% penurunan SICOM; sisa ~34% ditanggung margin
    assert d["passthrough"]["rasio"] == pytest.approx(0.66, abs=0.01)
    assert d["passthrough"]["porsi_ditanggung_margin"] == pytest.approx(0.34, abs=0.01)


def test_bridge_q1_vs_q4_konsisten(klien):
    d = _bridge(klien, "2025-03", "2025-12")  # rentang panjang: pola sama
    assert d["passthrough"]["rasio"] < 1  # OP Price mengikuti sebagian
    # Q1 rata-rata -> Q4 rata-rata (dihitung manual dari data) tetap konsisten
    assert d["periode_a"]["bulan"] == 3 and d["periode_b"]["bulan"] == 12


def test_bridge_per_bulan_menandai_pasar_vs_keputusan(klien):
    d = _bridge(klien, "2025-01", "2025-12")
    per = {b["bulan"]: b for b in d["per_bulan"]}
    # April 2025: dipicu pasar (SICOM −32,26; OP ikut −23,98; margin −8,28)
    assert per["Apr-25"]["delta_margin"] == pytest.approx(-8.28, abs=0.01)
    assert per["Apr-25"]["delta_sicom"] == pytest.approx(-32.26, abs=0.01)
    assert per["Apr-25"]["delta_op_price"] == pytest.approx(-23.98, abs=0.01)
    assert per["Apr-25"]["penyebab"] == "pasar"
    # Oktober 2025: dipicu keputusan (SICOM hanya −1,79; OP naik +1,99)
    assert per["Okt-25"]["delta_margin"] == pytest.approx(-3.77, abs=0.01)
    assert per["Okt-25"]["delta_sicom"] == pytest.approx(-1.79, abs=0.01)
    assert per["Okt-25"]["delta_op_price"] == pytest.approx(+1.99, abs=0.01)
    assert per["Okt-25"]["penyebab"] == "keputusan"


def test_bridge_ujung_sama_dengan_ringkasan_resmi(klien):
    d = _bridge(klien, "2026-01", "2026-08")
    ringkas = klien.get("/api/ringkasan/2026").json()
    margin = {b["bulan"]: b["op_margin"] for b in ringkas["bulan"]}
    assert d["awal"] == pytest.approx(margin[1], abs=1e-9)
    assert d["akhir"] == pytest.approx(margin[8], abs=1e-9)
    assert d["awal"] + sum(l["nilai"] for l in d["langkah"]) == pytest.approx(
        d["akhir"], abs=1e-9)


def test_bridge_rincian_op_price_berjumlah_sama(klien):
    d = _bridge(klien, "2026-03", "2026-08")
    r = d["rincian_op_price"]
    assert r["harga_rp"] + r["kurs"] == pytest.approx(r["total"], abs=1e-9)
    kontribusi_op = next(l["nilai"] for l in d["langkah"] if l["kode"] == "op_price")
    assert r["total"] == pytest.approx(kontribusi_op, abs=1e-6)


def test_bridge_satu_bulan_banding_sebelumnya(klien):
    d = _bridge(klien, "2026-08", "2026-08")
    assert d["periode_a"]["bulan"] == 7
    assert d["periode_b"]["bulan"] == 8


def test_bridge_format_salah_dan_bulan_kosong(klien):
    assert klien.get("/api/margin-bridge?dari=Agustus").status_code == 422
    assert klien.get("/api/margin-bridge?sampai=2026-13").status_code == 422
    assert klien.get("/api/margin-bridge?dari=1999-01&sampai=1999-06").status_code == 404


def test_bridge_ekspor_xlsx(klien):
    r = klien.get("/api/margin-bridge?dari=2025-01&sampai=2025-12&format=xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    teks = " ".join(str(c.value) for baris in wb.active.iter_rows() for c in baris)
    assert "OP Margin awal" in teks and "Δ OP Price" in teks


# ---------------------------------------------------------------- days of cover
def test_doc_kasus_emas_2025(klien):
    """Feb 26,6 / Mar 25,6 / Apr 12,3 / Mei 22,8 / Nov 6,9 hari."""
    d = klien.get("/api/days-of-cover",
                  params={"dari": "2025-02", "sampai": "2025-12"}).json()
    per = {b["bulan"]: b for b in d["baris"]}
    assert per["Feb-25"]["doc_hari"] == pytest.approx(26.6, abs=0.2)
    assert per["Mar-25"]["doc_hari"] == pytest.approx(25.6, abs=0.2)
    assert per["Apr-25"]["doc_hari"] == pytest.approx(12.3, abs=0.2)
    assert per["Mei-25"]["doc_hari"] == pytest.approx(22.8, abs=0.2)
    assert per["Nov-25"]["doc_hari"] == pytest.approx(6.9, abs=0.2)


def test_doc_pemakaian_implisit_dari_neraca(klien):
    d = klien.get("/api/days-of-cover",
                  params={"dari": "2025-02", "sampai": "2025-12"}).json()
    b = {x["bulan"]: x for x in d["baris"]}["Jul-25"]
    # pemakaian = stok awal + intake − stok akhir, dan DoC = akhir ÷ per hari
    assert b["pemakaian_ton"] == pytest.approx(
        b["stok_awal_ton"] + b["intake_ton"] - b["stok_akhir_ton"], abs=0.01)
    assert b["doc_hari"] == pytest.approx(
        b["stok_akhir_ton"] / b["pemakaian_harian_ton"], abs=0.02)
    # Juli 2025 = pemakaian tertinggi (4.547 ton) — patut dicek
    assert b["pemakaian_ton"] == pytest.approx(4547, abs=2)


def test_doc_rerata_dan_safety_dalam_hari(klien):
    d = klien.get("/api/days-of-cover",
                  params={"dari": "2025-02", "sampai": "2025-12"}).json()
    assert d["rerata_pemakaian_bulan_ton"] == pytest.approx(3944, abs=10)
    assert d["rerata_pemakaian_harian_ton"] == pytest.approx(130, abs=2)
    # safety 2.795 ton ≈ 21,5 hari PADA pemakaian rata-rata 130 ton/hari
    assert 2795.1 / d["rerata_pemakaian_harian_ton"] == pytest.approx(21.5, abs=0.5)
    # safety dalam hari = safety ton ÷ pemakaian harian bulan itu (berubah-ubah)
    for b in d["baris"]:
        if b["safety_hari"] is None:
            continue
        assert b["safety_hari"] == pytest.approx(
            b["safety_ton"] / b["pemakaian_harian_ton"], abs=0.05)
    kini = d["terkini"]
    assert kini["safety_ton"] == pytest.approx(2795.1, abs=1)
    # safety dinamis = hari acuan × pemakaian harian bulan itu
    assert kini["safety_dinamis_ton"] == pytest.approx(
        21.5 * kini["pemakaian_harian_ton"], abs=1)
    assert d["safety_dinamis_ton"] == pytest.approx(
        21.5 * d["rerata_pemakaian_harian_ton"], abs=1)


def test_doc_status_memakai_hari_bukan_ton(klien):
    d = klien.get("/api/days-of-cover",
                  params={"dari": "2025-02", "sampai": "2025-12"}).json()
    for b in d["baris"]:
        if b["safety_hari"] is None or b["doc_hari"] is None:
            continue
        harus = "aman" if b["doc_hari"] >= b["safety_hari"] else "di bawah safety"
        assert b["status"] == harus


def test_doc_sejak_juli_di_bawah_safety(klien):
    d = klien.get("/api/days-of-cover",
                  params={"dari": "2025-02", "sampai": "2025-12"}).json()
    per = {b["bulan"]: b for b in d["baris"]}
    for bulan in ("Jul-25", "Agu-25", "Sep-25", "Nov-25"):
        assert per[bulan]["doc_hari"] < 21.5
        assert per[bulan]["status"] == "di bawah safety"


def test_doc_bulan_tanpa_stok_sebelumnya_dilewati_jujur(klien):
    """Januari tidak bisa dihitung tanpa stok Desember tahun sebelumnya."""
    d = klien.get("/api/days-of-cover",
                  params={"dari": "2023-01", "sampai": "2023-03"}).json()
    assert all(b["bulan"] != "Jan-23" for b in d["baris"])
    assert any("Jan-23" in x["bulan"] for x in d["bulan_tak_terhitung"])


def test_doc_default_12_bulan_terakhir(klien):
    d = klien.get("/api/days-of-cover").json()
    assert d["jumlah_bulan"] <= 12
    assert d["baris"][-1]["bulan"] == d["terkini"]["bulan"]


def test_doc_filter_dan_validasi(klien):
    d = klien.get("/api/days-of-cover",
                  params={"dari": "2026-01", "sampai": "2026-03"}).json()
    assert d["baris"][0]["bulan"] == "Jan-26"
    assert d["baris"][-1]["bulan"] == "Mar-26"
    assert klien.get("/api/days-of-cover?dari=2026-99").status_code == 422
    assert klien.get("/api/days-of-cover?sampai=2026-01&dari=2026-06").status_code == 422
    assert klien.get("/api/days-of-cover?hari_safety=0").status_code == 422


def test_doc_ekspor_xlsx(klien):
    r = klien.get("/api/days-of-cover?dari=2025-02&sampai=2025-06&format=xlsx")
    assert r.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    teks = " ".join(str(c.value) for baris in wb.active.iter_rows() for c in baris)
    assert "Pemakaian" in teks and "DoC" in teks


# ---------------------------------------------------------------- cara dihitung
def test_metrik_kartu_baru_tersedia(klien):
    kartu = klien.get("/api/metrik").json()["kartu"]
    for kunci in ("margin_bridge", "days_of_cover"):
        assert kunci in kartu
        assert kartu[kunci]["cara_dihitung"].strip()


# -------------------------------------------------- narasi "kenapa naik/turun"
def test_bridge_ada_penjelasan_tiap_komponen(klien):
    d = _bridge(klien, "2025-01", "2025-12")
    for l in d["langkah"]:
        assert l["penjelasan"].strip()
        assert l["menekan"] is (l["nilai"] < 0)
        assert l["arah"] in ("naik", "turun", "datar")
    # SICOM turun 18,39 -> penjelasan menyebut angka & kata "menekan"
    sicom = next(l for l in d["langkah"] if l["kode"] == "sicom")
    assert "menekan" in sicom["penjelasan"]
    assert "18.39" in sicom["penjelasan"] or "18,39" in sicom["penjelasan"]
    # OP Price turun -> penjelasan menyebut "menolong" + pass-through 66%
    op = next(l for l in d["langkah"] if l["kode"] == "op_price")
    assert "menolong" in op["penjelasan"]
    assert "66%" in op["penjelasan"]


def test_bridge_analisa_kesimpulan(klien):
    d = _bridge(klien, "2025-01", "2025-12")
    assert len(d["analisa"]) >= 4
    teks = " ".join(d["analisa"])
    assert "turun 6.23" in teks or "turun 6,23" in teks
    assert "Penekan terbesar" in teks and "Penolong terbesar" in teks
    assert "66%" in teks and "34%" in teks
    assert "Penurunan bulanan terbesar: Apr-25" in teks
    assert d["kesimpulan"] == "Tekanan terutama dari pasar (SICOM)"


def test_bridge_penjelasan_per_bulan(klien):
    d = _bridge(klien, "2025-01", "2025-12")
    for b in d["per_bulan"]:
        assert b["penjelasan"].startswith(b["bulan"])
        assert "dipicu" in b["penjelasan"]
    per = {b["bulan"]: b for b in d["per_bulan"]}
    assert "naik" in per["Feb-25"]["penjelasan"]
    assert "turun 8.28" in per["Apr-25"]["penjelasan"]
    # Oktober: harga beli naik -> penjelasan menyebut berlawanan arah
    assert "berlawanan arah" in per["Okt-25"]["penjelasan"]


def test_bridge_analisa_saat_margin_naik(klien):
    """Periode yang marginnya naik harus punya kesimpulan & narasi yang benar."""
    d = _bridge(klien, "2024-01", "2024-12")
    assert d["delta_margin"] > 0
    assert d["kesimpulan"].startswith("Margin membaik")
    assert any("naik" in a for a in d["analisa"])
    # walau margin naik, penekan tetap dilaporkan
    assert any("Penekan terbesar" in a for a in d["analisa"])


# ------------------------------------- kartu "OP Margin bulanan vs target"
def test_margin_bulanan_tanpa_filter_semua_periode(klien):
    d = klien.get("/api/kartu/margin-bulanan").json()
    assert d["jumlah_bulan"] == len(d["baris"]) > 0
    # urut waktu
    kunci = [(b["tahun"], b["bulan"]) for b in d["baris"]]
    assert kunci == sorted(kunci)


def test_margin_bulanan_pakai_periode(klien):
    d = klien.get("/api/kartu/margin-bulanan",
                  params={"dari": "2025-03", "sampai": "2025-08"}).json()
    assert d["dari"] == "2025-03" and d["sampai"] == "2025-08"
    assert d["jumlah_bulan"] == 6
    assert all("2025-03" <= f"{b['tahun']}-{b['bulan']:02d}" <= "2025-08"
               for b in d["baris"])


def test_margin_bulanan_validasi_periode(klien):
    assert klien.get("/api/kartu/margin-bulanan?dari=2025-13").status_code == 422
    assert klien.get("/api/kartu/margin-bulanan?dari=2025-06&sampai=2025-01"
                     ).status_code == 422


def test_margin_antar_tahun_ikut_periode(klien):
    """Mode 'banding antar tahun' harus membandingkan bulan yang sama saja."""
    d = klien.get("/api/grafik/margin-antar-tahun",
                  params={"dari": "2024-03", "sampai": "2025-09"}).json()
    assert [x["tahun"] for x in d] == [2024, 2025]
    for th in d:
        terisi = [m["bulan"] for m in th["data"] if m["margin"] is not None]
        if th["tahun"] == 2024:
            assert terisi == list(range(3, 13))
        else:
            assert terisi == list(range(1, 10))


def test_margin_antar_tahun_validasi(klien):
    assert klien.get("/api/grafik/margin-antar-tahun?dari=Agustus"
                     ).status_code == 422


def test_margin_bulanan_ekspor_ikut_periode(klien):
    r = klien.get("/api/kartu/margin-bulanan?dari=2025-03&sampai=2025-08&format=xlsx")
    assert r.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.active.max_row == 7  # header + 6 bulan


# ------------------------------- status target & toggle Rp/kg (kurs bulanan)
def test_status_target_termasuk_tipis():
    """Ambang tipis: di atas target tetapi < 1 US¢/kg."""
    from app.api_analisis import AMBANG_TIPIS_USC, _status_target
    assert _status_target(13.4, 13.0) == "tipis"      # +0,40 -> tipis
    assert _status_target(13.0 + AMBANG_TIPIS_USC, 13.0) == "di atas target"
    assert _status_target(15.8, 13.0) == "di atas target"
    assert _status_target(12.63, 13.0) == "di bawah target"
    assert _status_target(None, 13.0) == "tanpa target"
    assert _status_target(10.0, None) == "tanpa target"


def test_margin_bulanan_punya_kurs_dan_status(klien):
    d = klien.get("/api/kartu/margin-bulanan",
                  params={"dari": "2026-01", "sampai": "2026-10"}).json()
    for b in d["baris"]:
        assert b["kurs"] and 15000 < b["kurs"] < 20000      # Rp/USD wajar
        assert b["status_target"] in ("di atas target", "tipis",
                                      "di bawah target", "tanpa target")
        assert b["selisih_vs_target"] == pytest.approx(
            b["op_margin"] - b["target"], abs=1e-9)
    # konversi Rp/kg = US¢/kg x kurs / 100
    b = d["baris"][0]
    assert b["op_margin"] * b["kurs"] / 100 == pytest.approx(1760, abs=6)


def test_margin_bulanan_ekspor_punya_kolom_rp_dan_status(klien):
    r = klien.get("/api/kartu/margin-bulanan?dari=2026-01&sampai=2026-03&format=xlsx")
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    judul = [c.value for c in wb.active[1]]
    for kolom in ("OP Margin (Rp/kg)", "Kurs efektif (Rp/USD)",
                  "Selisih vs target (USc/kg)", "Status"):
        assert kolom in judul
