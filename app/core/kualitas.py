"""Pemeriksaan kualitas data (bagian 9 spesifikasi).

Peringatan: SICOM/kurs/stok/tiket terlambat, hari pembelian tanpa SICOM,
lonjakan harga beli harian (>10% dari median bulan), tiket nol,
wilayah beda dari Asal Getah, dan KPI reject%.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Kurs,
    MartHarian,
    Pembelian,
    PeringatanData,
    Sicom,
    Stok,
    TiketBaris,
)


def _median(nilai: list[float]) -> float | None:
    if not nilai:
        return None
    urut = sorted(nilai)
    n = len(urut)
    return urut[n // 2] if n % 2 else (urut[n // 2 - 1] + urut[n // 2]) / 2


def kpi_reject(session: Session) -> dict:
    """KPI reject% = SUM(Reject)/SUM(Wet). Reject BELUM dikurangkan dari
    Wet/Dry [TERBUKA] — bila Amount dibayar atas berat bersih, margin bisa
    terlihat 2-3 US¢/kg terlalu tinggi."""
    wet = session.scalar(select(func.sum(TiketBaris.wet_kg)).where(
        TiketBaris.tiket_nol == False)) or 0  # noqa: E712
    reject = session.scalar(select(func.sum(TiketBaris.reject_kg)).where(
        TiketBaris.tiket_nol == False)) or 0  # noqa: E712
    tiket_nol = session.scalar(select(func.count()).select_from(TiketBaris).where(
        TiketBaris.tiket_nol == True)) or 0  # noqa: E712
    total_baris = session.scalar(select(func.count()).select_from(TiketBaris)) or 0
    return {
        "reject_pct": round(float(reject) / float(wet) * 100, 2) if wet else None,
        "wet_kg": float(wet), "reject_kg": float(reject),
        "tiket_nol": tiket_nol, "total_baris_tiket": total_baris,
        "asumsi": "Reject belum dikurangkan dari Wet/Dry [TERBUKA]. Bila Amount "
                  "dibayar atas berat bersih, harga/kg terlihat terlalu rendah dan "
                  "margin terlalu tinggi sekitar 2-3 US¢/kg.",
    }


def data_terlambat(session: Session, hari_ini: dt.date | None = None,
                   batas_hari: int = 3) -> list[dict]:
    hari_ini = hari_ini or dt.date.today()
    hasil = []
    sumber = [
        ("SICOM", session.scalar(select(func.max(Sicom.tanggal)))),
        ("Kurs", session.scalar(select(func.max(Kurs.berlaku_dari)))),
        ("Stok", session.scalar(select(func.max(Stok.tanggal)))),
        ("Tiket", session.scalar(select(func.max(TiketBaris.ticket_date)))),
        ("Pembelian", session.scalar(select(func.max(Pembelian.tanggal)))),
    ]
    for nama, terakhir in sumber:
        telat = (hari_ini - terakhir).days if terakhir else None
        hasil.append({
            "sumber": nama,
            "tanggal_terakhir": terakhir.isoformat() if terakhir else None,
            "umur_hari": telat,
            "terlambat": telat is None or (telat > batas_hari and nama != "Kurs"),
            "catatan": "kurs hanya diisi saat berubah" if nama == "Kurs" else None,
        })
    return hasil


def hari_pembelian_tanpa_sicom(session: Session) -> list[str]:
    """Hari pembelian yang tidak punya baris SICOM persis pada tanggalnya
    (perhitungan tetap memakai harga terakhir, tetapi perlu dicek)."""
    tanggal_sicom = {s for (s,) in session.execute(select(Sicom.tanggal))}
    tanggal_beli = {t for (t,) in session.execute(select(Pembelian.tanggal).distinct())}
    return [t.isoformat() for t in sorted(tanggal_beli - tanggal_sicom)]


def lonjakan_harga_harian(session: Session, ambang_pct: float = 10.0) -> list[dict]:
    """Hari pembelian dengan harga beli menyimpang >10% dari median bulannya."""
    per_bulan: dict[tuple[int, int], list] = defaultdict(list)
    for h in session.scalars(select(MartHarian).where(MartHarian.harga_rp_per_kg != None)):  # noqa: E711
        per_bulan[(h.tanggal.year, h.tanggal.month)].append(h)
    hasil = []
    for (tahun, bulan), hari in sorted(per_bulan.items()):
        med = _median([x.harga_rp_per_kg for x in hari])
        if not med:
            continue
        for x in hari:
            dev = (x.harga_rp_per_kg - med) / med * 100
            if abs(dev) > ambang_pct:
                hasil.append({
                    "tanggal": x.tanggal.isoformat(),
                    "harga_rp_per_kg": round(x.harga_rp_per_kg, 2),
                    "median_bulan_rp": round(med, 2),
                    "deviasi_pct": round(dev, 1),
                })
    return hasil


def ringkasan_peringatan(session: Session, batas_contoh: int = 5) -> list[dict]:
    """Rekap tabel peringatan_data per kode, dengan beberapa contoh pesan."""
    baris = list(session.scalars(select(PeringatanData).order_by(PeringatanData.id)))
    per_kode: dict[str, list[PeringatanData]] = defaultdict(list)
    for p in baris:
        per_kode[p.kode].append(p)
    return [{
        "kode": kode,
        "jumlah": len(items),
        "contoh": [f"[{p.sheet or '-'}" + (f" baris {p.baris_ke}" if p.baris_ke else "")
                   + f"] {p.pesan}" for p in items[:batas_contoh]],
    } for kode, items in sorted(per_kode.items())]
