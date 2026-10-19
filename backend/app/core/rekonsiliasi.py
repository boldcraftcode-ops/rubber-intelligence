"""Rekonsiliasi tonase (bagian 9 spesifikasi).

Aturan kunci: jumlah Dry tiket per tanggal tiket harus sama dengan
Quantity harian di Pembelian_Harian.

Kebijakan default [TERBUKA]: tiket dianggap sumber resmi tonase; selisih
perlu PERSETUJUAN pengguna sebelum angka lama dikoreksi — sistem tidak
mengoreksi diam-diam.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Pembelian, TiketBaris

# Selisih yang sudah diketahui dari analisis file lama (harus muncul di laporan).
SELISIH_DIKETAHUI = [
    {
        "periode": "Juli 2026", "tahun": 2026, "bulan": 7,
        "tiket_ton": 5269.319, "excel_ton": 5249.866,
    },
    {
        "periode": "Agustus 2026", "tahun": 2026, "bulan": 8,
        "tiket_ton": 4759.827, "excel_ton": 4752.949,
    },
]

CATATAN_DIKETAHUI = [
    "Data tiket di aplikasi internal berhenti pada 19 September 2026; "
    "bulan setelah itu belum bisa direkonsiliasi penuh.",
    "Kebijakan: tiket dianggap sumber resmi tonase. Selisih TIDAK dikoreksi "
    "otomatis — perlu persetujuan pengguna sebelum angka lama diubah [TERBUKA].",
]


def selisih_diketahui() -> list[dict]:
    hasil = []
    for s in SELISIH_DIKETAHUI:
        selisih = round(s["tiket_ton"] - s["excel_ton"], 3)
        hasil.append({**s, "selisih_ton": selisih,
                      "status": "menunggu persetujuan koreksi [TERBUKA]"})
    return hasil


def rekonsiliasi_harian(session: Session) -> list[dict]:
    """Bandingkan jumlah Dry tiket vs Quantity pembelian per tanggal
    (hanya tanggal yang punya data tiket)."""
    dry: dict[dt.date, Decimal] = defaultdict(Decimal)
    for t in session.scalars(select(TiketBaris).where(TiketBaris.tiket_nol == False)):  # noqa: E712
        if t.dry_kg is not None:
            dry[t.ticket_date] += t.dry_kg
    qty: dict[dt.date, Decimal] = defaultdict(Decimal)
    for p in session.scalars(select(Pembelian)):
        qty[p.tanggal] += p.qty_kering_kg

    hasil = []
    for tanggal in sorted(dry):
        d, q = float(dry[tanggal]), float(qty.get(tanggal, 0))
        hasil.append({
            "tanggal": tanggal.isoformat(),
            "dry_tiket_kg": round(d, 3),
            "qty_pembelian_kg": round(q, 3),
            "selisih_kg": round(d - q, 3),
            "cocok": abs(d - q) <= 1.0,
        })
    return hasil
