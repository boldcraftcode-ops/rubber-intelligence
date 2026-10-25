"""API analisis Fase 3: ringkasan ala Excel, rekonsiliasi, kualitas data,
kartu query dengan filter berdaftar-putih, telusur asal angka, dan ekspor
Excel. Tidak ada SQL dari klien — semua kartu adalah query terdefinisi.
"""
from __future__ import annotations

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
    @router.get("/margin-bridge")
    def margin_bridge(basis: str = "bulanan", tahun: int | None = None,
                      bulan: int | None = None, format: str | None = None,
                      session: Session = dep):
        """Jembatan OP Margin periode A -> periode B (waterfall).

        awal + ΔSICOM + efek harga Rp + efek kurs = akhir, tertutup persis
        (selisih hanya pembulatan float). Basis 'bulanan': B = (tahun, bulan),
        A = bulan sebelumnya. Basis 'tahunan': B = tahun, A = tahun-1, hanya
        bulan-bulan yang berdata di kedua tahun (bandingkan apples-to-apples).
        """
        if basis not in ("bulanan", "tahunan"):
            raise HTTPException(422, "basis harus 'bulanan' atau 'tahunan'.")
        if bulan is not None and not 1 <= bulan <= 12:
            raise HTTPException(422, "bulan harus antara 1 dan 12.")

        terakhir = session.scalars(
            select(MartBulanan).order_by(MartBulanan.tahun.desc(),
                                         MartBulanan.bulan.desc()).limit(1)).first()
        if terakhir is None:
            raise HTTPException(404, "Belum ada data mart bulanan. "
                                     "Jalankan import-template dulu.")
        if tahun is None:
            tahun = terakhir.tahun

        if basis == "bulanan":
            if bulan is None:
                m = session.scalars(select(MartBulanan).where(
                    MartBulanan.tahun == tahun).order_by(
                    MartBulanan.bulan.desc()).limit(1)).first()
                if m is None:
                    raise HTTPException(404, f"Belum ada data untuk tahun {tahun}.")
                bulan = m.bulan
            thn_a, bln_a = (tahun - 1, 12) if bulan == 1 else (tahun, bulan - 1)
            baris_a = _baris_periode_bulanan(session, thn_a, bln_a)
            baris_b = _baris_periode_bulanan(session, tahun, bulan)
            periode_a = {"tahun": thn_a, "bulan": bln_a}
            periode_b = {"tahun": tahun, "bulan": bulan}
        else:
            ada_a = {b.bulan for b in session.scalars(select(MartBulanan).where(
                MartBulanan.tahun == tahun - 1))}
            ada_b = {b.bulan for b in session.scalars(select(MartBulanan).where(
                MartBulanan.tahun == tahun))}
            umum = sorted(ada_a & ada_b)
            if not umum:
                raise HTTPException(
                    404, f"Tidak ada bulan berdata bersama antara "
                         f"{tahun - 1} dan {tahun} — tidak bisa dijembatani.")
            baris_a = _baris_periode_tahunan(session, tahun - 1, umum)
            baris_b = _baris_periode_tahunan(session, tahun, umum)
            periode_a = {"tahun": tahun - 1, "bulan_pertama": umum[0],
                         "bulan_terakhir": umum[-1], "bulan_list": umum}
            periode_b = {"tahun": tahun, "bulan_pertama": umum[0],
                         "bulan_terakhir": umum[-1], "bulan_list": umum}

        a = _agregat_bridge(baris_a)
        b = _agregat_bridge(baris_b)
        if a is None or b is None:
            raise HTTPException(
                404, "Salah satu periode belum punya hari pembelian "
                     "(qty > 0 dengan kurs & SICOM) — bridge tidak bisa dihitung.")

        d_sicom = b["sicom"] - a["sicom"]
        efek_harga = 100.0 * (b["e_rp_kg"] - a["e_rp_kg"]) / a["kurs_efektif"]
        efek_kurs = 100.0 * b["e_rp_kg"] * (1.0 / b["kurs_efektif"]
                                             - 1.0 / a["kurs_efektif"])
        langkah = [
            {"kode": "sicom", "label": "Δ SICOM", "nilai": d_sicom},
            {"kode": "harga_rp", "label": "Δ harga beli (Rp/kg)", "nilai": -efek_harga},
            {"kode": "kurs", "label": "Δ kurs", "nilai": -efek_kurs},
        ]
        awal = a["margin"]
        akhir = b["margin"]
        hasil = {
            "basis": basis,
            "periode_a": periode_a,
            "periode_b": periode_b,
            "awal": awal,
            "langkah": langkah,
            "akhir": akhir,
            "penutupan_selisih": round(awal + sum(l["nilai"] for l in langkah)
                                       - akhir, 12),
            "detail": {
                "sicom_a": a["sicom"], "sicom_b": b["sicom"],
                "harga_a": a["harga"], "harga_b": b["harga"],
                "margin_a": awal, "margin_b": akhir,
                "e_a": a["e_rp_kg"], "e_b": b["e_rp_kg"],
                "kurs_a": a["kurs_efektif"], "kurs_b": b["kurs_efektif"],
                "qty_a": a["qty_ton"], "qty_b": b["qty_ton"],
                "hari_a": a["hari_pembelian"], "hari_b": b["hari_pembelian"],
            },
            "catatan": [
                "OP Margin = SICOM − OP Price; bridge = penyusunan selisih "
                "periode A → periode B menjadi kontribusi yang tertutup persis.",
                "Kurs efektif K = ΣAmount / Σ(Amount/kurs) (tertimbang nilai "
                "transaksi); harga USc/kg = 100 × (Rp/kg tertimbang) / K.",
                "Basis tahunan memakai irisan bulan berdata kedua tahun "
                "supaya perbandingan adil (mis. Jan–Okt vs Jan–Okt).",
            ],
        }
        if format == "xlsx":
            judul = ["Komponen", "Nilai (USc/kg)"]
            isi = [[f"OP Margin awal — {periode_a}", awal]]
            isi += [[l["label"], l["nilai"]] for l in langkah]
            isi.append([f"OP Margin akhir — {periode_b}", akhir])
            isi.append(["Selisih penutupan (harus ~0)", hasil["penutupan_selisih"]])
            d = hasil["detail"]
            isi += [
                [], ["Detail", "Periode A", "Periode B"],
                ["SICOM (USc/kg)", d["sicom_a"], d["sicom_b"]],
                ["OP Price (USc/kg)", d["harga_a"], d["harga_b"]],
                ["Harga beli (Rp/kg, tertimbang)", d["e_a"], d["e_b"]],
                ["Kurs efektif (Rp/USD)", d["kurs_a"], d["kurs_b"]],
                ["Qty kering (ton)", d["qty_a"], d["qty_b"]],
                ["Hari pembelian", d["hari_a"], d["hari_b"]],
            ]
            nama = f"margin_bridge_{basis}_{tahun}.xlsx"
            return respon_xlsx(nama, judul, isi)
        return hasil

    # ------------------------------------------------------------ days of cover
    @router.get("/days-of-cover")
    def days_of_cover(dari: dt.date | None = None, sampai: dt.date | None = None,
                      format: str | None = None, session: Session = dep):
        """Cadangan hari olah dari stok (days of cover) + tren harian.

        days = stok_ton / kapasitas_ton_per_hari (parameter berversi tanggal).
        Bila tidak ada filter, memakai 180 hari data stok terakhir.
        """
        q = select(MartHarian).where(MartHarian.stok_ton != None)  # noqa: E711
        semua = list(session.scalars(q.order_by(MartHarian.tanggal)))
        if not semua:
            raise HTTPException(404, "Belum ada data stok harian di mart.")
        if dari is None and sampai is None:
            sampai = semua[-1].tanggal
            dari = sampai - dt.timedelta(days=179)
        baris = [h for h in semua
                 if (dari is None or h.tanggal >= dari)
                 and (sampai is None or h.tanggal <= sampai)]
        if not baris:
            raise HTTPException(404, f"Tidak ada data stok antara "
                                     f"{dari} dan {sampai}.")

        seri = [{
            "tanggal": h.tanggal.isoformat(),
            "stok_ton": round(h.stok_ton, 3),
            "kapasitas_ton": h.kapasitas_ton,
            "safety_ton": h.safety_ton,
            "days": round(h.days, 3) if h.days is not None else None,
            "safety_days": (round(h.safety_ton / h.kapasitas_ton, 3)
                            if h.safety_ton is not None and h.kapasitas_ton
                            else None),
            "rasio_stok": round(h.rasio_stok, 4) if h.rasio_stok is not None else None,
        } for h in baris]

        terkini = seri[-1]
        if terkini["rasio_stok"] is None:
            status = "tanpa safety"
        else:
            status = "di bawah safety" if terkini["rasio_stok"] < 1 else "aman"
        n30 = [s["days"] for s in seri[-30:] if s["days"] is not None]
        berhari = [s for s in seri if s["days"] is not None]
        terendah = min(berhari, key=lambda s: s["days"]) if berhari else None
        tertinggi = max(berhari, key=lambda s: s["days"]) if berhari else None
        bawah = [s for s in seri
                 if s["rasio_stok"] is not None and s["rasio_stok"] < 1]

        hasil = {
            "dari": baris[0].tanggal.isoformat(),
            "sampai": baris[-1].tanggal.isoformat(),
            "terkini": {**terkini, "status": status},
            "rerata_30_hari": round(sum(n30) / len(n30), 3) if n30 else None,
            "terendah": terendah,
            "tertinggi": tertinggi,
            "jumlah_hari": len(seri),
            "jumlah_hari_di_bawah_safety": len(bawah),
            "seri": seri,
            "catatan": [
                "Days of cover = stok ton ÷ kapasitas olah (ton/hari): berapa "
                "hari olah tersisa bila laju olah tetap. Angka terkini memakai "
                "parameter (kapasitas & safety) yang berlaku pada tanggal itu.",
                "Garis kuning putus-putus = safety stock pada hari yang sama "
                "(safety ton ÷ kapasitas), bukan ambang konstan.",
            ],
        }
        if format == "xlsx":
            judul = ["Tanggal", "Stok (ton)", "Kapasitas (ton/hari)",
                     "Safety (ton)", "Days of cover", "Safety (hari)", "Rasio stok"]
            isi = [[s["tanggal"], s["stok_ton"], s["kapasitas_ton"], s["safety_ton"],
                    s["days"], s["safety_days"], s["rasio_stok"]] for s in seri]
            isi += [
                [], ["Ringkas", "Nilai"],
                ["Rerata 30 hari data terakhir", hasil["rerata_30_hari"]],
                ["Terendah (hari)", terendah["days"] if terendah else None],
                ["Tertinggi (hari)", tertinggi["days"] if tertinggi else None],
                ["Hari di bawah safety", hasil["jumlah_hari_di_bawah_safety"]],
            ]
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
    def grafik_margin(session: Session = dep):
        per_tahun: dict[int, dict[int, float]] = defaultdict(dict)
        for b in session.scalars(select(MartBulanan)):
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
                     vendor: str | None = None, grade: str | None = None,
                     eudr: bool | None = None,
                     provinsi: str | None = None, kabupaten: str | None = None,
                     kecamatan: str | None = None, desa: str | None = None,
                     format: str | None = None, session: Session = dep):
        if dimensi not in DIMENSI_TONASE:
            raise HTTPException(422, f"Dimensi '{dimensi}' tidak dikenal. "
                                     f"Pilihan: {', '.join(DIMENSI_TONASE)}.")
        q = _filter_tiket(select(TiketBaris), tahun, bulan, vendor, grade, eudr,
                          provinsi, kabupaten, kecamatan, desa, session=session)
        kolom = {"vendor": "kode_vendor", "grade": "item_code"}.get(dimensi, dimensi)
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
                         format: str | None = None, session: Session = dep):
        """Penerimaan karet (kg kering) per dimensi, dipisah grade biasa vs
        EUDR (kode TTSR). eudr=true -> hanya tiket EUDR (mis. untuk melihat
        vendor mana yang memasok karet EUDR); eudr=false -> hanya biasa."""
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

        kolom = {"vendor": "kode_vendor", "grade": "item_code"}.get(dimensi, dimensi)
        agreg: dict[str, dict] = defaultdict(
            lambda: {"biasa": 0.0, "eudr": 0.0, "tiket": set()})
        for t in session.scalars(q):
            e = tiket_eudr(t.item_code)
            if eudr is True and not e:
                continue
            if eudr is False and e:
                continue
            kunci = getattr(t, kolom) or "(kosong)"
            agreg[kunci]["eudr" if e else "biasa"] += float(t.dry_kg or 0)
            agreg[kunci]["tiket"].add(t.ticket_no)

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
    def kartu_margin_bulanan(format: str | None = None, session: Session = dep):
        baris = [{
            "tahun": b.tahun, "bulan": b.bulan, "sicom": b.sicom_usc,
            "op_price": b.harga_beli_usc, "op_margin": b.op_margin_usc,
            "ton": b.qty_ton, "target": b.target_usc, "pencapaian": b.pencapaian,
            "catatan_koreksi": KOREKSI.get((b.tahun, b.bulan)),
        } for b in session.scalars(select(MartBulanan).order_by(
            MartBulanan.tahun, MartBulanan.bulan))]
        if format == "xlsx":
            return respon_xlsx(
                "margin_bulanan.xlsx",
                ["Tahun", "Bulan", "SICOM", "OP Price", "OP Margin", "Ton",
                 "Target", "Pencapaian", "Catatan"],
                [[b["tahun"], b["bulan"], b["sicom"], b["op_price"], b["op_margin"],
                  b["ton"], b["target"], b["pencapaian"], b["catatan_koreksi"] or ""]
                 for b in baris])
        return {"baris": baris}

    # ------------------------------------------------------------ kartu: margin per grade/vendor
    @router.get("/kartu/margin-per")
    def kartu_margin_per(dimensi: str, tahun: int, bulan: int | None = None,
                         format: str | None = None, session: Session = dep):
        if dimensi not in ("grade", "vendor"):
            raise HTTPException(422, "Dimensi hanya boleh 'grade' atau 'vendor'.")
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
