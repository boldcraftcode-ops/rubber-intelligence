"""Pembangun lapisan mart: mart_harian dan mart_bulanan.

Dibangun ulang penuh setiap selesai unggahan. Rumus mengikuti
app/core/rumus.py (persis Excel lama).
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .core import rumus
from .core.lookup import PencariBerlaku
from .models import (
    Kurs,
    MartBulanan,
    MartHarian,
    ParameterPabrik,
    Pembelian,
    Sicom,
    Stok,
    TargetMargin,
)


def bangun_mart(session: Session) -> None:
    session.execute(delete(MartHarian))
    session.execute(delete(MartBulanan))

    kurs_cari = PencariBerlaku([(k.berlaku_dari, k) for k in session.scalars(select(Kurs))])
    sicom_cari = PencariBerlaku([(s.tanggal, s) for s in session.scalars(select(Sicom))])
    param_cari = PencariBerlaku(
        [(p.berlaku_dari, p) for p in session.scalars(select(ParameterPabrik))])

    # Pembelian: pakai tingkat terhalus yang tersedia per tanggal.
    # Bila suatu tanggal punya baris selain 'ALL', baris ALL diabaikan
    # (menghindari hitung ganda total + rincian).
    per_tanggal: dict[dt.date, list[Pembelian]] = defaultdict(list)
    for p in session.scalars(select(Pembelian)):
        per_tanggal[p.tanggal].append(p)

    stok_per_tanggal: dict[dt.date, Decimal] = defaultdict(Decimal)
    for s in session.scalars(select(Stok)):
        stok_per_tanggal[s.tanggal] += s.stok_kg

    semua_tanggal = sorted(set(per_tanggal) | set(stok_per_tanggal))

    harian_bulanan: dict[tuple[int, int], list[rumus.BarisHarian]] = defaultdict(list)

    for tanggal in semua_tanggal:
        baris = per_tanggal.get(tanggal, [])
        rinci = [b for b in baris if b.item_code != "ALL"]
        dipakai = rinci or baris
        granularitas = None
        if dipakai:
            if any(b.ticket_no for b in dipakai):
                granularitas = "tiket"
            elif any(b.kode_vendor for b in dipakai):
                granularitas = "vendor"
            elif rinci:
                granularitas = "grade"
            else:
                granularitas = "total"

        qty = sum((b.qty_kering_kg for b in dipakai), Decimal(0))
        amount = sum((b.amount_rp for b in dipakai), Decimal(0))

        k = kurs_cari.pada(tanggal)
        s = sicom_cari.pada(tanggal)
        kurs_nilai = float(k.idr_per_usd) if k else None
        sicom_nilai = s.usc_per_kg if s else None

        harga_rp = rumus.harga_rp_per_kg(amount, qty) if qty else None
        harga_usc = rumus.rp_ke_usc(harga_rp, kurs_nilai) if (qty and kurs_nilai) else 0.0
        margin = rumus.margin_harian(sicom_nilai, harga_usc) if (qty and sicom_nilai is not None) else 0.0

        # Stok / Days
        stok_kg = stok_per_tanggal.get(tanggal)
        stok_ton = days = rasio = kapasitas = safety = None
        if stok_kg is not None:
            stok_ton = rumus.stok_ton(stok_kg)
            prm = param_cari.pada(tanggal)
            if prm:
                kapasitas = prm.kapasitas_ton_per_hari
                days = rumus.hitung_days(stok_ton, kapasitas)
                safety = rumus.hitung_safety_ton(
                    prm.safety_stock_ton, prm.safety_stock_hari, kapasitas)
                rasio = rumus.rasio_stok(stok_ton, safety)

        session.add(MartHarian(
            tanggal=tanggal,
            qty_kering_kg=float(qty) if dipakai else None,
            amount_rp=amount if dipakai else None,
            harga_rp_per_kg=harga_rp,
            kurs=kurs_nilai,
            sicom_usc=sicom_nilai,
            harga_usc_per_kg=harga_usc or 0.0,
            margin_usc=margin or 0.0,
            granularitas=granularitas,
            stok_kg=float(stok_kg) if stok_kg is not None else None,
            stok_ton=stok_ton,
            kapasitas_ton=kapasitas,
            safety_ton=safety,
            days=days,
            rasio_stok=rasio,
        ))

        if qty and kurs_nilai and sicom_nilai is not None:
            harian_bulanan[(tanggal.year, tanggal.month)].append(
                rumus.BarisHarian(float(qty), float(amount), kurs_nilai, sicom_nilai))

    target_map = {(t.tahun, t.bulan): t.target_usc_per_kg
                  for t in session.scalars(select(TargetMargin))}

    for (tahun, bulan), baris in sorted(harian_bulanan.items()):
        hasil = rumus.agregat_bulanan(baris)
        target = target_map.get((tahun, bulan))
        session.add(MartBulanan(
            tahun=tahun, bulan=bulan,
            qty_ton=hasil.qty_ton,
            sicom_usc=hasil.sicom_usc,
            harga_beli_usc=hasil.harga_beli_usc,
            op_margin_usc=hasil.op_margin_usc,
            target_usc=target,
            pencapaian=rumus.pencapaian(hasil.op_margin_usc, target),
            selisih_vs_target=(hasil.op_margin_usc - target)
            if (hasil.op_margin_usc is not None and target is not None) else None,
            hari_pembelian=len(baris),
        ))
    session.flush()
