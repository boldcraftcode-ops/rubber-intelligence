"""Fungsi Traceability: parsing asal, kunci wilayah, periode, dan persentase."""
from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import json
import re


_RE_SPASI = re.compile(r"\s+")
_PREFIX_KABUPATEN = ("KABUPATEN ADMINISTRASI ", "KABUPATEN ", "KAB. ")
_PREFIX_KOTA = ("KOTA ADMINISTRASI ", "KOTA ")


def normalisasi_teks_wilayah(nilai: str | None) -> str:
    """UPPER + TRIM + satukan spasi berulang; underscore menjadi pemisah."""
    return _RE_SPASI.sub(" ", (nilai or "").replace("_", " ").strip()).upper()


def normalisasi_kabupaten(nilai: str | None) -> str:
    """Samakan nama daerah meski sumber menambahkan label Kabupaten/Kota."""
    hasil = normalisasi_teks_wilayah(nilai)
    for awalan in (*_PREFIX_KABUPATEN, *_PREFIX_KOTA):
        if hasil.startswith(awalan):
            return hasil[len(awalan):].strip()
    return hasil


def parse_asal_getah(nilai: str | None) -> tuple[str, str, str, str] | None:
    """Asal Getah harus berisi tepat empat komponen dipisah koma.

    Spasi tidak konsisten di sekitar koma dan spasi ganda dibersihkan. Tidak
    membaca BIN atau Location sebagai bagian wilayah.
    """
    if not nilai or not str(nilai).strip():
        return None
    bagian = tuple(_RE_SPASI.sub(" ", p.strip()) for p in str(nilai).split(","))
    if len(bagian) != 4 or any(not p for p in bagian):
        return None
    return bagian  # type: ignore[return-value]


def kunci_hierarki(kabupaten: str | None, kecamatan: str | None,
                    desa: str | None) -> tuple[str, str, str]:
    return (normalisasi_kabupaten(kabupaten),
            normalisasi_teks_wilayah(kecamatan),
            normalisasi_teks_wilayah(desa))


def persen_traceable(volume_traceable: float | int | None,
                     volume_total: float | int | None) -> float | None:
    """Persentase volume yang cocok ke referensi; None bila total tidak ada."""
    total = float(volume_total or 0)
    if total <= 0:
        return None
    valid = max(0.0, float(volume_traceable or 0))
    return round(min(valid, total) / total * 100, 2)


def rentang_periode(tahun: int, periode: str | None) -> tuple[dt.date, dt.date]:
    """Rentang inklusif untuk ALL, H1/H2, Q1-Q4, atau bulan 01-12."""
    kode = (periode or "ALL").strip().upper()
    if kode in ("", "ALL", "TAHUN", "YEAR"):
        return dt.date(tahun, 1, 1), dt.date(tahun, 12, 31)
    if kode == "H1":
        return dt.date(tahun, 1, 1), dt.date(tahun, 6, 30)
    if kode == "H2":
        return dt.date(tahun, 7, 1), dt.date(tahun, 12, 31)
    if kode in {"Q1", "Q2", "Q3", "Q4"}:
        q = int(kode[1])
        bulan_awal = (q - 1) * 3 + 1
        bulan_akhir = bulan_awal + 2
        return (dt.date(tahun, bulan_awal, 1),
                dt.date(tahun, bulan_akhir,
                        calendar.monthrange(tahun, bulan_akhir)[1]))
    try:
        bulan = int(kode.removeprefix("M"))
        if 1 <= bulan <= 12:
            return (dt.date(tahun, bulan, 1),
                    dt.date(tahun, bulan, calendar.monthrange(tahun, bulan)[1]))
    except ValueError:
        pass
    raise ValueError("Periode harus ALL, H1/H2, Q1–Q4, atau bulan 01–12.")


def sidik_baris_sumber(nilai: tuple | list) -> str:
    """SHA-256 seluruh nilai kolom sumber tanpa menggabungkan nomor tiket."""
    serial = json.dumps(list(nilai), ensure_ascii=False, separators=(",", ":"),
                        default=lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x))
    return hashlib.sha256(serial.encode("utf-8")).hexdigest()


def item_eudr(item_code: str | None) -> bool:
    return (item_code or "").strip().upper().endswith("TTSR")
