"""Dua caption instruksi lama pada halaman Traceability sudah dihapus."""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
SUMBER = (AKAR / "frontend/src/pages/Traceability.tsx").read_text(encoding="utf-8")


def test_caption_panjang_tidak_ada_lagi():
    assert "Volume Dry dari tiket tervalidasi dan dideduplikasi hanya bila" not in SUMBER
    assert "Code sengaja kosong karena file referensi tidak menyediakan" not in SUMBER
    assert "Unduh file lewat tombol" not in SUMBER
    assert "Pemetaan tersimpan dapat dihapus dari detail Supplier Actors." not in SUMBER


def test_fitur_ekspor_dan_impor_mapping_tetap_ada():
    assert ">⬇ Ekspor Excel</a>" in SUMBER
    assert ">⬇ Unduh belum termapping</a>" in SUMBER
    assert "⬆ Unggah hasil mapping" in SUMBER
    assert "/api/traceability/unmapped" in SUMBER
    assert 'aria-live="polite"' in SUMBER
    assert "imporMapping.isSuccess" in SUMBER
    assert "imporMapping.error" in SUMBER
