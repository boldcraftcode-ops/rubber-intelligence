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
from typing import Iterable, Literal

import openpyxl
import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from openpyxl.cell import WriteOnlyCell
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.styles.colors import Color
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth_lokal import info_pengguna, wajib_admin
from .core import rumus
from .core.alarm import catat_audit, evaluasi_alarm
from .core.ringkasan_vendor import (
    MAKS_BULAN, MAKS_HARI, hitung_ringkasan_vendor,
    label_bulan_pendek, ringkas_untuk_layar,
)
from .core.traceability import (normalisasi_kabupaten,
                                normalisasi_teks_wilayah)
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
    PILIHAN_SUMBER,
    SELISIH_DIKETAHUI,
    keputusan_intake_diketahui,
    rekonsiliasi_harian,
    sah_kunci,
    selisih_diketahui,
)
from .models import (
    Grade,
    KoreksiRekonsiliasi,
    Kurs,
    MartBulanan,
    MartHarian,
    ParameterPabrik,
    Pembelian,
    RawUnggahan,
    ReferensiWilayahTrace,
    KoreksiWilayahTrace,
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

#: Satu sheet Excel maksimal 1.048.576 baris. Dipakai hanya sebagai pengaman
#: untuk rentang ekstrem; sheet ringkasan tetap memuat seluruh rentang.
MAKS_BARIS_XLSX = 1_000_000
#: Di atas jumlah baris ini workbook ditulis mengalir (write_only).
AMBANG_XLSX_STREAM = 200_000
#: Pengaman ekspor Excel Penerimaan Karet: 1.200 bulan = 100 tahun.
#: Excel sendiri maksimal 16.384 kolom, tapi rincian bulanan juga menyimpan
#: satu sel per dimensi per bulan; batas ini mencegah workbook raksasa.
MAKS_BULAN_XLSX = 1_200

# ---------------------------------------------------------------------------
# Format baku ekspor kartu Konsistensi intake harian vendor, mengikuti
# `Intake-2025_Ringkasan-Vendor.xlsx`. Berkas contoh HANYA referensi; style
# ditanam di kode agar ekspor tetap jalan tanpa file tersebut.
# ---------------------------------------------------------------------------
FONT_RINGKASAN_VENDOR = "Courier New"
WARNA_HEADER_RINGKASAN_VENDOR = "FF1F4E78"
WARNA_ABU_RINGKASAN_VENDOR = "FF595959"
WARNA_ABU_MUDA_RINGKASAN_VENDOR = "FF7F7F7F"
WARNA_LUAR_DATA_RINGKASAN_VENDOR = "FFF2F2F2"
FORMAT_TRIP_RINGKASAN_VENDOR = "#,##0"
FORMAT_PORSEN_RINGKASAN_VENDOR = "0.0%"
FORMAT_RATA_RINGKASAN_VENDOR = "0.0"
FORMAT_TANGGAL_RINGKASAN_VENDOR = "yyyy-mm-dd"
FORMAT_AWAL_BULAN_RINGKASAN_VENDOR = "dd\\-mmm"
LEBAR_RINGKASAN_VENDOR = (9.0, 40.0, 12.0, 9.0, 11.0, 18.0, 14.0, 15.0, 8.71)

# ---------------------------------------------------------------------------
# Format baku ekspor kartu Penerimaan Karet, mengikuti contoh
# `Format_penerimaan_per_desa.xlsx`. File contoh HANYA referensi; style
# ditanam di kode agar ekspor tetap jalan tanpa file tersebut.
# ---------------------------------------------------------------------------
FONT_PENERIMAAN = "Courier New"
WARNA_JUDUL_PENERIMAAN = "FF1D2434"
TINT_HEADER_PENERIMAAN = 0.39997558519241921  # theme dk2 (1F497D) → 558ED5
FORMAT_KG_PENERIMAAN = (
    '_(* #,##0_);_(* \\(#,##0\\);_(* "-"??_);_(@_)')
FORMAT_PORSEN_PENERIMAAN = "0%"
LEBAR_PENERIMAAN = (26.5703125, 19.5703125, 14.28515625, 19.5703125,
                    9.28515625, 19.28515625, 9.140625)
NAMA_BULAN_INGGRIS = ("", "January", "February", "March", "April", "May",
                      "June", "July", "August", "September", "October",
                      "November", "December")


class RekonsiliasiKeputusanMasuk(BaseModel):
    """Pilihan sumber benar untuk satu baris selisih Rekonsiliasi."""
    jenis: Literal["harian", "diketahui"]
    kunci: str = Field(min_length=7, max_length=10)
    sumber_benar: Literal["tiket", "pembelian", "excel"]
    alasan: str | None = Field(default=None, max_length=300)


def _boleh_revisi(request: Request) -> bool:
    """Admin (atau mode development tanpa login) boleh menyimpan keputusan."""
    try:
        wajib_admin(request)
        return True
    except HTTPException:
        return False


def _baris_rekonsiliasi(jenis: str, kunci: str, session: Session) -> dict | None:
    if jenis == "harian":
        return next((h for h in rekonsiliasi_harian(session)
                     if h["kunci"] == kunci), None)
    return next((d for d in selisih_diketahui(session)
                 if d["kunci"] == kunci), None)


def _validasi_keputusan(data: RekonsiliasiKeputusanMasuk,
                        session: Session) -> dict:
    kunci = data.kunci.strip()
    if not sah_kunci(data.jenis, kunci):
        raise HTTPException(422, "Kunci baris Rekonsiliasi tidak dikenal. "
                                "Gunakan YYYY-MM-DD untuk harian atau "
                                "YYYY-MM untuk selisih yang sudah diketahui.")
    if data.sumber_benar not in PILIHAN_SUMBER[data.jenis]:
        sah = ", ".join(PILIHAN_SUMBER[data.jenis])
        raise HTTPException(422, f"Sumber '{data.sumber_benar}' tidak sah "
                                f"untuk {data.jenis}. Pilih salah satu: {sah}.")
    baris = _baris_rekonsiliasi(data.jenis, kunci, session)
    if baris is None:
        raise HTTPException(422, f"Baris {data.jenis} '{kunci}' tidak ditemukan "
                                "pada data Rekonsiliasi.")
    if data.jenis == "harian" and baris["cocok_asli"] and not baris["direvisi"]:
        raise HTTPException(422, "Baris harian ini sudah cocok; tidak perlu "
                                "keputusan revisi.")
    return {**baris, "kunci": kunci}

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


def respon_xlsx_penerimaan(nama_file: str, judul: str, periode: str,
                           header: list[str], baris: list[list],
                           tipe_kolom: list[str],
                           kolom_tengah: int | None = None,
                           mode_bulan: bool = False) -> StreamingResponse:
    """Ekspor kartu Penerimaan Karet mengikuti `Format_penerimaan_per_desa.xlsx`.

    Susunan: baris 1 kosong, A2 judul, A3 periode, baris 4 kosong, header di
    baris 5, data mulai baris 6. Font Courier New 11 (judul 14), header putih
    di atas fill theme dk2+tint 40%, border tipis di header & data, format kg
    accounting, `Porsi` 0%, `Jumlah tiket` rata tengah. Tanpa freeze/merge.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"

    font_judul = Font(name=FONT_PENERIMAAN, sz=14,
                      color=WARNA_JUDUL_PENERIMAAN)
    font_isi = Font(name=FONT_PENERIMAAN, sz=11, color=Color(theme=1))
    font_header = Font(name=FONT_PENERIMAAN, sz=11, color=Color(theme=0))
    fill_header = PatternFill(
        fill_type="solid",
        fgColor=Color(theme=3, tint=TINT_HEADER_PENERIMAAN))
    sisi = Side(style="thin", color=Color(auto=True))
    border = Border(left=sisi, right=sisi, top=sisi, bottom=sisi)

    c = ws.cell(row=2, column=1, value=judul)
    c.font = font_judul
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[2].height = 18.75
    c = ws.cell(row=3, column=1, value=f"Periode :  [{periode}]")
    c.font = font_isi

    for i, teks in enumerate(header, start=1):
        c = ws.cell(row=5, column=i, value=teks)
        c.font = font_header
        c.fill = fill_header
        c.border = border
        tipe = tipe_kolom[i - 1] if i - 1 < len(tipe_kolom) else "teks"
        if tipe == "kg":
            c.number_format = FORMAT_KG_PENERIMAAN
        elif tipe == "persen":
            c.number_format = FORMAT_PORSEN_PENERIMAAN
        if kolom_tengah is not None and i - 1 == kolom_tengah:
            c.alignment = Alignment(horizontal="center")

    for indeks_baris, nilai_baris in enumerate(baris, start=6):
        for i, nilai in enumerate(nilai_baris, start=1):
            c = ws.cell(row=indeks_baris, column=i, value=nilai)
            c.font = font_isi
            c.border = border
            tipe = tipe_kolom[i - 1] if i - 1 < len(tipe_kolom) else "teks"
            if tipe == "kg":
                c.number_format = FORMAT_KG_PENERIMAAN
            elif tipe == "persen":
                c.number_format = FORMAT_PORSEN_PENERIMAAN
            if kolom_tengah is not None and i - 1 == kolom_tengah:
                c.alignment = Alignment(horizontal="center")

    if mode_bulan:
        # Kolom A, N kolom bulan, Total kg, Porsi.
        lebar = ([LEBAR_PENERIMAAN[0]]
                 + [LEBAR_PENERIMAAN[2]] * (len(header) - 3)
                 + [LEBAR_PENERIMAAN[3], LEBAR_PENERIMAAN[4]])
    else:
        lebar = list(LEBAR_PENERIMAAN[:len(header)])
        # Sampel juga menyimpan lebar kolom G meski tidak berisi data.
        ws.column_dimensions["G"].width = LEBAR_PENERIMAAN[6]
    for i, nilai in enumerate(lebar, start=1):
        ws.column_dimensions[get_column_letter(i)].width = nilai

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nama_file}"'})


def respon_xlsx_banyak(nama_file: str,
                       sheets: list[tuple[str, list[str], Iterable[list]]],
                       tulis_langsung: bool = False) -> StreamingResponse:
    """Ekspor beberapa sheet: dipakai kartu konsistensi intake vendor.

    Mode biasa menyimpan dimensi sheet sehingga pembaca `read_only` langsung
    tahu jumlah baris. Untuk rincian per tanggal yang sangat panjang,
    `tulis_langsung=True` memakai workbook `write_only` agar baris ditulis
    mengalir dan tidak ditampung semua di memori. Header tetap tebal + biru
    muda, baris pertama dibekukan, lebar kolom mengikuti 200 baris pertama.
    """
    tebal = Font(bold=True)
    biru = PatternFill("solid", fgColor="D7E7FF")
    wb = openpyxl.Workbook(write_only=tulis_langsung)
    if not tulis_langsung:
        wb.remove(wb.active)
    for nama, judul, baris in sheets:
        ws = wb.create_sheet(nama[:31])
        if tulis_langsung:
            # Pada write-only, freeze harus dipasang SEBELUM baris ditulis.
            ws.freeze_panes = "A2"
            sel_judul = []
            for teks in judul:
                sel = WriteOnlyCell(ws, value=teks)
                sel.font, sel.fill = tebal, biru
                sel_judul.append(sel)
            ws.append(sel_judul)
            terpanjang = [len(str(x or "")) for x in judul]
            for indeks, b in enumerate(baris):
                if indeks < 200:
                    for i, nilai in enumerate(b[:len(judul)]):
                        terpanjang[i] = max(terpanjang[i],
                                            len(str(nilai or "")))
                ws.append(b)
            for i, lebar in enumerate(terpanjang, start=1):
                ws.column_dimensions[get_column_letter(i)].width = \
                    min(48, lebar + 2)
        else:
            baris = list(baris)
            ws.append(judul)
            for sel in ws[1]:
                sel.font, sel.fill = tebal, biru
            for b in baris:
                ws.append(b)
            ws.freeze_panes = "A2"
            for i, _ in enumerate(judul, start=1):
                lebar = len(str(judul[i - 1] or ""))
                for b in baris[:200]:
                    if i - 1 < len(b):
                        lebar = max(lebar, len(str(b[i - 1] or "")))
                ws.column_dimensions[get_column_letter(i)].width = \
                    min(48, lebar + 2)
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


def _norm_wilayah(nilai: str | None) -> str:
    """Kunci baku nama wilayah: spasi dirapatkan, HURUF BESAR.

    Masalah nyata di data: "Sumatera Utara" dan "SUMATERA UTARA" masuk sebagai
    dua baris terpisah, begitu juga "Riau" vs "RIAU" — padahal provinsinya
    sama. Penyebabnya perbedaan huruf besar/kecil saat pengetikan/ekspor.
    Kunci dikumpulkan dengan normalisasi ini supaya satu provinsi = satu baris.
    """
    return " ".join((nilai or "").split()).upper() or "(kosong)"


def _pilih_ejaan(varian: dict[str, int]) -> str:
    """Pilih ejaan yang ditampilkan dari beberapa variasi penulisan.

    Yang paling sering muncul menang; bila jumlahnya sama, ejaan yang TIDAK
    seluruhnya huruf besar dipilih karena lebih enak dibaca ("Sumatera Utara"
    lebih baik daripada "SUMATERA UTARA").
    """
    if not varian:
        return "(kosong)"
    return sorted(varian.items(),
                  key=lambda kv: (-kv[1], kv[0].isupper(), kv[0]))[0][0]


def _kumpulkan_wilayah(peta: dict[str, dict[str, int]], kunci: str,
                       mentah: str | None) -> None:
    """Catat ejaan mentah untuk sebuah kunci wilayah (untuk label & laporan)."""
    peta.setdefault(kunci, {})
    ejaan = " ".join((mentah or "").split()) or "(kosong)"
    peta[kunci][ejaan] = peta[kunci].get(ejaan, 0) + 1


def _laporan_wilayah(peta: dict[str, dict[str, int]]) -> dict:
    """Ringkasan penggabungan ejaan — ditampilkan supaya kelihatan apa yang
    disatukan, bukan diam-diam diubah."""
    gabungan = [{
        "kunci": kunci,
        "label": _pilih_ejaan(varian),
        "varian": [{"ejaan": e, "jumlah": n}
                   for e, n in sorted(varian.items(), key=lambda kv: -kv[1])],
        "jumlah_ejaan": len(varian),
    } for kunci, varian in sorted(peta.items()) if len(varian) > 1]
    return {
        "dinormalisasi": True,
        "aturan": "spasi dirapatkan + HURUF BESAR (UPPER/TRIM); label memakai "
                  "ejaan yang paling sering muncul",
        "jumlah_kunci": len(peta),
        "digabung": gabungan,
        "catatan": ("Provinsi yang sama sempat muncul sebagai beberapa baris "
                    "karena beda huruf besar/kecil. Sekarang digabung."
                    if gabungan else
                    "Tidak ada ejaan wilayah yang dobel pada periode ini."),
    }


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
    # Perbandingan wilayah TIDAK peka huruf besar/kecil dan mengabaikan spasi
    # (termasuk spasi ganda di tengah: "sumatera   utara"), sejalan dengan
    # penggabungan ejaan di kartu (lihat _norm_wilayah).
    def samakan(kolom, nilai: str):
        return func.replace(func.upper(func.trim(kolom)), " ", "") == \
            _norm_wilayah(nilai).replace(" ", "")

    if provinsi:
        q = q.where(samakan(TiketBaris.provinsi, provinsi))
    if kabupaten:
        q = q.where(samakan(TiketBaris.kabupaten, kabupaten))
    if kecamatan:
        q = q.where(samakan(TiketBaris.kecamatan, kecamatan))
    if desa:
        q = q.where(samakan(TiketBaris.desa, desa))
    return q


def _bulan_berurutan(awal: tuple[int, int], akhir: tuple[int, int],
                     maks: int = 120) -> list[tuple[int, int]]:
    """Daftar (tahun, bulan) dari awal sampai akhir, termasuk bulan kosong.

    Bulan tanpa tiket tetap ditampilkan (nilai 0) supaya grafik tidak
    "melompat" dan pembaca melihat bulan yang memang tidak ada penerimaan.
    `maks` dipakai sebagai pengaman; ekspor Excel menaikkannya agar seluruh
    periode terpilih tetap menjadi kolom.
    """
    hasil: list[tuple[int, int]] = []
    th, bl = awal
    while (th, bl) <= akhir and len(hasil) < maks:
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


def _fmt_periode_penerimaan(awal: tuple[int, int] | None,
                            akhir: tuple[int, int] | None) -> str:
    """`((2026,1),(2026,12))` → `"January ~ December 2026"`."""
    if not awal or not akhir:
        return "Tidak ada data"
    if awal > akhir:
        awal, akhir = akhir, awal
    th1, bl1 = awal
    th2, bl2 = akhir
    if awal == akhir:
        return f"{NAMA_BULAN_INGGRIS[bl1]} {th1}"
    if th1 == th2:
        return (f"{NAMA_BULAN_INGGRIS[bl1]} ~ "
                f"{NAMA_BULAN_INGGRIS[bl2]} {th2}")
    return (f"{NAMA_BULAN_INGGRIS[bl1]} {th1} ~ "
            f"{NAMA_BULAN_INGGRIS[bl2]} {th2}")


def _bulan_xlsx_penuh(dari: dt.date | None, sampai: dt.date | None,
                      berdata: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sumbu bulan untuk EKSPOR EXCEL: seluruh periode terpilih, tanpa potong.

    Beda dengan sumbu grafik/JSON: di sini bulan kosong tetap menjadi kolom
    dan sisa dimensi tidak digabung. Bila hanya satu batas tanggal diisi,
    batas lainnya memakai ujung bulan berdata. `MAKS_BULAN_XLSX` mencegah
    rentang ekstrem membuat workbook berjuta-juta sel.
    """
    awal: tuple[int, int] | None = None
    akhir: tuple[int, int] | None = None
    if dari and sampai and (dari.year, dari.month) <= (sampai.year, sampai.month):
        awal, akhir = (dari.year, dari.month), (sampai.year, sampai.month)
    elif dari and berdata:
        awal, akhir = (dari.year, dari.month), berdata[-1]
    elif sampai and berdata:
        awal, akhir = berdata[0], (sampai.year, sampai.month)
    elif berdata:
        awal, akhir = berdata[0], berdata[-1]
    if not awal or not akhir or awal > akhir:
        return []
    bulan = _bulan_berurutan(awal, akhir, maks=MAKS_BULAN_XLSX + 1)
    if len(bulan) > MAKS_BULAN_XLSX:
        jumlah_label = f"{len(bulan):,}".replace(",", ".")
        maks_label = f"{MAKS_BULAN_XLSX:,}".replace(",", ".")
        raise HTTPException(
            422,
            f"Periode {jumlah_label} bulan terlalu panjang untuk ekspor Excel; "
            f"maksimal {maks_label} bulan (100 tahun). Persempit "
            f"'Dari/Sampai' agar setiap bulan tetap menjadi kolom.")
    return bulan


def _info_ekspor_penerimaan(dari: dt.date | None, sampai: dt.date | None,
                            vendor: str | None, provinsi: str | None,
                            kabupaten: str | None, kecamatan: str | None,
                            desa: str | None, potongan: list[tuple],
                            session: Session) -> tuple[str, str]:
    """Judul & periode untuk Excel Penerimaan Karet, mengikuti file contoh."""
    peta_vendor = {
        " ".join((v.kode or "").split()).upper(): v.nama_baku
        for v in session.scalars(select(Vendor))}
    bagian: list[str] = []
    if vendor:
        kode = " ".join(vendor.split()).upper()
        nama = peta_vendor.get(kode)
        bagian.append(f"{kode} {nama}" if nama else kode)
    for label, nilai in (("Provinsi", provinsi), ("Kabupaten", kabupaten),
                         ("Kecamatan", kecamatan), ("Desa", desa)):
        if nilai:
            bagian.append(f"{label}: {' '.join(nilai.split()).upper()}")
    isi_filter = " | ".join(bagian) if bagian else "Semua vendor"
    judul = f"Penerimaan Karet dari - [{isi_filter}] "

    berdata = sorted({b for _k, b, _kg, _e, _t in potongan if b})
    awal = (dari.year, dari.month) if dari else None
    akhir = (sampai.year, sampai.month) if sampai else None
    if awal and akhir:
        pass
    elif awal:
        akhir = berdata[-1] if berdata else awal
    elif akhir:
        awal = berdata[0] if berdata else akhir
    elif berdata:
        awal, akhir = berdata[0], berdata[-1]
    return judul, _fmt_periode_penerimaan(awal, akhir)


def _penerimaan_per_bulan(potongan: list[tuple], dimensi: str,
                          dari: dt.date | None, sampai: dt.date | None,
                          top: int, format: str | None,
                          session: Session,
                          label_peta: dict[str, str] | None = None,
                          info_ekspor: tuple[str, str] | None = None) -> dict:
    """Bentuk jawaban `per=bulan`: bulan x dimensi.

    Dipakai saat filter periode mencakup lebih dari satu bulan, supaya
    pembaca melihat pergerakan tiap vendor/wilayah dari bulan ke bulan —
    bukan hanya total sepanjang periode.

    Semua angka kg kering. Untuk JSON/grafik, `top` dimensi terbesar
    dipertahankan; sisanya digabung menjadi satu baris "Lainnya" agar grafik
    tetap terbaca. Khusus `format=xlsx`, ekspor TIDAK memakai `top`: semua
    dimensi ditulis sebagai baris detail tersendiri dan semua bulan terpilih
    menjadi kolom, tanpa baris "Lainnya".
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
    label_bulan = [_label_bulan_singkat(th, bl) for th, bl in bulan]

    def agregasi(daftar_bulan: list[tuple[int, int]]) -> dict[str, dict]:
        """Agregasi per (dimensi, bulan), dipisah biasa/EUDR.

        Dipakai dua kali: sumbu ringkas untuk grafik/JSON, dan sumbu penuh
        untuk ekspor Excel. Keduanya memakai potongan tiket yang sama.
        """
        indeks = {b: i for i, b in enumerate(daftar_bulan)}
        isi: dict[str, dict] = defaultdict(
            lambda: {"biasa": [0.0] * len(daftar_bulan),
                     "eudr": [0.0] * len(daftar_bulan), "tiket": set()})
        for kunci, bln, kg, e, no_tiket in potongan:
            i = indeks.get(bln)
            if i is None:
                continue
            isi[kunci]["eudr" if e else "biasa"][i] += kg
            isi[kunci]["tiket"].add(no_tiket)
        return isi

    def total(baris: dict) -> float:
        return sum(baris["biasa"]) + sum(baris["eudr"])

    isi = agregasi(bulan)
    total_kg = sum(total(a) for a in isi.values())
    urut = sorted(isi.items(), key=lambda kv: -total(kv[1]))

    nama_vendor = {v.kode: v.nama_baku for v in session.scalars(select(Vendor))} \
        if dimensi == "vendor" else {}

    def label_dari(kunci: str) -> str:
        if kunci in nama_vendor:
            return f"{kunci} — {nama_vendor[kunci]}"
        if label_peta and kunci in label_peta:
            return label_peta[kunci]      # ejaan wilayah terpilih (bukan mentah)
        return kunci

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
        # EKSPOR: seluruh bulan terpilih + SELURUH baris detail. Tidak memakai
        # `top` dan tidak ada baris "Lainnya (N dimensi)" seperti di grafik.
        bulan_xlsx = _bulan_xlsx_penuh(dari, sampai, berdata)
        label_bulan_xlsx = [_label_bulan_singkat(th, bl)
                            for th, bl in bulan_xlsx]
        agregat_xlsx = agregasi(bulan_xlsx)
        total_kg_xlsx = sum(total(a) for a in agregat_xlsx.values())
        urut_xlsx = sorted(agregat_xlsx.items(),
                           key=lambda kv: -total(kv[1]))
        baris_xlsx = [{
            "label": label_dari(kunci),
            "kg_per_bulan": kg_bulan(a),
            "kg_total": round(total(a), 1),
            "porsi": round(total(a) / total_kg_xlsx, 4)
                     if total_kg_xlsx else None,
        } for kunci, a in urut_xlsx]
        total_per_bulan_xlsx = [
            round(sum(b["kg_per_bulan"][i] for b in baris_xlsx), 1)
            for i in range(len(bulan_xlsx))]

        judul = ([dimensi.capitalize()] + label_bulan_xlsx
                 + ["Total kg", "Porsi"])
        isi_xlsx = [[b["label"]] + b["kg_per_bulan"]
                    + [b["kg_total"], b["porsi"]] for b in baris_xlsx]
        isi_xlsx.append(["TOTAL"] + total_per_bulan_xlsx
                        + [round(sum(total_per_bulan_xlsx), 1), None])
        if info_ekspor is None:
            awal = (dari.year, dari.month) if dari else (
                berdata[0] if berdata else None)
            akhir = (sampai.year, sampai.month) if sampai else (
                berdata[-1] if berdata else None)
            info_ekspor = ("Penerimaan Karet",
                           _fmt_periode_penerimaan(awal, akhir))
        return respon_xlsx_penerimaan(
            f"penerimaan_per_{dimensi}_per_bulan.xlsx",
            info_ekspor[0], info_ekspor[1], judul, isi_xlsx,
            ["teks"] + ["kg"] * (len(judul) - 2) + ["persen"],
            mode_bulan=True)
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
                      session: Session,
                      label_peta: dict[str, str] | None = None) -> dict:
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
            "label": (f"{kunci} — {nama_vendor[kunci]}" if kunci in nama_vendor
                      else (label_peta or {}).get(kunci, kunci)),
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


# ---------------------------------------------------------------------------
# Analisis tren & musiman (time series) untuk kartu Penerimaan karet
# ---------------------------------------------------------------------------
MIN_BULAN_MUSIMAN = 24        # di bawah ini dekomposisi belum bisa dipercaya
REKOMENDASI_BULAN_MUSIMAN = 36


def _rata(nilai: list[float]) -> float:
    return sum(nilai) / len(nilai) if nilai else 0.0


def _simpangan_baku(nilai: list[float]) -> float:
    """Simpangan baku populasi (tanpa koreksi sampel)."""
    if len(nilai) < 2:
        return 0.0
    r = _rata(nilai)
    return (_rata([(x - r) ** 2 for x in nilai])) ** 0.5


def _ma3(nilai: list[float]) -> list[float | None]:
    """Rata-rata bergerak 3 bulan (trailing). Dua bulan pertama kosong."""
    hasil: list[float | None] = []
    for i in range(len(nilai)):
        if i < 2:
            hasil.append(None)
        else:
            hasil.append(round(_rata(nilai[i - 2:i + 1]), 1))
    return hasil


def _pertumbuhan(nilai: list[float], geser: int) -> list[float | None]:
    """Pertumbuhan % dibanding `geser` bulan sebelumnya.

    MoM = geser 1, YoY = geser 12. Kosong bila data pembanding belum ada
    atau pembandingnya nol (pembagian nol tidak bermakna, bukan 0%).
    """
    hasil: list[float | None] = []
    for i in range(len(nilai)):
        j = i - geser
        if j < 0 or not nilai[j]:
            hasil.append(None)
        else:
            hasil.append(round((nilai[i] - nilai[j]) / nilai[j] * 100, 2))
    return hasil


def _dekomposisi_aditif(nilai: list[float], bulan: list[tuple[int, int]]) -> dict:  # noqa: C901
    """Dekomposisi aditif klasik (pendekatan STL) untuk data bulanan.

    Langkah:
      1. tren   = rata-rata bergerak 12 bulan terpusat (bobot ½ di ujung);
      2. musiman = rata-rata sisa (nilai - tren) untuk tiap bulan kalender,
                   dinormalkan agar total 12 bulan = 0;
      3. residu = nilai - tren - musiman.

    Bukan STL LOESS penuh (LOESS butuh pustaka tambahan), tetapi memisahkan
    tren/musiman/residu dengan cara yang sama dan cukup untuk membaca pola
    musim gugur daun Feb-Apr. Syarat data: minimal 24 bulan (idealnya 36)
    karena tren 12 bulan kehilangan 6 bulan di tiap ujung.
    """
    n = len(nilai)
    if n < MIN_BULAN_MUSIMAN:
        return {
            "tersedia": False,
            "min_bulan": MIN_BULAN_MUSIMAN,
            "rekomendasi_bulan": REKOMENDASI_BULAN_MUSIMAN,
            "jumlah_bulan": n,
            "kurang_bulan": MIN_BULAN_MUSIMAN - n,
            "metode": "dekomposisi aditif klasik (rata-rata bergerak 12 bulan)",
            "pesan": (f"Butuh minimal {MIN_BULAN_MUSIMAN} bulan data untuk "
                      f"memisahkan tren dan musiman; tersedia baru {n} bulan "
                      f"(kurang {MIN_BULAN_MUSIMAN - n} bulan). Angka tren/"
                      "musiman belum bisa dipercaya, jadi tidak ditampilkan."),
        }

    tren: list[float | None] = [None] * n
    for i in range(6, n - 6):
        jendela = nilai[i - 6:i + 7]            # 13 titik
        tren[i] = (0.5 * jendela[0] + sum(jendela[1:12]) + 0.5 * jendela[12]) / 12

    # rata-rata sisa per bulan kalender
    kumpulan: dict[int, list[float]] = defaultdict(list)
    for i in range(n):
        if tren[i] is not None:
            kumpulan[bulan[i][1]].append(nilai[i] - tren[i])
    indeks: dict[int, float] = {}
    for m in range(1, 13):
        nilai_m = kumpulan.get(m) or []
        indeks[m] = _rata(nilai_m)
    # normalkan: total 12 bulan = 0 (hanya bulan yang punya data)
    ada = [m for m in range(1, 13) if kumpulan.get(m)]
    if ada:
        geser = _rata([indeks[m] for m in ada])
        for m in ada:
            indeks[m] -= geser

    musiman = [indeks[b[1]] for b in bulan]
    residu: list[float | None] = [
        (nilai[i] - tren[i] - musiman[i]) if tren[i] is not None else None
        for i in range(n)]

    posisi = [i for i in range(n) if tren[i] is not None]
    sisa_tren = [nilai[i] - tren[i] for i in posisi]
    ragam_musiman = _rata([(musiman[i] - _rata(sisa_tren)) ** 2 for i in posisi]) if posisi else 0.0
    ragam_residu = _rata([(residu[i] or 0.0) ** 2 for i in posisi]) if posisi else 0.0
    total_ragam = ragam_musiman + ragam_residu
    kekuatan = round(ragam_musiman / total_ragam * 100, 1) if total_ragam else 0.0

    # Bulan bernilai nol ikut dihitung sebagai penerimaan nol. Kalau nol itu
    # sebenarnya "tiket belum diunggah", hasil dekomposisi akan bias — katakan
    # terus terang, jangan diam.
    jumlah_nol = sum(1 for x in nilai if x == 0)
    catatan = ("Kekuatan musiman < 15% berarti pola musiman lemah — "
               "jangan dipakai sebagai dasar tunggal perencanaan."
               if kekuatan < 15 else
               "Pola musiman cukup kuat; bulan dengan indeks negatif "
               "menunjukkan penerimaan di bawah tren.")
    if jumlah_nol:
        catatan += (f" Perhatian: ada {jumlah_nol} bulan bernilai nol di dalam "
                    "deret. Nol dihitung sebagai penerimaan nol; bila sebenarnya "
                    "tiket belum diunggah, angka musiman ini bias — lengkapi "
                    "datanya dulu.")

    return {
        "tersedia": True,
        "jumlah_bulan_nol": jumlah_nol,
        "metode": "dekomposisi aditif klasik (pendekatan STL): tren = rata-rata "
                  "bergerak 12 bulan terpusat, musiman = rata-rata sisa per bulan "
                  "kalender, residu = sisa",
        "min_bulan": MIN_BULAN_MUSIMAN,
        "rekomendasi_bulan": REKOMENDASI_BULAN_MUSIMAN,
        "jumlah_bulan": n,
        "tren": [round(x, 1) if x is not None else None for x in tren],
        "musiman": [round(x, 1) for x in musiman],
        "residu": [round(x, 1) if x is not None else None for x in residu],
        "indeks_musiman": [{
            "bulan": m,
            "label": NAMA_BULAN_SINGKAT[m],
            "kg": round(indeks[m], 1),
            "pct": (round(indeks[m] / _rata([x for x in nilai if x]) * 100, 2)
                    if _rata([x for x in nilai if x]) else None),
        } for m in range(1, 13)],
        "kekuatan_musiman_pct": kekuatan,
        "catatan": catatan,
    }


def _deteksi_pola_datar(nilai: list[float], bulan: list[tuple[int, int]],
                        min_bulan: int = 3, ambang_cv: float = 0.05) -> list[dict]:
    """Cari deret bulan berurutan yang nilainya nyaris sama.

    Penerimaan karet nyata tidak mungkin datar sampai <5% selama beberapa
    bulan — pola begini hampir selalu berarti data contoh/belum lengkap,
    bukan kenyataan. Deteksi ini mencegah angka seperti itu dipakai untuk
    forecasting tanpa dicek.
    """
    temuan: list[dict] = []
    mulai = None
    for i in range(len(nilai) + 1):
        berisi = i < len(nilai) and nilai[i] > 0
        if berisi and mulai is None:
            mulai = i
        elif not berisi and mulai is not None:
            rentang = nilai[mulai:i]
            if len(rentang) >= min_bulan:
                r = _rata(rentang)
                cv = (_simpangan_baku(rentang) / r) if r else 0.0
                if cv < ambang_cv:
                    temuan.append({
                        "mulai": f"{bulan[mulai][0]}-{bulan[mulai][1]:02d}",
                        "selesai": f"{bulan[i - 1][0]}-{bulan[i - 1][1]:02d}",
                        "jumlah_bulan": len(rentang),
                        "rata_kg": round(r, 1),
                        "cv_pct": round(cv * 100, 2),
                    })
            mulai = None
    return temuan


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


def _tanggal_iso(teks: str | None, nama: str) -> dt.date | None:
    """Parse 'YYYY-MM-DD' (filter tanggal persis kartu konsistensi vendor)."""
    if not teks:
        return None
    try:
        return dt.date.fromisoformat(teks)
    except Exception:
        raise HTTPException(422, f"Parameter '{nama}' harus format YYYY-MM-DD "
                                 f"(contoh: 2026-01-05), bukan '{teks}'.")


def _ke_tanggal_db(nilai) -> dt.date | None:
    """Normalisasi MIN/MAX tanggal SQL (bisa date, datetime, atau teks)."""
    if nilai is None:
        return None
    if isinstance(nilai, dt.datetime):
        return nilai.date()
    if isinstance(nilai, dt.date):
        return nilai
    try:
        return dt.date.fromisoformat(str(nilai)[:10])
    except Exception:
        return None


# Wilayah kartu "Daftar intake terakhir" mengikuti hierarki SCDF tanpa
# mengubah data tiket: ejaan resmi hanya dipakai bila kunci normalized cocok.
CATATAN_WILAYAH_INTAKE_TERAKHIR = (
    "Wilayah dipecah menjadi Provinsi, Kabupaten/Kota, Kecamatan, dan Desa. "
    "Ejaan resmi SCDF dipakai bila kombinasi kabupaten/kecamatan/desa cocok "
    "dengan traceability_wilayah atau koreksi terkontrol; bila tidak ada "
    "padanan, nilai pada tiket ditampilkan apa adanya tanpa menebak Provinsi."
)


def _nama_vendor_baku(session: Session) -> dict[str, str]:
    """Kode vendor UPPER/TRIM -> nama baku dari Master Vendor."""
    hasil: dict[str, str] = {}
    for v in session.scalars(select(Vendor)):
        kode = (v.kode or "").strip().upper()
        if kode:
            hasil[kode] = (v.nama_baku or "").strip() or kode
    return hasil


def _opsi_intake_terakhir(session: Session) -> dict:
    """Opsi filter vendor + batas tanggal untuk kartu intake terakhir.

    Dropdown memuat **semua** Master Vendor (termasuk yang belum punya tiket)
    ditambah kode yang ternyata hanya ada di `tiket_baris`. Daftar ini sengaja
    tidak mengikuti filter periode supaya pilihan vendor tidak berubah-ubah
    saat pengguna mengganti rentang tanggal.
    """
    nama_master = _nama_vendor_baku(session)
    nama_tiket: dict[str, str | None] = {}
    for kode, nama in session.execute(
            select(TiketBaris.kode_vendor,
                   func.min(TiketBaris.nama_vendor_asli)).where(
                TiketBaris.tiket_nol == False,  # noqa: E712
                TiketBaris.kode_vendor.is_not(None)).group_by(
                TiketBaris.kode_vendor)):
        k = (kode or "").strip().upper()
        if not k:
            continue
        n = (nama or "").strip() or None
        if k not in nama_tiket or (nama_tiket[k] is None and n):
            nama_tiket[k] = n

    pilihan = []
    for kode in sorted(set(nama_master) | set(nama_tiket)):
        if not kode:
            continue
        sumber = "master" if kode in nama_master else "tiket"
        nama = nama_master.get(kode) or nama_tiket.get(kode) or kode
        pilihan.append({
            "kode": kode,
            "label": f"{kode} — {nama}" if nama != kode else kode,
            "sumber": sumber,
        })

    batas = session.execute(
        select(func.min(TiketBaris.ticket_date),
               func.max(TiketBaris.ticket_date)).where(
            TiketBaris.tiket_nol == False,  # noqa: E712
            TiketBaris.ticket_date.is_not(None))).one()
    min_d, max_d = _ke_tanggal_db(batas[0]), _ke_tanggal_db(batas[1])
    return {
        "pilihan_vendor": pilihan,
        "batas_data": {
            "tersedia": bool(min_d and max_d),
            "dari": min_d.isoformat() if min_d else None,
            "sampai": max_d.isoformat() if max_d else None,
        },
    }


def _kunci_wilayah_intake(baris: dict) -> tuple[str, str, str]:
    """Kunci normalized kabupaten/kecamatan/desa untuk pencocokan SCDF."""
    return (
        baris["kabupaten_norm"] or normalisasi_kabupaten(baris["kabupaten"]),
        baris["kecamatan_norm"] or normalisasi_teks_wilayah(baris["kecamatan"]),
        baris["desa_norm"] or normalisasi_teks_wilayah(baris["desa"]),
    )


def _peta_wilayah_scdf(session: Session,
                       kunci_diminta: set[tuple[str, str, str]]):
    """Ambil padanan SCDF + koreksi terkontrol untuk kunci yang diperlukan.

    Mengembalikan `(peta_langsung, peta_koreksi)`. Tidak ada penebakan
    Provinsi: hanya baris referensi yang kuncinya benar-benar cocok dipakai.
    """
    if not kunci_diminta:
        return {}, {}
    kab_diminta = {k[0] for k in kunci_diminta}
    ref_by_id: dict[int, ReferensiWilayahTrace] = {}
    peta_koreksi: dict[tuple[str, str, str], int] = {}
    for c in session.scalars(select(KoreksiWilayahTrace).where(
            KoreksiWilayahTrace.source_kabupaten_norm.in_(kab_diminta))):
        kunci = (c.source_kabupaten_norm or "",
                 c.source_kecamatan_norm or "",
                 c.source_desa_norm or "")
        if kunci in kunci_diminta:
            peta_koreksi[kunci] = c.target_ref_id
    if peta_koreksi:
        for ref in session.scalars(select(ReferensiWilayahTrace).where(
                ReferensiWilayahTrace.id.in_(set(peta_koreksi.values())))):
            ref_by_id[ref.id] = ref

    peta_langsung: dict[tuple[str, str, str], ReferensiWilayahTrace] = {}
    for ref in session.scalars(select(ReferensiWilayahTrace).where(
            ReferensiWilayahTrace.kabupaten_norm.in_(kab_diminta))):
        ref_by_id.setdefault(ref.id, ref)
        kunci = (ref.kabupaten_norm, ref.kecamatan_norm, ref.desa_norm)
        if kunci in kunci_diminta:
            peta_langsung.setdefault(kunci, ref)
    koreksi = {k: ref_by_id.get(id_ref)
               for k, id_ref in peta_koreksi.items()}
    return peta_langsung, koreksi


def _wilayah_intake_tampil(baris: dict, peta_langsung, peta_koreksi) -> dict:
    """Empat kolom wilayah; ejaan SCDF bila ada padanan pasti."""
    kunci = (baris["kabupaten_norm"], baris["kecamatan_norm"],
             baris["desa_norm"])
    ref = peta_koreksi.get(kunci) or peta_langsung.get(kunci)
    if ref is None:
        return {
            "provinsi": baris["provinsi"],
            "kabupaten": baris["kabupaten"],
            "kecamatan": baris["kecamatan"],
            "desa": baris["desa"],
            "sumber_wilayah": "intake",
        }
    return {
        "provinsi": ref.provinsi or baris["provinsi"],
        "kabupaten": ref.kabupaten or baris["kabupaten"],
        "kecamatan": ref.kecamatan or baris["kecamatan"],
        "desa": ref.desa or baris["desa"],
        "sumber_wilayah": "SCDF",
    }


def _xlsx_ringkasan_vendor(hasil: dict) -> StreamingResponse:
    """Ekspor 3 sheet + 3 chart native mengikuti
    `Intake-2025_Ringkasan-Vendor.xlsx`.

    Perbedaan sadar dari contoh (keputusan pemilik):
    - tanpa sheet `Master Data` / raw tiket, jadi seluruh angka sudah dihitung
      backend dan ditulis sebagai nilai (bukan SUMIFS ke sheet mentah);
    - **setiap vendor** menjadi baris detail, tidak ada baris `Lainnya`;
    - judul, kolom bulan, dan `Rata² Trip/Bulan` mengikuti `Dari/Sampai`;
    - sheet `Vendor Harian` memuat **semua hari kalender** pada rentang, hari
      tanpa intake bernilai 0 Trip, dan tanggal di luar rentang tiket ditandai
      abu-abu dengan keterangan `Di luar data`.

    Workbook sengaja `write_only`: rentang 1.766 hari (bahkan ±100 tahun)
    tetap bisa ditulis mengalir. `WriteOnlyCell`, freeze, lebar kolom,
    colorScale, dan chart native tetap didukung openpyxl pada mode ini.
    """
    p, r, m = hasil["periode"], hasil["ringkasan"], hasil["catatan_metode"]
    baris = hasil["baris"]
    vendor_bulan = hasil["vendor_per_bulan"]
    vendor_harian = hasil["vendor_harian"]
    bulan = hasil["bulan"]
    hari = hasil["hari"]
    n_vendor, n_bulan, n_hari = len(baris), len(bulan), len(hari)
    if 5 + n_vendor > 16_384:
        raise HTTPException(
            422, "Jumlah vendor melebihi batas 16.384 kolom Excel.")

    satu_tahun = len({b["tahun"] for b in bulan}) <= 1
    label_bulan = [
        (b.get("label") or label_bulan_pendek(b["tahun"], b["bulan"]))
        if satu_tahun else b["label_ym"] for b in bulan]
    awal_bulan = [dt.date(b["tahun"], b["bulan"], 1) for b in bulan]
    judul_tahun = p["label_judul"]

    font_judul = Font(name=FONT_RINGKASAN_VENDOR, sz=14, bold=True)
    font_isi = Font(name=FONT_RINGKASAN_VENDOR, sz=11, color=Color(theme=1))
    font_tebal = Font(name=FONT_RINGKASAN_VENDOR, sz=11, bold=True)
    font_header = Font(name=FONT_RINGKASAN_VENDOR, sz=11, bold=True,
                       color=Color(rgb="FFFFFFFF"))
    font_abu = Font(name=FONT_RINGKASAN_VENDOR, sz=11,
                    color=Color(rgb=WARNA_ABU_RINGKASAN_VENDOR))
    font_kecil = Font(name=FONT_RINGKASAN_VENDOR, sz=8,
                      color=Color(rgb=WARNA_ABU_MUDA_RINGKASAN_VENDOR))
    fill_header = PatternFill("solid",
                              fgColor=WARNA_HEADER_RINGKASAN_VENDOR)
    fill_luar = PatternFill("solid",
                            fgColor=WARNA_LUAR_DATA_RINGKASAN_VENDOR)
    sisi = Side(style="thin", color=Color(auto=True))
    border = Border(left=sisi, right=sisi, top=sisi, bottom=sisi)
    tengah = Alignment(horizontal="center", vertical="center")

    def sel(ws, nilai, *, font=None, fill=None, fmt=None, tepi=None,
            align=None):
        c = WriteOnlyCell(ws, value=nilai)
        if font is not None:
            c.font = font
        if fill is not None:
            c.fill = fill
        if fmt is not None:
            c.number_format = fmt
        if tepi is not None:
            c.border = tepi
        if align is not None:
            c.alignment = align
        return c

    def skala(ws, rentang: str) -> None:
        ws.conditional_formatting.add(
            rentang,
            ColorScaleRule(start_type="min", start_color="FFFFFFFF",
                           end_type="max", end_color="FF5B9BD5"))

    wb = openpyxl.Workbook(write_only=True)

    # ===================================================== 1. Ringkasan Vendor
    ws1 = wb.create_sheet("Ringkasan Vendor")
    ws1.freeze_panes = "A5"
    ws1.row_dimensions[1].height = 19.5
    ws1.row_dimensions[2].height = 15.75
    ws1.row_dimensions[4].height = 31.5
    baris_total1 = 4 + n_vendor + 1
    ws1.row_dimensions[baris_total1].height = 15.75
    for i, lebar in enumerate(LEBAR_RINGKASAN_VENDOR, start=1):
        ws1.column_dimensions[get_column_letter(i)].width = lebar
    ws1.column_dimensions["J"].width = 18
    ws1.column_dimensions["K"].width = 10
    ws1.column_dimensions["L"].width = 14
    ws1.column_dimensions["M"].width = 10

    ws1.append([sel(ws1, f"Peringkat Vendor berdasarkan Frekuensi Intake "
                          f"[{judul_tahun}]", font=font_judul)])
    ws1.append([sel(ws1, f"Periode {p['label_inggris']} · Semua vendor "
                          f"ditulis sebagai baris detail", font=font_abu)])
    ws1.append([None])
    header1 = ["Rank", "Vendor", "Total Trip", "% Trip", "Hari Aktif",
               "Rata² Trip/Hari Operasional", "Rata² Trip/Bulan", "Dry (kg)"]
    row4 = [sel(ws1, t, font=font_header, fill=fill_header, tepi=border,
                align=tengah) for t in header1]
    row4 += [
        sel(ws1, None),
        sel(ws1, "Hari operasional", font=font_tebal),
        sel(ws1, r["hari_operasional"], fmt=FORMAT_TRIP_RINGKASAN_VENDOR),
        sel(ws1, "Jumlah bulan", font=font_tebal),
        sel(ws1, r["jumlah_bulan"], fmt=FORMAT_TRIP_RINGKASAN_VENDOR),
    ]
    ws1.append(row4)
    for b in baris:
        ws1.append([
            sel(ws1, b["peringkat"], font=font_isi, tepi=border,
                fmt=FORMAT_TRIP_RINGKASAN_VENDOR),
            sel(ws1, b["label"], font=font_isi, tepi=border),
            sel(ws1, b["total_trip"], font=font_isi, tepi=border,
                fmt=FORMAT_TRIP_RINGKASAN_VENDOR),
            sel(ws1, b["porsi_trip"], font=font_isi, tepi=border,
                fmt=FORMAT_PORSEN_RINGKASAN_VENDOR),
            sel(ws1, b["hari_aktif"], font=font_isi, tepi=border,
                fmt=FORMAT_TRIP_RINGKASAN_VENDOR),
            sel(ws1, b["rata_trip_per_hari_operasional"], font=font_isi,
                tepi=border, fmt=FORMAT_RATA_RINGKASAN_VENDOR),
            sel(ws1, b["rata_trip_per_bulan"], font=font_isi, tepi=border,
                fmt=FORMAT_RATA_RINGKASAN_VENDOR),
            sel(ws1, b["dry_kg"], font=font_isi, tepi=border,
                fmt=FORMAT_TRIP_RINGKASAN_VENDOR),
        ])
    ws1.append([
        sel(ws1, None, font=font_tebal, tepi=border),
        sel(ws1, "TOTAL", font=font_tebal, tepi=border),
        sel(ws1, r["total_trip"], font=font_tebal, tepi=border,
            fmt=FORMAT_TRIP_RINGKASAN_VENDOR),
        sel(ws1, 1.0 if r["total_trip"] else 0.0, font=font_tebal,
            tepi=border, fmt=FORMAT_PORSEN_RINGKASAN_VENDOR),
        sel(ws1, None, font=font_tebal, tepi=border),
        sel(ws1, None, font=font_tebal, tepi=border),
        sel(ws1, None, font=font_tebal, tepi=border),
        sel(ws1, r["total_dry_kg"], font=font_tebal, tepi=border,
            fmt=FORMAT_TRIP_RINGKASAN_VENDOR),
    ])
    catatan1 = [
        ["Periode", p["label_inggris"]],
        ["Sumber", m["sumber"]],
        ["Trip", m["trip"]],
        ["Hari Aktif & rata", m["hari_operasional"] + " " + m["rata"]],
        ["Semua vendor", "Tiap vendor menjadi baris detail; tidak ada baris "
                         "gabungan sisa vendor dan tidak ada sheet Master "
                         "Data."],
        ["Di luar data", m["di_luar_data"]],
        ["Periode panjang", m["minimalisir"]],
    ]
    for i, (a, b) in enumerate(catatan1):
        ws1.append([sel(ws1, a, font=font_tebal), sel(ws1, b, font=font_isi)])
    if n_vendor:
        skala(ws1, f"C5:C{4 + n_vendor}")

    ch1 = BarChart()
    ch1.type, ch1.grouping = "col", "clustered"
    ch1.title = (f"{min(10, n_vendor)} Vendor Teratas - Total Trip "
                 f"{judul_tahun}" if n_vendor else
                 f"Total Trip {judul_tahun}")
    ch1.y_axis.title, ch1.x_axis.title = "Total Trip", "Vendor"
    ch1.legend = None
    ch1.height, ch1.width = 10, 20
    if n_vendor:
        n_top1 = min(10, n_vendor)
        ch1.add_data(Reference(ws1, min_col=3, min_row=4,
                               max_row=4 + n_top1), titles_from_data=True)
        ch1.set_categories(Reference(ws1, min_col=2, min_row=5,
                                     max_row=4 + n_top1))
    ws1.add_chart(ch1, "J5")

    # ==================================================== 2. Vendor per Bulan
    ws2 = wb.create_sheet("Vendor per Bulan")
    ws2.freeze_panes = "B5"
    ws2.row_dimensions[1].height = 19.5
    ws2.row_dimensions[2].height = 15.75
    ws2.row_dimensions[3].height = 15.75
    ws2.row_dimensions[4].height = 15.75
    baris_total2 = 4 + n_vendor + 1
    ws2.row_dimensions[baris_total2].height = 15.75
    ws2.row_dimensions[baris_total2 + 2].height = 48
    ws2.row_dimensions[baris_total2 + 3].height = 15.75
    ws2.row_dimensions[baris_total2 + 4].height = 15.75
    ws2.column_dimensions["A"].width = 40
    for i in range(2, 2 + n_bulan):
        ws2.column_dimensions[get_column_letter(i)].width = 11
    ws2.column_dimensions[get_column_letter(2 + n_bulan)].width = 11
    ws2.column_dimensions[get_column_letter(3 + n_bulan)].width = 8.71

    ws2.append([sel(ws2, f"Trip Intake per Vendor per Bulan {judul_tahun} "
                          f"(Semua Vendor)", font=font_judul)])
    ws2.append([sel(ws2, f"Periode {p['label_inggris']} · "
                          f"{n_bulan} bulan mengikuti Dari/Sampai",
                     font=font_abu)])
    ws2.append([sel(ws2, "Awal bulan →", font=font_kecil)] + [
        sel(ws2, x, font=font_kecil,
            fmt=FORMAT_AWAL_BULAN_RINGKASAN_VENDOR) for x in awal_bulan])
    ws2.append([sel(ws2, t, font=font_header, fill=fill_header, tepi=border,
                    align=tengah)
                for t in ["Vendor"] + label_bulan + ["Total"]])
    for v in vendor_bulan:
        ws2.append(
            [sel(ws2, v["label"], font=font_isi, tepi=border)] +
            [sel(ws2, x, font=font_isi, tepi=border,
                 fmt=FORMAT_TRIP_RINGKASAN_VENDOR)
             for x in v["trip_per_bulan"]] +
            [sel(ws2, v["total_trip"], font=font_isi, tepi=border,
                 fmt=FORMAT_TRIP_RINGKASAN_VENDOR)])
    ws2.append(
        [sel(ws2, "TOTAL", font=font_tebal, tepi=border)] +
        [sel(ws2, x, font=font_tebal, tepi=border,
             fmt=FORMAT_TRIP_RINGKASAN_VENDOR)
         for x in hasil["total_per_bulan"]] +
        [sel(ws2, r["total_trip"], font=font_tebal, tepi=border,
             fmt=FORMAT_TRIP_RINGKASAN_VENDOR)])
    ws2.append([None])
    ws2.append(
        [sel(ws2, "Vendor #1 bulan ini", font=font_tebal)] +
        [sel(ws2, x, font=font_isi) for x in hasil["vendor_utama_bulan"]])
    ws2.append(
        [sel(ws2, "Trip vendor #1", font=font_tebal)] +
        [sel(ws2, x, font=font_isi, fmt=FORMAT_TRIP_RINGKASAN_VENDOR)
         for x in hasil["trip_utama_bulan"]])
    ws2.append(
        [sel(ws2, "Share vendor #1", font=font_tebal)] +
        [sel(ws2, x, font=font_isi,
             fmt=FORMAT_PORSEN_RINGKASAN_VENDOR)
         for x in hasil["share_utama_bulan"]])
    if n_vendor and n_bulan:
        skala(ws2, f"B5:{get_column_letter(1 + n_bulan)}{4 + n_vendor}")

    ch2 = BarChart()
    ch2.type, ch2.grouping, ch2.overlap = "col", "stacked", 100
    ch2.title = (f"Trip per Bulan per Vendor ({min(10, n_vendor)} teratas) "
                 f"{judul_tahun}" if n_vendor > 10 else
                 f"Trip per Bulan per Vendor (Semua Vendor) {judul_tahun}")
    ch2.y_axis.title, ch2.x_axis.title = "Trip", "Bulan"
    ch2.legend.position = "r"
    ch2.height, ch2.width = 11, 22
    for j in range(min(10, n_vendor)):
        ch2.add_data(
            Reference(ws2, min_col=1, max_col=1 + n_bulan,
                      min_row=5 + j, max_row=5 + j),
            titles_from_data=True, from_rows=True)
    ch2.set_categories(
        Reference(ws2, min_col=2, max_col=1 + n_bulan,
                  min_row=4, max_row=4))
    ws2.add_chart(ch2, f"A{baris_total2 + 6}")

    # ======================================================= 3. Vendor Harian
    ws3 = wb.create_sheet("Vendor Harian")
    ws3.freeze_panes = "C5"
    ws3.row_dimensions[1].height = 19.5
    ws3.row_dimensions[2].height = 15.75
    ws3.row_dimensions[4].height = 61.5
    baris_rata3 = 4 + n_hari + 1
    ws3.row_dimensions[baris_rata3].height = 15.75
    ws3.column_dimensions["A"].width = 21.29
    ws3.column_dimensions["B"].width = 9
    for i in range(3, 3 + n_vendor):
        ws3.column_dimensions[get_column_letter(i)].width = 12
    ws3.column_dimensions[get_column_letter(3 + n_vendor)].width = 34
    ws3.column_dimensions[get_column_letter(4 + n_vendor)].width = 8
    ws3.column_dimensions[get_column_letter(5 + n_vendor)].width = 14

    ws3.append([sel(ws3, f"Trip Intake Harian per Vendor {judul_tahun} "
                          f"(Semua Vendor, Semua Hari Kalender)",
                     font=font_judul)])
    ws3.append([sel(ws3, f"Periode {p['label_inggris']} · Tanggal di luar "
                          f"rentang tiket ditandai abu-abu (Di luar data)",
                     font=font_abu)])
    ws3.append([None])
    header3 = (["Tanggal", "Total Trip"] +
               [v["label"] for v in vendor_harian] +
               ["Vendor #1", "Trip #1", "Tanggal (YYYY-MM-DD)"])
    ws3.append([sel(ws3, t, font=font_header, fill=fill_header, tepi=border,
                    align=tengah) for t in header3])
    for i, h in enumerate(hari):
        tanggal = dt.date.fromisoformat(h["tanggal"])
        row = [
            sel(ws3, tanggal, font=font_isi, tepi=border,
                fmt=FORMAT_TANGGAL_RINGKASAN_VENDOR,
                fill=fill_luar if h["di_luar_data"] else None),
            sel(ws3, hasil["total_per_hari"][i], font=font_isi, tepi=border,
                fmt=FORMAT_TRIP_RINGKASAN_VENDOR),
        ]
        row += [sel(ws3, v["trip_per_hari"][i], font=font_isi, tepi=border,
                    fmt=FORMAT_TRIP_RINGKASAN_VENDOR)
                for v in vendor_harian]
        row += [
            sel(ws3, hasil["vendor_utama_harian"][i], font=font_isi,
                tepi=border),
            sel(ws3, hasil["trip_utama_harian"][i], font=font_isi,
                tepi=border, fmt=FORMAT_TRIP_RINGKASAN_VENDOR),
            sel(ws3, h["tanggal"], font=font_isi, tepi=border),
        ]
        ws3.append(row)
    ws3.append(
        [sel(ws3, "Rata² / hari", font=font_tebal),
         sel(ws3, hasil["rata_total_per_hari"], font=font_tebal,
             fmt=FORMAT_RATA_RINGKASAN_VENDOR)] +
        [sel(ws3, x, font=font_tebal,
             fmt=FORMAT_RATA_RINGKASAN_VENDOR)
         for x in hasil["rata_vendor_per_hari"]] +
        [sel(ws3, None), sel(ws3, None), sel(ws3, None)])
    ws3.append([None])
    ws3.append([sel(ws3, "Keterangan", font=font_tebal),
                sel(ws3, "Baris tanggal di luar rentang tiket ditandai "
                         "abu-abu (Di luar data); hari tanpa intake dari "
                         "vendor mana pun (pabrik tutup) bernilai 0 Trip "
                         "dan tetap ditulis.", font=font_isi)])
    ws3.append([sel(ws3, "Sumber", font=font_tebal),
                sel(ws3, m["sumber"] + " " + m["trip"], font=font_isi)])
    ws3.append([sel(ws3, "Catatan", font=font_tebal),
                sel(ws3, m["dasar_hari"] + " " + m["minimalisir"],
                    font=font_isi)])
    if n_vendor and n_hari:
        skala(ws3, f"C5:{get_column_letter(2 + n_vendor)}{4 + n_hari}")

    ch3 = LineChart()
    ch3.title = (f"Trip Harian - Total vs Vendor #1 {judul_tahun}"
                 if n_vendor else f"Trip Harian - Total {judul_tahun}")
    ch3.y_axis.title, ch3.x_axis.title = "Trip", "Tanggal"
    ch3.legend.position = "r"
    ch3.height, ch3.width = 9, 20
    ch3.add_data(
        Reference(ws3, min_col=2, max_col=3 if n_vendor else 2,
                  min_row=4, max_row=4 + n_hari),
        titles_from_data=True)
    ch3.set_categories(
        Reference(ws3, min_col=1, min_row=5, max_row=4 + n_hari))
    anchor3 = f"{get_column_letter(min(6 + n_vendor, 16_000))}3"
    ws3.add_chart(ch3, anchor3)

    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    buf.seek(0)
    nama = (f"ringkasan_vendor_{p['dari']}_sd_{p['sampai']}.xlsx")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nama}"'})


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
            "avg_ytd_sicom_sederhana": rumus.rata_rata_sederhana(
                [b.sicom_usc for b in baris]),
            "avg_ytd_op_price_sederhana": rumus.rata_rata_sederhana(
                [b.harga_beli_usc for b in baris]),
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
            isi.append(["Avg YTD sederhana (resmi)",
                        hasil["avg_ytd_sicom_sederhana"],
                        hasil["avg_ytd_op_price_sederhana"],
                        hasil["avg_ytd_sederhana"]])
            isi.append(["Avg OP Margin tertimbang tonase (informasi)", "", "",
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
        # Keputusan Rekonsiliasi Jul/Agu 2026 menggantikan sumber intake
        # pada kartu ini, termasuk bila data tiket mentah tersedia.
        keputusan = keputusan_intake_diketahui(session)

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
            kep = keputusan.get((th, bl))
            if kep:
                intake, sumber = round(kep[0], 3), kep[1]
            elif tiket_ton and (not pembelian_ton or tiket_ton >= 0.5 * pembelian_ton):
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
        # Tonase disediakan dalam dua satuan sekaligus: MT (*_ton, nilai lama
        # tetap ada supaya layar/tes lama aman) dan kg (*_kg). 1 MT = 1.000 kg.
        for b in baris:
            for kunci_ton in ("rm_stock_ton", "intake_ton", "safety_ton"):
                nilai_ton = b[kunci_ton]
                b[kunci_ton.replace("_ton", "_kg")] = (
                    round(nilai_ton * 1000, 3) if nilai_ton is not None else None)
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
            "Tonase tersedia dalam MT (*_ton) dan kg (*_kg); 1 MT = 1.000 kg. "
            "SICOM, OP Price, dan OP Margin tetap dalam US¢/kg.",
            "Untuk Jul/Agu 2026, sumber intake mengikuti keputusan pada "
            "halaman Rekonsiliasi bila sudah disimpan; data asli tidak diubah.",
        ]}
        if format == "xlsx":
            return respon_xlsx(
                "rm_stock_intake_vs_pricing.xlsx",
                ["Date", "RM Stock (MT)", "Intake (MT)",
                 "Safety Level Stock (MT)", "SICOM (US¢/kg)",
                 "OP Price (US¢/kg)", "OP Margin (US¢/kg)",
                 "Sumber intake", "Catatan",
                 "RM Stock (kg)", "Intake (kg)", "Safety (kg)"],
                [[b["label"], b["rm_stock_ton"], b["intake_ton"], b["safety_ton"],
                  b["sicom"], b["op_price"], b["op_margin"], b["sumber_intake"],
                  "stok sebagian" if b["stok_sebagian"] else "",
                  b["rm_stock_kg"], b["intake_kg"], b["safety_kg"]]
                 for b in baris])
        return hasil

    @router.get("/ringkasan-elemen/analisa")
    def analisa_elemen(dari: str | None = None, sampai: str | None = None,
                       session: Session = dep):
        """Analisa 5W1H otomatis atas grafik RM Stock - Intake vs Pricing,
        dihitung dari data pada periode terfilter."""
        from .core.analisa import analisa_5w1h
        data = ringkasan_elemen(dari=dari, sampai=sampai, session=session)
        return analisa_5w1h(data["baris"], session)

    @router.get("/ringkasan-elemen/rca")
    def analisa_rca_elemen(dari: str | None = None, sampai: str | None = None,
                           session: Session = dep):
        """RCA 5 Why berbasis angka kartu, memakai filter periode yang sama."""
        from .core.analisa_rca import analisa_rca
        data = ringkasan_elemen(dari=dari, sampai=sampai, session=session)
        return analisa_rca(data["baris"])

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
    def rekonsiliasi(request: Request, format: str | None = None,
                     session: Session = dep):
        harian = rekonsiliasi_harian(session)
        diketahui = selisih_diketahui(session)
        hasil = {
            "diketahui": diketahui,
            "catatan": CATATAN_DIKETAHUI,
            "harian": harian,
            "bisa_revisi": _boleh_revisi(request),
        }
        if format == "xlsx":
            judul = ["Periode", "Tiket (ton)", "Excel lama (ton)",
                     "Selisih asli (ton)", "Selisih setelah revisi (ton)",
                     "Sumber dipakai", "Status", "Direvisi oleh", "Waktu", "Alasan"]
            isi = [[d["periode"], d["tiket_ton"], d["excel_ton"],
                    d["selisih_ton"], d["selisih_efektif_ton"],
                    d["sumber_dipakai"] or "", d["status"],
                    (d["koreksi"] or {}).get("oleh", ""),
                    (d["koreksi"] or {}).get("pada", ""),
                    (d["koreksi"] or {}).get("alasan", "")]
                   for d in diketahui]
            return respon_xlsx("rekonsiliasi.xlsx", judul, isi)
        return hasil

    @router.post("/rekonsiliasi/keputusan")
    def simpan_keputusan_rekonsiliasi(data: RekonsiliasiKeputusanMasuk,
                                      request: Request,
                                      session: Session = dep):
        """Simpan sumber yang benar; data sumber asli sengaja tidak diubah."""
        wajib_admin(request)
        baris = _validasi_keputusan(data, session)
        kunci, alasan = baris["kunci"], (data.alasan or "").strip() or None
        lama = session.scalar(select(KoreksiRekonsiliasi).where(
            KoreksiRekonsiliasi.jenis == data.jenis,
            KoreksiRekonsiliasi.kunci == kunci))
        if lama and lama.sumber_benar == data.sumber_benar                 and (lama.alasan or None) == alasan:
            return {"status": "tidak berubah", "jenis": data.jenis,
                    "kunci": kunci, "sumber_benar": data.sumber_benar,
                    "pesan": "Keputusan sudah sama; tidak ada perubahan."}

        sebelum = None
        if lama is None:
            keputusan = KoreksiRekonsiliasi(jenis=data.jenis, kunci=kunci)
            session.add(keputusan)
            aksi = "tambah"
        else:
            keputusan = lama
            sebelum = {"sumber_benar": lama.sumber_benar,
                       "alasan": lama.alasan,
                       "oleh": lama.updated_by}
            aksi = "ubah"

        pengguna = info_pengguna(request) or {}
        siapa = pengguna.get("sub") or "dev"
        keputusan.sumber_benar = data.sumber_benar
        keputusan.alasan = alasan
        keputusan.updated_by = siapa
        keputusan.updated_at = dt.datetime.utcnow()
        session.flush()

        satuan = "kg" if data.jenis == "harian" else "ton"
        opsi = next((o for o in baris["pilihan_sumber"]
                     if o["kode"] == data.sumber_benar), None)
        nilai_dipakai = opsi[f"nilai_{satuan}"] if opsi else None
        catat_audit(session, siapa, aksi, "rekonsiliasi_koreksi", {
            "jenis": data.jenis,
            "kunci": kunci,
            "sumber_benar": data.sumber_benar,
            "alasan": alasan,
            "nilai_tiket": baris["pilihan_sumber"][0][f"nilai_{satuan}"],
            "nilai_lawan": baris["pilihan_sumber"][1][f"nilai_{satuan}"],
            "selisih_asli": baris[f"selisih_asli_{satuan}"],
            "selisih_efektif": 0.0,
            "nilai_dipakai": nilai_dipakai,
            "sebelumnya": sebelum,
        })
        evaluasi_alarm(session)
        session.commit()
        return {
            "status": "tersimpan",
            "jenis": data.jenis,
            "kunci": kunci,
            "sumber_benar": data.sumber_benar,
            "nilai_dipakai": nilai_dipakai,
            "satuan": satuan,
            "oleh": siapa,
            "pada": keputusan.updated_at.isoformat(timespec="seconds"),
            "alasan": alasan,
            "pesan": (f"Revisi {kunci} tersimpan: "
                      f"{data.sumber_benar} dipakai. Data asli tidak diubah."),
        }

    @router.delete("/rekonsiliasi/keputusan")
    def hapus_keputusan_rekonsiliasi(request: Request,
                                     jenis: str = Query(...),
                                     kunci: str = Query(...),
                                     session: Session = dep):
        """Batalkan keputusan; baris kembali memakai selisih aslinya."""
        wajib_admin(request)
        if jenis not in PILIHAN_SUMBER or not sah_kunci(jenis, kunci.strip()):
            raise HTTPException(422, "Jenis/kunci keputusan tidak dikenal.")
        kunci = kunci.strip()
        lama = session.scalar(select(KoreksiRekonsiliasi).where(
            KoreksiRekonsiliasi.jenis == jenis,
            KoreksiRekonsiliasi.kunci == kunci))
        if lama is None:
            raise HTTPException(404, "Belum ada keputusan revisi untuk baris ini.")
        sebelum = {"sumber_benar": lama.sumber_benar, "alasan": lama.alasan,
                   "oleh": lama.updated_by}
        session.delete(lama)
        session.flush()
        pengguna = info_pengguna(request) or {}
        siapa = pengguna.get("sub") or "dev"
        catat_audit(session, siapa, "hapus", "rekonsiliasi_koreksi", {
            "jenis": jenis, "kunci": kunci, "sebelumnya": sebelum,
        })
        evaluasi_alarm(session)
        session.commit()
        return {"status": "dibatalkan", "jenis": jenis, "kunci": kunci,
                "pesan": "Revisi dibatalkan; selisih asli kembali ditampilkan."}

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
        # Wilayah dinormalisasi sama seperti kartu penerimaan (UPPER/TRIM).
        wilayah = dimensi in URUTAN_WILAYAH
        peta_wilayah: dict[str, dict[str, int]] = {}

        def kunci_dari(t) -> str:
            mentah = getattr(t, kolom)
            if not wilayah:
                return mentah or "(kosong)"
            kunci = _norm_wilayah(mentah)
            _kumpulkan_wilayah(peta_wilayah, kunci, mentah)
            return kunci

        if per == "bulan":
            potongan: list[tuple[str, tuple[int, int] | None, float, str]] = []
            for t in session.scalars(q):
                potongan.append((
                    kunci_dari(t),
                    (t.ticket_date.year, t.ticket_date.month) if t.ticket_date else None,
                    float(t.dry_kg or 0) / 1000.0,
                    t.ticket_no))
            label_peta = ({k: _pilih_ejaan(v) for k, v in peta_wilayah.items()}
                          if wilayah else None)
            hasil = _tonase_per_bulan(potongan, dimensi, dari, sampai, top,
                                      format, session, label_peta)
            if isinstance(hasil, dict) and wilayah:
                hasil["wilayah"] = _laporan_wilayah(peta_wilayah)
            return hasil

        agreg: dict[str, dict] = defaultdict(lambda: {"ton": 0.0, "tiket": set()})
        for t in session.scalars(q):
            kunci = kunci_dari(t)
            agreg[kunci]["ton"] += float(t.dry_kg or 0) / 1000.0
            agreg[kunci]["tiket"].add(t.ticket_no)
        label_peta = ({k: _pilih_ejaan(v) for k, v in peta_wilayah.items()}
                      if wilayah else {})
        nama_vendor = {v.kode: v.nama_baku for v in session.scalars(select(Vendor))} \
            if dimensi == "vendor" else {}
        total = sum(a["ton"] for a in agreg.values())
        baris = sorted(({
            "kunci": k,
            "label": nama_vendor.get(k, label_peta.get(k, k)),
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
        if wilayah:
            hasil["wilayah"] = _laporan_wilayah(peta_wilayah)
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
        dimensi terbesar dan sisanya digabung menjadi "Lainnya" untuk grafik.
        Tanpa `per=bulan`, bentuk jawabannya tetap seperti semula (satu baris
        per dimensi untuk seluruh periode). Khusus `format=xlsx`, `top` dan
        "Lainnya" TIDAK dipakai: semua dimensi ditulis sebagai baris detail
        dan semua bulan terpilih menjadi kolom."""
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
        # Wilayah: kunci dibakukan (UPPER/TRIM) supaya "Sumatera Utara" dan
        # "SUMATERA UTARA" tidak muncul sebagai dua baris. Ejaan aslinya
        # dicatat untuk label & laporan penggabungan.
        wilayah = dimensi in URUTAN_WILAYAH
        peta_wilayah: dict[str, dict[str, int]] = {}

        def kunci_dari(t) -> str:
            mentah = getattr(t, kolom)
            if not wilayah:
                return mentah or "(kosong)"
            kunci = _norm_wilayah(mentah)
            _kumpulkan_wilayah(peta_wilayah, kunci, mentah)
            return kunci

        label_peta = {}
        # Satu lintasan data: dipakai untuk kedua bentuk keluaran.
        potongan: list[tuple[str, tuple[int, int] | None, float, bool, str]] = []
        for t in session.scalars(q):
            e = tiket_eudr(t.item_code)
            if eudr is True and not e:
                continue
            if eudr is False and e:
                continue
            bulan = (t.ticket_date.year, t.ticket_date.month) if t.ticket_date else None
            potongan.append((kunci_dari(t), bulan,
                             float(t.dry_kg or 0), e, t.ticket_no))
        if wilayah:
            label_peta = {k: _pilih_ejaan(v) for k, v in peta_wilayah.items()}
            laporan_wilayah = _laporan_wilayah(peta_wilayah)
        else:
            laporan_wilayah = None

        info_ekspor = None
        if format == "xlsx":
            info_ekspor = _info_ekspor_penerimaan(
                dari, sampai, vendor, provinsi, kabupaten, kecamatan, desa,
                potongan, session)

        if per == "bulan":
            hasil = _penerimaan_per_bulan(potongan, dimensi, dari, sampai,
                                          top, format, session, label_peta,
                                          info_ekspor)
            if isinstance(hasil, dict) and laporan_wilayah:
                hasil["wilayah"] = laporan_wilayah
            return hasil

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
            "label": (f"{k} — {nama_vendor[k]}" if k in nama_vendor
                      else (label_peta.get(k, k) if wilayah else k)),
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
        if laporan_wilayah:
            hasil["wilayah"] = laporan_wilayah
        if format == "xlsx":
            judul_xlsx, periode_xlsx = info_ekspor or (
                "Penerimaan Karet", "Tidak ada data")
            return respon_xlsx_penerimaan(
                f"penerimaan_per_{dimensi}.xlsx",
                judul_xlsx, periode_xlsx,
                [dimensi.capitalize(), "Kg biasa", "Kg EUDR", "Kg total",
                 "Porsi", "Jumlah tiket"],
                [[b["label"], b["kg_biasa"], b["kg_eudr"], b["kg_total"],
                  b["porsi"], b["jumlah_tiket"]] for b in baris],
                ["teks", "kg", "kg", "kg", "persen", "teks"],
                kolom_tengah=5)
        return hasil

    # ------------------------------------------- kartu penerimaan: tren & musiman
    @router.get("/kartu/penerimaan/tren")
    def kartu_penerimaan_tren(dari: str | None = None, sampai: str | None = None,
                              eudr: bool | None = None,
                              format: str | None = None, session: Session = dep):
        """Analisis tren & musiman penerimaan karet (kg kering per bulan).

        Isi jawaban:
        - deret bulanan total / grade biasa / EUDR;
        - `ma3` rata-rata bergerak 3 bulan (tren dasar);
        - `mom_pct` dan `yoy_pct` (YoY kosong bila tahun sebelumnya belum ada);
        - `dekomposisi` tren-musiman (pendekatan STL) — hanya bila data
          mencukupi (minimal 24 bulan, idealnya 36);
        - `validasi`: bulan bernilai nol, bulan terakhir belum lengkap, pola
          datar tidak wajar, dan penggabungan ejaan provinsi.

        Perhitungan MA3/MoM/YoY/dekomposisi memakai SELURUH deret yang ada
        (bukan hanya rentang tampil), supaya bulan-bulan di awal periode
        tidak kehilangan pembandingnya. `dari`/`sampai` hanya memotong
        tampilan.
        """
        kd = _bulan_ym(dari, "dari")
        ks = _bulan_ym(sampai, "sampai")
        if kd and ks and kd > ks:
            raise HTTPException(422, f"Periode terbalik: 'dari' ({dari}) lebih "
                                     f"akhir daripada 'sampai' ({sampai}).")

        kode_eudr = {g.item_code for g in session.scalars(
            select(Grade).where(Grade.eudr == True))}  # noqa: E712

        per_bulan: dict[tuple[int, int], dict] = defaultdict(
            lambda: {"total": 0.0, "biasa": 0.0, "eudr": 0.0, "tiket": set()})
        peta_wilayah: dict[str, dict[str, int]] = {}
        tanggal_terakhir: dt.date | None = None
        for t in session.scalars(select(TiketBaris).where(
                TiketBaris.tiket_nol == False)):  # noqa: E712
            if not t.ticket_date or t.dry_kg is None:
                continue
            e = (t.item_code in kode_eudr) or ("TTSR" in (t.item_code or "").upper())
            if eudr is True and not e:
                continue
            if eudr is False and e:
                continue
            kunci = (t.ticket_date.year, t.ticket_date.month)
            kg = float(t.dry_kg)
            per_bulan[kunci]["total"] += kg
            per_bulan[kunci]["eudr" if e else "biasa"] += kg
            per_bulan[kunci]["tiket"].add(t.ticket_no)
            _kumpulkan_wilayah(peta_wilayah, _norm_wilayah(t.provinsi), t.provinsi)
            if tanggal_terakhir is None or t.ticket_date > tanggal_terakhir:
                tanggal_terakhir = t.ticket_date

        if not per_bulan:
            return {
                "status": "kosong",
                "bulan": [], "total_kg": [], "biasa_kg": [], "eudr_kg": [],
                "ma3": [], "mom_pct": [], "yoy_pct": [],
                "dekomposisi": {"tersedia": False, "jumlah_bulan": 0,
                                "pesan": "Belum ada data tiket untuk dianalisis."},
                "validasi": {"peringatan": ["Belum ada data tiket penerimaan."]},
                "wilayah": _laporan_wilayah(peta_wilayah),
                "sumber": "tiket_baris (Dry, tanpa tiket nol)",
            }

        berdata = sorted(per_bulan)
        sumbu = _bulan_berurutan(berdata[0], berdata[-1])
        total = [round(per_bulan[b]["total"], 1) for b in sumbu]
        biasa = [round(per_bulan[b]["biasa"], 1) for b in sumbu]
        eudr_kg = [round(per_bulan[b]["eudr"], 1) for b in sumbu]
        tiket = [len(per_bulan[b]["tiket"]) for b in sumbu]

        ma3 = _ma3(total)
        mom = _pertumbuhan(total, 1)
        yoy = _pertumbuhan(total, 12)
        dekomposisi = _dekomposisi_aditif(total, sumbu)

        # ---- potong tampilan sesuai filter (perhitungan tetap seluruh deret)
        i0, i1 = 0, len(sumbu) - 1
        if kd:
            i0 = next((i for i, b in enumerate(sumbu) if b >= kd), len(sumbu))
        if ks:
            calon = [i for i, b in enumerate(sumbu) if b <= ks]
            i1 = calon[-1] if calon else -1
        if i0 > i1:
            i0, i1 = 0, -1

        def potong(deret: list) -> list:
            return deret[i0:i1 + 1]

        sumbu_tampil = potong(sumbu)
        bulan_tampil = [{"ym": f"{th}-{bl:02d}", "label": _label_bulan_singkat(th, bl)}
                        for th, bl in sumbu_tampil]

        # ---- validasi data sebelum dipakai untuk forecasting
        total_tampil = potong(total)
        bulan_nol = [b["ym"] for b, v in zip(bulan_tampil, total_tampil) if v == 0]
        # Deret nol yang diapit bulan berisi: hampir pasti tiket belum diunggah,
        # bukan penerimaan benar-benar berhenti. Rentetan nol dihitung utuh
        # (bukan per bulan), karena biasanya bolongnya beberapa bulan sekaligus.
        nol_di_tengah: list[str] = []
        i = 0
        while i < len(total_tampil):
            if total_tampil[i] != 0:
                i += 1
                continue
            j = i
            while j < len(total_tampil) and total_tampil[j] == 0:
                j += 1
            if i > 0 and j < len(total_tampil):
                nol_di_tengah.extend(b["ym"] for b in bulan_tampil[i:j])
            i = j
        pola_datar = _deteksi_pola_datar(total_tampil, sumbu_tampil)

        peringatan: list[str] = []
        bulan_terakhir = f"{berdata[-1][0]}-{berdata[-1][1]:02d}"
        akhir_bulan_data = (dt.date(berdata[-1][0], berdata[-1][1],
                                    calendar.monthrange(berdata[-1][0],
                                                        berdata[-1][1])[1]))
        lengkap = tanggal_terakhir is not None and tanggal_terakhir >= akhir_bulan_data
        if not lengkap:
            peringatan.append(
                f"Bulan terakhir ({bulan_terakhir}) baru terisi sampai "
                f"{tanggal_terakhir.strftime('%d/%m/%Y') if tanggal_terakhir else '-'}"
                f" — kemungkinan bulan berjalan atau data belum lengkap. "
                "Angka bulan ini akan naik setelah tiket berikutnya diunggah.")
        if nol_di_tengah:
            peringatan.append(
                f"{len(nol_di_tengah)} bulan bernilai nol di tengah periode "
                f"({', '.join(nol_di_tengah[:6])}{'…' if len(nol_di_tengah) > 6 else ''}). "
                "Nol biasanya berarti tiket belum diunggah, bukan penerimaan "
                "benar-benar berhenti.")
        if pola_datar:
            d = pola_datar[0]
            peringatan.append(
                f"Pola datar tidak wajar: {d['jumlah_bulan']} bulan berturut "
                f"({d['mulai']} sampai {d['selesai']}) rata-rata "
                f"{d['rata_kg']:,.0f} kg dengan variasi hanya {d['cv_pct']}%. "
                "Penerimaan nyata jarang seseragam ini — periksa apakah datanya "
                "data contoh atau belum lengkap sebelum dipakai untuk perkiraan."
                .replace(",", "."))
        laporan_wilayah = _laporan_wilayah(peta_wilayah)
        if laporan_wilayah["digabung"]:
            contoh = laporan_wilayah["digabung"][0]
            peringatan.append(
                f"Nama provinsi sempat tidak seragam ({contoh['jumlah_ejaan']} "
                f"ejaan untuk {contoh['label']}: "
                f"{', '.join(v['ejaan'] for v in contoh['varian'])}). Sudah "
                "digabung otomatis dengan UPPER/TRIM; sebaiknya sumber datanya "
                "juga dibakukan.")
        if not dekomposisi.get("tersedia"):
            peringatan.append(dekomposisi["pesan"])

        hasil = {
            "status": "ok",
            "bulan": bulan_tampil,
            "jumlah_bulan": len(bulan_tampil),
            "total_kg": potong(total),
            "biasa_kg": potong(biasa),
            "eudr_kg": potong(eudr_kg),
            "jumlah_tiket": potong(tiket),
            "ma3": potong(ma3),
            "mom_pct": potong(mom),
            "yoy_pct": potong(yoy),
            "dekomposisi": {
                **dekomposisi,
                "tren": potong(dekomposisi.get("tren", [])),
                "musiman": potong(dekomposisi.get("musiman", [])),
                "residu": potong(dekomposisi.get("residu", [])),
            },
            "validasi": {
                "dari_data": f"{berdata[0][0]}-{berdata[0][1]:02d}",
                "sampai_data": bulan_terakhir,
                "tanggal_terakhir": (tanggal_terakhir.isoformat()
                                     if tanggal_terakhir else None),
                "jumlah_bulan_data": len(berdata),
                "bulan_nol": bulan_nol,
                "bulan_nol_di_tengah": nol_di_tengah,
                "bulan_terakhir_lengkap": lengkap,
                "pola_datar": pola_datar,
                "peringatan": peringatan,
            },
            "wilayah": laporan_wilayah,
            "catatan_metode": {
                "ma3": "rata-rata bergerak 3 bulan (trailing); bulan ke-1–2 kosong",
                "mom": "pertumbuhan % terhadap bulan sebelumnya; kosong bila "
                       "pembanding nol/tidak ada",
                "yoy": "pertumbuhan % terhadap bulan yang sama tahun lalu; "
                       "kosong bila data tahun sebelumnya belum ada",
            },
            "sumber": "tiket_baris (Dry, tanpa tiket nol)",
        }
        if format == "xlsx":
            judul = ["Bulan", "Total kg", "Biasa kg", "EUDR kg", "MA3 kg",
                     "MoM %", "YoY %", "Jumlah tiket"]
            isi = [[b["label"], tot, bis, eud, ma, mo, yo, nt] for b, tot, bis, eud, ma, mo, yo, nt
                   in zip(bulan_tampil, hasil["total_kg"], hasil["biasa_kg"],
                          hasil["eudr_kg"], hasil["ma3"], hasil["mom_pct"],
                          hasil["yoy_pct"], hasil["jumlah_tiket"])]
            return respon_xlsx("penerimaan_tren_musiman.xlsx", judul, isi)
        return hasil

    # ------------------------------------- kartu penerimaan: deskriptif & komposisi
    @router.get("/kartu/penerimaan/komposisi")
    def kartu_penerimaan_komposisi(dimensi: str = "provinsi",
                                   dari: str | None = None,
                                   sampai: str | None = None,
                                   eudr: bool | None = None,
                                   format: str | None = None,
                                   session: Session = dep):
        """Analisis deskriptif & komposisi penerimaan (langsung bisa dipakai).

        Tiga hal yang dijawab:
        1. **Share per dimensi** (bawaannya provinsi): kg, porsi, kumulatif,
           jadi kelihatan ketergantungan pada satu wilayah/vendor.
        2. **Pareto/ABC**: kategori mana yang menyumbang 80% volume (kelas A),
           sampai 95% (B), sisanya C.
        3. **Share EUDR vs biasa**, total dan per bulan, untuk memantau target
           kepatuhan EUDR dari waktu ke waktu.

        `dimensi` mengikuti dimensi kartu (vendor/grade/provinsi/kabupaten/
        kecamatan/desa). Wilayah memakai kunci ter-normalisasi (UPPER/TRIM)
        seperti kartu Penerimaan, dan penggabungan ejaannya ikut dilaporkan.
        """
        if dimensi not in DIMENSI_TONASE:
            raise HTTPException(422, f"Dimensi '{dimensi}' tidak dikenal. "
                                     f"Pilihan: {', '.join(DIMENSI_TONASE)}.")
        kd = _bulan_ym(dari, "dari")
        ks = _bulan_ym(sampai, "sampai")
        if kd and ks and kd > ks:
            raise HTTPException(422, f"Periode terbalik: 'dari' ({dari}) lebih "
                                     f"akhir daripada 'sampai' ({sampai}).")

        kode_eudr = {g.item_code for g in session.scalars(
            select(Grade).where(Grade.eudr == True))}  # noqa: E712
        kolom = {"vendor": "kode_vendor", "grade": "item_code"}.get(dimensi, dimensi)
        wilayah = dimensi in URUTAN_WILAYAH
        peta_wilayah: dict[str, dict[str, int]] = {}

        per_kunci: dict[str, dict] = defaultdict(
            lambda: {"kg": 0.0, "eudr": 0.0, "tiket": set()})
        per_bulan: dict[tuple[int, int], dict] = defaultdict(
            lambda: {"total": 0.0, "eudr": 0.0})
        total_kg = 0.0
        total_eudr = 0.0
        semua_tiket: set[str] = set()

        for t in session.scalars(select(TiketBaris).where(
                TiketBaris.tiket_nol == False)):  # noqa: E712
            if not t.ticket_date or t.dry_kg is None:
                continue
            bulan = (t.ticket_date.year, t.ticket_date.month)
            if kd and bulan < kd:
                continue
            if ks and bulan > ks:
                continue
            e = (t.item_code in kode_eudr) or ("TTSR" in (t.item_code or "").upper())
            if eudr is True and not e:
                continue
            if eudr is False and e:
                continue
            kg = float(t.dry_kg)
            mentah = getattr(t, kolom)
            if wilayah:
                kunci = _norm_wilayah(mentah)
                _kumpulkan_wilayah(peta_wilayah, kunci, mentah)
            else:
                kunci = mentah or "(kosong)"
            isi = per_kunci[kunci]
            isi["kg"] += kg
            isi["tiket"].add(t.ticket_no)
            if e:
                isi["eudr"] += kg
                per_bulan[bulan]["eudr"] += kg
                total_eudr += kg
            per_bulan[bulan]["total"] += kg
            total_kg += kg
            semua_tiket.add(t.ticket_no)

        nama_vendor = ({v.kode: v.nama_baku for v in session.scalars(select(Vendor))}
                       if dimensi == "vendor" else {})
        peta_label = ({k: _pilih_ejaan(v) for k, v in peta_wilayah.items()}
                      if wilayah else {})

        def label_dari(kunci: str) -> str:
            if kunci in nama_vendor:
                return f"{kunci} — {nama_vendor[kunci]}"
            return peta_label.get(kunci, kunci)

        # ---- urut menurun, porsi, kumulatif, kelas ABC (80/95)
        urut = sorted(per_kunci.items(), key=lambda kv: -kv[1]["kg"])
        baris: list[dict] = []
        kumulatif = 0.0
        for kunci, isi in urut:
            porsi = (isi["kg"] / total_kg) if total_kg else 0.0
            sebelum = kumulatif
            kumulatif += porsi
            # Kelas A = yang membuat kumulatif mencapai 80% (termasuk yang
            # melewatinya), B sampai 95%, sisanya C. Memakai nilai SEBELUM
            # baris ini supaya satu kategori tidak terbelah dua kelas.
            kelas = "A" if sebelum < 0.80 else ("B" if sebelum < 0.95 else "C")
            baris.append({
                "kunci": kunci, "label": label_dari(kunci),
                "kg": round(isi["kg"], 1),
                "porsi": round(porsi, 4),
                "porsi_pct": round(porsi * 100, 2),
                "kumulatif_pct": round(kumulatif * 100, 2),
                "kelas": kelas,
                "eudr_kg": round(isi["eudr"], 1),
                "eudr_pct": round(isi["eudr"] / isi["kg"] * 100, 2) if isi["kg"] else None,
                "jumlah_tiket": len(isi["tiket"]),
            })

        kelas_ringkas = {}
        for k in ("A", "B", "C"):
            anggota = [b for b in baris if b["kelas"] == k]
            kg_kelas = sum(b["kg"] for b in anggota)
            kelas_ringkas[k] = {
                "jumlah": len(anggota),
                "kg": round(kg_kelas, 1),
                "porsi_pct": round(kg_kelas / total_kg * 100, 2) if total_kg else 0.0,
                "anggota": [b["label"] for b in anggota],
            }

        # ---- konsentrasi pasokan
        hhi = sum(b["porsi"] ** 2 for b in baris) if total_kg else 0.0
        if hhi >= 0.25:
            label_hhi = "tinggi (pasokan terkonsentrasi pada sedikit pihak)"
        elif hhi >= 0.15:
            label_hhi = "sedang"
        else:
            label_hhi = "rendah (pasokan menyebar)"
        top1 = baris[0] if baris else None
        # Berapa kategori yang DIPERLUKAN untuk mencapai 80% (termasuk yang
        # melewatinya). Kalau 2 kategori baru 75%, kategori ke-3 ikut dihitung.
        jumlah_80 = next((i + 1 for i, b in enumerate(baris)
                          if b["kumulatif_pct"] >= 80.0), len(baris))

        # ---- EUDR vs biasa
        bulan_urut = sorted(per_bulan)
        eudr_per_bulan = [{
            "ym": f"{th}-{bl:02d}",
            "label": _label_bulan_singkat(th, bl),
            "total_kg": round(per_bulan[(th, bl)]["total"], 1),
            "eudr_kg": round(per_bulan[(th, bl)]["eudr"], 1),
            "eudr_pct": (round(per_bulan[(th, bl)]["eudr"] / per_bulan[(th, bl)]["total"] * 100, 2)
                         if per_bulan[(th, bl)]["total"] else None),
        } for th, bl in bulan_urut]

        peringatan: list[str] = []
        if total_kg == 0:
            peringatan.append("Tidak ada data tiket pada periode/dimensi ini.")
        if total_kg and total_eudr == 0:
            peringatan.append(
                "Belum ada grade ber-flag EUDR pada periode ini (share EUDR 0%). "
                "Periksa penandaan EUDR di menu Grade & Harga bila seharusnya ada.")
        laporan_wilayah = _laporan_wilayah(peta_wilayah)
        if laporan_wilayah["digabung"]:
            peringatan.append(
                f"{len(laporan_wilayah['digabung'])} nama wilayah digabung karena "
                "beda huruf besar/kecil — share dihitung setelah penggabungan.")

        hasil = {
            "status": "ok",
            "dimensi": dimensi,
            "periode": {"dari": dari, "sampai": sampai},
            "total_kg": round(total_kg, 1),
            "total_ton": round(total_kg / 1000, 3),
            "jumlah_tiket": len(semua_tiket),
            "jumlah_kategori": len(baris),
            "baris": baris,
            "pareto": {
                "ambang_a_pct": 80.0, "ambang_b_pct": 95.0,
                "jumlah_kategori_80": jumlah_80,
                "kelas": kelas_ringkas,
                "catatan": (f"{jumlah_80} dari {len(baris)} {dimensi} diperlukan "
                            "untuk mencapai 80% volume — sisanya ekor panjang."
                            if baris else ""),
            },
            "konsentrasi": {
                "hhi": round(hhi, 4),
                "label": label_hhi,
                "top1_label": top1["label"] if top1 else None,
                "top1_porsi_pct": top1["porsi_pct"] if top1 else None,
                "top3_porsi_pct": round(sum(b["porsi_pct"] for b in baris[:3]), 2),
            },
            "eudr": {
                "total_kg": round(total_eudr, 1),
                "porsi_pct": round(total_eudr / total_kg * 100, 2) if total_kg else None,
                "biasa_kg": round(total_kg - total_eudr, 1),
                "biasa_porsi_pct": (round((total_kg - total_eudr) / total_kg * 100, 2)
                                    if total_kg else None),
                "per_bulan": eudr_per_bulan,
            },
            "wilayah": laporan_wilayah if wilayah else None,
            "peringatan": peringatan,
            "sumber": "tiket_baris (Dry, tanpa tiket nol); EUDR = grade ber-flag "
                      "EUDR / kode TTSR",
        }
        if format == "xlsx":
            judul = [dimensi.capitalize(), "Kg", "Porsi %", "Kumulatif %",
                     "Kelas ABC", "EUDR kg", "EUDR %", "Jumlah tiket"]
            isi_xlsx = [[b["label"], b["kg"], b["porsi_pct"], b["kumulatif_pct"],
                         b["kelas"], b["eudr_kg"], b["eudr_pct"], b["jumlah_tiket"]]
                        for b in baris]
            return respon_xlsx(f"komposisi_penerimaan_{dimensi}.xlsx", judul, isi_xlsx)
        return hasil

    # --------------------------------------------- kartu: konsistensi intake vendor
    @router.get("/kartu/konsistensi-intake-vendor")
    def kartu_konsistensi_intake_vendor(dari: str | None = None,
                                        sampai: str | None = None,
                                        format: str | None = None,
                                        rinci: int | None = None,
                                        session: Session = dep):
        """Laporan Ringkasan Vendor berbasis **Trip**, mengikuti contoh
        `Intake-2025_Ringkasan-Vendor.xlsx`.

        Kartu layar kini berupa **tiga tabel** (`Ringkasan Vendor`,
        `Vendor per Bulan`, `Vendor Harian`); chart lama dihapus. Metrik
        memakai Total Trip, % Trip, Hari Aktif, Rata² Trip/Hari Operasional,
        Rata² Trip/Bulan, dan Dry (kg). Peringkat diurutkan menurut jumlah
        Trip (Ticket No unik), bukan lagi jumlah tanggal unik ber-intake.

        `format=xlsx` menghasilkan **3 sheet + 3 chart Excel native** tanpa
        sheet `Master Data`/raw tiket. Semua vendor (termasuk yang 0 Trip)
        ditulis sebagai baris detail, tanpa `Lainnya`. Judul, kolom bulan, dan
        pembagi `Rata² Trip/Bulan` mengikuti `Dari/Sampai`. Sheet harian memuat
        **semua hari kalender** pada rentang; hari tanpa intake bernilai 0 Trip.

        Bila `dari`/`sampai` kosong, batas diisi dari tanggal tiket paling awal
        / paling akhir. Seluruh rentang data boleh dipilih; batas 731 hari sudah
        dihapus. `MAKS_HARI` hanya pengaman tanggal ekstrem (±100 tahun) dan
        `MAKS_BULAN` pengaman kolom bulan. Periode panjang diminimalisir di
        layar menjadi rekap per bulan + rentang tanggal `YYYY-MM-DD`; `rinci=1`
        meminta matriks harian penuh bila pengguna ingin membuka semua baris,
        sementara ekspor Excel selalu menulis satu baris per tanggal. Data
        sumber tidak diubah dan tidak ada tabel/dependensi baru.
        """
        d = _tanggal_iso(dari, "dari")
        s = _tanggal_iso(sampai, "sampai")
        if d and s and d > s:
            raise HTTPException(422, f"Periode terbalik: 'dari' ({dari}) lebih "
                                     f"akhir daripada 'sampai' ({sampai}).")

        batas = session.execute(
            select(func.min(TiketBaris.ticket_date),
                   func.max(TiketBaris.ticket_date)).where(
                TiketBaris.tiket_nol == False,  # noqa: E712
                TiketBaris.ticket_date.is_not(None))).one()
        min_d, max_d = _ke_tanggal_db(batas[0]), _ke_tanggal_db(batas[1])
        hari_ini = dt.date.today()
        awal = d or min_d or dt.date(hari_ini.year, 1, 1)
        akhir = s or max_d or hari_ini
        if awal > akhir:
            raise HTTPException(422, f"Periode terbalik: {awal} lebih akhir "
                                     f"daripada {akhir}.")
        jumlah_hari = (akhir - awal).days + 1
        if jumlah_hari > MAKS_HARI:
            raise HTTPException(
                422, f"Rentang {jumlah_hari} hari di luar jangkauan tanggal "
                     f"yang wajar (batas keamanan {MAKS_HARI} hari, ±100 "
                     "tahun). Periksa kembali 'Dari/Sampai'.")
        jumlah_bulan = ((akhir.year - awal.year) * 12
                        + akhir.month - awal.month + 1)
        if jumlah_bulan > MAKS_BULAN:
            jml = f"{jumlah_bulan:,}".replace(",", ".")
            maks = f"{MAKS_BULAN:,}".replace(",", ".")
            raise HTTPException(
                422, f"Periode {jml} bulan terlalu panjang untuk laporan "
                     f"Ringkasan Vendor; maksimal {maks} bulan (100 tahun). "
                     "Persempit 'Dari/Sampai' agar tiap bulan tetap menjadi "
                     "kolom.")

        mentah = session.execute(
            select(TiketBaris.ticket_date, TiketBaris.kode_vendor,
                   TiketBaris.ticket_no, TiketBaris.dry_kg).where(
                TiketBaris.tiket_nol == False,  # noqa: E712
                TiketBaris.ticket_date.is_not(None),
                TiketBaris.ticket_date >= awal,
                TiketBaris.ticket_date <= akhir)).all()
        nama_vendor = {v.kode: v.nama_baku
                       for v in session.scalars(select(Vendor))}
        batas_data = (min_d, max_d) if min_d and max_d else None
        try:
            hasil = hitung_ringkasan_vendor(
                mentah, awal, akhir, nama_vendor, batas_data=batas_data)
        except ValueError as galat:
            raise HTTPException(422, str(galat)) from galat
        hasil["periode"]["dari_otomatis"] = d is None
        hasil["periode"]["sampai_otomatis"] = s is None
        if d is None or s is None:
            hasil["peringatan"].append(
                "Batas periode yang tidak diisi diambil otomatis dari tanggal "
                "tiket paling awal/akhir pada database.")
        hasil["sumber"] = ("tiket_baris (Ticket Date, tanpa tiket nol); "
                           "Trip = Ticket No unik; dasar hari = semua hari "
                           "kalender; urutan = jumlah Trip")

        if format == "xlsx":
            return _xlsx_ringkasan_vendor(hasil)
        if rinci:
            return hasil
        return ringkas_untuk_layar(hasil)

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
    def kartu_reject(tahun: int | None = None, bulan: int = 12,
                     format: str | None = None, session: Session = dep):
        """Reject% per bulan, dibatasi `bulan` bulan terakhir yang berdata.

        Bawaannya 12 bulan (permintaan pemilik): kartu KPI tidak lagi
        menumpahkan seluruh riwayat 2020-2026 sehingga angkanya terbaca.
        `bulan=0` mengembalikan seluruh bulan.
        Angka KPI (reject%) dihitung dari bulan yang benar-benar ditampilkan,
        supaya ringkasan di atas tabel tidak bertentangan dengan tabelnya.
        """
        if bulan is not None and (bulan < 0 or bulan > 120):
            raise HTTPException(422, "`bulan` harus antara 0 dan 120 "
                                     "(0 = semua bulan).")
        q = select(TiketBaris).where(TiketBaris.tiket_nol == False)  # noqa: E712
        awal, akhir = _rentang(tahun, None)
        if awal:
            q = q.where(TiketBaris.ticket_date >= awal, TiketBaris.ticket_date <= akhir)
        per_bulan: dict[tuple[int, int], dict] = defaultdict(lambda: {"wet": Decimal(0), "reject": Decimal(0)})
        for t in session.scalars(q):
            k = (t.ticket_date.year, t.ticket_date.month)
            per_bulan[k]["wet"] += t.wet_kg or 0
            per_bulan[k]["reject"] += t.reject_kg or 0
        semua_baris = [{
            "tahun": thn, "bulan": bln,
            "wet_ton": round(float(v["wet"]) / 1000, 3),
            "reject_ton": round(float(v["reject"]) / 1000, 3),
            "reject_pct": round(float(v["reject"]) / float(v["wet"]) * 100, 2)
            if v["wet"] else None,
            "_wet": v["wet"], "_reject": v["reject"],
        } for (thn, bln), v in sorted(per_bulan.items())]

        total_bulan = len(semua_baris)
        baris = semua_baris if bulan == 0 else semua_baris[-bulan:]
        wet = sum((b["_wet"] for b in baris), Decimal(0))
        reject = sum((b["_reject"] for b in baris), Decimal(0))
        for b in baris:
            b.pop("_wet")
            b.pop("_reject")

        kpi = kpi_reject(session)
        kpi["kpi_periode"] = {
            "wet_kg": float(wet), "reject_kg": float(reject),
            "reject_pct": round(float(reject) / float(wet) * 100, 2) if wet else None,
            "jumlah_bulan": len(baris),
            "bulan_pertama": (f"{baris[0]['tahun']}-{baris[0]['bulan']:02d}"
                              if baris else None),
            "bulan_terakhir": (f"{baris[-1]['tahun']}-{baris[-1]['bulan']:02d}"
                               if baris else None),
        }
        hasil = {
            "baris": baris, "kpi": kpi,
            "bulan_ditampilkan": bulan,
            "jumlah_bulan_tampil": len(baris),
            "jumlah_bulan_total": total_bulan,
            "terpotong": len(baris) < total_bulan,
        }
        if format == "xlsx":
            return respon_xlsx("reject.xlsx",
                               ["Tahun", "Bulan", "Wet ton", "Reject ton", "Reject %"],
                               [[b["tahun"], b["bulan"], b["wet_ton"], b["reject_ton"],
                                 b["reject_pct"]] for b in baris])
        return hasil

    # ------------------------------------------------------------ kartu: daftar intake
    @router.get("/kartu/intake-terakhir/opsi")
    def opsi_intake_terakhir(session: Session = dep):
        """Opsi filter vendor + batas tiket, bisa dimuat sebelum Refresh kartu."""
        return _opsi_intake_terakhir(session)

    @router.get("/kartu/intake-terakhir")
    def kartu_intake_terakhir(limit: int = 20, format: str | None = None,
                              dari: str | None = None,
                              sampai: str | None = None,
                              vendor: str | None = Query(default=None,
                                                         max_length=120),
                              session: Session = dep):
        """Daftar tiket intake terbaru dengan filter records dan breakdown wilayah.

        Satu baris = satu tiket (bukan satu baris tiket): beberapa `line_seq`
        dengan nomor tiket sama digabung, karena satu tiket adalah satu
        kendaraan yang datang. `dari`/`sampai` memakai tanggal persis
        `YYYY-MM-DD` (inklusif); `vendor` menyaring `kode_vendor` secara
        exact. Ringkasan atas, tabel, jumlah total, dan Ekspor Excel sama-sama
        mengikuti kedua filter. `limit` hanya memotong baris yang ditampilkan.

        Wilayah tidak lagi digabung menjadi `Kabupaten, Provinsi`: tabel dan
        Excel memuat **Provinsi, Kabupaten/Kota, Kecamatan, Desa** terpisah.
        Ejaan resmi SCDF dipakai bila kunci normalized cocok dengan
        `traceability_wilayah` atau koreksi terkontrol; tanpa padanan, nilai
        tiket ditampilkan apa adanya. Tidak ada penebakan Provinsi dan data
        intake mentah tidak diubah.
        """
        if limit < 1 or limit > 200:
            raise HTTPException(422, "`limit` harus antara 1 dan 200.")
        d = _tanggal_iso(dari, "dari")
        s = _tanggal_iso(sampai, "sampai")
        if d and s and d > s:
            raise HTTPException(422, f"Periode terbalik: 'dari' ({dari}) lebih "
                                     f"akhir daripada 'sampai' ({sampai}).")
        if d and s and (s - d).days + 1 > MAKS_HARI:
            raise HTTPException(
                422, f"Rentang {(s - d).days + 1} hari di luar jangkauan "
                     f"tanggal yang wajar (batas keamanan {MAKS_HARI} hari, "
                     "±100 tahun). Periksa kembali 'Dari/Sampai'.")

        opsi = _opsi_intake_terakhir(session)
        kode_diminta = (vendor or "").strip().upper() or None
        if kode_diminta and kode_diminta not in {
                p["kode"] for p in opsi["pilihan_vendor"]}:
            raise HTTPException(
                422, f"Kode vendor '{vendor}' tidak dikenal. Pilih kode dari "
                     "Master Vendor atau kode yang benar-benar ada di tiket.")

        kondisi = [TiketBaris.tiket_nol == False,  # noqa: E712
                   TiketBaris.ticket_date.is_not(None)]
        if d:
            kondisi.append(TiketBaris.ticket_date >= d)
        if s:
            kondisi.append(TiketBaris.ticket_date <= s)
        if kode_diminta:
            kondisi.append(func.upper(func.trim(
                TiketBaris.kode_vendor)) == kode_diminta)

        mentah = session.execute(
            select(TiketBaris.ticket_date, TiketBaris.ticket_no,
                   TiketBaris.line_seq, TiketBaris.kode_vendor,
                   TiketBaris.nama_vendor_asli, TiketBaris.item_code,
                   TiketBaris.provinsi, TiketBaris.kabupaten,
                   TiketBaris.kecamatan, TiketBaris.desa,
                   TiketBaris.kabupaten_norm, TiketBaris.kecamatan_norm,
                   TiketBaris.desa_norm, TiketBaris.wet_kg,
                   TiketBaris.dry_kg, TiketBaris.reject_kg).where(
                *kondisi).order_by(
                TiketBaris.ticket_date.desc(),
                TiketBaris.ticket_no.desc(),
                TiketBaris.line_seq.asc())).mappings()

        tiket: dict[tuple, dict] = {}
        for r in mentah:
            k = (r["ticket_date"], r["ticket_no"])
            v = tiket.get(k)
            if v is None:
                tgl = _ke_tanggal_db(r["ticket_date"])
                v = tiket[k] = {
                    "tanggal": tgl.isoformat() if tgl else "",
                    "ticket_no": r["ticket_no"],
                    "kode_vendor": (r["kode_vendor"] or "").strip().upper(),
                    "nama_vendor": r["nama_vendor_asli"],
                    "item_code": set(),
                    "provinsi": r["provinsi"], "kabupaten": r["kabupaten"],
                    "kecamatan": r["kecamatan"], "desa": r["desa"],
                    "kabupaten_norm": (r["kabupaten_norm"] or
                                       normalisasi_kabupaten(r["kabupaten"])),
                    "kecamatan_norm": (r["kecamatan_norm"] or
                                       normalisasi_teks_wilayah(r["kecamatan"])),
                    "desa_norm": (r["desa_norm"] or
                                  normalisasi_teks_wilayah(r["desa"])),
                    "wet_kg": Decimal(0), "dry_kg": Decimal(0),
                    "reject_kg": Decimal(0), "jumlah_baris": 0,
                }
            if r["item_code"]:
                v["item_code"].add(r["item_code"])
            for kolom in ("wet_kg", "dry_kg", "reject_kg"):
                v[kolom] += Decimal(str(r[kolom] or 0))
            v["jumlah_baris"] += 1

        kunci_diminta = {(v["kabupaten_norm"], v["kecamatan_norm"],
                          v["desa_norm"]) for v in tiket.values()}
        peta_langsung, peta_koreksi = _peta_wilayah_scdf(session,
                                                         kunci_diminta)
        wilayah = {k: _wilayah_intake_tampil(v, peta_langsung, peta_koreksi)
                   for k, v in tiket.items()}
        nama_vendor = _nama_vendor_baku(session)

        urut = sorted(tiket.items(),
                      key=lambda kv: (kv[1]["tanggal"], kv[1]["ticket_no"]),
                      reverse=True)
        semua = []
        for k, v in urut:
            w = wilayah[k]
            kode = v["kode_vendor"]
            semua.append({
                "tanggal": v["tanggal"], "ticket_no": v["ticket_no"],
                "kode_vendor": kode,
                "label_vendor": (f"{kode} — {nama_vendor[kode]}"
                                 if nama_vendor.get(kode)
                                 else (v["nama_vendor"] or kode)),
                "grade": ", ".join(sorted(v["item_code"])) or None,
                "wet_ton": round(float(v["wet_kg"]) / 1000, 3),
                "dry_ton": round(float(v["dry_kg"]) / 1000, 3),
                "reject_ton": round(float(v["reject_kg"]) / 1000, 3),
                "jumlah_baris": v["jumlah_baris"],
                "provinsi": w["provinsi"], "kabupaten": w["kabupaten"],
                "kecamatan": w["kecamatan"], "desa": w["desa"],
                "sumber_wilayah": w["sumber_wilayah"],
            })

        terakhir = semua[0] if semua else None
        hari_ini = dt.date.today()
        ringkas = None
        if terakhir:
            tgl = dt.date.fromisoformat(terakhir["tanggal"])
            tiket_hari_itu = [b for b in semua
                              if b["tanggal"] == terakhir["tanggal"]]
            ringkas = {
                "tanggal": terakhir["tanggal"],
                "umur_hari": (hari_ini - tgl).days,
                "ticket_no": terakhir["ticket_no"],
                "label_vendor": terakhir["label_vendor"],
                "grade": terakhir["grade"],
                "dry_ton": terakhir["dry_ton"],
                "provinsi": terakhir["provinsi"],
                "kabupaten": terakhir["kabupaten"],
                "kecamatan": terakhir["kecamatan"],
                "desa": terakhir["desa"],
                "sumber_wilayah": terakhir["sumber_wilayah"],
                "jumlah_tiket_hari_itu": len(tiket_hari_itu),
                "dry_ton_hari_itu": round(
                    sum(b["dry_ton"] for b in tiket_hari_itu), 3),
            }
        baris = semua[:limit]

        if format == "xlsx":
            return respon_xlsx(
                "intake_terakhir.xlsx",
                ["Tanggal", "No tiket", "Kode vendor", "Vendor", "Grade",
                 "Wet ton", "Dry ton", "Reject ton", "Provinsi",
                 "Kabupaten/Kota", "Kecamatan", "Desa"],
                [[b["tanggal"], b["ticket_no"], b["kode_vendor"],
                  b["label_vendor"], b["grade"], b["wet_ton"], b["dry_ton"],
                  b["reject_ton"], b["provinsi"], b["kabupaten"],
                  b["kecamatan"], b["desa"]] for b in baris])

        return {"terakhir": ringkas, "baris": baris, "limit": limit,
                "jumlah_tiket_total": len(semua),
                "tanggal_pertama": semua[-1]["tanggal"] if semua else None,
                "filter": {"dari": dari, "sampai": sampai,
                           "vendor": kode_diminta, "limit": limit},
                "pilihan_vendor": opsi["pilihan_vendor"],
                "batas_data": opsi["batas_data"],
                "catatan_wilayah": CATATAN_WILAYAH_INTAKE_TERAKHIR}

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
