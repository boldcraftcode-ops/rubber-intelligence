"""Analisis hubungan rasio stok dengan OP Margin per bulan (bagian 7).

PENTING: ini INFORMASI, bukan aturan. Korelasi adalah asosiasi,
bukan bukti sebab-akibat — teks itu wajib tampil di layar.

Halaman "Stok vs Margin" dulu hanya mengembalikan SATU korelasi untuk seluruh
periode. Itu menyesatkan: tahun yang berbeda bisa punya hubungan yang berbeda
arah. Karena itu sekarang dikirim juga:
- `per_tahun`  : korelasi & rata-rata tiap tahun (untuk melihat kestabilan);
- `kelompok`   : margin rata-rata per kelompok rasio stok (tipis/sedang/tebal);
- `peringatan` : kalimat siap tampil bila hubungannya tidak stabil.
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

#: Ambang kelompok stok: (label, batas bawah inklusif, batas atas eksklusif).
#: Sengaja sama dengan ambang yang sudah dipakai di layar ("< 50%" dan ">= 80%").
KELOMPOK: list[tuple[str, float | None, float | None]] = [
    ("Stok tipis (< 50% safety)", None, 0.5),
    ("Stok sedang (50% s.d. 80% safety)", 0.5, 0.8),
    ("Stok tebal (>= 80% safety)", 0.8, None),
]


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


def _rata(nilai: list[float]) -> float | None:
    return round(sum(nilai) / len(nilai), 4) if nilai else None


def _ringkas(titik: list[dict]) -> dict:
    """Ringkasan satu kumpulan titik (semua periode, atau satu tahun)."""
    x = [t["rasio_stok"] for t in titik]
    y = [t["op_margin"] for t in titik]
    rendah = [t["op_margin"] for t in titik if t["rasio_stok"] < 0.5]
    tinggi = [t["op_margin"] for t in titik if t["rasio_stok"] >= 0.8]
    korelasi = _korelasi_pearson(x, y)
    m_rendah = _rata(rendah)
    m_tinggi = _rata(tinggi)
    return {
        "jumlah_bulan": len(titik),
        "korelasi": round(korelasi, 4) if korelasi is not None else None,
        "rasio_rata": _rata(x),
        "margin_rata": _rata(y),
        "margin_stok_rendah": m_rendah,
        "jumlah_bulan_stok_rendah": len(rendah),
        "margin_stok_tinggi": m_tinggi,
        "jumlah_bulan_stok_tinggi": len(tinggi),
        "selisih_tinggi_rendah": (round(m_tinggi - m_rendah, 4)
                                  if m_rendah is not None and m_tinggi is not None
                                  else None),
    }


def _semua_titik(session: Session) -> list[dict]:
    """Satu titik per bulan: rata-rata rasio stok harian + OP Margin bulanan."""
    rasio_bulan: dict[tuple[int, int], list[float]] = defaultdict(list)
    for h in session.scalars(select(MartHarian).where(MartHarian.rasio_stok != None)):  # noqa: E711
        rasio_bulan[(h.tanggal.year, h.tanggal.month)].append(h.rasio_stok)

    titik: list[dict] = []
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
    return titik


def _kelompok(titik: list[dict]) -> list[dict]:
    hasil = []
    for label, bawah, atas in KELOMPOK:
        anggota = [t for t in titik
                   if (bawah is None or t["rasio_stok"] >= bawah)
                   and (atas is None or t["rasio_stok"] < atas)]
        hasil.append({
            "label": label,
            "batas_bawah": bawah,
            "batas_atas": atas,
            "jumlah_bulan": len(anggota),
            "margin_rata": _rata([t["op_margin"] for t in anggota]),
            "ton_rata": _rata([t["ton"] for t in anggota]),
            "bulan": [f"{t['tahun']}-{t['bulan']:02d}" for t in anggota],
        })
    return hasil


def _peringatan(ringkas: dict, per_tahun: list[dict], tahun: int | None) -> list[str]:
    pesan: list[str] = []
    nilai = [p["korelasi"] for p in per_tahun if p["korelasi"] is not None]
    # Tanpa korelasi gabungan (mis. tahun terpilih kosong) tidak ada yang bisa
    # dibandingkan: peringatan ketidakstabilan dilewati.
    if ringkas["korelasi"] is not None and len(nilai) >= 2:
        beda = max(nilai) - min(nilai)
        if beda >= 0.5:
            rinci = ", ".join(f"{p['tahun']}: {p['korelasi']:.2f}"
                              for p in per_tahun if p["korelasi"] is not None)
            pesan.append(
                "Hubungan ini TIDAK stabil antar tahun (" + rinci + "). "
                f"Angka gabungan {ringkas['korelasi']:.2f} mencampur kondisi "
                "pasar yang berbeda, jadi jangan dipakai sebagai aturan. "
                "Baca per tahun, atau pilih satu tahun di atas.")
    if tahun is not None and ringkas["jumlah_bulan"] < 12:
        pesan.append(f"Tahun {tahun} baru berisi {ringkas['jumlah_bulan']} bulan, "
                     "jadi angkanya belum bisa dibandingkan dengan tahun penuh.")
    if ringkas["korelasi"] is None:
        pesan.append("Bulan berdata kurang dari 3, korelasi belum bisa dihitung.")
    return pesan


def analisis_stok_margin(session: Session, tahun: int | None = None) -> dict:
    """Hubungan rasio stok vs OP Margin. `tahun` hanya menyaring yang ditampilkan;
    `per_tahun` selalu memakai seluruh data supaya kestabilannya kelihatan."""
    semua = _semua_titik(session)
    titik = [t for t in semua if tahun is None or t["tahun"] == tahun]

    kelompok_tahun: dict[int, list[dict]] = defaultdict(list)
    for t in semua:
        kelompok_tahun[t["tahun"]].append(t)
    per_tahun = [{"tahun": th, **_ringkas(isi)}
                 for th, isi in sorted(kelompok_tahun.items())]

    ringkas = _ringkas(titik)
    return {
        "tahun": tahun,
        "tahun_tersedia": sorted(kelompok_tahun),
        **ringkas,
        "titik": titik,
        "per_tahun": per_tahun,
        "kelompok": _kelompok(titik),
        "peringatan": _peringatan(ringkas, per_tahun, tahun),
        "catatan": CATATAN,
    }
