"""Perencanaan margin tahun depan (pengganti sheet Y27).

net_margin bulan m = rata-rata OP Margin bulan m dari tahun-tahun terpilih
                     + penyesuaian_manual_m + effort_m
Nilai dasar diambil otomatis dari mart_bulanan (bukan salinan tempelan).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MartBulanan, Perencanaan
from . import rumus


@dataclass
class BarisRencana:
    bulan: int
    tahun_dipakai: list[int]
    margin_per_tahun: dict[int, float]
    rata_rata_dasar: float | None
    penyesuaian_manual: float
    effort: float
    sebelum_effort: float | None  # dasar + penyesuaian (tanpa effort)
    net_margin: float | None
    alasan: str | None
    perkiraan: bool  # True bila ada tahun dasar yang bulannya belum lengkap/belum ada


def hitung_rencana(session: Session, tahun_target: int,
                   tahun_dipilih: list[int] | None = None) -> list[BarisRencana]:
    if tahun_dipilih is None:
        tahun_dipilih = [tahun_target - 4, tahun_target - 3, tahun_target - 2, tahun_target - 1]

    mart = {(m.tahun, m.bulan): m.op_margin_usc
            for m in session.scalars(select(MartBulanan))}
    rencana = {r.bulan: r for r in session.scalars(
        select(Perencanaan).where(Perencanaan.tahun_target == tahun_target))}

    hasil = []
    for bulan in range(1, 13):
        nilai = {t: mart[(t, bulan)] for t in tahun_dipilih if (t, bulan) in mart}
        dasar = rumus.rata_rata_sederhana(list(nilai.values()))
        r = rencana.get(bulan)
        penyesuaian = r.penyesuaian_manual_usc if r else 0.0
        effort = r.effort_usc if r else 0.0
        sebelum = (dasar + penyesuaian) if dasar is not None else None
        net = (sebelum + effort) if sebelum is not None else None
        hasil.append(BarisRencana(
            bulan=bulan,
            tahun_dipakai=sorted(nilai),
            margin_per_tahun=nilai,
            rata_rata_dasar=dasar,
            penyesuaian_manual=penyesuaian,
            effort=effort,
            sebelum_effort=sebelum,
            net_margin=net,
            alasan=r.alasan if r else None,
            perkiraan=len(nilai) < len(tahun_dipilih),
        ))
    return hasil
