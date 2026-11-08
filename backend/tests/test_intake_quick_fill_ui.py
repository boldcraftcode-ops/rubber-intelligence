"""Struktur UI quick-fill pada Data Intake Details — Penerimaan Karet."""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
SUMBER = (AKAR / "frontend/src/pages/IntakeData.tsx").read_text(encoding="utf-8")
UTAMA = (AKAR / "backend/app/main.py").read_text(encoding="utf-8")


def test_panel_dan_endpoint_quick_fill_ada():
    assert "function PanelQuickFill" in SUMBER
    assert "<PanelQuickFill terpilih={terpilihIds}" in SUMBER
    assert "/api/intake/quick-fill/pratinjau" in SUMBER
    assert "/api/intake/quick-fill/terapkan" in SUMBER
    assert '"DELETE"' in SUMBER
    assert "Pratinjau" in SUMBER
    assert "Konfirmasi pratinjau" in SUMBER
    assert "Konfirmasi & terapkan ${hasil.berubah} perubahan" in SUMBER
    assert "Tombol konfirmasi ada di blok hijau di bawah tabel diff." in SUMBER
    assert "Hapus pilihan" in SUMBER


def test_checkbox_pilihan_banyak():
    assert 'aria-label="Pilih semua baris di halaman ini"' in SUMBER
    assert "Pilih ${row.ticket_no} baris ${row.line_seq}" in SUMBER
    assert "colSpan={11}" in SUMBER
    assert "terpilihIds = useMemo" in SUMBER
    assert "toggleSemuaHalaman" in SUMBER
    assert "setQuickFillEpoch" in SUMBER


def test_pratinjau_dan_konfirmasi_eksplisit():
    assert "window.confirm(" in SUMBER
    assert "Perubahan tercatat per baris di audit log" in SUMBER
    assert "Hanya admin yang dapat menerapkan." in SUMBER
    assert "Kosongkan nilai" in SUMBER
    assert "kolom" in SUMBER
    assert "sebelumnya" in SUMBER
    assert "sesudah" in SUMBER


def test_health_dan_tidak_memakai_unggah_excel():
    assert '"intake-quick-fill"' in UTAMA
    assert "Unduh template koreksi" not in SUMBER
    assert "/api/unggah/pratinjau" not in SUMBER
