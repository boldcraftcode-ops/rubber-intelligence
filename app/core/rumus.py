"""Rumus inti OP Margin — harus persis seperti Excel lama.

Semua fungsi di sini murni (tanpa database) supaya mudah diuji dengan
kasus uji emas. Satuan:
- qty  : kg berat kering
- amount: Rupiah penuh
- kurs : IDR per USD
- harga/margin: US¢/kg
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence


def _f(x) -> float:
    """Konversi aman Decimal/int/str ke float untuk perhitungan."""
    return float(x) if x is not None else 0.0


# ----------------------------------------------------------------------------
# Harian
# ----------------------------------------------------------------------------
def harga_rp_per_kg(amount_rp, qty_kg) -> float:
    """harga_rp_kg = amount_rp / qty_kering_kg. Hari tanpa pembelian -> 0."""
    q = _f(qty_kg)
    if q == 0:
        return 0.0
    return _f(amount_rp) / q


def rp_ke_usc(harga_rp_kg, kurs) -> float:
    """harga_usc_kg = harga_rp_kg / kurs * 100."""
    k = _f(kurs)
    if k == 0:
        return 0.0
    return _f(harga_rp_kg) / k * 100.0


def usc_ke_rp(harga_usc_kg, kurs) -> float:
    """Kebalikan rp_ke_usc: US¢/kg -> Rp/kg."""
    return _f(harga_usc_kg) * _f(kurs) / 100.0


def margin_harian(sicom_usc, harga_usc) -> float:
    """margin = SICOM - harga beli (US¢/kg)."""
    return _f(sicom_usc) - _f(harga_usc)


# ----------------------------------------------------------------------------
# Bulanan (bobot = tonase kering, hanya hari pembelian)
# ----------------------------------------------------------------------------
@dataclass
class BarisHarian:
    """Satu hari pembelian: qty (kg kering), amount (Rp), kurs, sicom."""

    qty_kg: float
    amount_rp: float
    kurs: float
    sicom_usc: float


@dataclass
class HasilBulanan:
    qty_ton: float
    sicom_usc: float | None
    harga_beli_usc: float | None
    op_margin_usc: float | None


def agregat_bulanan(baris: Sequence[BarisHarian]) -> HasilBulanan:
    """sicom_bulan = SUM(qty*sicom)/SUM(qty);
    harga_beli_bulan_usc = 100 * SUM(amount/kurs) / SUM(qty);
    op_margin_bulan = sicom_bulan - harga_beli_bulan_usc.
    Hanya hari dengan pembelian (qty > 0) yang dihitung."""
    aktif = [b for b in baris if _f(b.qty_kg) > 0]
    total_qty = sum(_f(b.qty_kg) for b in aktif)
    if total_qty == 0:
        return HasilBulanan(0.0, None, None, None)
    sicom = sum(_f(b.qty_kg) * _f(b.sicom_usc) for b in aktif) / total_qty
    usd = sum(_f(b.amount_rp) / _f(b.kurs) for b in aktif)
    harga = 100.0 * usd / total_qty
    return HasilBulanan(total_qty / 1000.0, sicom, harga, sicom - harga)


def pencapaian(op_margin_usc, target_usc) -> float | None:
    """pencapaian = op_margin_bulan / target_bulan (di Excel berlabel '%')."""
    t = _f(target_usc)
    if t == 0:
        return None
    return _f(op_margin_usc) / t


def rata_rata_sederhana(nilai: Iterable[float]) -> float | None:
    """Rata-rata sederhana bulan yang berdata (resmi, seperti Excel)."""
    v = [x for x in nilai if x is not None]
    return sum(v) / len(v) if v else None


def rata_rata_tertimbang(pasangan: Iterable[tuple[float, float]]) -> float | None:
    """Rata-rata tertimbang tonase (informasi). pasangan = (nilai, bobot_ton)."""
    p = [(n, b) for n, b in pasangan if n is not None and b]
    tot = sum(b for _, b in p)
    return sum(n * b for n, b in p) / tot if tot else None


# ----------------------------------------------------------------------------
# Stok & Days
# ----------------------------------------------------------------------------
def stok_ton(stok_kg) -> float:
    return _f(stok_kg) / 1000.0


def hitung_days(stok_ton_: float, kapasitas_ton_per_hari) -> float | None:
    """days = stok_ton / kapasitas olah (ton/hari)."""
    k = _f(kapasitas_ton_per_hari)
    return stok_ton_ / k if k else None


def hitung_safety_ton(safety_stock_ton, safety_stock_hari, kapasitas_ton_per_hari) -> float | None:
    """Bila Safety_Stock_Ton kosong: safety_ton = Safety_Stock_Hari x kapasitas."""
    if safety_stock_ton not in (None, 0):
        return _f(safety_stock_ton)
    if safety_stock_hari not in (None, 0):
        return _f(safety_stock_hari) * _f(kapasitas_ton_per_hari)
    return None


def rasio_stok(stok_ton_: float, safety_ton: float | None) -> float | None:
    if not safety_ton:
        return None
    return stok_ton_ / safety_ton


@dataclass
class BarisAturan:
    """Satu baris aturan stok->harga: batas bawah (>=), batas atas (<)."""

    batas_bawah: float | None
    batas_atas: float | None
    penyesuaian_usc: float
    keterangan: str | None = None


def cari_aturan(aturan: Sequence[BarisAturan], rasio: float) -> BarisAturan | None:
    """Cari baris aturan yang memuat rasio: batas_bawah <= rasio < batas_atas.
    Batas kosong berarti tak terbatas. Mengembalikan None bila tidak ada."""
    for a in aturan:
        bawah_ok = a.batas_bawah is None or rasio >= a.batas_bawah
        atas_ok = a.batas_atas is None or rasio < a.batas_atas
        if bawah_ok and atas_ok:
            return a
    return None


def target_efektif(target_usc, penyesuaian_usc) -> float:
    return _f(target_usc) + _f(penyesuaian_usc)


def harga_beli_maks_usc(sicom_usc, target_efektif_usc) -> float:
    """harga_beli_maks_usc = sicom hari ini - target efektif."""
    return _f(sicom_usc) - _f(target_efektif_usc)


# ----------------------------------------------------------------------------
# Perencanaan tahun depan (pengganti sheet Y27)
# ----------------------------------------------------------------------------
def rencana_net_margin(margin_bulan_tahun_dipilih: Sequence[float],
                       penyesuaian_manual_usc,
                       effort_usc) -> float | None:
    """net_margin = rata-rata OP Margin bulan yang sama dari tahun terpilih
    + penyesuaian manual + effort."""
    dasar = rata_rata_sederhana(margin_bulan_tahun_dipilih)
    if dasar is None:
        return None
    return dasar + _f(penyesuaian_manual_usc) + _f(effort_usc)
