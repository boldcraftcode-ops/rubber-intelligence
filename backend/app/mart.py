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
    HargaGrade,
    TiketBaris,
    Sicom,
    Stok,
    TargetMargin,
)


def bangun_mart(session: Session, *, sinkronkan_pembelian: bool = True) -> None:
    session.execute(delete(MartHarian))
    session.execute(delete(MartBulanan))

    kurs_cari = PencariBerlaku([(k.berlaku_dari, k) for k in session.scalars(select(Kurs))])
    sicom_cari = PencariBerlaku([(s.tanggal, s) for s in session.scalars(select(Sicom))])
    param_cari = PencariBerlaku(
        [(p.berlaku_dari, p) for p in session.scalars(select(ParameterPabrik))])

    # Nilai pembelian dihitung dari tiket × harga grade untuk setiap tanggal
    # yang memiliki intake. Pembelian tersimpan hanya menjadi fallback tanggal
    # yang sama sekali belum memiliki intake historis; tidak menggantikan hasil
    # intake dan tidak dipakai bila tanggal intake belum punya harga lengkap.
    pembelian_lama: dict[dt.date, list[Pembelian]] = defaultdict(list)
    for p in session.scalars(select(Pembelian)):
        pembelian_lama[p.tanggal].append(p)

    tiket_per_tanggal: dict[dt.date, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    tanggal_dengan_intake: set[dt.date] = set()
    invalid_tanggal: set[dt.date] = set()
    for t in session.scalars(select(TiketBaris)):
        tanggal_dengan_intake.add(t.ticket_date)
        if not t.dry_kg or t.dry_kg <= 0:
            continue
        if not t.item_code:
            invalid_tanggal.add(t.ticket_date)
            continue
        tiket_per_tanggal[t.ticket_date][t.item_code] += t.dry_kg

    harga_per_grade: dict[str, PencariBerlaku] = {}
    harga_rows: dict[str, list[tuple[dt.date, HargaGrade]]] = defaultdict(list)
    for h in session.scalars(select(HargaGrade)):
        harga_rows[h.item_code].append((h.tanggal, h))
    harga_per_grade = {kode: PencariBerlaku(rows) for kode, rows in harga_rows.items()}
    pembelian_harian: dict[dt.date, tuple[Decimal, Decimal]] = {}
    pembelian_per_grade: dict[dt.date, dict[str, tuple[Decimal, Decimal]]] = {}
    for tanggal, per_grade in tiket_per_tanggal.items():
        if tanggal in invalid_tanggal:
            continue
        qty = Decimal(0)
        amount = Decimal(0)
        rincian_harga: dict[str, tuple[Decimal, Decimal]] = {}
        lengkap = True
        for grade, berat in per_grade.items():
            lookup = harga_per_grade.get(grade)
            harga = lookup.pada(tanggal) if lookup else None
            if harga is not None and harga.berlaku_sampai is not None and tanggal > harga.berlaku_sampai:
                harga = None
            if harga is None:
                lengkap = False
                break
            nilai_grade = berat * harga.harga_rp_per_kg
            qty += berat
            amount += nilai_grade
            rincian_harga[grade] = (berat, nilai_grade)
        if lengkap and qty:
            pembelian_harian[tanggal] = (qty, amount)
            pembelian_per_grade[tanggal] = rincian_harga

    # Sumber hasil tak perlu ditulis ulang untuk perubahan yang tidak menyentuh
    # intake/harga (mis. pembaruan SICOM atau kurs); ini menghindari ribuan
    # DELETE/INSERT yang tidak relevan pada setiap input harian.
    if sinkronkan_pembelian:
        for tanggal in tanggal_dengan_intake:
            session.execute(delete(Pembelian).where(Pembelian.tanggal == tanggal))
            for grade, (qty, amount) in pembelian_per_grade.get(tanggal, {}).items():
                session.add(Pembelian(tanggal=tanggal, item_code=grade, kode_vendor="",
                                      ticket_no="", qty_kering_kg=qty, amount_rp=amount))
        session.flush()

    stok_per_tanggal: dict[dt.date, Decimal] = defaultdict(Decimal)
    for s in session.scalars(select(Stok)):
        stok_per_tanggal[s.tanggal] += s.stok_kg

    semua_tanggal = sorted(set(tanggal_dengan_intake) | set(pembelian_lama) | set(stok_per_tanggal))

    harian_bulanan: dict[tuple[int, int], list[rumus.BarisHarian]] = defaultdict(list)

    for tanggal in semua_tanggal:
        hasil_beli = pembelian_harian.get(tanggal)
        granularitas = "grade" if hasil_beli else None
        if tanggal not in tanggal_dengan_intake:
            legacy = pembelian_lama.get(tanggal, [])
            rinci = [b for b in legacy if b.item_code != "ALL"]
            dipakai = rinci or legacy
            if dipakai:
                qty = sum((b.qty_kering_kg for b in dipakai), Decimal(0))
                amount = sum((b.amount_rp for b in dipakai), Decimal(0))
                hasil_beli = (qty, amount)
                granularitas = "tiket" if any(b.ticket_no for b in dipakai) else "grade" if rinci else "total"
        qty, amount = hasil_beli if hasil_beli else (Decimal(0), Decimal(0))

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
            qty_kering_kg=float(qty) if hasil_beli else None,
            amount_rp=amount if hasil_beli else None,
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

        if hasil_beli and qty and kurs_nilai and sicom_nilai is not None:
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
