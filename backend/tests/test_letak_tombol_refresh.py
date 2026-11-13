"""Tombol Refresh kartu harus mengikuti kontrol periode yang disegarkannya.

Perubahan ini murni tata letak React: `KartuMuatSaatDiminta` menyediakan aksi
refresh lewat konteks, lalu `TombolRefreshKartu` merender tombol itu di baris
filter. Tes sumber ini menjaga agar tombol tidak kembali ke header kartu
berperiode dan kartu tanpa kontrol periode tetap punya Refresh di header.
"""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]


def _teks(rel: str) -> str:
    return (AKAR / rel).read_text(encoding="utf-8")


def test_kartu_menyediakan_slot_refresh_di_baris_periode():
    """Tombol filter memakai aksi kartu induk; header hanya fallback."""
    bersama = _teks("frontend/src/bersama.tsx")

    assert 'letakRefresh?: "header" | "filter"' in bersama
    assert "export function TombolRefreshKartu" in bersama
    assert 'konteks.letakRefresh !== "filter"' in bersama
    assert 'letakRefresh === "header" && (' in bersama
    assert "letakRefresh,\n    refresh: { jalankan: refresh" in bersama
    assert "aksi?: ReactNode" in bersama
    assert "      {aksi}\n" in bersama

    kamus = _teks("frontend/src/i18n.tsx")
    assert '"Refresh periode ini": "Refresh this period"' in kamus
    assert '"Preview lokal bila tersedia · pilih periode, lalu tekan Refresh di sampingnya"' in kamus


def test_intake_analisis_refresh_di_samping_periode():
    """10 kartu berperiode memindahkan Refresh; semua kontrol ikut filter."""
    analisis = _teks("frontend/src/pages/Analisis.tsx")

    assert analisis.count('letakRefresh="filter"') == 10
    # 3 PilihPeriode (tahun) + 3 PilihRentangBulan (Dari/Sampai bulan)
    # + 2 PilihRentangTanggal (konsistensi intake vendor & daftar intake
    #   terakhir yang kini punya filter records).
    assert analisis.count("aksi={<TombolRefreshKartu />}") == 8
    # Pilihan tahun+bulan pada Margin harian tidak memakai komponen pemilih bersama.
    assert "</select>\n          <TombolRefreshKartu />" in analisis
    assert "TombolRefreshKartu,\n} from \"../bersama\"" in analisis

    # "Daftar intake terakhir" sekarang punya Periode records + filter vendor,
    # jadi Refresh miliknya ikut berada di baris filter.
    awal = analisis.rindex('judul="Daftar intake terakhir"')
    assert 'letakRefresh="filter"' in analisis[awal - 200:awal + 200]


def test_margin_performance_refresh_di_samping_periode():
    """Kartu dengan rentang bulan / tombol tahun memakai slot filter."""
    ringkasan = _teks("frontend/src/pages/Ringkasan.tsx")

    assert ringkasan.count('letakRefresh="filter"') == 3
    assert ringkasan.count("aksi={<TombolRefreshKartu />}") == 2
    assert '<TombolRefreshKartu className="ml-auto" />' in ringkasan
    # Keadaan galat / data kosong tidak boleh membuat kartu kehilangan Refresh.
    assert ringkasan.count('<TombolRefreshKartu className="mt-2" />') == 2

    # Dua kartu tanpa kontrol periode tetap memakai tombol header.
    awal = ringkasan.index('judul="Angka kunci Margin Performance"')
    assert 'letakRefresh="filter"' not in ringkasan[awal - 120:awal + 120]
    awal = ringkasan.index('judul="Perlu perhatian hari ini"')
    assert 'letakRefresh="filter"' not in ringkasan[awal - 120:awal + 120]


def test_peta_intake_tetap_punya_refresh_saat_periode_disembunyikan():
    """Mode 'Sentra produksi' menyembunyikan input bulan, bukan tombol Refresh."""
    peta = _teks("frontend/src/pages/PetaIntake.tsx")

    assert "aksi={<TombolRefreshKartu />}" in peta
    assert peta.count("<TombolRefreshKartu />") == 2
    assert "<TombolRefreshKartu />\n              </>" in peta
