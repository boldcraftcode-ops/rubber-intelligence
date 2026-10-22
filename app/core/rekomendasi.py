"""Rekomendasi harga beli maksimum berdasarkan aturan stok -> target margin.

Selalu menyertakan alasan: rasio stok, baris aturan yang kena, target,
SICOM, dan kurs. Bila tabel aturan kosong: status 'ATURAN BELUM DIISI'.
Dihitung di level rata-rata semua grade (selisih antar grade [TERBUKA]).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AturanStokHarga, MartHarian, TargetMargin
from . import rumus


@dataclass
class HasilRekomendasi:
    status: str  # "OK" | "ATURAN BELUM DIISI" | "DATA KURANG"
    tanggal: dt.date | None = None
    alasan: list[str] = field(default_factory=list)
    rasio_stok: float | None = None
    aturan_contoh: bool = False
    penyesuaian_usc: float | None = None
    target_bulan_usc: float | None = None
    target_efektif_usc: float | None = None
    sicom_usc: float | None = None
    kurs: float | None = None
    harga_beli_maks_usc: float | None = None
    harga_beli_maks_rp_kg: float | None = None
    harga_beli_aktual_terakhir_usc: float | None = None
    tanggal_harga_aktual: dt.date | None = None


def rekomendasi_harga(session: Session, tanggal: dt.date | None = None) -> HasilRekomendasi:
    h = HasilRekomendasi(status="OK")

    baris = session.scalars(select(MartHarian).order_by(MartHarian.tanggal.desc())).first() \
        if tanggal is None else session.get(MartHarian, tanggal)
    if baris is None:
        return HasilRekomendasi(status="DATA KURANG",
                                alasan=["Belum ada data harian di mart untuk tanggal itu."])
    h.tanggal = baris.tanggal
    h.sicom_usc = baris.sicom_usc
    h.kurs = baris.kurs
    h.rasio_stok = baris.rasio_stok

    if baris.rasio_stok is None or baris.sicom_usc is None or baris.kurs is None:
        h.status = "DATA KURANG"
        h.alasan.append("Stok/SICOM/kurs belum lengkap pada tanggal ini.")
        return h

    # Aturan yang berlaku: versi terbaru dengan berlaku_dari <= tanggal, baris aktif.
    semua = list(session.scalars(select(AturanStokHarga).where(
        AturanStokHarga.aktif == True,  # noqa: E712
        AturanStokHarga.berlaku_dari <= baris.tanggal,
    ).order_by(AturanStokHarga.berlaku_dari.desc(), AturanStokHarga.urutan)))
    if not semua:
        h.status = "ATURAN BELUM DIISI"
        h.alasan.append("Tabel aturan stok->harga kosong. Isi aturan resmi dahulu.")
        return h
    versi = semua[0].berlaku_dari
    aturan_versi = [a for a in semua if a.berlaku_dari == versi]
    h.aturan_contoh = any("CONTOH" in (a.keterangan or "").upper() for a in aturan_versi)

    kena = rumus.cari_aturan(
        [rumus.BarisAturan(a.batas_bawah, a.batas_atas, a.penyesuaian_usc, a.keterangan)
         for a in sorted(aturan_versi, key=lambda a: a.urutan)],
        baris.rasio_stok)
    if kena is None:
        h.status = "DATA KURANG"
        h.alasan.append(f"Tidak ada baris aturan untuk rasio stok {baris.rasio_stok:.4f}.")
        return h

    target = session.scalar(select(TargetMargin).where(
        TargetMargin.tahun == baris.tanggal.year, TargetMargin.bulan == baris.tanggal.month))
    if target is None:
        h.status = "DATA KURANG"
        h.alasan.append(f"Target margin bulan {baris.tanggal.month}/{baris.tanggal.year} belum ada.")
        return h

    h.penyesuaian_usc = kena.penyesuaian_usc
    h.target_bulan_usc = target.target_usc_per_kg
    h.target_efektif_usc = rumus.target_efektif(target.target_usc_per_kg, kena.penyesuaian_usc)
    h.harga_beli_maks_usc = rumus.harga_beli_maks_usc(baris.sicom_usc, h.target_efektif_usc)
    h.harga_beli_maks_rp_kg = rumus.usc_ke_rp(h.harga_beli_maks_usc, baris.kurs)

    # Harga beli aktual terakhir (hari pembelian terakhir <= tanggal)
    aktual = session.scalars(select(MartHarian).where(
        MartHarian.tanggal <= baris.tanggal, MartHarian.qty_kering_kg != None,  # noqa: E711
    ).order_by(MartHarian.tanggal.desc())).first()
    if aktual and aktual.harga_usc_per_kg:
        h.harga_beli_aktual_terakhir_usc = aktual.harga_usc_per_kg
        h.tanggal_harga_aktual = aktual.tanggal

    batas = f"{kena.batas_bawah if kena.batas_bawah is not None else '-tak terbatas'} s.d. " \
            f"{kena.batas_atas if kena.batas_atas is not None else 'tak terbatas'}"
    h.alasan.extend([
        f"Rasio stok/safety = {baris.rasio_stok:.4f} (stok {baris.stok_ton:,.1f} ton, "
        f"safety {baris.safety_ton:,.1f} ton).",
        f"Baris aturan yang kena: rentang [{batas}) -> penyesuaian {kena.penyesuaian_usc:+.2f} US¢/kg"
        + (f" ({kena.keterangan})" if kena.keterangan else ""),
        f"Target bulan {target.target_usc_per_kg:.2f} + penyesuaian {kena.penyesuaian_usc:+.2f} "
        f"= target efektif {h.target_efektif_usc:.2f} US¢/kg.",
        f"SICOM {baris.sicom_usc:.2f} US¢/kg, kurs {baris.kurs:,.0f} IDR/USD.",
        f"Harga beli maks = SICOM - target efektif = {h.harga_beli_maks_usc:.4f} US¢/kg "
        f"= {h.harga_beli_maks_rp_kg:,.2f} Rp/kg.",
    ])
    if h.aturan_contoh:
        h.alasan.append("PERHATIAN: aturan yang dipakai masih CONTOH dari template, "
                        "belum kebijakan resmi.")
    return h
