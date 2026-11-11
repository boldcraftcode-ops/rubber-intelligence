"""Sumber UI: modul Master Data → SCDF, hierarki baca saja."""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
APP = (AKAR / "frontend/src/App.tsx").read_text(encoding="utf-8")
HALAMAN = (AKAR / "frontend/src/pages/MasterScdf.tsx").read_text(encoding="utf-8")
I18N = (AKAR / "frontend/src/i18n.tsx").read_text(encoding="utf-8")
MAIN = (AKAR / "backend/app/main.py").read_text(encoding="utf-8")
METRIK = (AKAR / "backend/semantic/metrics.yaml").read_text(encoding="utf-8")
DOK = (AKAR / "docs/CARA_MENJALANKAN.md").read_text(encoding="utf-8")
RIWAYAT = (AKAR / "docs/SERAH_TERIMA.md").read_text(encoding="utf-8")


def test_modul_terdaftar_di_menu_master_data():
    assert 'import MasterScdf from "./pages/MasterScdf";' in APP
    assert '{ id: "scdf", label: "SCDF", ikon: "▣", grup: "master" }' in APP
    assert '{tab === "scdf" && <MasterScdf />}' in APP
    assert '"SCDF": "SCDF"' in I18N
    assert '"Cari lokasi SCDF": "Search SCDF location"' in I18N
    assert "master-scdf-hierarki" in MAIN
    assert "master-scdf-pencarian" in MAIN
    assert "pasang_router_master_scdf(app, ambil_session)" in MAIN
    assert "  master_scdf:" in METRIK
    assert "Kolom pencarian GET" in METRIK
    assert "## 3r. Master Data → SCDF" in DOK
    assert "**Kolom pencarian**" in DOK
    assert "GET /api/master/scdf/cari" in DOK
    assert "berikan kolom searching" in RIWAYAT


def test_hierarki_empat_tingkat_dan_endpoint_baca_saja():
    assert 'data-uji="modul-master-scdf"' in HALAMAN
    assert 'data-uji="ringkasan-scdf"' in HALAMAN
    assert 'data-uji="pohon-scdf"' in HALAMAN
    assert 'data-uji="rincian-scdf"' in HALAMAN
    assert "/api/master/scdf/ringkasan" in HALAMAN
    assert "/api/master/scdf/pohon" in HALAMAN
    assert "/api/master/scdf/detail" in HALAMAN
    assert "/api/master/scdf/cari" in HALAMAN
    assert "BERIKUTNYA" in HALAMAN
    assert "provinsi: \"kabupaten\"" in HALAMAN
    assert "kecamatan: \"desa\"" in HALAMAN
    assert "Jumlah anak" in HALAMAN
    assert "Baris SCDF" in HALAMAN
    assert "CabangScdf" in HALAMAN
    assert "useMutation" not in HALAMAN
    assert "kirimMetode" not in HALAMAN
    assert "urlEkspor" not in HALAMAN
    assert "<form" not in HALAMAN
    assert 'type="file"' not in HALAMAN
    for tombol in ("Tambah", "Edit", "Hapus", "Simpan", "Impor"):
        assert f">{tombol}<" not in HALAMAN
    assert 'method: "POST"' not in HALAMAN
    assert 'method: "PUT"' not in HALAMAN
    assert 'method: "DELETE"' not in HALAMAN


def test_kolom_nama_normalized_status_dan_belum_dipetakan():
    assert "idMetrik=\"master_scdf\"" in HALAMAN
    assert "Provinsi → Kabupaten/Kota → Kecamatan → Desa/Kelurahan" in HALAMAN
    assert "Provinsi norm" in HALAMAN
    assert "Kabupaten norm" in HALAMAN
    assert "Kecamatan norm" in HALAMAN
    assert "Desa norm" in HALAMAN
    assert "Status Provinsi" in HALAMAN
    assert "Belum dipetakan" in HALAMAN
    assert "Terpetakan" in HALAMAN
    assert "b.provinsi_norm" in HALAMAN
    assert "b.kabupaten_norm" in HALAMAN
    assert "b.kecamatan_norm" in HALAMAN
    assert "b.desa_norm" in HALAMAN
    assert "baca saja" in HALAMAN.lower()
    assert "tidak ditebak" in HALAMAN.lower()


def test_kolom_pencarian_baca_saja():
    assert 'data-uji="pencarian-scdf"' in HALAMAN
    assert 'data-uji="input-pencarian-scdf"' in HALAMAN
    assert 'data-uji="status-pencarian-scdf"' in HALAMAN
    assert "hasil-pencarian-scdf" in HALAMAN
    assert "Cari lokasi SCDF" in HALAMAN
    assert "Hasil pencarian SCDF" in HALAMAN
    assert "Mode pencarian" in HALAMAN
    assert "4 nama resmi" in HALAMAN
    assert "4 normalized key" in HALAMAN
    assert "status Provinsi" in HALAMAN
    assert "Belum dipetakan" in HALAMAN
    assert "traceability_wilayah" in HALAMAN
    assert "useEffect" in HALAMAN
    assert "setTeksCari" in HALAMAN
    assert "setKataCari" in HALAMAN
    assert "hapusCari" in HALAMAN
    assert "cariAktif" in HALAMAN
    assert "paramsCari" in HALAMAN
    assert "q: kata, cari: kata" in HALAMAN
    assert "enabled: cariAktif" in HALAMAN
    assert "enabled: Boolean(detail) && !cariAktif" in HALAMAN
    assert "dataTabel" in HALAMAN
    assert "offsetAktif" in HALAMAN
    assert "setOffsetAktif" in HALAMAN
    assert 'type="text"' in HALAMAN
    assert "autoComplete=\"off\"" in HALAMAN
    assert "useMutation" not in HALAMAN
    assert "kirimMetode" not in HALAMAN
    assert "urlEkspor" not in HALAMAN
    assert "<form" not in HALAMAN
    assert 'type="file"' not in HALAMAN
    for tombol in ("Tambah", "Edit", "Hapus", "Simpan", "Impor"):
        assert f">{tombol}<" not in HALAMAN
    assert 'method: "POST"' not in HALAMAN
    assert 'method: "PUT"' not in HALAMAN
    assert 'method: "DELETE"' not in HALAMAN
