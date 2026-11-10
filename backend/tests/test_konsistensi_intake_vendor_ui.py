"""Kontrak sumber kartu konsistensi intake vendor (Intake Analisis).

Menjaga agar kartu baru tidak kehilangan: filter tanggal persis, Refresh di
baris filter, ekspor Excel beberapa sheet, rincian hari/bulan kosong, dan
dokumentasi/health/metrik yang menyertainya.
"""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]


def _teks(rel: str) -> str:
    return (AKAR / rel).read_text(encoding="utf-8")


def test_kartu_baru_terpasang_di_halaman_analisis():
    s = _teks("frontend/src/pages/Analisis.tsx")
    assert "function KartuKonsistensiIntake()" in s
    assert 'judul="Konsistensi intake harian vendor"' in s
    assert 'idMetrik="konsistensi_intake_vendor"' in s
    assert "const url = `/api/kartu/konsistensi-intake-vendor" in s
    assert 'queryKey: ["konsistensi-intake-vendor", url]' in s
    assert "useQueryKartu({" in s
    assert "urlEkspor={url}" in s
    assert "anak={<KartuKonsistensiIntake />}" in s


def test_filter_tanggal_persis_dan_refresh_di_baris_filter():
    s = _teks("frontend/src/pages/Analisis.tsx")
    assert "function PilihRentangTanggal(" in s
    assert '<input type="date"' in s
    assert 'aria-label="Dari tanggal"' in s
    assert 'aria-label="Sampai tanggal"' in s
    assert "aksi={<TombolRefreshKartu />}" in s
    assert 'data-uji="rentang-tanggal-konsistensi"' in s
    # Tidak memakai PilihRentangBulan untuk kartu ini.
    blok = s[s.index("function KartuKonsistensiIntake()"):
             s.index("export default function Analisis()")]
    assert "PilihRentangBulan" not in blok
    # Rentang bulanan dari backend berbentuk YYYY-MM, jadi tidak boleh
    # dilewatkan begitu saja ke fmtTanggal (butuh YYYY-MM-DD).
    assert "const fmtRentang = (nilai: string)" in blok
    assert "nilai?.length === 7 ? nilai : fmtTanggal(nilai)" in blok


def test_rincian_hari_bulan_kosong_dan_vendor_paling_sering_tampil():
    s = _teks("frontend/src/pages/Analisis.tsx")
    assert 'data-uji="tabel-konsistensi-vendor"' in s
    assert "Hari kosong ({b.jumlah_hari_kosong})" in s
    assert "Bulan kosong ({b.jumlah_bulan_kosong})" in s
    assert "Bulan lengkap (setiap hari kalender ada intake)" in s
    assert "b.hari_kosong_terpotong" in s
    assert "… seluruhnya ada di Excel" in s
    assert "Vendor paling sering masuk:" in s
    assert "paling sering" in s
    assert "h.sepi_pabrik" in s
    assert "Rentang harian tanpa putus" in s
    assert 'id="analisis-09"' in s
    # Grafik peringkat memakai batang berdiri (layout horizontal di Recharts).
    assert '<BarChart data={grafikTeratas} layout="horizontal"' in s


def test_backend_endpoint_dan_enam_sheet_ekspor():
    s = _teks("backend/app/api_analisis.py")
    assert '@router.get("/kartu/konsistensi-intake-vendor")' in s
    assert "def respon_xlsx_banyak(" in s
    assert "def _xlsx_konsistensi(" in s
    for nama in ("Rekap vendor", "Hari kosong", "Bulan kosong",
                 "Bulan lengkap", "Hari sepi pabrik", "Metode"):
        assert f'("{nama}"' in s
    assert "_ringkas_konsistensi(hasil)" in s
    assert "MAKS_HARI" in s
    assert "_tanggal_iso" in s


def test_modul_murni_dan_keputusan_pemilik_terkunci():
    s = _teks("backend/app/core/konsistensi_intake.py")
    assert "MAKS_HARI = 731" in s
    assert '"hari": "kalender"' in s
    assert '"urutan": "jumlah_hari_masuk"' in s
    assert "termasuk Sabtu/Minggu/libur" in s
    assert "def rentang_harian_terpanjang(" in s
    assert "def rentang_bulan_terpanjang(" in s
    assert "def hitung_konsistensi(" in s
    assert "def daftar_hari(" in s


def test_i18n_health_metrik_dan_dokumentasi():
    assert '"Konsistensi intake harian vendor": "Vendor daily intake consistency"' \
        in _teks("frontend/src/i18n.tsx")
    assert '"kartu-konsistensi-intake-vendor"' in _teks("backend/app/main.py")
    metrik = _teks("backend/semantic/metrics.yaml")
    assert "konsistensi_intake_vendor:" in metrik
    assert "SEMUA HARI KALENDER" in metrik
    cara = _teks("docs/CARA_MENJALANKAN.md")
    assert "## 3o. Konsistensi intake harian/bulanan vendor" in cara
    assert "/api/kartu/konsistensi-intake-vendor" in cara
    assert "6 sheet" in cara
    serah = _teks("docs/SERAH_TERIMA.md")
    assert "**Kartu konsistensi intake harian/bulanan vendor ditambahkan**" in serah
