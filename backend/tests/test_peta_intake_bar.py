"""Bar intake per provinsi pada kartu 'Sebaran Intake per Provinsi Indonesia'.

Perubahan ini murni presentasi SVG di frontend: bar oranye diletakkan pada
titik tengah cincin poligon terbesar tiap provinsi yang punya intake. Tidak ada
endpoint, agregasi, tabel, atau data sumber yang berubah.
"""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]


def _teks(rel: str) -> str:
    return (AKAR / rel).read_text(encoding="utf-8")


def test_peta_menggambar_bar_hanya_untuk_intake_positif_dan_toggle_aktif():
    """Bar muncul di lapisan intake, bisa disembunyikan, dan tidak hardcoded."""
    peta = _teks("frontend/src/pages/PetaIntake.tsx")

    assert 'const WARNA_BAR = "#EA580C";' in peta
    assert "const [tampilBar, setTampilBar] = useState(true);" in peta
    assert "Bar per wilayah" in peta
    assert 'data-testid="bar-intake"' in peta
    assert 'mode === "intake" && tampilBar && barRows.length > 0' in peta
    assert "if (!row || row.kg_total <= 0) return [];" in peta
    assert "<rect" in peta and "<circle" in peta

    # Toggle tidak boleh menghilangkan Refresh pada mode tanpa input periode.
    assert peta.count("<TombolRefreshKartu />") == 2
    assert "aksi={<TombolRefreshKartu />}" in peta


def test_pusat_bar_dihitung_dari_geometri_dan_skala_logaritmik():
    """Pusat bar mengikuti GeoJSON; tinggi bar tidak linear agar kecil terlihat."""
    peta = _teks("frontend/src/pages/PetaIntake.tsx")

    assert "type Titik = [number, number];" in peta
    assert "function cincinTerbesar(" in peta
    assert "function pusatPoligon(" in peta
    assert "function luasPoligon(" in peta
    assert "cincinTerbesar(feature.geometry, project)" in peta
    assert "new Map<string, Titik>()" in peta
    assert "pusat.set(feature.properties.PROVINSI" in peta
    assert "proyeksi?.paths.get(feature.properties.PROVINSI)" in peta
    assert "Math.log10" in peta
    assert "TINGGI_BAR_MIN" in peta and "TINGGI_BAR_MAKS" in peta
    assert "skala logaritmik" in peta
    assert "skalaBar(row.kg_total)" in peta

    # Warna bar sengaja beda dari skala biru choropleth.
    assert 'const WARNA_BERURUT = ["#DBEAFE", "#93C5FD", "#3B82F6", "#1D4ED8", "#172554"];' in peta
    assert "#EA580C" not in peta.split("WARNA_BERURUT")[1].split("];")[0]


def test_legenda_dan_catatan_tidak_mengklaim_bar_sebagai_angka_pasti():
    """Angka pasti tetap mengacu ke tooltip/ekspor, bukan tinggi bar."""
    peta = _teks("frontend/src/pages/PetaIntake.tsx")

    assert "Bar intake" in peta
    assert "Provinsi ber-intake:" in peta
    assert "jumlahBerintake = barRows.length" in peta
    assert "Angka pasti tetap ada pada tooltip provinsi." in peta
    assert "bar hanya muncul pada provinsi yang cocok dengan batas peta" in peta
    assert fmt_angka_masih_dipakai(peta)


def fmt_angka_masih_dipakai(peta: str) -> bool:
    return "fmtAngka(bar.kg, 0)" in peta and "fmtAngka(value, 0)" in peta


def test_kartu_induk_dan_dokumentasi_menyebut_bar():
    """Keterangan kartu dan panduan pemakaian mengikuti perubahan UI."""
    analisis = _teks("frontend/src/pages/Analisis.tsx")
    cara = _teks("docs/CARA_MENJALANKAN.md")
    serah = _teks("docs/SERAH_TERIMA.md")

    assert "bar oranye muncul pada provinsi yang punya intake" in analisis
    assert "## 3k. Bar intake pada peta provinsi" in cara
    assert "Bar per wilayah" in cara
    assert "indonesia-provinsi.geojson" in cara
    assert "skala logaritmik" in cara
    assert "| 2026-11-08 | **Bar intake ditambahkan di peta provinsi**" in serah
