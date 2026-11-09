"""Deteksi potensi salah ketik nama District/Sub-district terhadap SCDF.

Modul ini sengaja murni perhitungan: tidak membaca database, tidak menulis
koreksi, dan tidak memakai riwayat pembelian. Namanya dibandingkan dengan ejaan
pada referensi SCDF setelah huruf, spasi, tanda baca, dan awalan wilayah yang
lazim dibakukan. Hasilnya hanya indikator kemiripan, BUKAN vonis lokasi benar.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher, get_close_matches

from .traceability import normalisasi_teks_wilayah

# Awalan yang sering ditulis pada intake tetapi tidak selalu dipakai SCDF.
# Diurutkan dari yang terpanjang agar pemotongan tidak menyisakan potongan.
AWALAN_UMUM = (
    "KABUPATENADMINISTRASI", "KOTAADMINISTRASI", "KELURAHAN", "KECAMATAN",
    "KABUPATEN", "GAMPONG", "KEUCHIK", "KAMPUNG", "KOTA", "DUSUN", "DESA",
)

AMBANG_CARI = 0.65          # pra-seleksi get_close_matches, lebih longgar
AMBANG_UMUM = 78.0          # skor akhir minimum untuk nama panjang
AMBANG_PENDEK = 90.0        # nama <=6 huruf mudah mirip kebetulan
PANJANG_PENDEK = 6
MAKSIMAL_KANDIDAT = 6

_RE_NON_ALNUM = re.compile(r"[^A-Z0-9]")


def padatkan(nilai: str | None) -> str:
    """Huruf kapital, spasi/underscore/tanda baca dibuang."""
    teks = normalisasi_teks_wilayah(nilai)
    return _RE_NON_ALNUM.sub("", teks)


def varian_padat(nilai: str | None) -> set[str]:
    """Bentuk padat plus bentuk tanpa awalan administratif yang lazim.

    Contoh: ``D U M A I`` -> ``DUMAI``; ``GAM[PONG REUSAK`` ->
    ``GAMPONGREUSAK`` dan ``REUSAK``. Varian tanpa awalan membuat ejaan SCDF
    ``Reusak`` tetap dapat ditemukan meski intake menulis ``Gampong Reusak``.
    """
    utuh = padatkan(nilai)
    if not utuh:
        return set()
    hasil = {utuh}
    for awalan in AWALAN_UMUM:
        if utuh.startswith(awalan) and len(utuh) > len(awalan) + 2:
            hasil.add(utuh[len(awalan):])
    return hasil


def skor_kemiripan(sumber: str | None, kandidat: str | None) -> float:
    """Skor 0–100; 100 bila salah satu varian padat sama persis."""
    kiri = varian_padat(sumber)
    kanan = varian_padat(kandidat)
    if not kiri or not kanan:
        return 0.0
    terbaik = 0.0
    for a in kiri:
        for b in kanan:
            if a == b:
                return 100.0
            terbaik = max(terbaik,
                          SequenceMatcher(None, a, b, autojunk=False).ratio() * 100)
    return round(terbaik, 1)


def ambang_untuk(nilai: str | None) -> float:
    """Nama pendek butuh kemiripan lebih tinggi agar tidak banyak false alarm."""
    varian = varian_padat(nilai)
    if not varian:
        return 100.0
    return AMBANG_PENDEK if min(map(len, varian)) <= PANJANG_PENDEK else AMBANG_UMUM


def indeks_kandidat(pasangan: list[tuple[str | None, str | None]]) -> dict[str, set[str]]:
    """Petakan setiap varian padat ke kumpulan nilai normal SCDF."""
    indeks: dict[str, set[str]] = {}
    for norm, _label in pasangan:
        if not norm:
            continue
        for varian in varian_padat(norm):
            indeks.setdefault(varian, set()).add(norm)
    return indeks


def norma_mirip(sumber: str | None, indeks: dict[str, set[str]],
                maksimal: int = 24) -> dict[str, float]:
    """Ambil nilai normal SCDF yang skornya melewati ambang untuk `sumber`.

    `get_close_matches` dipakai sebagai pra-seleksi cepat; skor akhir tetap
    memakai `skor_kemiripan` dengan semua varian dan `autojunk=False`.
    """
    if not indeks or not padatkan(sumber):
        return {}
    daftar = list(indeks)
    skor: dict[str, float] = {}
    for varian in varian_padat(sumber):
        # Ejaan persis tetap masuk walaupun pra-seleksi punya batas n.
        for norm in indeks.get(varian, set()):
            skor[norm] = 100.0
        for cocok in get_close_matches(varian, daftar, n=maksimal * 2,
                                       cutoff=AMBANG_CARI):
            for norm in indeks.get(cocok, set()):
                skor[norm] = max(skor.get(norm, 0.0),
                                 skor_kemiripan(sumber, norm))
    ambang = ambang_untuk(sumber)
    layak = {norm: nilai for norm, nilai in skor.items() if nilai >= ambang}
    return dict(sorted(layak.items(), key=lambda kv: (-kv[1], kv[0]))[:maksimal])


def skor_pasangan(skor_district: float, skor_subdistrict: float) -> float:
    """Sub-district lebih spesifik, jadi bobotnya lebih besar."""
    return round(0.35 * skor_district + 0.65 * skor_subdistrict, 1)
