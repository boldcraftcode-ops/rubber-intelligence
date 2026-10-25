"""API analisis Fase 3: ringkasan ala Excel, rekonsiliasi, kualitas data,
kartu query dengan filter berdaftar-putih, telusur asal angka, dan ekspor
Excel. Tidak ada SQL dari klien — semua kartu adalah query terdefinisi.
"""
from __future__ import annotations

import calendar
import datetime as dt
import io
import pathlib
from collections import defaultdict
from decimal import Decimal

import openpyxl
import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core import rumus
from .core.kualitas import (
    data_terlambat,
    hari_pembelian_tanpa_sicom,
    kpi_reject,
    lonjakan_harga_harian,
    ringkasan_peringatan,
)
from .core.lookup import PencariBerlaku
from .core.rekonsiliasi import (
    CATATAN_DIKETAHUI,
    SELISIH_DIKETAHUI,
    rekonsiliasi_harian,
    selisih_diketahui,
)
from .models import (
    Grade,
    Kurs,
    MartBulanan,
    MartHarian,
    ParameterPabrik,
    Pembelian,
    RawUnggahan,
    Sicom,
    TiketBaris,
    Vendor,
)

# Catatan koreksi resmi terhadap Excel lama (bagian 6 spesifikasi).
KOREKSI = {
    (2022, 4): "Excel lama menampilkan 5,5232 karena salah ketik di sel T147 "
               "(sudah dikonfirmasi). Sistem memakai nilai benar 4,3391 — "
               "dicatat sebagai koreksi, tidak direplikasi.",
}

NAMA_BULAN_SINGKAT = ("", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                      "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

DIMENSI_TONASE = ("vendor", "grade", "provinsi", "kabupaten", "kecamatan", "desa")
URUTAN_WILAYAH = ("provinsi", "kabupaten", "kecamatan", "desa")


# ----------------------------------------------------------------------------
# Alat bantu
# ----------------------------------------------------------------------------
def respon_xlsx(nama_file: str, judul: list[str], baris: list[list]) -> StreamingResponse:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(judul)
    for b in baris:
        ws.append(b)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nama_file}"'})


def _rentang(tahun: int | None, bulan: int | None):
    if tahun is None:
        return None, None
    if bulan is None:
        return dt.date(tahun, 1, 1), dt.date(tahun, 12, 31)
    akhir = (dt.date(tahun + (bulan == 12), (bulan % 12) + 1, 1) - dt.timedelta(days=1))
    return dt.date(tahun, bulan, 1), akhir


def _filter_tiket(q, tahun=None, bulan=None, vendor=None, grade=None, eudr=None,
                  provinsi=None, kabupaten=None, kecamatan=None, desa=None,
                  session: Session | None = None):
    """Filter berdaftar-putih untuk kartu berbasis tiket."""
    q = q.where(TiketBaris.tiket_nol == False)  # noqa: E712
    awal, akhir = _rentang(tahun, bulan)
    if awal:
        q = q.where(TiketBaris.ticket_date >= awal, TiketBaris.ticket_date <= akhir)
    if vendor:
        q = q.where(TiketBaris.kode_vendor == vendor.upper())
    if grade:
        q = q.where(TiketBaris.item_code == grade)
    if eudr is not None and session is not None:
        kode_eudr = [g.item_code for g in session.scalars(select(Grade).where(Grade.eudr == True))]  # noqa: E712
        q = q.where(TiketBaris.item_code.in_(kode_eudr) if eudr
                    else TiketBaris.item_code.not_in(kode_eudr))
    if provinsi:
        q = q.where(TiketBaris.provinsi == provinsi)
    if kabupaten:
        q = q.where(TiketBaris.kabupaten == kabupaten)
    if kecamatan:
        q = q.where(TiketBaris.kecamatan == kecamatan)
    if desa:
        q = q.where(TiketBaris.desa == desa)
    return q


def _bulan_berurutan(awal: tuple[int, int], akhir: tuple[int, int]) -> list[tuple[int, int]]:
    """Daftar (tahun, bulan) dari awal sampai akhir, termasuk bulan kosong.

    Bulan tanpa tiket tetap ditampilkan (nilai 0) supaya grafik tidak
    "melompat" dan pembaca melihat bulan yang memang tidak ada penerimaan.
    """
    hasil: list[tuple[int, int]] = []
    th, bl = awal
    while (th, bl) <= akhir and len(hasil) < 120:
        hasil.append((th, bl))
        bl += 1
        if bl > 12:
            th, bl = th + 1, 1
    return hasil


def _daftar_bulan(dari: dt.date | None, sampai: dt.date | None,
                 berdata: list[tuple[int, int]], maks: int = 24) -> list[tuple[int, int]]:
    """Sumbu bulan untuk rincian bulanan.

    Mengikuti periode filter (bukan data), supaya mengganti filter lain tidak
    menggeser sumbu dan membandingkan bulan jadi menyesatkan. Bila rentangnya
    lebih panjang dari `maks` bulan, dipotong ke rentang bulan berdata.
    """
    if dari and sampai and (dari.year, dari.month) <= (sampai.year, sampai.month):
        bulan = _bulan_berurutan((dari.year, dari.month), (sampai.year, sampai.month))
        if len(bulan) > maks and berdata:
            bulan = [b for b in bulan if berdata[0] <= b <= berdata[-1]]
        return bulan
    if berdata:
        return _bulan_berurutan(berdata[0], berdata[-1])
    return []


def _label_bulan_singkat(th: int, bl: int) -> str:
    return f"{NAMA_BULAN_SINGKAT[bl]}-{str(th)[2:]}"


def _penerimaan_per_bulan(potongan: list[tuple], dimensi: str,
                          dari: dt.date | None, sampai: dt.date | None,
                          top: int, format: str | None,
                          session: Session) -> dict:
    """Bentuk jawaban `per=bulan`: bulan x dimensi.

    Dipakai saat filter periode mencakup lebih dari satu bulan, supaya
    pembaca melihat pergerakan tiap vendor/wilayah dari bulan ke bulan —
    bukan hanya total sepanjang periode.

    Semua angka kg kering. `top` dimensi terbesar dipertahankan; sisanya
    digabung menjadi satu baris "Lainnya" agar grafik tetap terbaca.
    """
    # ---- daftar bulan
    # Sumbu bulan MENGIKUTI periode filter (bukan data), supaya mengganti filter
    # lain (mis. hanya EUDR) tidak menggeser sumbu dan membandingkan bulan jadi
    # menyesatkan. Bulan tanpa tiket tampil sebagai 0.
    # Pengecualian: bila rentangnya sangat panjang (> 24 bulan) tetapi datanya
    # hanya menempati sebagian, dipotong ke rentang bulan berdata agar grafik
    # tidak dipenuhi puluhan kolom kosong.
    berdata = sorted({b for _k, b, _kg, _e, _t in potongan if b})
    if dari and sampai and (dari.year, dari.month) <= (sampai.year, sampai.month):
        bulan = _bulan_berurutan((dari.year, dari.month), (sampai.year, sampai.month))
        if len(bulan) > 24 and berdata:
            bulan = [b for b in bulan if berdata[0] <= b <= berdata[-1]]
    elif berdata:
        bulan = _bulan_berurutan(berdata[0], berdata[-1])
    else:
        bulan = []
    indeks = {b: i for i, b in enumerate(bulan)}
    label_bulan = [_label_bulan_singkat(th, bl) for th, bl in bulan]

    # ---- agregasi per (dimensi, bulan), dipisah biasa/EUDR
    isi: dict[str, dict] = defaultdict(
        lambda: {"biasa": [0.0] * len(bulan), "eudr": [0.0] * len(bulan),
                 "tiket": set()})
    for kunci, bln, kg, e, no_tiket in potongan:
        i = indeks.get(bln)
        if i is None:
            continue
        isi[kunci]["eudr" if e else "biasa"][i] += kg
        isi[kunci]["tiket"].add(no_tiket)

    def total(baris: dict) -> float:
        return sum(baris["biasa"]) + sum(baris["eudr"])

    total_kg = sum(total(a) for a in isi.values())
    urut = sorted(isi.items(), key=lambda kv: -total(kv[1]))

    nama_vendor = {v.kode: v.nama_baku for v in session.scalars(select(Vendor))} \
        if dimensi == "vendor" else {}

    def label_dari(kunci: str) -> str:
        return f"{kunci} — {nama_vendor[kunci]}" if kunci in nama_vendor else kunci

    def kg_bulan(a: dict) -> list[float]:
        return [round(x + y, 1) for x, y in zip(a["biasa"], a["eudr"])]

    baris_keluar: list[dict] = []
    for kunci, a in urut[:top]:
        baris_keluar.append({
            "kunci": kunci, "label": label_dari(kunci),
            "kg_per_bulan": kg_bulan(a),
            "kg_biasa_per_bulan": [round(x, 1) for x in a["biasa"]],
            "kg_eudr_per_bulan": [round(x, 1) for x in a["eudr"]],
            "kg_total": round(total(a), 1),
            "porsi": round(total(a) / total_kg, 4) if total_kg else None,
            "jumlah_tiket": len(a["tiket"]),
        })

    # sisa dimensi digabung supaya jumlah baris di grafik tetap wajar
    if len(urut) > top:
        sisa = urut[top:]
        gab = {"biasa": [0.0] * len(bulan), "eudr": [0.0] * len(bulan),
               "tiket": set()}
        for _k, a in sisa:
            for i in range(len(bulan)):
                gab["biasa"][i] += a["biasa"][i]
                gab["eudr"][i] += a["eudr"][i]
            gab["tiket"] |= a["tiket"]
        baris_keluar.append({
            "kunci": "__lainnya__",
            "label": f"Lainnya ({len(sisa)} {dimensi})",
            "kg_per_bulan": kg_bulan(gab),
            "kg_biasa_per_bulan": [round(x, 1) for x in gab["biasa"]],
            "kg_eudr_per_bulan": [round(x, 1) for x in gab["eudr"]],
            "kg_total": round(total(gab), 1),
            "porsi": round(total(gab) / total_kg, 4) if total_kg else None,
            "jumlah_tiket": len(gab["tiket"]),
            "gabungan": True,
        })

    total_per_bulan = [round(sum(b["kg_per_bulan"][i] for b in baris_keluar), 1)
                       for i in range(len(bulan))]

    drill = None
    if dimensi in URUTAN_WILAYAH[:-1]:
        drill = URUTAN_WILAYAH[URUTAN_WILAYAH.index(dimensi) + 1]

    hasil = {
        "dimensi": dimensi, "per": "bulan", "top": top,
        "drill_berikutnya": drill,
        "bulan": [{"ym": f"{th}-{bl:02d}", "label": lb}
                  for (th, bl), lb in zip(bulan, label_bulan)],
        "jumlah_bulan": len(bulan),
        "baris": baris_keluar,
        "total_per_bulan": total_per_bulan,
        "total_kg": round(total_kg, 1),
        # dipertahankan agar ringkasan di layar bisa memakai satu bentuk
        "total_kg_biasa": round(sum(sum(a["biasa"]) for a in isi.values()), 1),
        "total_kg_eudr": round(sum(sum(a["eudr"]) for a in isi.values()), 1),
        "total_tiket": len({t for k, _b, _kg, _e, t in potongan}),
        "jumlah_dimensi": len(urut),
        "sumber": "tiket_baris (Dry kg, tanpa tiket nol); EUDR = grade ber-flag "
                  "EUDR / kode TTSR",
    }
    if format == "xlsx":
        judul = [dimensi] + label_bulan + ["Total kg", "Porsi"]
        isi_xlsx = []
        for b in baris_keluar:
            isi_xlsx.append([b["label"]] + b["kg_per_bulan"] + [b["kg_total"],
                                                                b["porsi"]])
        isi_xlsx.append(["TOTAL"] + total_per_bulan
                        + [round(sum(total_per_bulan), 1), None])
        return respon_xlsx(f"penerimaan_per_{dimensi}_per_bulan.xlsx",
                           judul, isi_xlsx)
    return hasil


def _margin_per_bulan(rinci: list, dimensi: str, kurs_cari, sicom_cari,
                      awal: dt.date, akhir: dt.date, top: int,
                      format: str | None) -> dict:
    """Bentuk jawaban `per=bulan` untuk kartu Margin per grade/vendor.

    Margin adalah TINGKAT (US¢/kg), bukan jumlah — jadi tidak boleh dijumlahkan
    antar dimensi. Untuk total per bulan dipakai agregat tertimbang tonase
    seluruh data bulan itu (rumus yang sama dengan mart bulanan).
    """
    berdata = sorted({(p.tanggal.year, p.tanggal.month) for p in rinci})
    bulan = _daftar_bulan(awal, akhir, berdata)
    indeks = {b: i for i, b in enumerate(bulan)}
    label_bulan = [_label_bulan_singkat(th, bl) for th, bl in bulan]
    n = len(bulan)

    per_kunci: dict[str, dict] = defaultdict(
        lambda: {"harian": [[] for _ in range(n)]})
    semua_bulan: list[list] = [[] for _ in range(n)]
    tiket_bulan: list[set] = [set() for _ in range(n)]
    for p in rinci:
        k = kurs_cari.pada(p.tanggal)
        s = sicom_cari.pada(p.tanggal)
        if not k or not s:
            continue
        i = indeks.get((p.tanggal.year, p.tanggal.month))
        if i is None:
            continue
        baris_h = rumus.BarisHarian(float(p.qty_kering_kg), float(p.amount_rp),
                                   float(k.idr_per_usd), s.usc_per_kg)
        kunci = p.item_code if dimensi == "grade" else p.kode_vendor
        per_kunci[kunci]["harian"][i].append(baris_h)
        semua_bulan[i].append(baris_h)

    def ton_dari(data: list) -> float:
        return sum(x.qty_kg for x in data) / 1000.0

    def margin_dari(data: list) -> float | None:
        if not data:
            return None
        return rumus.agregat_bulanan(data).op_margin_usc

    keluar: list[dict] = []
    urut = sorted(per_kunci.items(),
                  key=lambda kv: -sum(ton_dari(d) for d in kv[1]["harian"]))
    total_ton = sum(ton_dari(d) for _k, a in urut for d in a["harian"])

    for kunci, a in urut[:top]:
        ton_baris = [round(ton_dari(d), 3) for d in a["harian"]]
        keluar.append({
            "kunci": kunci,
            "ton_per_bulan": ton_baris,
            "margin_per_bulan": [
                (round(m, 4) if (m := margin_dari(d)) is not None else None)
                for d in a["harian"]],
            "ton": round(sum(ton_baris), 3),
            "porsi": round(sum(ton_baris) / total_ton, 4) if total_ton else None,
            "op_margin": margin_dari([x for d in a["harian"] for x in d]),
        })

    if len(urut) > top:
        sisa = urut[top:]
        gab = [[] for _ in range(n)]
        for _k, a in sisa:
            for i in range(n):
                gab[i].extend(a["harian"][i])
        ton_baris = [round(ton_dari(d), 3) for d in gab]
        keluar.append({
            "kunci": "__lainnya__",
            "label": f"Lainnya ({len(sisa)} {dimensi})",
            "ton_per_bulan": ton_baris,
            "margin_per_bulan": [
                (round(m, 4) if (m := margin_dari(d)) is not None else None)
                for d in gab],
            "ton": round(sum(ton_baris), 3),
            "porsi": round(sum(ton_baris) / total_ton, 4) if total_ton else None,
            "op_margin": margin_dari([x for d in gab for x in d]),
            "gabungan": True,
        })

    total_per_bulan = {
        "ton": [round(ton_dari(d), 3) for d in semua_bulan],
        "op_margin": [
            (round(m, 4) if (m := margin_dari(d)) is not None else None)
            for d in semua_bulan],
    }
    hasil = {
        "status": "ok", "dimensi": dimensi, "per": "bulan", "top": top,
        "bulan": [{"ym": f"{th}-{bl:02d}", "label": lb}
                  for (th, bl), lb in zip(bulan, label_bulan)],
        "jumlah_bulan": n,
        "baris": keluar,
        "total_per_bulan": total_per_bulan,
        "jumlah_dimensi": len(urut),
        "sumber": "pembelian rinci (bukan total harian) — margin US¢/kg "
                  "tertimbang tonase kering",
    }
    if format == "xlsx":
        judul = [dimensi] + [f"Margin {lb}" for lb in label_bulan] + ["Margin total"]
        isi_xlsx = [[b.get("label", b["kunci"])] + b["margin_per_bulan"]
                    + [b["op_margin"]] for b in keluar]
        return respon_xlsx(f"margin_per_{dimensi}_per_bulan.xlsx", judul, isi_xlsx)
    return hasil


def _tonase_per_bulan(potongan: list[tuple], dimensi: str,
                      dari: dt.date | None, sampai: dt.date | None,
                      top: int, format: str | None,
                      session: Session) -> dict:
    """Bentuk jawaban `per=bulan` untuk kartu Tonase: bulan x dimensi (ton)."""
    berdata = sorted({b for _k, b, _t, _n in potongan if b})
    bulan = _daftar_bulan(dari, sampai, berdata)
    indeks = {b: i for i, b in enumerate(bulan)}
    label_bulan = [_label_bulan_singkat(th, bl) for th, bl in bulan]

    isi: dict[str, dict] = defaultdict(lambda: {"ton": [0.0] * len(bulan),
                                                "tiket": set()})
    for kunci, bln, ton, no_tiket in potongan:
        i = indeks.get(bln)
        if i is None:
            continue
        isi[kunci]["ton"][i] += ton
        isi[kunci]["tiket"].add(no_tiket)

    total_ton = sum(sum(a["ton"]) for a in isi.values())
    urut = sorted(isi.items(), key=lambda kv: -sum(kv[1]["ton"]))
    nama_vendor = {v.kode: v.nama_baku for v in session.scalars(select(Vendor))} \
        if dimensi == "vendor" else {}

    baris_keluar: list[dict] = []
    for kunci, a in urut[:top]:
        baris_keluar.append({
            "kunci": kunci,
            "label": f"{kunci} — {nama_vendor[kunci]}" if kunci in nama_vendor else kunci,
            "ton_per_bulan": [round(x, 3) for x in a["ton"]],
            "ton": round(sum(a["ton"]), 3),
            "porsi": round(sum(a["ton"]) / total_ton, 4) if total_ton else None,
            "jumlah_tiket": len(a["tiket"]),
        })

    if len(urut) > top:
        sisa = urut[top:]
        gab = [0.0] * len(bulan)
        tiket = set()
        for _k, a in sisa:
            for i in range(len(bulan)):
                gab[i] += a["ton"][i]
            tiket |= a["tiket"]
        baris_keluar.append({
            "kunci": "__lainnya__",
            "label": f"Lainnya ({len(sisa)} {dimensi})",
            "ton_per_bulan": [round(x, 3) for x in gab],
            "ton": round(sum(gab), 3),
            "porsi": round(sum(gab) / total_ton, 4) if total_ton else None,
            "jumlah_tiket": len(tiket),
            "gabungan": True,
        })

    total_per_bulan = [round(sum(b["ton_per_bulan"][i] for b in baris_keluar), 3)
                       for i in range(len(bulan))]
    drill = None
    if dimensi in URUTAN_WILAYAH[:-1]:
        drill = URUTAN_WILAYAH[URUTAN_WILAYAH.index(dimensi) + 1]

    hasil = {
        "dimensi": dimensi, "per": "bulan", "top": top,
        "drill_berikutnya": drill,
        "bulan": [{"ym": f"{th}-{bl:02d}", "label": lb}
                  for (th, bl), lb in zip(bulan, label_bulan)],
        "jumlah_bulan": len(bulan),
        "baris": baris_keluar,
        "total_per_bulan": total_per_bulan,
        "total_ton": round(total_ton, 3),
        "total_tiket": len({n for _k, _b, _t, n in potongan}),
        "jumlah_dimensi": len(urut),
        "sumber": "tiket_baris (Dry, tanpa tiket nol)",
    }
    if format == "xlsx":
        judul = [dimensi] + label_bulan + ["Total ton", "Porsi"]
        isi_xlsx = [[b["label"]] + b["ton_per_bulan"] + [b["ton"], b["porsi"]]
                    for b in baris_keluar]
        isi_xlsx.append(["TOTAL"] + total_per_bulan
                        + [round(sum(total_per_bulan), 3), None])
        return respon_xlsx(f"tonase_per_{dimensi}_per_bulan.xlsx", judul, isi_xlsx)
    return hasil


def _agregat_bridge(baris) -> dict | None:
    """Agregasi satu periode memakai rumus persis mart bulanan, plus pasangan
    (E, K) untuk dekomposisi bridge:

        E = SUM(amount) / SUM(qty)              -- harga beli Rp/kg tertimbang
        K = SUM(amount) / SUM(amount/kurs)      -- kurs efektif tertimbang

    Sehingga harga USc/kg = 100 x E/K secara identik, dan selisih harga
    antar periode terurai PERSIS (tanpa sisa) menjadi:

        efek harga Rp  = 100 x (E_B - E_A) / K_A
        efek kurs      = 100 x E_B x (1/K_B - 1/K_A)

    Syarat baris sama dengan agregat_bulanan: qty > 0, kurs ada, sicom ada.
    Mengembalikan None bila periode tidak punya hari pembelian.
    """
    aktif = [b for b in baris
             if b.qty_kering_kg and b.qty_kering_kg > 0
             and b.kurs and b.sicom_usc is not None]
    if not aktif:
        return None
    qty = sum(b.qty_kering_kg for b in aktif)
    if qty <= 0:
        return None
    rp = sum(float(b.amount_rp or 0.0) for b in aktif)
    usd = sum(float(b.amount_rp or 0.0) / b.kurs for b in aktif)
    if usd <= 0:
        return None
    sicom = sum(b.qty_kering_kg * b.sicom_usc for b in aktif) / qty
    harga = 100.0 * usd / qty
    return {
        "sicom": sicom,
        "harga": harga,
        "margin": sicom - harga,
        "qty_ton": qty / 1000.0,
        "hari_pembelian": len(aktif),
        "e_rp_kg": rp / qty,
        "kurs_efektif": rp / usd,
    }


def _bulan_ym(teks: str | None, nama: str) -> tuple[int, int] | None:
    """Parse periode 'YYYY-MM' (format filter kartu RM Stock - Intake vs Pricing)."""
    if not teks:
        return None
    try:
        th, bl = teks.split("-")[:2]
        th, bl = int(th), int(bl)
        if not 1 <= bl <= 12:
            raise ValueError
        return th, bl
    except Exception:
        raise HTTPException(422, f"Parameter '{nama}' harus format YYYY-MM "
                                 f"(contoh: 2026-08), bukan '{teks}'.")


# Ambang "tipis": margin di atas target tetapi kurang dari 1 US¢/kg. Hijau
# penuh pada selisih sekecil itu menyesatkan (mis. Agu-26 hanya +0,37).
AMBANG_TIPIS_USC = 1.0


def _status_target(margin, target) -> str:
    """'di atas target' / 'tipis' / 'di bawah target' / 'tanpa target'."""
    if margin is None or target is None:
        return "tanpa target"
    selisih = margin - target
    if selisih < 0:
        return "di bawah target"
    if selisih < AMBANG_TIPIS_USC:
        return "tipis"
    return "di atas target"


def _jumlah_hari(th: int, bl: int) -> int:
    """Jumlah hari dalam bulan (untuk pemakaian per hari)."""
    return calendar.monthrange(th, bl)[1]


def _bulan_sebelum(th: int, bl: int) -> tuple[int, int]:
    return (th - 1, 12) if bl == 1 else (th, bl - 1)


def _tanggal_teks(teks: str | None, nama: str, akhir_bulan: bool = False):
    """Parse 'YYYY-MM' (jadi tanggal 1 / akhir bulan) atau 'YYYY-MM-DD'."""
    if not teks:
        return None
    try:
        if len(teks) == 7:  # YYYY-MM
            th, bl = _bulan_ym(teks, nama)
            return _rentang(th, bl)[1] if akhir_bulan else dt.date(th, bl, 1)
        return dt.date.fromisoformat(teks)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, f"Parameter '{nama}' harus format YYYY-MM atau "
                                 f"YYYY-MM-DD, bukan '{teks}'.")


def _baris_periode_bulanan(session: Session, tahun: int, bulan: int):
    """Baris mart harian satu bulan (dipakai margin bridge)."""
    awal, akhir = _rentang(tahun, bulan)
    return list(session.scalars(select(MartHarian).where(
        MartHarian.tanggal >= awal, MartHarian.tanggal <= akhir)))


def _baris_periode_tahunan(session: Session, tahun: int, bulan_umum: list[int]):
    """Baris mart harian satu tahun, hanya pada bulan-bulan yang diminta."""
    return [h for h in session.scalars(select(MartHarian).where(
            MartHarian.tanggal >= dt.date(tahun, 1, 1),
            MartHarian.tanggal <= dt.date(tahun, 12, 31)))
            if h.tanggal.month in bulan_umum]


def _unggahan_info(session: Session, unggahan_id: int | None) -> dict | None:
    if unggahan_id is None:
        return None
    u = session.get(RawUnggahan, unggahan_id)
    if u is None:
        return None
    return {"id": u.id, "nama_file": u.nama_file, "pengunggah": u.pengunggah,
            "waktu": u.waktu.isoformat(timespec="seconds")}


def pasang_router(app, ambil_session):
    """Dipanggil dari main.buat_app dengan dependency session milik app itu."""

    router = APIRouter(prefix="/api")
    dep = Depends(ambil_session)

    # ------------------------------------------------------------ metrik / cara dihitung
    @router.get("/metrik")
    def metrik():
        path = pathlib.Path(__file__).resolve().parents[1] / "semantic" / "metrics.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------ ringkasan ala Excel
    @router.get("/tahun")
    def daftar_tahun(session: Session = dep):
        tahun = sorted({t for (t,) in session.execute(select(MartBulanan.tahun).distinct())})
        return tahun

    @router.get("/ringkasan/{tahun}")
    def ringkasan(tahun: int, format: str | None = None, session: Session = dep):
        baris = list(session.scalars(select(MartBulanan).where(
            MartBulanan.tahun == tahun).order_by(MartBulanan.bulan)))
        if not baris:
            raise HTTPException(404, f"Belum ada data untuk tahun {tahun}.")
        bulan_data = [{
            "bulan": b.bulan,
            "sicom": b.sicom_usc, "op_price": b.harga_beli_usc,
            "op_margin": b.op_margin_usc, "ton": b.qty_ton,
            "target": b.target_usc, "pencapaian": b.pencapaian,
            "vs_target": b.selisih_vs_target,
            "hari_pembelian": b.hari_pembelian,
            "catatan_koreksi": KOREKSI.get((tahun, b.bulan)),
        } for b in baris]
        hasil = {
            "tahun": tahun,
            "bulan": bulan_data,
            "avg_ytd_sederhana": rumus.rata_rata_sederhana(
                [b.op_margin_usc for b in baris]),
            "avg_ytd_tertimbang": rumus.rata_rata_tertimbang(
                [(b.op_margin_usc, b.qty_ton) for b in baris]),
            "catatan": [f"{dt.date(tahun, bln, 1).strftime('%b %Y')}: {teks}"
                        for (thn, bln), teks in KOREKSI.items() if thn == tahun],
        }
        if format == "xlsx":
            judul = ["Bulan", "SICOM USc/kg", "OP Price USc/kg", "OP Margin USc/kg",
                     "Ton (kering)", "Target", "Pencapaian", "vs Target", "Catatan"]
            isi = [[b["bulan"], b["sicom"], b["op_price"], b["op_margin"], b["ton"],
                    b["target"], b["pencapaian"], b["vs_target"],
                    b["catatan_koreksi"] or ""] for b in bulan_data]
            isi.append(["Avg YTD sederhana (resmi)", "", "", hasil["avg_ytd_sederhana"]])
            isi.append(["Avg tertimbang tonase (informasi)", "", "",
                        hasil["avg_ytd_tertimbang"]])
            return respon_xlsx(f"ringkasan_{tahun}.xlsx", judul, isi)
        return hasil

    # ------------------------------------------------------------ margin bridge
    def _margin_bulan(session: Session, th: int, bl: int) -> dict | None:
        """Angka resmi satu bulan dari mart bulanan (SICOM, OP Price, margin)."""
        m = session.scalars(select(MartBulanan).where(
            MartBulanan.tahun == th, MartBulanan.bulan == bl)).first()
        if m is None or m.sicom_usc is None or m.harga_beli_usc is None:
            return None
        return {"tahun": th, "bulan": bl,
                "label": f"{NAMA_BULAN_SINGKAT[bl]}-{str(th)[2:]}",
                "sicom": m.sicom_usc, "op_price": m.harga_beli_usc,
                "margin": m.op_margin_usc, "qty_ton": m.qty_ton,
                "hari_pembelian": m.hari_pembelian}

    def _penyebab(d_sicom: float, d_op: float) -> str:
        """Siapa yang menentukan perubahan margin bulan itu.

        Kontribusi pasar = Δ SICOM (di luar kendali), kontribusi keputusan =
        −Δ OP Price. Bila SICOM nyaris tidak bergerak tetapi OP Price bergerak,
        perubahan itu murni keputusan pembelian.
        """
        if abs(d_sicom) < 1.0 and abs(d_op) >= 1.0:
            return "keputusan"
        return "keputusan" if abs(d_op) > abs(d_sicom) else "pasar"

    def _narasi_langkah(langkah: list[dict], passthrough: dict | None) -> None:
        """Isi 'penjelasan' tiap komponen bridge (kenapa menekan/menolong)."""
        for l in langkah:
            nilai = l["nilai"]
            mentah = l["perubahan_mentah"]
            if l["kode"] == "sicom":
                if mentah < 0:
                    l["penjelasan"] = (
                        f"SICOM turun {abs(mentah):.2f} US¢/kg — harga acuan pasar "
                        f"melemah, menekan margin {abs(nilai):.2f} US¢/kg. Ini di luar "
                        f"kendali pembelian.")
                    l["arah"] = "turun"
                elif mentah > 0:
                    l["penjelasan"] = (
                        f"SICOM naik {mentah:.2f} US¢/kg — pasar menguat, menolong "
                        f"margin +{nilai:.2f} US¢/kg.")
                    l["arah"] = "naik"
                else:
                    l["penjelasan"] = "SICOM praktis tidak berubah."
                    l["arah"] = "datar"
            else:  # op_price
                if mentah < 0:
                    l["penjelasan"] = (
                        f"Harga beli (OP Price) turun {abs(mentah):.2f} US¢/kg — "
                        f"pembelian lebih murah, menolong margin +{nilai:.2f} US¢/kg.")
                    l["arah"] = "turun"
                elif mentah > 0:
                    l["penjelasan"] = (
                        f"Harga beli (OP Price) naik {mentah:.2f} US¢/kg — biaya "
                        f"pembelian lebih mahal, menekan margin {abs(nilai):.2f} US¢/kg.")
                    l["arah"] = "naik"
                else:
                    l["penjelasan"] = "Harga beli (OP Price) praktis tidak berubah."
                    l["arah"] = "datar"
            l["menekan"] = nilai < 0

        if passthrough:
            rasio = passthrough["rasio"]
            ds = passthrough["delta_sicom"]
            arah = "penurunan" if ds < 0 else "kenaikan"
            if rasio < 0:
                teks = (f"Harga beli bergerak BERLAWANAN arah dengan SICOM "
                        f"(pass-through {rasio * 100:.0f}%) — keputusan pembelian "
                        f"menahan sebagian {arah} SICOM.")
            elif rasio > 1.02:
                teks = (f"Harga beli turun/naik lebih besar daripada SICOM "
                        f"(pass-through {rasio * 100:.0f}%) — margin justru tertolong.")
            else:
                teks = (f"OP Price hanya mengikuti {rasio * 100:.0f}% dari {arah} SICOM; "
                        f"sisa {passthrough['porsi_ditanggung_margin'] * 100:.0f}% "
                        f"ditanggung margin.")
            langkah[1]["penjelasan"] += " " + teks
            langkah[1]["passthrough_teks"] = teks

    def _narasi_bulan(baris: dict) -> str:
        """Penjelasan satu bulan: kenapa margin naik/turun."""
        d_m = baris["delta_margin"]
        ds = baris["delta_sicom"]
        dp = baris["delta_op_price"]
        arah = "naik" if d_m > 0 else "turun" if d_m < 0 else "datar"
        kepala = (f"{baris['bulan']}: margin {arah} {abs(d_m):.2f} US¢/kg"
                  if d_m else f"{baris['bulan']}: margin datar")
        bagian = []
        if abs(ds) >= 0.005:
            bagian.append(f"SICOM {'turun' if ds < 0 else 'naik'} {abs(ds):.2f}")
        else:
            bagian.append("SICOM nyaris tidak bergerak")
        if abs(dp) >= 0.005:
            bagian.append(f"OP Price {'turun' if dp < 0 else 'naik'} {abs(dp):.2f}")
        else:
            bagian.append("OP Price tetap")
        isi = ", ".join(bagian)
        pas = baris.get("passthrough")
        if pas is not None and abs(ds) >= 0.005 and pas >= 0:
            isi += f" (hanya {pas * 100:.0f}% mengikuti SICOM)"
        elif pas is not None and pas < 0:
            isi += " (harga beli berlawanan arah SICOM)"
        ekor = ("→ dipicu keputusan pembelian." if baris["penyebab"] == "keputusan"
                else "→ dipicu pasar.")
        return f"{kepala} — {isi} {ekor}"

    @router.get("/margin-bridge")
    def margin_bridge(dari: str | None = None, sampai: str | None = None,
                      tahun: int | None = None, bulan: int | None = None,
                      format: str | None = None, session: Session = dep):
        """Margin bridge: ΔM = ΔSICOM − ΔOP Price (dua penyebab).

        SICOM = harga acuan pasar (di luar kendali); OP Price = harga beli kita
        (keputusan). OP Price turun menolong margin, SICOM turun menekan margin.
        Bridge tertutup persis karena margin resmi memang SICOM − OP Price.

        Periode: `dari` (awal) & `sampai` (akhir), format YYYY-MM — mengikuti
        filter kartu 'RM Stock - Intake vs Pricing'. Bila `sampai` tidak diisi,
        dipakai bulan itu juga (banding dengan bulan sebelumnya).
        """
        pb = _bulan_ym(sampai or dari, "sampai" if sampai else "dari")
        if pb is None:
            m = session.scalars(
                select(MartBulanan).order_by(MartBulanan.tahun.desc(),
                                             MartBulanan.bulan.desc()).limit(1)).first()
            if m is None:
                raise HTTPException(404, "Belum ada data mart bulanan. "
                                         "Jalankan import-template dulu.")
            pb = (m.tahun, m.bulan)
        if bulan is not None and 1 <= bulan <= 12 and not sampai:
            pb = (tahun or pb[0], bulan)
        pa = _bulan_ym(dari, "dari") or _bulan_sebelum(*pb)
        if pa == pb:
            pa = _bulan_sebelum(*pb)

        a = _margin_bulan(session, *pa)
        b = _margin_bulan(session, *pb)
        if a is None or b is None:
            kurang = ["%s-%s" % (th, f"{bl:02d}")
                      for th, bl, isi in ((*pa, a), (*pb, b)) if isi is None]
            raise HTTPException(
                404, f"Bulan {', '.join(kurang)} belum punya data (SICOM & OP "
                     f"Price) — bridge tidak bisa dihitung.")

        d_sicom = b["sicom"] - a["sicom"]
        d_op = b["op_price"] - a["op_price"]
        d_margin = b["margin"] - a["margin"]
        # kontribusi: SICOM searah, OP Price berlawanan (OP turun = menolong)
        langkah = [
            {"kode": "sicom", "label": "Δ SICOM", "jenis": "eksternal",
             "nilai": d_sicom, "perubahan_mentah": d_sicom},
            {"kode": "op_price", "label": "Δ OP Price", "jenis": "keputusan",
             "nilai": -d_op, "perubahan_mentah": d_op},
        ]

        # Rincian Δ OP Price (opsional): berapa dari harga Rp dan berapa dari kurs
        rincian = None
        ag_a = _agregat_bridge(_baris_periode_bulanan(session, *pa))
        ag_b = _agregat_bridge(_baris_periode_bulanan(session, *pb))
        if ag_a and ag_b:
            efek_harga = 100.0 * (ag_b["e_rp_kg"] - ag_a["e_rp_kg"]) / ag_a["kurs_efektif"]
            efek_kurs = 100.0 * ag_b["e_rp_kg"] * (1.0 / ag_b["kurs_efektif"]
                                                   - 1.0 / ag_a["kurs_efektif"])
            rincian = {
                "harga_rp": -efek_harga, "kurs": -efek_kurs,
                "total": -efek_harga - efek_kurs,
                "e_a": ag_a["e_rp_kg"], "e_b": ag_b["e_rp_kg"],
                "kurs_a": ag_a["kurs_efektif"], "kurs_b": ag_b["kurs_efektif"],
            }

        # OP Price mengikuti berapa persen dari penurunan SICOM?
        passthrough = None
        if abs(d_sicom) > 0.005:
            passthrough = {
                "rasio": d_op / d_sicom,
                "porsi_ditanggung_margin": 1.0 - d_op / d_sicom,
                "delta_sicom": d_sicom, "delta_op": d_op,
            }

        # Bridge bulanan sepanjang rentang (nilai tambah: mana yang dipicu pasar)
        per_bulan = []
        th, bl = pa
        while (th, bl) < pb:
            nxt = (th + 1, 1) if bl == 12 else (th, bl + 1)
            m0 = _margin_bulan(session, th, bl)
            m1 = _margin_bulan(session, *nxt)
            if m0 and m1:
                ds = m1["sicom"] - m0["sicom"]
                dp = m1["op_price"] - m0["op_price"]
                per_bulan.append({
                    "bulan": m1["label"], "tahun": nxt[0], "nomor_bulan": nxt[1],
                    "delta_sicom": ds, "delta_op_price": dp,
                    "delta_margin": m1["margin"] - m0["margin"],
                    "kontribusi_sicom": ds, "kontribusi_op_price": -dp,
                    "passthrough": (dp / ds) if abs(ds) > 0.005 else None,
                    "penyebab": _penyebab(ds, dp),
                })
                per_bulan[-1]["penjelasan"] = _narasi_bulan(per_bulan[-1])
            th, bl = nxt

        _narasi_langkah(langkah, passthrough)

        # ---- Analisa: kenapa margin naik/turun sepanjang periode
        penekan = [l for l in langkah if l["nilai"] < 0]
        penolong = [l for l in langkah if l["nilai"] > 0]
        analisa = []
        if abs(d_margin) < 0.005:
            analisa.append(
                f"Margin praktis tidak berubah ({d_margin:+.2f} US¢/kg) dari "
                f"{a['label']} ke {b['label']}: pengaruh SICOM dan harga beli saling "
                f"meniadakan.")
        else:
            arah = "turun" if d_margin < 0 else "naik"
            analisa.append(
                f"Margin {arah} {abs(d_margin):.2f} US¢/kg dari {a['label']} "
                f"({a['margin']:.2f}) ke {b['label']} ({b['margin']:.2f}).")
        if penekan:
            utama = min(penekan, key=lambda l: l["nilai"])
            analisa.append(
                f"Penekan terbesar: {utama['label']} {utama['nilai']:+.2f} US¢/kg"
                + (" — harga acuan pasar, di luar kendali." if utama["kode"] == "sicom"
                   else " — harga beli naik, ini keputusan pembelian."))
        if penolong:
            utama = max(penolong, key=lambda l: l["nilai"])
            analisa.append(
                f"Penolong terbesar: {utama['label']} {utama['nilai']:+.2f} US¢/kg"
                + (" — pasar menguat." if utama["kode"] == "sicom"
                   else " — pembelian lebih murah, ini yang bisa dikendalikan."))
        if passthrough:
            porsi = passthrough["rasio"] * 100
            if 0 <= porsi <= 100:
                analisa.append(
                    f"Harga beli hanya mengikuti {porsi:.0f}% dari pergerakan SICOM, "
                    f"jadi {100 - porsi:.0f}% pergerakan pasar langsung menjadi "
                    f"perubahan margin — inilah risiko yang tidak bisa dikendalikan "
                    f"lewat negosiasi harga.")
            elif porsi > 100:
                analisa.append(
                    f"Harga beli bergerak {porsi:.0f}% dari pergerakan SICOM (lebih "
                    f"besar dari pasar) — pembelian justru memperbaiki margin.")
            else:
                analisa.append(
                    f"Harga beli bergerak berlawanan arah dengan SICOM "
                    f"({porsi:.0f}%) — pembelian menahan sebagian tekanan pasar.")
        if len(per_bulan) >= 2:
            turun = min(per_bulan, key=lambda r: r["delta_margin"])
            naik = max(per_bulan, key=lambda r: r["delta_margin"])
            if turun["delta_margin"] < 0:
                analisa.append(
                    f"Penurunan bulanan terbesar: {turun['bulan']} "
                    f"({turun['delta_margin']:+.2f}) — "
                    f"{'dipicu pasar (SICOM jatuh)' if turun['penyebab'] == 'pasar' else 'dipicu keputusan pembelian'}.")
            if naik["delta_margin"] > 0:
                analisa.append(
                    f"Kenaikan bulanan terbesar: {naik['bulan']} "
                    f"({naik['delta_margin']:+.2f}) — "
                    f"{'ditopang pasar (SICOM naik)' if naik['penyebab'] == 'pasar' else 'hasil keputusan pembelian'}.")
            jml_putusan = sum(1 for r in per_bulan if r["penyebab"] == "keputusan")
            analisa.append(
                f"Dari {len(per_bulan)} bulan, {jml_putusan} bulan pergerakan margin "
                f"ditentukan keputusan pembelian dan {len(per_bulan) - jml_putusan} "
                f"bulan oleh pasar.")
        # Kesimpulan mengikuti hasil akhir dulu, baru penyebab dominannya
        if d_margin > 0.005:
            kontrib_neg = [l for l in langkah if l["nilai"] < 0]
            if kontrib_neg and abs(kontrib_neg[0]["nilai"]) > abs(d_margin):
                kesimpulan = "Margin membaik meski ada penekan"
            else:
                kesimpulan = "Margin membaik"
        elif d_margin < -0.005:
            kontrib_neg = [l for l in langkah if l["nilai"] < 0]
            utama = min(kontrib_neg, key=lambda l: l["nilai"]) if kontrib_neg else None
            if utama and utama["kode"] == "op_price":
                kesimpulan = "Tekanan terutama dari keputusan harga beli"
            else:
                kesimpulan = "Tekanan terutama dari pasar (SICOM)"
        else:
            kesimpulan = "Margin stabil"

        hasil = {
            "periode_a": a, "periode_b": b,
            "awal": a["margin"], "langkah": langkah, "akhir": b["margin"],
            "penutupan_selisih": round(a["margin"] + sum(l["nilai"] for l in langkah)
                                       - b["margin"], 12),
            "delta_margin": d_margin,
            "rumus": "ΔM = ΔSICOM − ΔOP Price (kontribusi OP Price = −Δ OP Price)",
            "passthrough": passthrough,
            "rincian_op_price": rincian,
            "per_bulan": per_bulan,
            "analisa": analisa,
            "kesimpulan": kesimpulan,
            "catatan": [
                "SICOM = harga acuan pasar (di luar kendali); OP Price = harga beli "
                "kita (keputusan). SICOM turun menekan margin, OP Price turun menolong.",
                "OP Price yang hanya mengikuti sebagian penurunan SICOM berarti sisa "
                "penurunannya ditanggung margin (lihat rasio pass-through).",
                "Rincian Δ OP Price memisahkan efek harga beli (Rp/kg) dan efek kurs; "
                "keduanya berjumlah sama dengan −Δ OP Price.",
                "Angka SICOM/OP Price/margin = angka resmi mart bulanan, sehingga ujung "
                "bridge selalu sama dengan ringkasan OP Margin.",
            ],
        }
        if format == "xlsx":
            isi = [["Komponen", "Kontribusi ke margin (USc/kg)", "Perubahan mentah (USc/kg)"],
                   [f"OP Margin awal {a['label']}", a["margin"], ""]]
            isi += [[l["label"], l["nilai"], l["perubahan_mentah"]] for l in langkah]
            isi += [[f"OP Margin akhir {b['label']}", b["margin"], ""],
                    ["Selisih penutupan (harus ~0)", hasil["penutupan_selisih"], ""],
                    [], ["Detail", a["label"], b["label"]],
                    ["SICOM", a["sicom"], b["sicom"]],
                    ["OP Price", a["op_price"], b["op_price"]],
                    ["OP Margin", a["margin"], b["margin"]],
                    ["Qty kering (ton)", a["qty_ton"], b["qty_ton"]],
                    ["Hari pembelian", a["hari_pembelian"], b["hari_pembelian"]]]
            if passthrough:
                isi.append(["OP Price mengikuti SICOM (%)",
                            passthrough["rasio"] * 100, ""])
            if per_bulan:
                isi += [[], ["Bulan", "Δ SICOM", "Δ OP Price", "Δ Margin",
                             "Pass-through", "Penyebab"]]
                isi += [[r["bulan"], r["delta_sicom"], r["delta_op_price"],
                         r["delta_margin"],
                         (r["passthrough"] * 100) if r["passthrough"] is not None else None,
                         r["penyebab"]] for r in per_bulan]
            return respon_xlsx(f"margin_bridge_{a['label']}_{b['label']}.xlsx",
                               isi[0], isi[1:])
        return hasil

    # ------------------------------------------------------------ days of cover
    def _seri_doc(session: Session, dari: tuple[int, int] | None,
                  sampai: tuple[int, int] | None, hari_acuan: float):
        """Stok akhir bulan + intake (qty kering mart) per bulan."""
        stok: dict[tuple[int, int], MartHarian] = {}
        intake: dict[tuple[int, int], float] = defaultdict(float)
        for h in session.scalars(select(MartHarian).order_by(MartHarian.tanggal)):
            kunci = (h.tanggal.year, h.tanggal.month)
            if h.stok_ton is not None:
                stok[kunci] = h            # nilai terakhir bulan itu menang
            if h.qty_kering_kg:
                intake[kunci] += h.qty_kering_kg / 1000.0
        if not stok:
            return [], []
        semua_bulan = sorted(stok)
        dipakai = [k for k in semua_bulan
                   if (dari is None or k >= dari) and (sampai is None or k <= sampai)]
        if dari is None and sampai is None:
            dipakai = semua_bulan[-12:]

        param = PencariBerlaku([(p.berlaku_dari, p) for p in session.scalars(
            select(ParameterPabrik))])
        baris, lewat = [], []
        for kunci in dipakai:
            th, bl = kunci
            sebelumnya = (th - 1, 12) if bl == 1 else (th, bl - 1)
            if sebelumnya not in stok:
                lewat.append({"bulan": f"{NAMA_BULAN_SINGKAT[bl]}-{str(th)[2:]}",
                              "alasan": "stok akhir bulan sebelumnya tidak ada di data "
                                        "(pemakaian tidak bisa dihitung)"})
                continue
            awal = stok[sebelumnya].stok_ton
            akhir = stok[kunci].stok_ton
            masuk = intake.get(kunci, 0.0)
            pemakaian = awal + masuk - akhir
            hari = _jumlah_hari(th, bl)
            per_hari = pemakaian / hari if hari else None
            doc = (akhir / per_hari) if per_hari and per_hari > 0 else None
            prm = param.pada(dt.date(th, bl, hari))
            safety_ton = prm.safety_stock_ton if prm else None
            safety_hari = (safety_ton / per_hari) if (safety_ton and per_hari
                                                      and per_hari > 0) else None
            if safety_hari is None:
                status = "tanpa safety"
            else:
                status = "aman" if (doc is not None and doc >= safety_hari) \
                    else "di bawah safety"
            alasan_cek = []
            if pemakaian <= 0:
                alasan_cek.append("stok naik lebih banyak daripada intake — "
                                  "ada penyesuaian/transfer yang terhitung sebagai "
                                  "pemakaian negatif")
            if masuk == 0:
                alasan_cek.append("tidak ada baris intake (pembelian) bulan ini")
            baris.append({
                "bulan": f"{NAMA_BULAN_SINGKAT[bl]}-{str(th)[2:]}",
                "tahun": th, "nomor_bulan": bl,
                "stok_awal_ton": round(awal, 3), "intake_ton": round(masuk, 3),
                "stok_akhir_ton": round(akhir, 3),
                "pemakaian_ton": round(pemakaian, 3),
                "hari": hari,
                "pemakaian_harian_ton": round(per_hari, 3) if per_hari is not None else None,
                "doc_hari": round(doc, 2) if doc is not None else None,
                "safety_ton": safety_ton,
                "safety_hari": round(safety_hari, 2) if safety_hari is not None else None,
                "safety_dinamis_ton": round(hari_acuan * per_hari, 3)
                if per_hari and per_hari > 0 else None,
                "status": status,
                "perlu_cek": bool(alasan_cek),
                "alasan_cek": alasan_cek,
            })
        return baris, lewat

    @router.get("/days-of-cover")
    def days_of_cover(dari: str | None = None, sampai: str | None = None,
                      hari_safety: float = 21.5, format: str | None = None,
                      session: Session = dep):
        """Days of cover dari neraca stok (pemakaian implisit).

        Pemakaian = stok awal + intake − stok akhir;
        DoC = stok akhir / (pemakaian / jumlah hari).
        Tidak ada data pemakaian langsung, jadi selisih neraca itulah pemakaian.
        Safety dibandingkan dalam HARI (safety ton / pemakaian harian), dan
        disediakan safety dinamis = hari_safety × pemakaian harian.
        """
        kd = _bulan_ym(dari, "dari")
        ks = _bulan_ym(sampai, "sampai")
        if kd and ks and kd > ks:
            raise HTTPException(422, "Periode 'dari' harus sebelum atau sama "
                                     "dengan 'sampai'.")
        if hari_safety <= 0:
            raise HTTPException(422, "hari_safety harus lebih besar dari 0.")
        baris, lewat = _seri_doc(session, kd, ks, hari_safety)
        if not baris:
            raise HTTPException(
                404, "Tidak ada bulan yang bisa dihitung (butuh stok akhir bulan "
                     "ini dan stok akhir bulan sebelumnya).")

        sahih = [b for b in baris if b["pemakaian_ton"] > 0]
        total_pakai = sum(b["pemakaian_ton"] for b in sahih)
        total_hari = sum(b["hari"] for b in sahih)
        rerata_bulan = total_pakai / len(sahih) if sahih else None
        rerata_harian = total_pakai / total_hari if total_hari else None
        ber_doc = [b for b in baris if b["doc_hari"] is not None]
        terkini = baris[-1]
        hasil = {
            "dari": baris[0]["bulan"], "sampai": baris[-1]["bulan"],
            "terkini": terkini,
            "rerata_pemakaian_bulan_ton": round(rerata_bulan, 1) if rerata_bulan else None,
            "rerata_pemakaian_harian_ton": round(rerata_harian, 1) if rerata_harian else None,
            "terendah": min(ber_doc, key=lambda b: b["doc_hari"]) if ber_doc else None,
            "tertinggi": max(ber_doc, key=lambda b: b["doc_hari"]) if ber_doc else None,
            "jumlah_bulan": len(baris),
            "jumlah_bulan_di_bawah_safety": sum(
                1 for b in baris if b["status"] == "di bawah safety"),
            "hari_safety_acuan": hari_safety,
            "safety_dinamis_ton": round(hari_safety * rerata_harian, 1)
            if rerata_harian else None,
            "bulan_tak_terhitung": lewat,
            "baris": baris,
            "catatan": [
                "Pemakaian tidak ada di data, jadi dihitung dari neraca stok: "
                "pemakaian = stok awal + intake − stok akhir; DoC = stok akhir ÷ "
                "(pemakaian ÷ jumlah hari).",
                "Intake memakai kuantitas kering pembelian (mart). Susut, transfer, "
                "dan penyesuaian stok ikut terhitung sebagai pemakaian.",
                "DoC lebih adil daripada tonase karena menyesuaikan pemakaian. "
                f"Safety dinamis = {hari_safety:g} hari × pemakaian harian; safety "
                "tetap (ton) tidak berubah walau pemakaian naik/turun.",
                "Bulan pertama tidak bisa dihitung bila stok akhir bulan sebelumnya "
                "tidak ada di data (mis. Januari butuh stok Desember tahun lalu).",
            ],
        }
        if format == "xlsx":
            judul = ["Bulan", "Stok awal (ton)", "Intake (ton)", "Stok akhir (ton)",
                     "Pemakaian (ton)", "Hari", "Pemakaian/hari (ton)", "DoC (hari)",
                     "Safety (ton)", "Safety (hari)", "Safety dinamis (ton)", "Status"]
            isi = [[b["bulan"], b["stok_awal_ton"], b["intake_ton"], b["stok_akhir_ton"],
                    b["pemakaian_ton"], b["hari"], b["pemakaian_harian_ton"],
                    b["doc_hari"], b["safety_ton"], b["safety_hari"],
                    b["safety_dinamis_ton"], b["status"]] for b in baris]
            isi += [["Rerata pemakaian (ton/bulan)", hasil["rerata_pemakaian_bulan_ton"]],
                    ["Rerata pemakaian (ton/hari)", hasil["rerata_pemakaian_harian_ton"]],
                    ["Safety dinamis (ton)", hasil["safety_dinamis_ton"]],
                    ["Bulan di bawah safety", hasil["jumlah_bulan_di_bawah_safety"]]]
            return respon_xlsx(f"days_of_cover_{hasil['dari']}_{hasil['sampai']}.xlsx",
                               judul, isi)
        return hasil
    @router.get("/ringkasan-elemen")
    def ringkasan_elemen(dari: str | None = None, sampai: str | None = None,
                         format: str | None = None, session: Session = dep):
        """Elemen pemengaruh OP Margin per bulan, meniru sheet Excel
        'RM Stock-Intake VS Pricing': RM Stock (akhir bulan), Intake,
        Safety Level, SICOM, OP Price.

        Intake memakai tonase TIKET bila tersedia (tiket = sumber resmi
        tonase); bila belum ada tiket bulan itu, dipakai angka referensi
        rekonsiliasi yang sudah diketahui, lalu kuantitas Pembelian."""
        # stok akhir bulan dari mart harian
        stok_bulan: dict[tuple[int, int], MartHarian] = {}
        for h in session.scalars(select(MartHarian).where(
                MartHarian.stok_ton != None).order_by(MartHarian.tanggal)):  # noqa: E711
            stok_bulan[(h.tanggal.year, h.tanggal.month)] = h  # terakhir menang

        # tonase tiket per bulan (tanpa tiket nol)
        tiket_bulan: dict[tuple[int, int], float] = defaultdict(float)
        for t in session.scalars(select(TiketBaris).where(
                TiketBaris.tiket_nol == False)):  # noqa: E712
            if t.dry_kg is not None:
                tiket_bulan[(t.ticket_date.year, t.ticket_date.month)] += \
                    float(t.dry_kg) / 1000.0
        referensi = {(s["tahun"], s["bulan"]): s["tiket_ton"]
                     for s in SELISIH_DIKETAHUI}

        mart = {(m.tahun, m.bulan): m for m in session.scalars(select(MartBulanan))}
        if not stok_bulan:
            return {"baris": [], "catatan": []}
        mulai = min(stok_bulan)
        kunci = sorted(set(stok_bulan) | {k for k in mart if k >= mulai})

        # Filter periode (format YYYY-MM), contoh: dari=2024-01&sampai=2026-10
        def _bulan(teks: str, nama: str) -> tuple[int, int]:
            try:
                th, bl = teks.split("-")[:2]
                th, bl = int(th), int(bl)
                assert 1 <= bl <= 12
                return th, bl
            except Exception:
                raise HTTPException(422, f"Parameter '{nama}' harus format "
                                         f"YYYY-MM, contoh 2024-01 (bukan '{teks}').")
        if dari:
            kunci = [k for k in kunci if k >= _bulan(dari, "dari")]
        if sampai:
            kunci = [k for k in kunci if k <= _bulan(sampai, "sampai")]

        baris = []
        for (th, bl) in kunci:
            h = stok_bulan.get((th, bl))
            m = mart.get((th, bl))
            pembelian_ton = m.qty_ton if m else None
            tiket_ton = tiket_bulan.get((th, bl))
            # tiket dipakai hanya bila wajar (>=50% pembelian) agar baris
            # contoh/parsial tidak menggantikan angka bulan penuh
            if tiket_ton and (not pembelian_ton or tiket_ton >= 0.5 * pembelian_ton):
                intake, sumber = round(tiket_ton, 3), "tiket"
            elif (th, bl) in referensi:
                intake, sumber = referensi[(th, bl)], "tiket (referensi rekonsiliasi)"
            elif pembelian_ton is not None:
                intake, sumber = round(pembelian_ton, 3), "pembelian"
            else:
                intake, sumber = None, None
            akhir_kalender = (dt.date(th + (bl == 12), (bl % 12) + 1, 1)
                              - dt.timedelta(days=1))
            baris.append({
                "tahun": th, "bulan": bl,
                "label": f"{['','Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'][bl]}-{str(th)[2:]}",
                "rm_stock_ton": round(h.stok_ton, 3) if h else None,
                "tanggal_stok": h.tanggal.isoformat() if h else None,
                "stok_sebagian": bool(h and h.tanggal < akhir_kalender),
                "safety_ton": h.safety_ton if h else None,
                "intake_ton": intake,
                "sumber_intake": sumber,
                "sicom": m.sicom_usc if m else None,
                "op_price": m.harga_beli_usc if m else None,
                "op_margin": m.op_margin_usc if m else None,
            })
        hasil = {"baris": baris, "catatan": [
            "Intake = tonase kering tiket (sumber resmi); bulan tanpa data tiket "
            "memakai angka referensi rekonsiliasi atau kuantitas Pembelian.",
            "RM Stock = stok hari terakhir yang berdata di bulan itu; bulan yang "
            "datanya belum sampai akhir bulan ditandai 'sebagian'.",
            "Jun-25: Excel lampiran menulis RM Stock 2.795,1 (persis sama dengan "
            "Safety Level) sedangkan data stok harian menunjukkan 2.038,681 per "
            "30/06/2025 — diduga salah isi di Excel; sistem memakai data harian. "
            "Mohon konfirmasi.",
            "Baris proyeksi (Sep-Des 26) di Excel tidak direplikasi karena rumus "
            "proyeksinya belum ditetapkan [TERBUKA].",
        ]}
        if format == "xlsx":
            return respon_xlsx(
                "rm_stock_intake_vs_pricing.xlsx",
                ["Date", "RM Stock", "Intake", "Safety Level Stock", "SICOM",
                 "OP Price", "OP Margin", "Sumber intake", "Catatan"],
                [[b["label"], b["rm_stock_ton"], b["intake_ton"], b["safety_ton"],
                  b["sicom"], b["op_price"], b["op_margin"], b["sumber_intake"],
                  "stok sebagian" if b["stok_sebagian"] else ""] for b in baris])
        return hasil

    @router.get("/ringkasan-elemen/analisa")
    def analisa_elemen(dari: str | None = None, sampai: str | None = None,
                       session: Session = dep):
        """Analisa 5W1H otomatis atas grafik RM Stock - Intake vs Pricing,
        dihitung dari data pada periode terfilter."""
        from .core.analisa import analisa_5w1h
        data = ringkasan_elemen(dari=dari, sampai=sampai, session=session)
        return analisa_5w1h(data["baris"], session)

    @router.get("/analisis/analisa")
    def analisa_halaman_analisis(dari: str | None = None, sampai: str | None = None,
                                 session: Session = dep):
        """Analisa 5W1H otomatis atas SELURUH data halaman Analisis."""
        from .core.analisa import analisa_analitik

        def _bulan(teks, nama):
            try:
                th, bl = teks.split("-")[:2]
                th, bl = int(th), int(bl)
                assert 1 <= bl <= 12
                return th, bl
            except Exception:
                raise HTTPException(422, f"Parameter '{nama}' harus format "
                                         f"YYYY-MM, contoh 2024-01 (bukan '{teks}').")
        d = _bulan(dari, "dari") if dari else None
        z = _bulan(sampai, "sampai") if sampai else None
        return analisa_analitik(session, d, z)

    @router.get("/grafik/margin-antar-tahun")
    def grafik_margin(dari: str | None = None, sampai: str | None = None,
                      session: Session = dep):
        """Pola bulanan per tahun untuk mode 'banding antar tahun'.

        `dari`/`sampai` (YYYY-MM) membatasi bulan yang dibandingkan, supaya
        perbandingan antar tahun memakai periode yang sama.
        """
        kd = _bulan_ym(dari, "dari")
        ks = _bulan_ym(sampai, "sampai")
        if kd and ks and kd > ks:
            raise HTTPException(422, "Periode 'dari' harus sebelum atau sama "
                                     "dengan 'sampai'.")
        per_tahun: dict[int, dict[int, float]] = defaultdict(dict)
        for b in session.scalars(select(MartBulanan)):
            if kd and (b.tahun, b.bulan) < kd:
                continue
            if ks and (b.tahun, b.bulan) > ks:
                continue
            per_tahun[b.tahun][b.bulan] = b.op_margin_usc
        return [{"tahun": t,
                 "data": [{"bulan": m, "margin": per_tahun[t].get(m)}
                          for m in range(1, 13)]}
                for t in sorted(per_tahun)]

    # ------------------------------------------------------------ rekonsiliasi
    @router.get("/rekonsiliasi")
    def rekonsiliasi(format: str | None = None, session: Session = dep):
        harian = rekonsiliasi_harian(session)
        hasil = {
            "diketahui": selisih_diketahui(),
            "catatan": CATATAN_DIKETAHUI,
            "harian": harian,
        }
        if format == "xlsx":
            judul = ["Periode", "Tiket (ton)", "Excel lama (ton)", "Selisih (ton)", "Status"]
            isi = [[d["periode"], d["tiket_ton"], d["excel_ton"], d["selisih_ton"],
                    d["status"]] for d in hasil["diketahui"]]
            return respon_xlsx("rekonsiliasi.xlsx", judul, isi)
        return hasil

    # ------------------------------------------------------------ kualitas data
    @router.get("/kualitas")
    def kualitas(session: Session = dep):
        return {
            "kpi_reject": kpi_reject(session),
            "terlambat": data_terlambat(session),
            "hari_pembelian_tanpa_sicom": hari_pembelian_tanpa_sicom(session)[-30:],
            "lonjakan_harga": lonjakan_harga_harian(session)[-50:],
            "peringatan": ringkasan_peringatan(session),
        }

    # ------------------------------------------------------------ kartu: tonase drill-down
    @router.get("/kartu/tonase")
    def kartu_tonase(dimensi: str = "provinsi",
                     tahun: int | None = None, bulan: int | None = None,
                     dari: dt.date | None = None, sampai: dt.date | None = None,
                     vendor: str | None = None, grade: str | None = None,
                     eudr: bool | None = None,
                     provinsi: str | None = None, kabupaten: str | None = None,
                     kecamatan: str | None = None, desa: str | None = None,
                     per: str = "dimensi", top: int = 8,
                     format: str | None = None, session: Session = dep):
        """Tonase kering per dimensi. `per=bulan` -> rincian bulan x dimensi
        (dipakai bila filter periode lebih dari satu bulan)."""
        if dimensi not in DIMENSI_TONASE:
            raise HTTPException(422, f"Dimensi '{dimensi}' tidak dikenal. "
                                     f"Pilihan: {', '.join(DIMENSI_TONASE)}.")
        if per not in ("dimensi", "bulan"):
            raise HTTPException(422, "Parameter per hanya boleh \"dimensi\" "
                                     "atau \"bulan\".")
        if not 1 <= top <= 40:
            raise HTTPException(422, "Parameter top harus antara 1 dan 40.")
        q = _filter_tiket(select(TiketBaris), tahun, bulan, vendor, grade, eudr,
                          provinsi, kabupaten, kecamatan, desa, session=session)
        if dari:
            q = q.where(TiketBaris.ticket_date >= dari)
        if sampai:
            q = q.where(TiketBaris.ticket_date <= sampai)
        kolom = {"vendor": "kode_vendor", "grade": "item_code"}.get(dimensi, dimensi)

        if per == "bulan":
            potongan: list[tuple[str, tuple[int, int] | None, float, str]] = []
            for t in session.scalars(q):
                potongan.append((
                    getattr(t, kolom) or "(kosong)",
                    (t.ticket_date.year, t.ticket_date.month) if t.ticket_date else None,
                    float(t.dry_kg or 0) / 1000.0,
                    t.ticket_no))
            return _tonase_per_bulan(potongan, dimensi, dari, sampai, top,
                                     format, session)

        agreg: dict[str, dict] = defaultdict(lambda: {"ton": 0.0, "tiket": set()})
        for t in session.scalars(q):
            kunci = getattr(t, kolom) or "(kosong)"
            agreg[kunci]["ton"] += float(t.dry_kg or 0) / 1000.0
            agreg[kunci]["tiket"].add(t.ticket_no)
        nama_vendor = {v.kode: v.nama_baku for v in session.scalars(select(Vendor))} \
            if dimensi == "vendor" else {}
        total = sum(a["ton"] for a in agreg.values())
        baris = sorted(({
            "kunci": k, "label": nama_vendor.get(k, k),
            "ton": round(a["ton"], 3),
            "porsi": round(a["ton"] / total, 4) if total else None,
            "jumlah_tiket": len(a["tiket"]),
        } for k, a in agreg.items()), key=lambda x: -x["ton"])
        drill = None
        if dimensi in URUTAN_WILAYAH[:-1]:
            drill = URUTAN_WILAYAH[URUTAN_WILAYAH.index(dimensi) + 1]
        hasil = {"dimensi": dimensi, "drill_berikutnya": drill,
                 "total_ton": round(total, 3), "baris": baris,
                 "sumber": "tiket_baris (Dry, tanpa tiket nol)"}
        if format == "xlsx":
            return respon_xlsx(
                f"tonase_per_{dimensi}.xlsx",
                [dimensi, "Nama", "Ton kering", "Porsi", "Jumlah tiket"],
                [[b["kunci"], b["label"], b["ton"], b["porsi"], b["jumlah_tiket"]]
                 for b in baris])
        return hasil

    # ------------------------------------------------------------ kartu: penerimaan biasa vs EUDR
    @router.get("/kartu/penerimaan")
    def kartu_penerimaan(dimensi: str = "vendor",
                         dari: dt.date | None = None, sampai: dt.date | None = None,
                         eudr: bool | None = None, vendor: str | None = None,
                         provinsi: str | None = None, kabupaten: str | None = None,
                         kecamatan: str | None = None, desa: str | None = None,
                         per: str = "dimensi", top: int = 8,
                         format: str | None = None, session: Session = dep):
        """Penerimaan karet (kg kering) per dimensi, dipisah grade biasa vs
        EUDR (kode TTSR). eudr=true -> hanya tiket EUDR (mis. untuk melihat
        vendor mana yang memasok karet EUDR); eudr=false -> hanya biasa.

        `per=bulan` -> rincian per bulan untuk dimensi terpilih (dipakai bila
        periode filter lebih dari satu bulan): bulan x dimensi, dengan `top`
        dimensi terbesar dan sisanya digabung menjadi "Lainnya". Tanpa
        `per=bulan`, bentuk jawabannya tetap seperti semula (satu baris per
        dimensi untuk seluruh periode)."""
        if dimensi not in DIMENSI_TONASE:
            raise HTTPException(422, f"Dimensi '{dimensi}' tidak dikenal. "
                                     f"Pilihan: {', '.join(DIMENSI_TONASE)}.")
        q = _filter_tiket(select(TiketBaris), vendor=vendor, provinsi=provinsi,
                          kabupaten=kabupaten, kecamatan=kecamatan, desa=desa,
                          session=session)
        if dari:
            q = q.where(TiketBaris.ticket_date >= dari)
        if sampai:
            q = q.where(TiketBaris.ticket_date <= sampai)

        kode_eudr = {g.item_code for g in session.scalars(
            select(Grade).where(Grade.eudr == True))}  # noqa: E712

        def tiket_eudr(item: str | None) -> bool:
            return (item in kode_eudr) or ("TTSR" in (item or "").upper())

        if per not in ("dimensi", "bulan"):
            raise HTTPException(422, "Parameter per hanya boleh \"dimensi\" "
                                     "atau \"bulan\".")
        if not 1 <= top <= 40:
            raise HTTPException(422, "Parameter top harus antara 1 dan 40.")

        kolom = {"vendor": "kode_vendor", "grade": "item_code"}.get(dimensi, dimensi)
        # Satu lintasan data: dipakai untuk kedua bentuk keluaran.
        potongan: list[tuple[str, tuple[int, int] | None, float, bool, str]] = []
        for t in session.scalars(q):
            e = tiket_eudr(t.item_code)
            if eudr is True and not e:
                continue
            if eudr is False and e:
                continue
            bulan = (t.ticket_date.year, t.ticket_date.month) if t.ticket_date else None
            potongan.append((getattr(t, kolom) or "(kosong)", bulan,
                             float(t.dry_kg or 0), e, t.ticket_no))

        if per == "bulan":
            return _penerimaan_per_bulan(potongan, dimensi, dari, sampai,
                                         top, format, session)

        agreg: dict[str, dict] = defaultdict(
            lambda: {"biasa": 0.0, "eudr": 0.0, "tiket": set()})
        for kunci, _bulan, kg, e, no_tiket in potongan:
            agreg[kunci]["eudr" if e else "biasa"] += kg
            agreg[kunci]["tiket"].add(no_tiket)

        nama_vendor = {v.kode: v.nama_baku for v in session.scalars(select(Vendor))} \
            if dimensi == "vendor" else {}
        total = sum(a["biasa"] + a["eudr"] for a in agreg.values())
        baris = sorted(({
            "kunci": k,
            "label": (f"{k} — {nama_vendor[k]}" if k in nama_vendor else k),
            "kg_biasa": round(a["biasa"], 1),
            "kg_eudr": round(a["eudr"], 1),
            "kg_total": round(a["biasa"] + a["eudr"], 1),
            "porsi": round((a["biasa"] + a["eudr"]) / total, 4) if total else None,
            "jumlah_tiket": len(a["tiket"]),
        } for k, a in agreg.items()), key=lambda x: -x["kg_total"])
        drill = None
        if dimensi in URUTAN_WILAYAH[:-1]:
            drill = URUTAN_WILAYAH[URUTAN_WILAYAH.index(dimensi) + 1]
        hasil = {"dimensi": dimensi, "drill_berikutnya": drill,
                 "total_kg": round(total, 1),
                 "total_kg_biasa": round(sum(b["kg_biasa"] for b in baris), 1),
                 "total_kg_eudr": round(sum(b["kg_eudr"] for b in baris), 1),
                 "baris": baris,
                 "sumber": "tiket_baris (Dry kg, tanpa tiket nol); EUDR = grade "
                           "ber-flag EUDR / kode TTSR"}
        if format == "xlsx":
            return respon_xlsx(
                f"penerimaan_per_{dimensi}.xlsx",
                [dimensi, "Kg biasa", "Kg EUDR", "Kg total", "Porsi",
                 "Jumlah tiket"],
                [[b["label"], b["kg_biasa"], b["kg_eudr"], b["kg_total"],
                  b["porsi"], b["jumlah_tiket"]] for b in baris])
        return hasil

    # ------------------------------------------------------------ kartu: konsentrasi vendor
    @router.get("/kartu/konsentrasi-vendor")
    def kartu_konsentrasi(top: int = 5, tahun: int | None = None,
                          bulan: int | None = None, format: str | None = None,
                          session: Session = dep):
        if top not in (5, 10):
            raise HTTPException(422, "Parameter top hanya boleh 5 atau 10.")
        data = kartu_tonase(dimensi="vendor", tahun=tahun, bulan=bulan,
                            session=session)
        baris = data["baris"][:top]
        porsi_top = sum(b["porsi"] or 0 for b in baris)
        hasil = {"top": top, "total_ton": data["total_ton"], "baris": baris,
                 "porsi_top": round(porsi_top, 4)}
        if format == "xlsx":
            return respon_xlsx(
                f"konsentrasi_vendor_top{top}.xlsx",
                ["Kode", "Nama", "Ton kering", "Porsi", "Jumlah tiket"],
                [[b["kunci"], b["label"], b["ton"], b["porsi"], b["jumlah_tiket"]]
                 for b in baris])
        return hasil

    # ------------------------------------------------------------ kartu: bauran grade & EUDR
    @router.get("/kartu/bauran-grade")
    def kartu_grade(tahun: int | None = None, bulan: int | None = None,
                    format: str | None = None, session: Session = dep):
        data = kartu_tonase(dimensi="grade", tahun=tahun, bulan=bulan, session=session)
        grade_map = {g.item_code: g for g in session.scalars(select(Grade))}
        baris = []
        porsi_eudr = 0.0
        for b in data["baris"]:
            g = grade_map.get(b["kunci"])
            eudr = bool(g.eudr) if g else ("TTSR" in b["kunci"].upper())
            if eudr:
                porsi_eudr += b["porsi"] or 0
            baris.append({**b, "kelompok": g.kelompok if g else None, "eudr": eudr})
        hasil = {"total_ton": data["total_ton"], "baris": baris,
                 "porsi_eudr": round(porsi_eudr, 4)}
        if format == "xlsx":
            return respon_xlsx(
                "bauran_grade.xlsx",
                ["Grade", "Kelompok", "EUDR", "Ton kering", "Porsi"],
                [[b["kunci"], b["kelompok"], "Ya" if b["eudr"] else "Tidak",
                  b["ton"], b["porsi"]] for b in baris])
        return hasil

    # ------------------------------------------------------------ kartu: reject%
    @router.get("/kartu/reject")
    def kartu_reject(tahun: int | None = None, format: str | None = None,
                     session: Session = dep):
        q = select(TiketBaris).where(TiketBaris.tiket_nol == False)  # noqa: E712
        awal, akhir = _rentang(tahun, None)
        if awal:
            q = q.where(TiketBaris.ticket_date >= awal, TiketBaris.ticket_date <= akhir)
        per_bulan: dict[tuple[int, int], dict] = defaultdict(lambda: {"wet": Decimal(0), "reject": Decimal(0)})
        for t in session.scalars(q):
            k = (t.ticket_date.year, t.ticket_date.month)
            per_bulan[k]["wet"] += t.wet_kg or 0
            per_bulan[k]["reject"] += t.reject_kg or 0
        baris = [{
            "tahun": thn, "bulan": bln,
            "wet_ton": round(float(v["wet"]) / 1000, 3),
            "reject_ton": round(float(v["reject"]) / 1000, 3),
            "reject_pct": round(float(v["reject"]) / float(v["wet"]) * 100, 2)
            if v["wet"] else None,
        } for (thn, bln), v in sorted(per_bulan.items())]
        hasil = {"baris": baris, "kpi": kpi_reject(session)}
        if format == "xlsx":
            return respon_xlsx("reject.xlsx",
                               ["Tahun", "Bulan", "Wet ton", "Reject ton", "Reject %"],
                               [[b["tahun"], b["bulan"], b["wet_ton"], b["reject_ton"],
                                 b["reject_pct"]] for b in baris])
        return hasil

    # ------------------------------------------------------------ kartu: margin harian/bulanan
    @router.get("/kartu/margin-harian")
    def kartu_margin_harian(tahun: int, bulan: int, format: str | None = None,
                            session: Session = dep):
        awal, akhir = _rentang(tahun, bulan)
        baris = [{
            "tanggal": h.tanggal.isoformat(), "qty_kg": h.qty_kering_kg,
            "amount_rp": float(h.amount_rp) if h.amount_rp is not None else None,
            "harga_rp_per_kg": h.harga_rp_per_kg, "kurs": h.kurs,
            "sicom": h.sicom_usc, "harga_usc": h.harga_usc_per_kg,
            "margin": h.margin_usc,
        } for h in session.scalars(select(MartHarian).where(
            MartHarian.tanggal >= awal, MartHarian.tanggal <= akhir,
            MartHarian.qty_kering_kg != None).order_by(MartHarian.tanggal))]  # noqa: E711
        if format == "xlsx":
            return respon_xlsx(
                f"margin_harian_{tahun}_{bulan:02d}.xlsx",
                ["Tanggal", "Qty kg", "Amount Rp", "Harga Rp/kg", "Kurs",
                 "SICOM", "Harga USc/kg", "Margin USc/kg"],
                [[b["tanggal"], b["qty_kg"], b["amount_rp"], b["harga_rp_per_kg"],
                  b["kurs"], b["sicom"], b["harga_usc"], b["margin"]] for b in baris])
        return {"baris": baris}

    @router.get("/kartu/margin-bulanan")
    def kartu_margin_bulanan(dari: str | None = None, sampai: str | None = None,
                             format: str | None = None, session: Session = dep):
        """OP Margin bulanan untuk grafik tren vs target.

        `dari`/`sampai` (YYYY-MM) membatasi periode yang ditampilkan; kartu di
        layar selalu mengirim periode pilihannya, bawaannya seluruh data.
        """
        kd = _bulan_ym(dari, "dari")
        ks = _bulan_ym(sampai, "sampai")
        if kd and ks and kd > ks:
            raise HTTPException(422, "Periode 'dari' harus sebelum atau sama "
                                     "dengan 'sampai'.")
        semua = [b for b in session.scalars(select(MartBulanan).order_by(
            MartBulanan.tahun, MartBulanan.bulan))
            if (kd is None or (b.tahun, b.bulan) >= kd)
            and (ks is None or (b.tahun, b.bulan) <= ks)]
        # Kurs efektif bulanan (tertimbang nilai transaksi) untuk toggle Rp/kg:
        # K = SUM(Amount) / SUM(Amount/kurs). Jatuh ke rata-rata kurs bila kosong.
        rp: dict[tuple[int, int], float] = defaultdict(float)
        usd: dict[tuple[int, int], float] = defaultdict(float)
        kurs_avg: dict[tuple[int, int], list[float]] = defaultdict(list)
        for h in session.scalars(select(MartHarian)):
            kunci = (h.tanggal.year, h.tanggal.month)
            if h.kurs:
                kurs_avg[kunci].append(h.kurs)
                if h.qty_kering_kg and h.qty_kering_kg > 0 and h.amount_rp:
                    rp[kunci] += float(h.amount_rp)
                    usd[kunci] += float(h.amount_rp) / h.kurs

        def _kurs(kunci: tuple[int, int]) -> float | None:
            if usd.get(kunci):
                return rp[kunci] / usd[kunci]
            v = kurs_avg.get(kunci)
            return sum(v) / len(v) if v else None

        baris = [{
            "tahun": b.tahun, "bulan": b.bulan, "sicom": b.sicom_usc,
            "op_price": b.harga_beli_usc, "op_margin": b.op_margin_usc,
            "ton": b.qty_ton, "target": b.target_usc, "pencapaian": b.pencapaian,
            "kurs": _kurs((b.tahun, b.bulan)),
            "selisih_vs_target": (b.op_margin_usc - b.target_usc)
            if (b.target_usc is not None and b.op_margin_usc is not None) else None,
            "status_target": _status_target(b.op_margin_usc, b.target_usc),
            "catatan_koreksi": KOREKSI.get((b.tahun, b.bulan)),
        } for b in semua]
        if format == "xlsx":
            return respon_xlsx(
                "margin_bulanan.xlsx",
                ["Tahun", "Bulan", "SICOM (USc/kg)", "OP Price (USc/kg)",
                 "OP Margin (USc/kg)", "Ton", "Target (USc/kg)", "Pencapaian",
                 "OP Margin (Rp/kg)", "Kurs efektif (Rp/USD)", "Selisih vs target (USc/kg)",
                 "Status", "Catatan"],
                [[b["tahun"], b["bulan"], b["sicom"], b["op_price"], b["op_margin"],
                  b["ton"], b["target"], b["pencapaian"],
                  (b["op_margin"] * b["kurs"] / 100.0) if b["kurs"] else None,
                  b["kurs"],
                  (b["op_margin"] - b["target"])
                  if (b["target"] is not None and b["op_margin"] is not None) else None,
                  _status_target(b["op_margin"], b["target"]),
                  b["catatan_koreksi"] or ""]
                 for b in baris])
        return {"baris": baris,
                "dari": f"{baris[0]['tahun']}-{baris[0]['bulan']:02d}" if baris else None,
                "sampai": f"{baris[-1]['tahun']}-{baris[-1]['bulan']:02d}" if baris else None,
                "jumlah_bulan": len(baris)}

    # ------------------------------------------------------------ kartu: margin per grade/vendor
    @router.get("/kartu/margin-per")
    def kartu_margin_per(dimensi: str, tahun: int | None = None,
                         bulan: int | None = None,
                         dari: dt.date | None = None, sampai: dt.date | None = None,
                         per: str = "dimensi", top: int = 8,
                         format: str | None = None, session: Session = dep):
        """Margin per grade/vendor.

        `per=bulan` -> rincian bulan x dimensi (margin US¢/kg + ton), dipakai
        bila filter periode lebih dari satu bulan. Tanpa `per=bulan` bentuk
        jawaban lama tidak berubah.
        """
        if dimensi not in ("grade", "vendor"):
            raise HTTPException(422, "Dimensi hanya boleh 'grade' atau 'vendor'.")
        if per not in ("dimensi", "bulan"):
            raise HTTPException(422, "Parameter per hanya boleh \"dimensi\" "
                                     "atau \"bulan\".")
        if not 1 <= top <= 40:
            raise HTTPException(422, "Parameter top harus antara 1 dan 40.")
        if dari or sampai:
            awal = dari or sampai
            akhir = sampai or dari
            if awal > akhir:
                raise HTTPException(422, "Tanggal 'dari' harus sebelum 'sampai'.")
        else:
            if tahun is None:
                # Tanpa tahun: pakai tahun terakhir yang ada datanya.
                akhir_p = session.scalars(select(Pembelian)
                                          .order_by(Pembelian.tanggal.desc())
                                          .limit(1)).first()
                tahun = akhir_p.tanggal.year if akhir_p else dt.date.today().year
            awal, akhir = _rentang(tahun, bulan)
        q = select(Pembelian).where(Pembelian.tanggal >= awal, Pembelian.tanggal <= akhir)
        semua = list(session.scalars(q))
        if dimensi == "grade":
            rinci = [p for p in semua if p.item_code not in ("ALL", "", None)]
        else:
            rinci = [p for p in semua if p.kode_vendor]
        if not rinci:
            return {"status": "data harga belum tersedia",
                    "pesan": f"Amount pembelian periode ini hanya tersedia sebagai "
                             f"total per hari, belum per {dimensi}. Margin per "
                             f"{dimensi} TIDAK dialokasikan diam-diam.",
                    "baris": []}
        kurs_cari = PencariBerlaku([(k.berlaku_dari, k) for k in session.scalars(select(Kurs))])
        sicom_cari = PencariBerlaku([(s.tanggal, s) for s in session.scalars(select(Sicom))])
        grup: dict[str, list[rumus.BarisHarian]] = defaultdict(list)
        for p in rinci:
            k = kurs_cari.pada(p.tanggal)
            s = sicom_cari.pada(p.tanggal)
            if not k or not s:
                continue
            kunci = p.item_code if dimensi == "grade" else p.kode_vendor
            grup[kunci].append(rumus.BarisHarian(
                float(p.qty_kering_kg), float(p.amount_rp),
                float(k.idr_per_usd), s.usc_per_kg))
        if per == "bulan":
            return _margin_per_bulan(rinci, dimensi, kurs_cari, sicom_cari,
                                     awal, akhir, top, format)

        baris = []
        for kunci, data in sorted(grup.items()):
            h = rumus.agregat_bulanan(data)
            baris.append({"kunci": kunci, "ton": round(h.qty_ton, 3),
                          "sicom": h.sicom_usc, "op_price": h.harga_beli_usc,
                          "op_margin": h.op_margin_usc})
        hasil = {"status": "ok", "dimensi": dimensi, "baris": baris}
        if format == "xlsx":
            return respon_xlsx(f"margin_per_{dimensi}.xlsx",
                               [dimensi, "Ton", "SICOM", "OP Price", "OP Margin"],
                               [[b["kunci"], b["ton"], b["sicom"], b["op_price"],
                                 b["op_margin"]] for b in baris])
        return hasil

    # ------------------------------------------------------------ telusur asal angka
    @router.get("/telusur/bulan")
    def telusur_bulan(tahun: int, bulan: int, session: Session = dep):
        """Dari angka margin bulanan -> hari-hari pembelian penyusunnya."""
        awal, akhir = _rentang(tahun, bulan)
        m = session.scalar(select(MartBulanan).where(
            MartBulanan.tahun == tahun, MartBulanan.bulan == bulan))
        hari = [{
            "tanggal": h.tanggal.isoformat(), "qty_kg": h.qty_kering_kg,
            "amount_rp": float(h.amount_rp) if h.amount_rp is not None else None,
            "harga_rp_per_kg": h.harga_rp_per_kg, "kurs": h.kurs,
            "sicom": h.sicom_usc, "margin": h.margin_usc,
        } for h in session.scalars(select(MartHarian).where(
            MartHarian.tanggal >= awal, MartHarian.tanggal <= akhir,
            MartHarian.qty_kering_kg != None).order_by(MartHarian.tanggal))]  # noqa: E711
        return {"tahun": tahun, "bulan": bulan,
                "op_margin": m.op_margin_usc if m else None,
                "rumus": "op_margin_bulan = SUM(qty*sicom)/SUM(qty) - "
                         "100*SUM(amount/kurs)/SUM(qty), hanya hari pembelian",
                "hari": hari}

    @router.get("/telusur/tanggal")
    def telusur_tanggal(tanggal: dt.date, session: Session = dep):
        """Dari angka harian -> baris pembelian & tiket asal + unggahan asal."""
        pembelian = [{
            "tanggal": p.tanggal.isoformat(), "item_code": p.item_code,
            "kode_vendor": p.kode_vendor or None, "ticket_no": p.ticket_no or None,
            "qty_kering_kg": float(p.qty_kering_kg), "amount_rp": float(p.amount_rp),
            "unggahan": _unggahan_info(session, p.unggahan_id),
        } for p in session.scalars(select(Pembelian).where(Pembelian.tanggal == tanggal))]
        tiket = [{
            "ticket_no": t.ticket_no, "line_seq": t.line_seq,
            "kode_vendor": t.kode_vendor, "item_code": t.item_code,
            "wet_kg": float(t.wet_kg) if t.wet_kg is not None else None,
            "dry_kg": float(t.dry_kg) if t.dry_kg is not None else None,
            "drc_pct": t.drc_pct, "tiket_nol": t.tiket_nol,
            "peringatan": t.peringatan,
            "unggahan": _unggahan_info(session, t.unggahan_id),
        } for t in session.scalars(select(TiketBaris).where(
            TiketBaris.ticket_date == tanggal).order_by(
            TiketBaris.ticket_no, TiketBaris.line_seq))]
        sicom = session.get(Sicom, tanggal)
        return {"tanggal": tanggal.isoformat(),
                "pembelian": pembelian, "tiket": tiket,
                "sicom": {"usc_per_kg": sicom.usc_per_kg, "sumber": sicom.sumber,
                          "unggahan": _unggahan_info(session, sicom.unggahan_id)}
                if sicom else None}

    app.include_router(router)
