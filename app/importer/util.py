"""Alat bantu impor: konversi tanggal/angka dan header."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation


def kunci_header(nilai) -> str:
    """Header template bisa berisi keterangan di baris baru, mis.
    'Qty_Kering_Kg\\n(...)' -> 'qty_kering_kg'."""
    if nilai is None:
        return ""
    return str(nilai).split("\n")[0].strip().lower()


def ke_tanggal(nilai) -> dt.date | None:
    if nilai is None or nilai == "":
        return None
    if isinstance(nilai, dt.datetime):
        return nilai.date()
    if isinstance(nilai, dt.date):
        return nilai
    teks = str(nilai).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(teks, fmt).date()
        except ValueError:
            continue
    return None


def ke_desimal(nilai) -> Decimal | None:
    """Angka tepat (untuk Rupiah dan kg)."""
    if nilai is None or nilai == "":
        return None
    try:
        return Decimal(str(nilai))
    except InvalidOperation:
        return None


def ke_float(nilai) -> float | None:
    if nilai is None or nilai == "":
        return None
    try:
        return float(nilai)
    except (TypeError, ValueError):
        return None


def ke_teks(nilai) -> str | None:
    if nilai is None:
        return None
    teks = str(nilai).strip()
    return teks or None


def baris_kosong(baris) -> bool:
    return all(v is None or str(v).strip() == "" or str(v).startswith("=") for v in baris)
