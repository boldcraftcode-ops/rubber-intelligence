"""Tes narasi "Jelaskan ke saya" (/api/jelaskan/{kartu}).

Yang dijaga:
- struktur jawaban-dulu (what / so_what / now_what) selalu ada;
- HANYA SATU angka utama, dan angkanya dibulatkan (bukan empat desimal);
- bahasa sehari-hari: tanpa istilah teknis (variance, bridge, MoM);
- narasi berasal dari data nyata (angka cocok dengan mart);
- periode kartu dipakai (dari/sampai/tahun);
- lapisan kedua (detail + rumus) tersedia terpisah;
- kartu tak dikenal -> 404, format periode salah -> 422.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import buat_app
from app.api_jelaskan import sen, angka, arah

KARTU_BERDATA = ["margin_bulanan", "ringkasan", "elemen_op_margin",
                 "margin_bridge", "days_of_cover", "stok"]


@pytest.fixture(scope="module")
def klien(engine):
    return TestClient(buat_app(engine))


# ---------------------------------------------------------------- pembulatan
def test_pembulatan_ramah_orang_awam():
    # contoh dari pengguna: -1,89 dibicarakan sebagai "sekitar 2"
    assert sen(-1.89) == "sekitar 2 sen"
    assert sen(-2.17) == "sekitar 2 sen"
    assert sen(-3.23) == "sekitar 3 sen"
    assert sen(0.37) == "0,4 sen"          # di bawah 1 sen: satu desimal
    assert sen(None) == "tidak tersedia"
    # tidak pernah empat desimal
    for n in (1.234567, -12.98765, 0.049):
        assert "000" not in sen(n)


def test_format_angka_indonesia():
    assert angka(13.0, 1) == "13,0"
    assert angka(2795.1, 0) == "2.795"
    assert arah(5) == "naik" and arah(-5) == "turun"
    assert arah(0.01) == "praktis tidak berubah"


# ---------------------------------------------------------------- struktur
@pytest.mark.parametrize("kartu", KARTU_BERDATA)
def test_struktur_jelaskan(klien, kartu):
    d = klien.get(f"/api/jelaskan/{kartu}").json()
    for kunci in ("judul", "ada_data", "what", "so_what", "now_what",
                  "analogi", "cara_baca", "detail", "rumus"):
        assert kunci in d, kunci
    assert d["what"], "kesimpulan tidak boleh kosong"
    assert d["now_what"], "harus ada tindakan, bukan hanya temuan"
    assert d["analogi"]
    assert d["rumus"].strip()          # rujukan teknis tetap tersedia


def test_hanya_satu_angka_utama(klien):
    d = klien.get("/api/jelaskan/margin_bulanan").json()
    assert isinstance(d["angka_utama"], dict)
    assert set(d["angka_utama"]) == {"nilai", "label"}
    assert d["angka_utama"]["nilai"].strip()


def test_bahasa_sehari_hari_tanpa_istilah_teknis(klien):
    d = klien.get("/api/jelaskan/margin_bulanan").json()
    teks = " ".join(d["what"] + d["so_what"] + d["now_what"]
                    + [d["cara_baca"], d["analogi"]]).lower()
    for istilah in ("variance", "bridge", "mom", "delta", "volatilitas"):
        assert istilah not in teks
    assert "target" in teks


def test_tidak_ada_angka_empat_desimal(klien):
    d = klien.get("/api/jelaskan/margin_bulanan").json()
    teks = " ".join(d["what"] + d["so_what"] + d["now_what"])
    import re
    assert not re.search(r"\d,\d{3,}", teks), teks


# ---------------------------------------------------------------- isi & data
def test_margin_bulanan_narasi_sesuai_data(klien):
    """2025: Okt-Des di bawah target -> angka utama = jumlah bulan."""
    d = klien.get("/api/jelaskan/margin_bulanan",
                  params={"dari": "2025-01", "sampai": "2025-12"}).json()
    assert d["angka_utama"]["nilai"] == "3 bulan"
    assert "Okt-25" in d["angka_utama"]["label"]
    assert any("di bawah" in w for w in d["what"])
    # penyebab disebut dengan arah yang jelas
    assert any("harga acuan" in s for s in d["so_what"])
    assert any(kata in " ".join(d["so_what"]).lower() for kata in ("naik", "turun"))
    # tindakan menyebut pilihan konkret
    now = " ".join(d["now_what"]).lower()
    assert "harga beli" in now
    assert "pemasok" in now or "target" in now


def test_margin_bulanan_periode_dipakai(klien):
    d = klien.get("/api/jelaskan/margin_bulanan",
                  params={"dari": "2026-01", "sampai": "2026-10"}).json()
    # hanya bulan 2026 yang dibicarakan
    teks = " ".join(d["what"] + d["so_what"])
    assert "26" in teks and "-25" not in teks


def test_perubahan_target_diungkap_jujur(klien):
    """Pertanyaan 'kenapa target Maret 16?' harus dijawab dari sumber data."""
    d = klien.get("/api/jelaskan/margin_bulanan",
                  params={"dari": "2025-01", "sampai": "2025-12"}).json()
    catatan = " ".join(d["catatan"])
    assert "Target berubah" in catatan
    assert "tabel target margin" in catatan
    # mis. Mar-25 6,0 -> 16,0 (pola 6/16 yang dikhawatirkan pengguna)
    assert "Mar-25" in catatan and "16,0" in catatan


def test_sumber_target_tidak_ditebak(klien):
    d = klien.get("/api/jelaskan/margin_bulanan").json()
    assert "tabel target margin" in d.get("sumber_target", "")


def test_ringkasan_memakai_tahun(klien):
    d = klien.get("/api/jelaskan/ringkasan", params={"tahun": 2025}).json()
    assert "2025" in d["angka_utama"]["label"]
    assert any("2025" in w for w in d["what"])


def test_days_of_cover_menyebut_hari_dan_batas_aman(klien):
    d = klien.get("/api/jelaskan/days_of_cover",
                  params={"dari": "2025-01", "sampai": "2025-12"}).json()
    assert "hari" in d["angka_utama"]["nilai"]
    teks = " ".join(d["what"])
    assert "batas aman" in teks


def test_lapisan_kedua_tersedia_terpisah(klien):
    d = klien.get("/api/jelaskan/margin_bulanan").json()
    assert d["detail"], "detail angka harus tersedia untuk pertanyaan lanjutan"
    tabel = d["detail"][0]
    assert tabel["kolom"] and tabel["baris"]
    assert any("Penyebab" in t["judul"] for t in d["detail"])


# ---------------------------------------------------------------- kartu lain
def test_kartu_lain_memakai_kerangka_sama(klien):
    d = klien.get("/api/jelaskan/alarm").json()
    assert d["what"] and d["now_what"]
    assert "Kartu ini menjawab" in d["what"][0]


def test_kartu_tidak_dikenal_404(klien):
    r = klien.get("/api/jelaskan/kartu_ngawur")
    assert r.status_code == 404
    assert "tidak dikenal" in r.json()["detail"]


def test_periode_salah_422(klien):
    assert klien.get("/api/jelaskan/margin_bulanan?dari=2026-13").status_code == 422
    assert klien.get("/api/jelaskan/margin_bulanan?dari=2026-06&sampai=2026-01"
                     ).status_code == 422
