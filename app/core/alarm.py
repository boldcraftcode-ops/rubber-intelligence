"""Mesin alarm (Fase 4). Dievaluasi setelah tiap unggahan/perubahan data.

Jenis alarm (bisa diatur admin: aktif/nonaktif + ambang, TANPA angka
yang ditanam di kode):
- STOK_DI_BAWAH_SAFETY    : rasio stok hari terakhir < ambang (default 1,0)
- MARGIN_DI_BAWAH_TARGET  : OP Margin bulan berjalan < target
- SICOM_TERLAMBAT         : SICOM terakhir lebih tua dari ambang hari
- KURS_TERLAMBAT          : kurs terakhir lebih tua dari ambang hari
- STOK_TERLAMBAT          : stok terakhir lebih tua dari ambang hari
- TIKET_TERLAMBAT         : tiket terakhir lebih tua dari ambang hari
- SELISIH_REKONSILIASI    : selisih harian tiket vs pembelian > ambang kg,
                            atau selisih diketahui yang belum disetujui
- HARGA_DI_ATAS_MAKS      : harga beli aktual terakhir > harga beli maksimum
                            menurut aturan stok
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models import (
    Alarm,
    AuditLog,
    Kurs,
    MartBulanan,
    MartHarian,
    PengaturanAlarm,
    Sicom,
    Stok,
    TiketBaris,
)
from .rekomendasi import rekomendasi_harga
from .rekonsiliasi import rekonsiliasi_harian, selisih_diketahui

PENGATURAN_BAWAAN = [
    ("STOK_DI_BAWAH_SAFETY", 1.0, "rasio",
     "Alarm bila stok hari terakhir di bawah ambang x safety stock."),
    ("MARGIN_DI_BAWAH_TARGET", None, None,
     "Alarm bila OP Margin bulan terakhir di bawah target bulan itu."),
    ("SICOM_TERLAMBAT", 1, "hari", "Alarm bila SICOM terakhir lebih tua dari ambang."),
    ("KURS_TERLAMBAT", 60, "hari",
     "Kurs hanya diisi saat berubah; ambang longgar."),
    ("STOK_TERLAMBAT", 3, "hari", "Alarm bila stok terakhir lebih tua dari ambang."),
    ("TIKET_TERLAMBAT", 3, "hari", "Alarm bila tiket terakhir lebih tua dari ambang."),
    ("SELISIH_REKONSILIASI", 100, "kg",
     "Alarm bila selisih harian tiket vs pembelian melebihi ambang, atau ada "
     "selisih diketahui yang belum disetujui."),
    ("HARGA_DI_ATAS_MAKS", None, None,
     "Alarm bila harga beli aktual terakhir melebihi harga beli maksimum aturan."),
]


def pastikan_pengaturan(session: Session) -> None:
    """Isi pengaturan bawaan sekali; setelah itu admin yang mengatur."""
    ada = {p.kode for p in session.scalars(select(PengaturanAlarm))}
    for kode, ambang, satuan, ket in PENGATURAN_BAWAAN:
        if kode not in ada:
            session.add(PengaturanAlarm(kode=kode, aktif=True, ambang=ambang,
                                        satuan=satuan, keterangan=ket))
    session.flush()


def catat_audit(session: Session, siapa: str, aksi: str, objek: str, detail: dict):
    session.add(AuditLog(siapa=siapa or "?", aksi=aksi, objek=objek,
                         detail=json.dumps(detail, default=str, ensure_ascii=False)))


def evaluasi_alarm(session: Session, hari_ini: dt.date | None = None) -> list[Alarm]:
    """Bangun ulang tabel alarm berdasarkan pengaturan aktif."""
    hari_ini = hari_ini or dt.date.today()
    pastikan_pengaturan(session)
    atur = {p.kode: p for p in session.scalars(select(PengaturanAlarm))}
    session.execute(delete(Alarm))
    hasil: list[Alarm] = []

    def nyalakan(kode: str, pesan: str, tanggal: dt.date | None = None,
                 nilai: float | None = None):
        a = Alarm(kode=kode, pesan=pesan, tanggal_data=tanggal, nilai=nilai)
        session.add(a)
        hasil.append(a)

    def aktif(kode: str) -> PengaturanAlarm | None:
        p = atur.get(kode)
        return p if p and p.aktif else None

    # ---- stok di bawah safety ------------------------------------------------
    p = aktif("STOK_DI_BAWAH_SAFETY")
    if p:
        h = session.scalars(select(MartHarian).where(
            MartHarian.rasio_stok != None)  # noqa: E711
            .order_by(MartHarian.tanggal.desc())).first()
        if h and p.ambang is not None and h.rasio_stok < p.ambang:
            nyalakan("STOK_DI_BAWAH_SAFETY",
                     f"Stok {h.tanggal.strftime('%d/%m/%Y')} = {h.stok_ton:,.1f} ton "
                     f"({h.rasio_stok:.1%} dari safety {h.safety_ton:,.1f} ton); "
                     f"di bawah ambang {p.ambang:.0%}. Days tersisa {h.days:,.1f}.",
                     h.tanggal, h.rasio_stok)

    # ---- margin di bawah target ---------------------------------------------
    p = aktif("MARGIN_DI_BAWAH_TARGET")
    if p:
        b = session.scalars(select(MartBulanan).order_by(
            MartBulanan.tahun.desc(), MartBulanan.bulan.desc())).first()
        if b and b.target_usc is not None and b.op_margin_usc is not None \
                and b.op_margin_usc < b.target_usc:
            nyalakan("MARGIN_DI_BAWAH_TARGET",
                     f"OP Margin {b.bulan:02d}/{b.tahun} = {b.op_margin_usc:.4f} "
                     f"US¢/kg, di bawah target {b.target_usc:.2f}.",
                     dt.date(b.tahun, b.bulan, 1), b.op_margin_usc)

    # ---- data terlambat --------------------------------------------------------
    sumber = [
        ("SICOM_TERLAMBAT", "SICOM", session.scalar(select(func.max(Sicom.tanggal)))),
        ("KURS_TERLAMBAT", "kurs", session.scalar(select(func.max(Kurs.berlaku_dari)))),
        ("STOK_TERLAMBAT", "stok", session.scalar(select(func.max(Stok.tanggal)))),
        ("TIKET_TERLAMBAT", "tiket",
         session.scalar(select(func.max(TiketBaris.ticket_date)))),
    ]
    for kode, nama, terakhir in sumber:
        p = aktif(kode)
        if not p or p.ambang is None:
            continue
        if terakhir is None:
            nyalakan(kode, f"Belum ada data {nama} sama sekali.")
            continue
        umur = (hari_ini - terakhir).days
        if umur > p.ambang:
            nyalakan(kode,
                     f"Data {nama} terakhir {terakhir.strftime('%d/%m/%Y')} "
                     f"({umur} hari lalu, ambang {p.ambang:.0f} hari). "
                     f"Mohon isi/unggah data {nama} terbaru.",
                     terakhir, float(umur))

    # ---- selisih rekonsiliasi --------------------------------------------------
    p = aktif("SELISIH_REKONSILIASI")
    if p:
        for d in selisih_diketahui():
            nyalakan("SELISIH_REKONSILIASI",
                     f"{d['periode']}: selisih tiket vs Excel {d['selisih_ton']:,.3f} "
                     f"ton — {d['status']}.",
                     dt.date(d["tahun"], d["bulan"], 1), d["selisih_ton"])
        if p.ambang is not None:
            buruk = [h for h in rekonsiliasi_harian(session)
                     if abs(h["selisih_kg"]) > p.ambang]
            if buruk:
                terparah = max(buruk, key=lambda h: abs(h["selisih_kg"]))
                nyalakan("SELISIH_REKONSILIASI",
                         f"{len(buruk)} tanggal dengan selisih tiket vs pembelian "
                         f"> {p.ambang:,.0f} kg; terparah "
                         f"{terparah['tanggal']} ({terparah['selisih_kg']:,.1f} kg).",
                         None, float(len(buruk)))

    # ---- harga aktual di atas harga beli maksimum -------------------------------
    p = aktif("HARGA_DI_ATAS_MAKS")
    if p:
        r = rekomendasi_harga(session)
        if r.status == "OK" and r.harga_beli_aktual_terakhir_usc is not None \
                and r.harga_beli_maks_usc is not None \
                and r.harga_beli_aktual_terakhir_usc > r.harga_beli_maks_usc:
            nyalakan("HARGA_DI_ATAS_MAKS",
                     f"Harga beli aktual terakhir "
                     f"({r.tanggal_harga_aktual.strftime('%d/%m/%Y')}) = "
                     f"{r.harga_beli_aktual_terakhir_usc:.4f} US¢/kg, di atas harga "
                     f"beli maksimum aturan {r.harga_beli_maks_usc:.4f} US¢/kg"
                     + (" (aturan masih CONTOH)" if r.aturan_contoh else "") + ".",
                     r.tanggal_harga_aktual, r.harga_beli_aktual_terakhir_usc)

    session.flush()
    return hasil
