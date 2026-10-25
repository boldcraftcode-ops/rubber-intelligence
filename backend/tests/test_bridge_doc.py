"""Tes kartu Ringkasan baru: margin bridge & days of cover.

Fokus pengujian:
- bridge TERTUTUP persis (awal + seluruh komponen = akhir) dan angkanya sama
  dengan OP Margin resmi di ringkasan bulanan;
- dekomposisi kurs/harga Rp konsisten secara matematis (harga = 100 x E/K);
- days of cover sama dengan mart harian & /api/stok (satu sumber angka);
- ekspor Excel berfungsi untuk keduanya.
"""
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.main import buat_app


@pytest.fixture(scope="module")
def klien(engine):
    return TestClient(buat_app(engine))


# ---------------------------------------------------------------- margin bridge
def test_bridge_bulanan_tertutup_persis(klien):
    r = klien.get("/api/margin-bridge")
    assert r.status_code == 200
    d = r.json()
    assert d["basis"] == "bulanan"
    assert [l["kode"] for l in d["langkah"]] == ["sicom", "harga_rp", "kurs"]

    jumlah = d["awal"] + sum(l["nilai"] for l in d["langkah"])
    assert jumlah == pytest.approx(d["akhir"], abs=1e-9)
    assert abs(d["penutupan_selisih"]) < 1e-9


def test_bridge_akhir_sama_dengan_margin_resmi(klien):
    """Angka ujung bridge harus persis OP Margin resmi (bukan hitungan baru)."""
    d = klien.get("/api/margin-bridge").json()
    pb = d["periode_b"]
    ringkas = klien.get(f"/api/ringkasan/{pb['tahun']}").json()
    bulan = {b["bulan"]: b for b in ringkas["bulan"]}
    assert d["akhir"] == pytest.approx(bulan[pb["bulan"]]["op_margin"], abs=1e-9)
    assert d["awal"] == pytest.approx(bulan[d["periode_a"]["bulan"]]["op_margin"],
                                      abs=1e-9)


def test_bridge_dekomposisi_sesuai_rumus(klien):
    """Cek ulang dekomposisi dari detail: efek kurs + efek harga Rp = Δharga."""
    d = klien.get("/api/margin-bridge?basis=bulanan&tahun=2026&bulan=8").json()
    x = d["detail"]
    efek_harga = 100.0 * (x["e_b"] - x["e_a"]) / x["kurs_a"]
    efek_kurs = 100.0 * x["e_b"] * (1.0 / x["kurs_b"] - 1.0 / x["kurs_a"])
    assert (x["harga_b"] - x["harga_a"]) == pytest.approx(efek_harga + efek_kurs,
                                                          abs=1e-9)
    # harga = 100 x E / K secara identik
    assert x["harga_b"] == pytest.approx(100.0 * x["e_b"] / x["kurs_b"], abs=1e-9)
    assert x["harga_a"] == pytest.approx(100.0 * x["e_a"] / x["kurs_a"], abs=1e-9)


def test_bridge_tahunan_tertutup(klien):
    d = klien.get("/api/margin-bridge?basis=tahunan&tahun=2026").json()
    assert d["basis"] == "tahunan"
    assert d["periode_a"]["tahun"] == 2025
    assert d["periode_b"]["tahun"] == 2026
    # hanya bulan yang berdata di kedua tahun
    assert d["periode_a"]["bulan_list"] == d["periode_b"]["bulan_list"]
    assert d["periode_a"]["bulan_list"] == sorted(d["periode_a"]["bulan_list"])
    jumlah = d["awal"] + sum(l["nilai"] for l in d["langkah"])
    assert jumlah == pytest.approx(d["akhir"], abs=1e-9)


def test_bridge_memakai_periode_kartu_elemen(klien):
    """dari/sampai (YYYY-MM) = periode grafik RM Stock - Intake vs Pricing."""
    d = klien.get("/api/margin-bridge",
                  params={"dari": "2026-01", "sampai": "2026-08"}).json()
    assert d["basis"] == "rentang"
    assert d["periode_a"] == {"tahun": 2026, "bulan": 1}
    assert d["periode_b"] == {"tahun": 2026, "bulan": 8}
    # ujung bridge = OP Margin resmi bulan awal & akhir kartu
    ringkas = klien.get("/api/ringkasan/2026").json()
    margin = {b["bulan"]: b["op_margin"] for b in ringkas["bulan"]}
    assert d["awal"] == pytest.approx(margin[1], abs=1e-9)
    assert d["akhir"] == pytest.approx(margin[8], abs=1e-9)
    assert d["awal"] + sum(l["nilai"] for l in d["langkah"]) == pytest.approx(
        d["akhir"], abs=1e-9)


def test_bridge_satu_bulan_banding_bulan_sebelumnya(klien):
    d = klien.get("/api/margin-bridge",
                  params={"dari": "2026-08", "sampai": "2026-08"}).json()
    assert d["periode_a"] == {"tahun": 2026, "bulan": 7}
    assert d["periode_b"] == {"tahun": 2026, "bulan": 8}


def test_bridge_format_bulan_salah_422(klien):
    assert klien.get("/api/margin-bridge?dari=Agustus").status_code == 422
    assert klien.get("/api/margin-bridge?sampai=2026-13").status_code == 422


def test_bridge_tahun_tanpa_data_404(klien):
    r = klien.get("/api/margin-bridge?basis=bulanan&tahun=1999")
    assert r.status_code == 404
    assert r.json()["detail"]


def test_bridge_basis_salah_422(klien):
    assert klien.get("/api/margin-bridge?basis=mingguan").status_code == 422
    assert klien.get("/api/margin-bridge?bulan=13").status_code == 422


def test_bridge_ekspor_xlsx(klien):
    r = klien.get("/api/margin-bridge?format=xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    teks = " ".join(str(c.value) for baris in wb.active.iter_rows() for c in baris)
    assert "OP Margin awal" in teks and "OP Margin akhir" in teks


# ---------------------------------------------------------------- days of cover
def test_doc_terkini_sama_dengan_stok_terakhir(klien):
    d = klien.get("/api/days-of-cover").json()
    # /api/stok tanpa filter = seluruh data; bandingkan pada rentang yang sama
    stok = klien.get(f"/api/stok?dari={d['dari']}&sampai={d['sampai']}").json()
    assert d["terkini"]["tanggal"] == stok["terakhir"]["tanggal"]
    assert d["terkini"]["days"] == pytest.approx(stok["terakhir"]["days"], abs=1e-6)
    assert d["terkini"]["status"] == stok["terakhir"]["status"]
    assert d["jumlah_hari"] == stok["jumlah_hari"]
    assert d["jumlah_hari_di_bawah_safety"] == stok["jumlah_hari_di_bawah_safety"]


def test_doc_seri_default_180_hari_terurut(klien):
    d = klien.get("/api/days-of-cover").json()
    assert d["jumlah_hari"] == 180
    tanggal = [s["tanggal"] for s in d["seri"]]
    assert tanggal == sorted(tanggal)
    assert tanggal[-1] == d["terkini"]["tanggal"]
    assert d["seri"][-1] is not d["terkini"]  # struktur terpisah, bukan referensi
    # days = stok / kapasitas, aman dari pembagian nol
    for s in d["seri"]:
        if s["days"] is not None:
            assert s["days"] == pytest.approx(s["stok_ton"] / s["kapasitas_ton"],
                                              abs=1e-3)


def test_doc_filter_rentang(klien):
    d = klien.get("/api/days-of-cover?dari=2025-01-01&sampai=2025-01-31").json()
    assert d["dari"] == "2025-01-01" and d["sampai"] == "2025-01-31"
    assert all("2025-01-01" <= s["tanggal"] <= "2025-01-31" for s in d["seri"])


def test_doc_memakai_periode_kartu_elemen(klien):
    """Filter bulan (YYYY-MM) dari kartu elemen = rentang yang dianalisa."""
    d = klien.get("/api/days-of-cover",
                  params={"dari": "2026-01", "sampai": "2026-03"}).json()
    assert d["dari"] == "2026-01-01"
    assert d["sampai"] == "2026-03-31"      # akhir bulan, bukan tanggal 1
    assert all("2026-01-01" <= s["tanggal"] <= "2026-03-31" for s in d["seri"])
    assert d["terkini"]["tanggal"] == max(s["tanggal"] for s in d["seri"])


def test_doc_format_bulan_salah_422(klien):
    assert klien.get("/api/days-of-cover?dari=2026-99").status_code == 422


def test_doc_ekspor_xlsx(klien):
    r = klien.get("/api/days-of-cover?format=xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.active.max_row >= 181  # header + 180 baris seri + ringkasan


# ---------------------------------------------------------------- cara dihitung
def test_metrik_kartu_baru_tersedia(klien):
    kartu = klien.get("/api/metrik").json()["kartu"]
    for kunci in ("margin_bridge", "days_of_cover"):
        assert kunci in kartu
        assert kartu[kunci]["cara_dihitung"].strip()
