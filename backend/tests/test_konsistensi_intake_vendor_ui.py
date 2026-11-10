"""Kontrak sumber kartu Ringkasan Vendor (Intake Analisis).

Menjaga agar perubahan format `Intake-2025_Ringkasan-Vendor.xlsx` tidak
kehilangan: filter tanggal persis, Refresh di baris filter, tiga tabel,
chart lama yang dihapus, ekspor 3 sheet + 3 chart native, dokumen/metrik,
health, dan i18n yang menyertainya.
"""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]


def _teks(rel: str) -> str:
    return (AKAR / rel).read_text(encoding="utf-8")


def _blok_kartu() -> str:
    s = _teks("frontend/src/pages/Analisis.tsx")
    return s[s.index("function KartuKonsistensiIntake()"):
             s.index("export default function Analisis()")]


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
    blok = _blok_kartu()
    assert "PilihRentangBulan" not in blok
    # Rentang bulanan dari backend berbentuk YYYY-MM, jadi tidak boleh
    # dilewatkan begitu saja ke fmtTanggal (butuh YYYY-MM-DD).
    assert "const fmtRentang = (nilai: string)" in blok
    assert "nilai?.length === 7 ? nilai : fmtTanggal(nilai)" in blok
    assert "batasData={d?.batas_data}" in blok
    assert "pakai batas tiket" in _teks("frontend/src/pages/Analisis.tsx")


def test_tiga_tabel_dan_chart_lama_dihapus():
    blok = _blok_kartu()
    for nama in ("tabel-ringkasan-vendor", "tabel-vendor-per-bulan",
                 "tabel-vendor-harian"):
        assert f'data-uji="{nama}"' in blok
    assert "1. Ringkasan Vendor" in blok
    assert "2. Vendor per Bulan" in blok
    assert "3. Vendor Harian" in blok
    for teks in ("Total Trip", "% Trip", "Hari Aktif",
                 "Rata² Trip/Hari Operasional", "Rata² Trip/Bulan",
                 "Dry (kg)", "TOTAL", "Rata² / hari"):
        assert teks in blok
    # Chart lama benar-benar hilang dari kartu ini.
    assert "AlatGrafik" not in blok
    assert "BarChart" not in blok
    assert 'id="analisis-09"' not in blok
    assert "grafikTeratas" not in blok
    assert "kodeTerbuka" not in blok
    # Periode panjang: ringkas di layar, `rinci=1` untuk matriks penuh.
    assert 'const modeRingkas = d?.periode?.mode_rincian === "ringkas"' in blok
    assert 'data-uji="mode-ringkas-konsistensi"' in blok
    assert 'data-uji="rekap-bulan-konsistensi"' in blok
    assert 'data-uji="rentang-hari-kosong"' in blok
    assert "metode.minimalisir" in blok
    assert "… seluruhnya ada di Excel" in blok
    assert "h.sepi_pabrik" in blok
    assert "Di luar data" in blok
    assert "YYYY-MM-DD" in blok
    assert "rinci=1" in blok
    assert "qRinci" in blok
    assert "tampilkan semua" in blok
    assert "tanpa pengelompokan sisa" in blok
    assert "3 sheet" in blok and "3 chart Excel" in blok


def test_backend_endpoint_dan_tiga_sheet_ekspor():
    s = _teks("backend/app/api_analisis.py")
    assert '@router.get("/kartu/konsistensi-intake-vendor")' in s
    assert "def respon_xlsx_banyak(" in s
    assert "def _xlsx_ringkasan_vendor(" in s
    for nama in ("Ringkasan Vendor", "Vendor per Bulan", "Vendor Harian"):
        assert f'create_sheet("{nama}")' in s
    for nama in ("Rekap vendor", "Hari kosong", "Rentang hari kosong",
                 "Bulan kosong", "Bulan lengkap", "Hari sepi pabrik",
                 "Metode"):
        assert f'("{nama}"' not in s
    assert 'create_sheet("Master Data' not in s
    assert "def _ringkas_konsistensi(" not in s
    assert "def _xlsx_konsistensi(" not in s
    assert "ringkas_untuk_layar(hasil)" in s
    assert "hitung_ringkasan_vendor(" in s
    assert "MAKS_HARI" in s and "MAKS_BULAN" in s
    assert "_tanggal_iso" in s
    assert "_ke_tanggal_db" in s
    assert "batas_data=batas_data" in s
    assert "rinci=1" in s
    assert "731 hari sudah" in s
    assert "openpyxl.Workbook(write_only=True)" in s
    assert "ColorScaleRule" in s
    assert "BarChart()" in s and "LineChart()" in s


def test_modul_murni_dan_keputusan_pemilik_terkunci():
    s = _teks("backend/app/core/ringkasan_vendor.py")
    assert "MAKS_HARI = 366 * 100" in s
    assert "AMBANG_RINGKAS_HARI = 366" in s
    assert "MAKS_BULAN = 1_200" in s
    assert '"hari": "kalender"' in s
    assert '"urutan": "jumlah_trip"' in s
    assert "termasuk Sabtu/Minggu/libur" in s
    assert "def daftar_hari(" in s
    assert "def daftar_bulan(" in s
    assert "def hitung_ringkasan_vendor(" in s
    assert "def ringkas_untuk_layar(" in s
    assert '"mode_rincian": "ringkas"' in s
    assert '"minimalisir": "Batas 731 hari dihapus' in s
    assert "Trip = Ticket No unik" in s
    assert "Rata² Trip/Bulan" in s
    assert "semua hari kalender" in s


def test_i18n_health_metrik_dan_dokumentasi():
    i18n = _teks("frontend/src/i18n.tsx")
    assert '"Konsistensi intake harian vendor": "Vendor daily intake consistency"' \
        in i18n
    for k in ("Ringkasan Vendor", "Vendor per Bulan", "Vendor Harian",
              "Total Trip", "Hari Aktif", "Dry (kg)"):
        assert f'"{k}"' in i18n
    health = _teks("backend/app/main.py")
    assert '"kartu-konsistensi-intake-vendor"' in health
    assert '"kartu-ringkasan-vendor-trip"' in health
    metrik = _teks("backend/semantic/metrics.yaml")
    assert "konsistensi_intake_vendor:" in metrik
    assert "SEMUA HARI KALENDER" in metrik
    assert "Batas 731 hari dihapus" in metrik
    assert "Trip dihitung" in metrik and "Ticket No unik" in metrik
    assert "3 sheet" in metrik and "3 chart Excel native" in metrik
    cara = _teks("docs/CARA_MENJALANKAN.md")
    assert "## 3o. Laporan Ringkasan Vendor" in cara
    assert "/api/kartu/konsistensi-intake-vendor" in cara
    assert "3 sheet" in cara and "3 chart Excel native" in cara
    assert "731 hari" in cara and "sudah dihapus" in cara
    assert "rinci=1" in cara
    assert "pengelompokan sisa vendor" in cara
    serah = _teks("docs/SERAH_TERIMA.md")
    assert "**Kartu konsistensi intake harian/bulanan vendor ditambahkan**" \
        in serah
    assert "**Batas 731 hari dihapus dari kartu konsistensi intake**" in serah
    assert "Intake-2025_Ringkasan-Vendor.xlsx" in serah
    assert "3 sheet + 3 chart Excel native" in serah
