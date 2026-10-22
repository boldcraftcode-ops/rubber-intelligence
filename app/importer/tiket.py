"""Impor tiket intake.

Mendukung dua format:
1. Ekspor "Master Data" aplikasi internal: judul baris 1-4, header baris 7
   (sel digabung 7-8), data mulai baris 9, kolom A-S (kolom T diabaikan).
   Satu file bisa berisi beberapa sheet (Master Data 2024/2025/2026).
2. Template (sheet Intake_Tiket): header di baris 1, data mulai baris 2.

Aturan pembersihan (bagian 5 spesifikasi):
- Baris subtotal (tanpa Ticket No tetapi punya Dry) dibuang.
- Kunci = (ticket_no, line_seq); line_seq = urutan baris dalam tiket di file.
- Kode vendor di-UPPER + TRIM; ejaan nama yang beda dari master dicatat
  sebagai peringatan, tidak diubah diam-diam.
- Validasi: |Dry - Wet x DRC/100| <= 1,5 kg; DRC 20-95; Dry <= Wet.
- Wet = 0 -> disimpan dengan penanda "tiket nol".
- Wilayah kosong / berbeda dari Asal Getah -> peringatan.
- Item Code tak dikenal di master grade -> peringatan.
- Ekspor terpotong: tonase hari terakhir < 50% median 7 hari sebelumnya -> peringatan.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Grade, PeringatanData, TiketBaris, Vendor
from .util import baris_kosong, ke_desimal, ke_float, ke_tanggal, ke_teks, kunci_header

KOLOM = [
    "ticket date", "ticket no", "supplier code", "supplier name", "vehicle no",
    "item code", "drc date", "wet", "sample", "reject", "drc", "dry",
    "asal getah", "provinsi", "kabupaten/kota", "kecamatan", "desa", "bin", "location",
]


def cari_header(ws) -> tuple[int, dict[str, int]] | None:
    """Cari baris header (baris 1 untuk template, baris 7 untuk Master Data).
    Mengembalikan (nomor_baris_header, peta kolom->indeks)."""
    for baris in ws.iter_rows(min_row=1, max_row=10):
        nilai = [kunci_header(c.value) for c in baris]
        if "ticket date" in nilai and "ticket no" in nilai:
            peta = {}
            for idx, v in enumerate(nilai):
                if v in KOLOM:
                    peta[v] = idx
            return baris[0].row, peta
    return None


def impor_sheet_tiket(ws, session: Session, unggahan_id: int | None,
                      peringatan: list[str]) -> int:
    """Impor satu sheet tiket. Mengembalikan jumlah baris yang disimpan."""
    hasil = cari_header(ws)
    if hasil is None:
        return 0
    baris_header, peta = hasil

    vendor_map = {v.kode: v for v in session.scalars(select(Vendor))}
    grade_set = {g.item_code for g in session.scalars(select(Grade))}

    def catat(baris_ke: int | None, kode: str, pesan: str):
        lokasi = f"[{ws.title}" + (f" baris {baris_ke}" if baris_ke else "") + "]"
        peringatan.append(f"{lokasi} {pesan}")
        session.add(PeringatanData(unggahan_id=unggahan_id, sheet=ws.title,
                                   baris_ke=baris_ke, kode=kode, pesan=pesan))

    urutan_tiket: dict[str, int] = defaultdict(int)
    tonase_per_tanggal: dict[dt.date, Decimal] = defaultdict(Decimal)
    jumlah = 0

    for baris in ws.iter_rows(min_row=baris_header + 1, values_only=False):
        nilai = [c.value for c in baris]
        if baris_kosong(nilai):
            continue
        nomor = baris[0].row

        def ambil(nama):
            idx = peta.get(nama)
            return nilai[idx] if idx is not None and idx < len(nilai) else None

        ticket_no = ke_teks(ambil("ticket no"))
        dry = ke_desimal(ambil("dry"))

        # Baris subtotal yang tersisip: tanpa Ticket No tetapi punya Dry -> buang.
        if ticket_no is None:
            if dry is not None:
                catat(nomor, "SUBTOTAL", "Baris subtotal (tanpa Ticket No) dibuang. "
                      "Tidak perlu diperbaiki, hanya informasi.")
            continue

        tanggal = ke_tanggal(ambil("ticket date"))
        if tanggal is None:
            catat(nomor, "TANGGAL_KOSONG",
                  f"Tiket {ticket_no}: kolom Ticket Date kosong/tidak terbaca. "
                  "Perbaiki tanggal di file lalu unggah ulang.")
            continue

        kode_vendor = (ke_teks(ambil("supplier code")) or "").upper().strip()
        nama_vendor = ke_teks(ambil("supplier name"))
        wet = ke_desimal(ambil("wet"))
        drc = ke_float(ambil("drc"))
        item_code = ke_teks(ambil("item code"))
        provinsi = ke_teks(ambil("provinsi"))
        kabupaten = ke_teks(ambil("kabupaten/kota"))
        kecamatan = ke_teks(ambil("kecamatan"))
        desa = ke_teks(ambil("desa"))
        asal_getah = ke_teks(ambil("asal getah"))

        tanda: list[str] = []

        # Vendor
        v = vendor_map.get(kode_vendor)
        if v is None:
            catat(nomor, "VENDOR_TAK_DIKENAL",
                  f"Tiket {ticket_no}: kode vendor {kode_vendor} tidak ada di Master_Vendor. "
                  "Tambahkan vendor itu ke master, atau cek salah ketik kodenya.")
            tanda.append("vendor tak dikenal")
        elif nama_vendor and v.nama_baku.strip().upper() != nama_vendor.strip().upper():
            varian = [x.strip().upper() for x in (v.varian_nama or "").split("|") if x.strip()]
            if nama_vendor.strip().upper() in varian:
                tanda.append("nama varian")
            else:
                catat(nomor, "NAMA_VENDOR_BEDA",
                      f"Tiket {ticket_no}: nama '{nama_vendor}' beda dari nama baku "
                      f"'{v.nama_baku}' untuk {kode_vendor}. Tidak diubah otomatis - "
                      "mohon dicek apakah salah pilih vendor.")
                tanda.append("nama vendor beda")

        # Grade
        if item_code and grade_set and item_code not in grade_set:
            catat(nomor, "GRADE_TAK_DIKENAL",
                  f"Tiket {ticket_no}: Item Code '{item_code}' tidak ada di Master_Grade. "
                  "Tambahkan ke master bila memang grade baru.")
            tanda.append("grade tak dikenal")

        # Tiket nol (Wet = 0)
        tiket_nol = wet is not None and wet == 0
        if tiket_nol:
            tanda.append("tiket nol")

        # Validasi Dry
        if not tiket_nol and wet is not None and drc is not None and dry is not None:
            selisih = abs(float(dry) - float(wet) * drc / 100.0)
            if selisih > 1.5:
                catat(nomor, "DRY_TAK_COCOK",
                      f"Tiket {ticket_no}: Dry {dry} kg beda {selisih:.1f} kg dari "
                      f"Wet x DRC/100. Batas wajar 1,5 kg - cek kolom Wet/DRC/Dry.")
                tanda.append("dry tak cocok")
        if not tiket_nol and drc is not None and not (20 <= drc <= 95):
            catat(nomor, "DRC_DI_LUAR_BATAS",
                  f"Tiket {ticket_no}: DRC {drc}% di luar batas wajar 20-95%.")
            tanda.append("drc di luar batas")
        if wet is not None and dry is not None and dry > wet:
            catat(nomor, "DRY_LEBIH_DARI_WET",
                  f"Tiket {ticket_no}: Dry {dry} kg lebih besar dari Wet {wet} kg.")
            tanda.append("dry > wet")

        # Wilayah
        if not provinsi or not kabupaten:
            catat(nomor, "WILAYAH_KOSONG",
                  f"Tiket {ticket_no}: kolom Provinsi/Kabupaten kosong. "
                  "Lengkapi wilayah di sumber data.")
            tanda.append("wilayah kosong")
        elif asal_getah:
            pecahan = [x for x in (provinsi, kabupaten, kecamatan, desa) if x]
            asal_u = asal_getah.upper()
            if any(p.upper() not in asal_u for p in pecahan):
                catat(nomor, "WILAYAH_BEDA",
                      f"Tiket {ticket_no}: kolom wilayah berbeda dari teks Asal Getah. "
                      "Perlu ditinjau, tidak diubah otomatis.")
                tanda.append("wilayah beda dari asal getah")

        urutan_tiket[ticket_no] += 1
        line_seq = urutan_tiket[ticket_no]

        ada = session.scalar(select(TiketBaris).where(
            TiketBaris.ticket_no == ticket_no, TiketBaris.line_seq == line_seq))
        if ada is None:
            ada = TiketBaris(ticket_no=ticket_no, line_seq=line_seq, ticket_date=tanggal,
                             kode_vendor=kode_vendor)
            session.add(ada)
        ada.ticket_date = tanggal
        ada.kode_vendor = kode_vendor
        ada.nama_vendor_asli = nama_vendor
        ada.vehicle_no = ke_teks(ambil("vehicle no"))
        ada.item_code = item_code
        ada.drc_date = ke_tanggal(ambil("drc date"))
        ada.wet_kg = wet
        ada.sample_kg = ke_desimal(ambil("sample"))
        ada.reject_kg = ke_desimal(ambil("reject"))
        ada.drc_pct = drc
        ada.dry_kg = dry
        ada.asal_getah = asal_getah
        ada.provinsi = provinsi
        ada.kabupaten = kabupaten
        ada.kecamatan = kecamatan
        ada.desa = desa
        ada.bin = ke_teks(ambil("bin"))
        ada.location = ke_teks(ambil("location"))
        ada.tiket_nol = tiket_nol
        ada.peringatan = "; ".join(tanda) or None
        ada.unggahan_id = unggahan_id
        jumlah += 1

        if dry is not None and not tiket_nol:
            tonase_per_tanggal[tanggal] += dry

    # Deteksi ekspor terpotong di hari terakhir
    if len(tonase_per_tanggal) >= 2:
        tanggal_urut = sorted(tonase_per_tanggal)
        terakhir = tanggal_urut[-1]
        sebelum = [float(tonase_per_tanggal[t]) for t in tanggal_urut[-8:-1]]
        if sebelum:
            urut = sorted(sebelum)
            n = len(urut)
            median = urut[n // 2] if n % 2 else (urut[n // 2 - 1] + urut[n // 2]) / 2
            if median > 0 and float(tonase_per_tanggal[terakhir]) < 0.5 * median:
                catat(None, "EKSPOR_TERPOTONG",
                      f"Tonase hari terakhir ({terakhir.strftime('%d/%m/%Y')}) kurang dari "
                      "50% median 7 hari sebelumnya. Kemungkinan ekspor terpotong di "
                      "tengah hari - unggah ulang ekspor lengkap bila ada.")

    return jumlah
