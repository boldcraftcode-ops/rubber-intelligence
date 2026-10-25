"""Satu sumber versi kode aplikasi.

VERSI dipakai di /api/health dan di diagnosa.bat, supaya mudah memastikan
apakah folder yang dijalankan berisi kode terbaru. Versi juga ditulis di
VERSI.txt pada akar repo (berguna untuk folder hasil unduhan ZIP yang tidak
punya riwayat Git).
"""
from __future__ import annotations

import pathlib

VERSI = "0.7.3"

#: akar repo (satu tingkat di atas folder backend/)
AKAR = pathlib.Path(__file__).resolve().parents[2]


def versi_folder() -> str:
    """Versi menurut baris pertama VERSI.txt; VERSI bila berkas tidak ada.

    VERSI.txt baris 1 = nomor versi, baris 2 = tanggal. Format ini sengaja
    sederhana supaya bisa dibaca start-web.bat dengan `set /p` (tanpa for /f).
    """
    berkas = AKAR / "VERSI.txt"
    try:
        baris = berkas.read_text(encoding="utf-8").strip().splitlines()
        return baris[0].strip() if baris else VERSI
    except OSError:
        return VERSI
