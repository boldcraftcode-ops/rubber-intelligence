"""Sumber UI: drill-down modal gap ke tiket + koreksi SCDF inline."""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
SUMBER = (AKAR / "frontend/src/pages/Traceability.tsx").read_text(encoding="utf-8")


def test_modal_gap_memiliki_jalur_tiket_dan_form_inline():
    assert "/api/traceability/gap-details" in SUMBER
    assert "/api/traceability/gap-correction" in SUMBER
    assert 'data-uji="tombol-rincian-gap"' in SUMBER
    assert 'data-uji="rincian-gap"' in SUMBER
    assert 'data-uji="rincian-tiket-gap"' in SUMBER
    assert 'data-uji="tabel-tiket-gap"' in SUMBER
    assert 'data-uji="form-koreksi-gap"' in SUMBER
    assert "Lihat tiket & perbaiki" in SUMBER
    assert "Simpan koreksi" in SUMBER
    assert "Baris tiket penyebab gap" in SUMBER
    assert "source_kabupaten_norm: kelompok.source_key.kabupaten_norm" in SUMBER
    assert "target_kabupaten_norm: kelompok.source_key.kabupaten_norm" in SUMBER
    assert "Data tiket asli serta referensi SCDF tetap tidak diubah" in SUMBER
    assert "Untuk mengubah isi tiket, gunakan Data Intake Details" in SUMBER
    assert "Kembali ke daftar wilayah" in SUMBER


def test_detail_gap_hanya_membaca_dan_koreksi_hanya_setelah_put():
    blok_detail = SUMBER.split('queryKey: ["traceability-gap-detail"', 1)[1].split(
        "const actors = useQuery", 1)[0]
    assert "ambilJson(`/api/traceability/gap-details?${p}`)" in blok_detail
    assert "method: \"PUT\"" not in blok_detail
    blok_simpan = SUMBER.split("const simpanKoreksiGap = useMutation", 1)[1].split(
        "const simpanKoreksi = useMutation", 1)[0]
    assert "method: \"PUT\"" in blok_simpan
    assert "gap-correction" in blok_simpan
    assert "queryClient.invalidateQueries" in blok_simpan


def test_alur_lama_tetap_utuh():
    assert ">⬇ Unduh belum termapping</a>" in SUMBER
    assert "⬆ Unggah hasil mapping" in SUMBER
    assert "/api/traceability/unmapped" in SUMBER
    assert "/api/traceability/actors/${encodeURIComponent(selectedActor!)}/origin-correction" in SUMBER
    assert "Sourcing locations from Asal Getah" in SUMBER
    assert "Deteksi potensi salah ketik dari SCDF" in SUMBER
    assert "Wilayah belum traceable" in SUMBER
    assert "Volume belum traceable" in SUMBER
