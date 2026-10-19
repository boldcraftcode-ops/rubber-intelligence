"""Analisis hubungan rasio stok dengan OP Margin per bulan (bagian 7).

PENTING: ini INFORMASI, bukan aturan. Korelasi adalah asosiasi,
bukan bukti sebab-akibat — teks itu wajib tampil di layar.
"""
from __future__ import annotations

from collections import defaultdict
from math import sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MartBulanan, MartHarian

CATATAN = ("Korelasi ini adalah ASOSIASI, bukan bukti sebab-akibat. "
           "Stok rendah bisa terjadi bersamaan dengan kondisi pasar yang "
           "menekan margin tanpa saling menyebabkan.")


def _korelasi_pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 3:
        return None
    rx = sum(x) / n
    ry = sum(y) / n
    kov = sum((a - rx) * (b - ry) for a, b in zip(x, y))
    vx = sqrt(sum((a - rx) ** 2 for a in x))
    vy = sqrt(sum((b - ry) ** 2 for b in y))
    if vx == 0 or vy == 0:
        return None
    return kov / (vx * vy)


def analisis_stok_margin(session: Session) -> dict:
    # Rata-rata rasio stok per bulan (dari mart harian)
    rasio_bulan: dict[tuple[int, int], list[float]] = defaultdict(list)
    for h in session.scalars(select(MartHarian).where(MartHarian.rasio_stok != None)):  # noqa: E711
        rasio_bulan[(h.tanggal.year, h.tanggal.month)].append(h.rasio_stok)

    titik = []
    for b in session.scalars(select(MartBulanan).order_by(
            MartBulanan.tahun, MartBulanan.bulan)):
        rasio = rasio_bulan.get((b.tahun, b.bulan))
        if not rasio or b.op_margin_usc is None:
            continue
        titik.append({
            "tahun": b.tahun, "bulan": b.bulan,
            "rasio_stok": round(sum(rasio) / len(rasio), 4),
            "op_margin": round(b.op_margin_usc, 4),
            "ton": round(b.qty_ton, 3),
        })

    x = [t["rasio_stok"] for t in titik]
    y = [t["op_margin"] for t in titik]
    korelasi = _korelasi_pearson(x, y)

    rendah = [t["op_margin"] for t in titik if t["rasio_stok"] < 0.5]
    tinggi = [t["op_margin"] for t in titik if t["rasio_stok"] >= 0.8]
    return {
        "titik": titik,
        "jumlah_bulan": len(titik),
        "korelasi": round(korelasi, 4) if korelasi is not None else None,
        "margin_stok_rendah": round(sum(rendah) / len(rendah), 4) if rendah else None,
        "jumlah_bulan_stok_rendah": len(rendah),
        "margin_stok_tinggi": round(sum(tinggi) / len(tinggi), 4) if tinggi else None,
        "jumlah_bulan_stok_tinggi": len(tinggi),
        "catatan": CATATAN,
    }
