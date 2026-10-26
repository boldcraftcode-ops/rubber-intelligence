"""Klasifikasi vendor (Small holder / Small estate / Rubber trader).

Pemilik meminta master vendor memuat **klasifikasi** dengan tiga pilihan itu.
Kode disimpan dalam huruf kecil bergaris bawah (`small_holder`) supaya stabil
dipakai untuk penyaringan dan laporan; yang tampil di layar & Excel adalah
labelnya.

Ejaan bebas di Excel tetap diterima (mis. "Smallholder", "SMALL HOLDER",
"trader"), tetapi ejaan yang tidak dikenal **ditolak dengan pesan jelas** —
bukan disimpan diam-diam sebagai nilai lain, karena klasifikasi ini dipakai
untuk melihat komposisi pemasok (kebun rakyat vs kebun besar vs pedagang).
"""
from __future__ import annotations

#: kode -> label yang dilihat pengguna
KLASIFIKASI: dict[str, str] = {
    "small_holder": "Small holder",
    "small_estate": "Small estate",
    "rubber_trader": "Rubber trader",
}

#: ejaan lain yang sering muncul (sudah dinormalkan: huruf kecil, spasi tunggal)
_ALIAS: dict[str, str] = {
    "small holder": "small_holder",
    "smallholder": "small_holder",
    "small-holder": "small_holder",
    "small holder (kebun rakyat)": "small_holder",
    "kebun rakyat": "small_holder",
    "small estate": "small_estate",
    "smallestate": "small_estate",
    "small-estate": "small_estate",
    "estate": "small_estate",
    "rubber trader": "rubber_trader",
    "rubbertrader": "rubber_trader",
    "rubber-trader": "rubber_trader",
    "trader": "rubber_trader",
    "pedagang": "rubber_trader",
}

PESAN_PILIHAN = "Small holder, Small estate, atau Rubber trader"


def kunci(nilai) -> str:
    """Normalkan teks bebas: huruf kecil, spasi tunggal, tanpa tepi."""
    return " ".join(str(nilai or "").strip().lower().split())


def bakukan(nilai) -> str | None:
    """Teks bebas -> kode klasifikasi. Kosong -> None.

    Melempar ValueError bila ejaannya tidak dikenal, supaya pemanggil bisa
    melaporkannya sebagai baris yang perlu diperbaiki.
    """
    teks = kunci(nilai)
    if not teks:
        return None
    if teks in KLASIFIKASI:
        return teks
    if teks in _ALIAS:
        return _ALIAS[teks]
    raise ValueError(f"Klasifikasi '{str(nilai).strip()}' tidak dikenal. "
                     f"Pilih salah satu: {PESAN_PILIHAN}.")


def label(kode_nilai) -> str | None:
    """Kode klasifikasi -> label tampilan (None bila kosong/tak dikenal)."""
    kode_nilai = kunci(kode_nilai)
    return KLASIFIKASI.get(kode_nilai) or None


def daftar_untuk_layar() -> list[dict]:
    """Pilihan untuk dropdown: [{kode, label}]."""
    return [{"kode": k, "label": v} for k, v in KLASIFIKASI.items()]
