"""Revisi Rekonsiliasi tampil sebagai histori ringkas, bukan form besar."""
from __future__ import annotations

import re
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
SUMBER = (AKAR / "frontend/src/pages/Rekonsiliasi.tsx").read_text(encoding="utf-8")
KAMUS = (AKAR / "frontend/src/i18n.tsx").read_text(encoding="utf-8")


def test_baris_direvisi_punyi_tanda_dan_tombol_kecil():
    assert "function TandaRevisi" in SUMBER
    assert "✓ {t(\"Direvisi\")} · {t(\"Histori\")}" in SUMBER
    assert "function RingkasanRevisi" in SUMBER
    assert "{t(\"Revisi\")}" in SUMBER
    assert "{t(\"Batal\")}" in SUMBER
    assert "title={t(\"Batalkan revisi\")}" in SUMBER
    assert "window.confirm" in SUMBER
    assert 'border-l-2 border-l-[#15803D]' in SUMBER


def test_form_besar_hanya_saat_diminta():
    assert "if (baris.direvisi && !modeUbah) {" in SUMBER
    assert "buka={() => setModeUbah(true)}" in SUMBER
    assert "const [modeUbah, setModeUbah] = useState(false);" in SUMBER
    assert "epoch={epochRevisi}" in SUMBER
    assert "setEpochRevisi((n) => n + 1)" in SUMBER
    assert "{t(\"Tutup\")}" in SUMBER
    assert "{t(\"Batalkan revisi\")}" in SUMBER


def test_sel_isih_tidak_lagi_dicoret_di_sel_utama():
    assert "line-through" not in SUMBER
    assert "title={`${t(\"Selisih asli\")}" in SUMBER
    assert "t(\"setelah revisi\")" in SUMBER
    assert "selisih_efektif_${satuan}" in SUMBER


def test_kamus_bahasa_lengkap_dan_tanpa_kunci_ganda():
    for kunci in ["Revisi", "Batal", "Direvisi", "Histori", "Tutup",
                  "Selisih asli", "Selisih asli akan kembali ditampilkan."]:
        assert f'"{kunci}":' in KAMUS
    # Kunci kamus ditulis di awal baris dengan indentasi dua spasi.
    kunci = re.findall(r'^  "([^"]+)":', KAMUS, re.M)
    assert len(kunci) == len(set(kunci)), "Ada kunci terjemahan ganda"
