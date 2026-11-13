"""Rekonsiliasi tonase (bagian 9 spesifikasi).

Aturan kunci: jumlah Dry tiket per tanggal tiket harus sama dengan
Quantity harian di Pembelian_Harian.

Kebijakan default: tiket dianggap sumber resmi tonase. Selisih TIDAK
dikoreksi diam-diam. Pengguna dapat memilih sumber yang benar lewat halaman
Rekonsiliasi; keputusannya disimpan pada tabel `rekonsiliasi_koreksi`,
dipakai untuk menutup selisih pada baris rekap, dan tercatat di audit log.
Data tiket / pembelian / angka Excel lama tetap utuh dan keputusan bisa
dibatalkan.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import KoreksiRekonsiliasi, Pembelian, TiketBaris

# Selisih yang sudah diketahui dari analisis file lama (harus muncul di laporan).
SELISIH_DIKETAHUI = [
    {
        "periode": "Juli 2026", "tahun": 2026, "bulan": 7,
        "tiket_ton": 5269.319, "excel_ton": 5249.866,
    },
    {
        "periode": "Agustus 2026", "tahun": 2026, "bulan": 8,
        "tiket_ton": 4759.827, "excel_ton": 4752.949,
    },
]

CATATAN_DIKETAHUI = [
    "Data tiket di aplikasi internal berhenti pada 19 September 2026; "
    "bulan setelah itu belum bisa direkonsiliasi penuh.",
    "Kebijakan: tiket dianggap sumber resmi tonase. Selisih TIDAK dikoreksi "
    "otomatis — perlu persetujuan pengguna sebelum angka lama diubah [TERBUKA].",
    "Revisi bersifat keputusan terkontrol: pilih sumber yang benar, lalu "
    "simpan. Data asli tidak diubah; keputusan tercatat di audit log dan "
    "dapat dibatalkan.",
]

PILIHAN_SUMBER: dict[str, tuple[str, ...]] = {
    "harian": ("tiket", "pembelian"),
    "diketahui": ("tiket", "excel"),
}

LABEL_SUMBER: dict[str, dict[str, str]] = {
    "harian": {"tiket": "Dry tiket", "pembelian": "Qty pembelian"},
    "diketahui": {"tiket": "Tiket", "excel": "Excel lama"},
}

STATUS_MENUNGGU = "menunggu persetujuan koreksi [TERBUKA]"


def kunci_diketahui(tahun: int, bulan: int) -> str:
    """Kunci stabil untuk baris selisih bulanan: `2026-07`."""
    return f"{tahun:04d}-{bulan:02d}"


def _peta_diketahui() -> dict[str, dict]:
    return {kunci_diketahui(s["tahun"], s["bulan"]): s
            for s in SELISIH_DIKETAHUI}


def sah_kunci(jenis: str, kunci: str) -> bool:
    """Format kunci dan (untuk bulanan) keberadaan baris referensi."""
    if jenis == "harian":
        try:
            dt.date.fromisoformat(kunci)
            return True
        except ValueError:
            return False
    if jenis == "diketahui":
        return bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", kunci)) \
            and kunci in _peta_diketahui()
    return False


def _peta_keputusan(session: Session | None,
                    jenis: str) -> dict[str, KoreksiRekonsiliasi]:
    if session is None:
        return {}
    return {k.kunci: k for k in session.scalars(
        select(KoreksiRekonsiliasi).where(KoreksiRekonsiliasi.jenis == jenis))}


def _keputusan_dict(k: KoreksiRekonsiliasi | None) -> dict | None:
    if k is None:
        return None
    return {
        "jenis": k.jenis,
        "kunci": k.kunci,
        "sumber_benar": k.sumber_benar,
        "alasan": k.alasan,
        "oleh": k.updated_by,
        "pada": k.updated_at.isoformat(timespec="seconds")
                if k.updated_at else None,
    }


def _label(jenis: str, sumber: str) -> str:
    return LABEL_SUMBER[jenis].get(sumber, sumber)


def _opsi_sumber(jenis: str, nilai_tiket: float, nilai_lawan: float,
                 satuan: str) -> list[dict]:
    kode_lawan = "pembelian" if jenis == "harian" else "excel"
    return [
        {"kode": "tiket", "label": _label(jenis, "tiket"),
         f"nilai_{satuan}": round(nilai_tiket, 3)},
        {"kode": kode_lawan, "label": _label(jenis, kode_lawan),
         f"nilai_{satuan}": round(nilai_lawan, 3)},
    ]


def _nilai_dipakai(jenis: str, sumber: str, nilai_tiket: float,
                   nilai_lawan: float) -> float | None:
    if sumber == "tiket":
        return round(nilai_tiket, 3)
    if sumber == ("pembelian" if jenis == "harian" else "excel"):
        return round(nilai_lawan, 3)
    return None


def selisih_diketahui(session: Session | None = None) -> list[dict]:
    """Baris Jul/Agu 2026, termasuk keputusan revisi bila sudah ada."""
    keputusan = _peta_keputusan(session, "diketahui")
    hasil = []
    for s in SELISIH_DIKETAHUI:
        kunci = kunci_diketahui(s["tahun"], s["bulan"])
        k = keputusan.get(kunci)
        selisih = round(s["tiket_ton"] - s["excel_ton"], 3)
        sumber = k.sumber_benar if k else None
        nilai = _nilai_dipakai("diketahui", sumber, s["tiket_ton"],
                               s["excel_ton"]) if sumber else None
        status = (f"Direvisi · {_label('diketahui', sumber)} dipakai"
                  if k else STATUS_MENUNGGU)
        hasil.append({
            **s,
            "kunci": kunci,
            "jenis": "diketahui",
            "satuan": "ton",
            "selisih_ton": selisih,
            "selisih_asli_ton": selisih,
            "selisih_efektif_ton": 0.0 if k else selisih,
            "status": status,
            "status_asli": STATUS_MENUNGGU,
            "direvisi": bool(k),
            "sumber_dipakai": sumber,
            "nilai_dipakai_ton": nilai,
            "pilihan_sumber": _opsi_sumber("diketahui", s["tiket_ton"],
                                           s["excel_ton"], "ton"),
            "koreksi": _keputusan_dict(k),
        })
    return hasil


def rekonsiliasi_harian(session: Session) -> list[dict]:
    """Bandingkan Dry tiket vs Quantity pembelian per tanggal.

    Bila ada keputusan, `selisih_efektif_kg` menjadi 0 dan `cocok` menjadi
    True, tetapi nilai sumber asli tetap ditampilkan apa adanya.
    """
    dry: dict[dt.date, Decimal] = defaultdict(Decimal)
    for t in session.scalars(select(TiketBaris).where(TiketBaris.tiket_nol == False)):  # noqa: E712
        if t.dry_kg is not None:
            dry[t.ticket_date] += t.dry_kg
    qty: dict[dt.date, Decimal] = defaultdict(Decimal)
    for p in session.scalars(select(Pembelian)):
        qty[p.tanggal] += p.qty_kering_kg

    keputusan = _peta_keputusan(session, "harian")
    hasil = []
    for tanggal in sorted(dry):
        d, q = float(dry[tanggal]), float(qty.get(tanggal, 0))
        kunci = tanggal.isoformat()
        k = keputusan.get(kunci)
        selisih = round(d - q, 3)
        cocok_asli = abs(selisih) <= 1.0
        sumber = k.sumber_benar if k else None
        nilai = _nilai_dipakai("harian", sumber, d, q) if sumber else None
        status_asli = "Cocok" if cocok_asli else "Belum direvisi"
        if k:
            status = f"Direvisi · {_label('harian', sumber)} dipakai"
        else:
            status = status_asli
        hasil.append({
            "tanggal": kunci,
            "kunci": kunci,
            "jenis": "harian",
            "satuan": "kg",
            "dry_tiket_kg": round(d, 3),
            "qty_pembelian_kg": round(q, 3),
            "selisih_kg": selisih,
            "selisih_asli_kg": selisih,
            "selisih_efektif_kg": 0.0 if k else selisih,
            "cocok": cocok_asli or bool(k),
            "cocok_asli": cocok_asli,
            "status": status,
            "status_asli": status_asli,
            "direvisi": bool(k),
            "sumber_dipakai": sumber,
            "nilai_dipakai_kg": nilai,
            "pilihan_sumber": _opsi_sumber("harian", d, q, "kg"),
            "koreksi": _keputusan_dict(k),
        })
    return hasil


def keputusan_intake_diketahui(session: Session) -> dict[tuple[int, int],
                                                         tuple[float, str]]:
    """Sumber intake Jul/Agu 2026 yang sudah diputuskan di Rekonsiliasi.

    Dipakai kartu `RM Stock – Intake vs Pricing`: bulan tanpa keputusan
    mengikuti logika lama (tiket bila wajar, lalu referensi, lalu pembelian).
    """
    dasar = _peta_diketahui()
    hasil: dict[tuple[int, int], tuple[float, str]] = {}
    for k in _peta_keputusan(session, "diketahui").values():
        if k.kunci not in dasar:
            continue
        th, bl = (int(x) for x in k.kunci.split("-"))
        baris = dasar[k.kunci]
        if k.sumber_benar == "excel":
            hasil[(th, bl)] = (baris["excel_ton"],
                               "excel lama (keputusan rekonsiliasi)")
        elif k.sumber_benar == "tiket":
            hasil[(th, bl)] = (baris["tiket_ton"],
                               "tiket (keputusan rekonsiliasi)")
    return hasil
