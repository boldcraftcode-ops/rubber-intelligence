"""Struktur UI Excel diff pada Data Intake Details — Penerimaan Karet."""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
SUMBER = (AKAR / "frontend/src/pages/IntakeData.tsx").read_text(encoding="utf-8")
UTAMA = (AKAR / "backend/app/main.py").read_text(encoding="utf-8")


def test_panel_excel_diff_dirender_bersama_quick_fill():
    assert "function PanelExcelDiff" in SUMBER
    assert "<PanelExcelDiff filter={filterAktif}" in SUMBER
    assert "<PanelQuickFill terpilih={terpilihIds}" in SUMBER
    assert "useRef" in SUMBER


def test_unduhan_dan_input_file():
    assert "/api/intake/excel-diff/template?" in SUMBER
    assert "Unduh Excel baris filter ini" in SUMBER
    assert "Unduh template kosong" in SUMBER
    assert 'type="file"' in SUMBER
    assert 'accept=".xlsx' in SUMBER
    assert "FormData" in SUMBER
    assert 'form.append("file", berkas)' in SUMBER


def test_endpoint_pratinjau_terapkan_batal():
    assert "/api/intake/excel-diff/pratinjau" in SUMBER
    assert "/api/intake/excel-diff/terapkan" in SUMBER
    assert '"DELETE"' in SUMBER
    assert "Batalkan pratinjau" in SUMBER


def test_pratinjau_dan_konfirmasi_eksplisit():
    assert "Konfirmasi pratinjau" in SUMBER
    assert "Konfirmasi & terapkan ${hasil.jumlah_perubahan} perubahan" in SUMBER
    assert "window.confirm(" in SUMBER
    assert "Perubahan tercatat per baris di audit log" in SUMBER
    assert "Hanya admin yang dapat menerapkan." in SUMBER
    assert "Tombol konfirmasi ada di blok hijau di bawah tabel diff." in SUMBER


def test_diff_per_sel_dan_status_kosong():
    assert "Sebelumnya" in SUMBER and "Sesudah" in SUMBER
    assert "d.label" in SUMBER
    assert 'status: "siap" | "ada_galat" | "kosong"' in SUMBER
    assert "Tidak ada nilai yang berubah" in SUMBER
    assert "sel kosong berarti menghapus nilai opsional" in SUMBER


def test_health_dan_tidak_memakai_endpoint_unggah_lama():
    assert '"intake-excel-diff"' in UTAMA
    assert '"intake-quick-fill"' in UTAMA
    assert "/api/unggah/pratinjau" not in SUMBER
