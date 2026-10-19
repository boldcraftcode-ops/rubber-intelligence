"""Pencarian baris "yang berlaku" pada suatu tanggal.

Aturan resmi: baris terbaru dengan tanggal_berlaku <= tanggal yang dicari.
Dipakai untuk: kurs, parameter pabrik, SICOM hari libur (harga terakhir),
dan versi aturan stok->harga.
"""
from __future__ import annotations

import datetime as dt
from bisect import bisect_right

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Kurs, ParameterPabrik, Sicom


class PencariBerlaku:
    """Indeks kecil di memori: cari baris terbaru dengan tanggal <= tanggal."""

    def __init__(self, pasangan: list[tuple[dt.date, object]]):
        self.pasangan = sorted(pasangan, key=lambda p: p[0])
        self.tanggal = [p[0] for p in self.pasangan]

    def pada(self, tanggal: dt.date):
        i = bisect_right(self.tanggal, tanggal)
        return self.pasangan[i - 1][1] if i else None


def kurs_pada(session: Session, tanggal: dt.date) -> Kurs | None:
    """Kurs yang berlaku: baris terbaru dengan berlaku_dari <= tanggal."""
    return session.scalars(
        select(Kurs).where(Kurs.berlaku_dari <= tanggal)
        .order_by(Kurs.berlaku_dari.desc())).first()


def sicom_pada(session: Session, tanggal: dt.date) -> Sicom | None:
    """SICOM pada tanggal; hari libur memakai harga terakhir sebelumnya."""
    return session.scalars(
        select(Sicom).where(Sicom.tanggal <= tanggal)
        .order_by(Sicom.tanggal.desc())).first()


def parameter_pada(session: Session, tanggal: dt.date) -> ParameterPabrik | None:
    """Parameter pabrik (kapasitas, safety stock) yang berlaku pada tanggal."""
    return session.scalars(
        select(ParameterPabrik).where(ParameterPabrik.berlaku_dari <= tanggal)
        .order_by(ParameterPabrik.berlaku_dari.desc())).first()
