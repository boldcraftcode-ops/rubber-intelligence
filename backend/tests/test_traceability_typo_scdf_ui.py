"""Sumber UI: panel deteksi salah ketik SCDF di detail Supplier Actors."""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]


def _teks() -> str:
    return (AKAR / "frontend/src/pages/Traceability.tsx").read_text(encoding="utf-8")


def test_panel_deteksi_scdf_ada_di_mode_edit():
    teks = _teks()
    assert "Deteksi potensi salah ketik dari SCDF" in teks
    assert "/origin-typo-check" in teks
    assert '["traceability-origin-typo-scdf"' in teks
    assert 'typoScdf.data?.status === "potensi_salah_ketik"' in teks
    assert 'typoScdf.data?.status === "cocok"' in teks
    assert "bukan rekomendasi pembelian terdahulu" not in teks
    assert "Skor kemiripan" in teks


def test_tombol_pakai_hanya_mengisi_dropdown_bukan_menyimpan():
    teks = _teks()
    assert "const pakaiKandidatScdf = (kandidat: KandidatScdf) => {" in teks
    blok = teks.split("const pakaiKandidatScdf", 1)[1].split(
        "const pakaiRekomendasiHistoris", 1)[0]
    assert "setTargetRegency(kandidat.kabupaten_norm)" in blok
    assert "setTargetDistrict(kandidat.kecamatan_norm)" in blok
    assert "setTargetSubdistrict(kandidat.desa_norm)" in blok
    assert "simpanKoreksi.mutate" not in blok
    assert "onClick={() => pakaiKandidatScdf(kandidat)}>Pakai</button>" in teks
    assert "Klik Pakai hanya mengisi pilihan" not in teks


def test_koreksi_lintas_induk_scdf_eksplisit_dan_intake_tidak_diubah():
    teks = _teks()
    assert "target_kabupaten_norm: targetRegency || origin.source_key.kabupaten_norm" in teks
    assert "Induk SCDF:" in teks
    assert "berbeda dari Kabupaten/Kota sumber" in teks
    assert "intake asli tidak diubah" in teks
    assert "kembaliKeIndukSumber" in teks
    assert "Kembali ke induk sumber" in teks


def test_rekomendasi_historis_dan_simpan_eksplisit_tetap_ada():
    teks = _teks()
    assert "Rekomendasi dari intake tahun sebelumnya" in teks
    assert "pakaiRekomendasiHistoris(recommendation)" in teks
    assert "onClick={() => simpanKoreksi.mutate({ origin, target: targetSubdistrict })}" in teks
    assert "onClick={tutupEditOrigin}>Batal</button>" in teks
    assert "mulaiEditOrigin(origin)" in teks
    assert 'queryKey: ["traceability-origin-typo-scdf"]' in teks


def test_dropdown_menjaga_kandidat_yang_belum_masuk_opsi():
    teks = _teks()
    assert "const opsiDistrict: any[] = districtOptions.data?.options ?? [];" in teks
    assert "const opsiSubdistrict: any[] = subdistrictOptions.data?.options ?? [];" in teks
    assert "scdfDipakai?.kecamatan_norm === targetDistrict" in teks
    assert "scdfDipakai?.desa_norm === targetSubdistrict" in teks


def test_caption_panjang_yang_diminta_dihapus_tidak_ada_lagi():
    teks = _teks()
    assert "Belum ada lokasi cocok dari intake tahun sebelumnya" not in teks
    assert "Persentase adalah porsi volume Dry historis" not in teks
    assert "Mohon verifikasi sebelum menyimpan" not in teks
    assert "Membandingkan ejaan District dan Sub-district sumber" not in teks
    assert "Skor kemiripan bukan probabilitas" not in teks
    assert "Tombol Pakai hanya mengisi pilihan" not in teks
    assert "Intake asli tetap tidak diubah" not in teks
    assert "Deteksi ini membandingkan ejaan dengan SCDF" not in teks
    assert "typoScdf.data?.basis" not in teks
    assert "typoScdf.data?.catatan" not in teks
    # Yang bukan caption tetap bertahan.
    assert "Rekomendasi dari intake tahun sebelumnya" in teks
    assert "Deteksi potensi salah ketik dari SCDF" in teks
    assert "Skor kemiripan" in teks
