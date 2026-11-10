"""Kontrak sumber: crosswalk Provinsi resmi tidak boleh kembali ke teks lama."""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]


def _baca(path: str) -> str:
    return (AKAR / path).read_text(encoding="utf-8")


def test_ui_collector_tidak_lagi_mengatakan_provinsi_dinonaktifkan():
    teks = _baca("frontend/src/pages/MasterCollector.tsx")
    assert "crosswalk resmi" in teks
    assert "nilai dari intake tidak dipakai" in teks
    assert "File SCDF yang tersedia tidak memiliki kolom Provinsi" not in teks
    assert "sehingga Provinsi dinonaktifkan" not in teks


def test_backend_collector_tidak_lagi_menganggap_id_aux_tanpa_provinsi():
    teks = _baca("backend/app/api_collector.py")
    assert "crosswalk resmi" in teks
    assert "Provinsi tidak ditemukan pada crosswalk resmi SCDF" in teks
    assert "ID_AUX saat ini tidak memiliki data provinsi" not in teks
    assert "referensi SCDF tidak menyediakan kolom Provinsi" not in teks
    assert "kolom Provinsi dibiarkan kosong sampai crosswalk resmi tersedia" not in teks


def test_snapshot_crosswalk_dapat_diaudit():
    csv = _baca("backend/data/crosswalk_provinsi_id_aux.csv")
    baris = [x for x in csv.splitlines() if x.strip()]
    assert baris[0].startswith("kabupaten_norm,provinsi,")
    assert len(baris) == 488  # header + 487 kabupaten/kota termapping
    assert "BANJAR," not in csv
    dok = _baca("backend/data/CROSSWALK_PROVINSI.md")
    assert "Keputusan Mendagri No. 100.1.1-6117 Tahun 2022" in dok
    assert "487" in dok and "494" in dok
    assert "BANJAR" in dok
    assert (AKAR / "backend/data/sumber_crosswalk/LICENSE.txt").exists()
    assert (AKAR / "backend/data/sumber_crosswalk/provinces.csv").exists()
    assert (AKAR / "backend/data/sumber_crosswalk/regencies.csv").exists()


def test_dokumentasi_dan_health_mencatat_fitur_baru():
    assert "## 3n. Crosswalk Provinsi resmi" in _baca("docs/CARA_MENJALANKAN.md")
    assert "available: true" in _baca("docs/CARA_MENJALANKAN.md")
    assert "Crosswalk Provinsi resmi dipasang" in _baca("docs/SERAH_TERIMA.md")
    assert "dropdown Provinsi dinonaktifkan" not in _baca("docs/SERAH_TERIMA.md")
    assert '"scdf-provinsi-crosswalk"' in _baca("backend/app/main.py")
