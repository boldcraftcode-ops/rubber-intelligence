"""API daftar dan koreksi baris intake.

Perubahan pada tiket dicatat ke audit log. Ticket No, nomor urut, Asal Getah
asli, sidik sumber, dan hubungan ke unggahan sengaja tidak dapat diubah dari
layar ini; koreksi hanya memperbarui kolom operasional yang dipilih.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import secrets
import threading
import time
from decimal import Decimal

import openpyxl
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .api_traceability import (kabupaten_memiliki_provinsi,
                               muat_referensi_bawaan)
from .auth_lokal import info_pengguna, wajib_admin
from .core.alarm import catat_audit, evaluasi_alarm
from .core.traceability import normalisasi_kabupaten, normalisasi_teks_wilayah
from .mart import bangun_mart
from .models import ReferensiWilayahTrace, TiketBaris


class IntakeUbah(BaseModel):
    ticket_date: dt.date | None = None
    kode_vendor: str | None = Field(default=None, max_length=20)
    nama_vendor_asli: str | None = Field(default=None, max_length=200)
    vehicle_no: str | None = Field(default=None, max_length=50)
    item_code: str | None = Field(default=None, max_length=50)
    drc_date: dt.date | None = None
    wet_kg: float | None = Field(default=None, ge=0, le=99_999_999_999.999)
    sample_kg: float | None = Field(default=None, ge=0, le=99_999_999_999.999)
    reject_kg: float | None = Field(default=None, ge=0, le=99_999_999_999.999)
    drc_pct: float | None = Field(default=None, ge=0, le=100)
    dry_kg: float | None = Field(default=None, ge=0, le=99_999_999_999.999)
    provinsi: str | None = Field(default=None, max_length=100)
    kabupaten: str | None = Field(default=None, max_length=100)
    kecamatan: str | None = Field(default=None, max_length=100)
    desa: str | None = Field(default=None, max_length=100)
    bin: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=50)


_KOLOM_UBAH = tuple(IntakeUbah.model_fields)
_KOLOM_CEPAT = _KOLOM_UBAH
_KOLOM_WAJIB = ("ticket_date", "kode_vendor")
_KOLOM_NUMERIK = {"wet_kg", "sample_kg", "reject_kg", "drc_pct", "dry_kg"}
_KOLOM_DESIMAL = {"wet_kg", "sample_kg", "reject_kg", "dry_kg"}
_BATAS_QUICK_FILL = 500
_UMUR_PRATINJAU = 15 * 60  # detik
#: Token pratinjau quick-fill. Hanya di memori proses; tidak ada tabel baru.
_PRATINJAU_QUICK_FILL: dict[str, dict] = {}
_KUNCI_QUICK_FILL = threading.Lock()
_BATAS_EXCEL_BARIS = 500
_MAKS_EXCEL_MB = 5
_PRATINJAU_EXCEL: dict[str, dict] = {}
_KUNCI_EXCEL = threading.Lock()

_LABEL_EXCEL = {
    "ticket_date": "Tanggal tiket",
    "kode_vendor": "Kode supplier",
    "nama_vendor_asli": "Nama supplier",
    "vehicle_no": "Nomor kendaraan",
    "item_code": "Item / grade",
    "drc_date": "Tanggal DRC",
    "wet_kg": "Wet (kg)",
    "sample_kg": "Sample (kg)",
    "reject_kg": "Reject (kg)",
    "drc_pct": "DRC (%)",
    "dry_kg": "Dry (kg)",
    "provinsi": "Provinsi",
    "kabupaten": "Kabupaten/Kota",
    "kecamatan": "Kecamatan / Sub-district",
    "desa": "Desa",
    "bin": "Bin",
    "location": "Location",
}
_KOLOM_IDENTITAS_EXCEL = ("id", "ticket_no", "line_seq")
_KOLOM_LINDUNG_EXCEL = ("asal_getah", "source_fingerprint", "unggahan_id", "peringatan")
_KOLOM_DIIZINKAN_EXCEL = (
    set(_KOLOM_IDENTITAS_EXCEL) | set(_KOLOM_LINDUNG_EXCEL) | set(_KOLOM_UBAH)
)


def _norm_kunci_excel(nilai) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(nilai or "").strip().lower()).strip("_")


_ALIAS_EXCEL = {_norm_kunci_excel(k): k for k in _KOLOM_DIIZINKAN_EXCEL}
_ALIAS_EXCEL.update({_norm_kunci_excel(v): k for k, v in _LABEL_EXCEL.items()})
_ALIAS_EXCEL.update({
    "baris": "line_seq",
    "id_baris": "id",
    "no_tiket": "ticket_no",
})


class QuickFillMasuk(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=_BATAS_QUICK_FILL)
    kolom: str
    nilai: str | None = None
    kosongkan: bool = False


class QuickFillTerapkan(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class ExcelTerapkan(BaseModel):
    token: str = Field(min_length=1, max_length=200)


def _nilai_tampil(nilai):
    if isinstance(nilai, dt.date):
        return nilai.isoformat()
    if isinstance(nilai, Decimal):
        return float(nilai)
    return nilai


def _nilai_akhir(kolom: str, nilai):
    if isinstance(nilai, str):
        return nilai.strip() or None
    if nilai is not None and kolom in _KOLOM_NUMERIK:
        return float(nilai)
    return nilai


def _nilai_db(kolom: str, nilai):
    if nilai is not None and kolom in _KOLOM_DESIMAL:
        return Decimal(str(nilai))
    return nilai


def _bersih_pratinjau() -> None:
    batas = time.time() - _UMUR_PRATINJAU
    with _KUNCI_QUICK_FILL:
        for token, entri in list(_PRATINJAU_QUICK_FILL.items()):
            if entri["dibuat"] < batas:
                _PRATINJAU_QUICK_FILL.pop(token, None)
    with _KUNCI_EXCEL:
        for token, entri in list(_PRATINJAU_EXCEL.items()):
            if entri["dibuat"] < batas:
                _PRATINJAU_EXCEL.pop(token, None)


def _ke_int_excel(nilai):
    """ID/line_seq dari sel Excel boleh int, float bulat, atau teks angka."""
    if isinstance(nilai, bool):
        return None
    if isinstance(nilai, int):
        return nilai
    if isinstance(nilai, float) and nilai.is_integer():
        return int(nilai)
    if isinstance(nilai, Decimal) and nilai == nilai.to_integral_value():
        return int(nilai)
    if isinstance(nilai, str) and nilai.strip().isdigit():
        return int(nilai.strip())
    return None


def _sel_ke_mentah(nilai):
    """Ubah sel Excel menjadi nilai mentah yang bisa divalidasi IntakeUbah."""
    if nilai is None:
        return None
    if isinstance(nilai, bool):
        raise ValueError("Sel berisi TRUE/FALSE tidak didukung; isi teks/angka/tanggal.")
    if isinstance(nilai, dt.datetime):
        return nilai.date().isoformat()
    if isinstance(nilai, dt.date):
        return nilai.isoformat()
    if isinstance(nilai, (int, float, Decimal)):
        return str(nilai)
    teks = str(nilai).strip()
    return teks or None


def _baca_excel_koreksi(isi: bytes) -> list[dict]:
    """Baca sheet 'Koreksi' (atau sheet aktif) jadi rekaman per baris."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(isi), read_only=True, data_only=True)
    except Exception as e:
        raise HTTPException(422, "File Excel tidak bisa dibuka. Pastikan .xlsx tidak rusak/terkunci password.") from e
    try:
        ws = wb["Koreksi"] if "Koreksi" in wb.sheetnames else wb.active
        iterator = ws.iter_rows(values_only=True)
        try:
            header = next(iterator)
        except StopIteration as e:
            raise HTTPException(422, "Sheet 'Koreksi' kosong. Unduh template lalu isi kembali.") from e

        asing = [
            str(j).strip() for j in header
            if j is not None and str(j).strip() and _norm_kunci_excel(j) not in _ALIAS_EXCEL
        ]
        if asing:
            raise HTTPException(422, "Kolom tidak dikenal: " + ", ".join(asing[:5]) +
                                ". Pakai header dari template koreksi intake.")

        peta: dict[str, int] = {}
        for idx, judul in enumerate(header):
            kunci = _ALIAS_EXCEL.get(_norm_kunci_excel(judul))
            if not kunci:
                continue
            if kunci in peta:
                raise HTTPException(422, f"Kolom {kunci} muncul lebih dari sekali pada header.")
            peta[kunci] = idx
        if "id" not in peta:
            raise HTTPException(422, "Template wajib memiliki kolom ID.")

        rekaman: list[dict] = []
        for nomor, nilai in enumerate(iterator, start=2):
            if all(v is None or (isinstance(v, str) and not v.strip()) for v in nilai):
                continue
            rek = {kunci: (nilai[idx] if idx < len(nilai) else None)
                   for kunci, idx in peta.items()}
            rek["_no_baris"] = nomor
            rekaman.append(rek)
            if len(rekaman) > _BATAS_EXCEL_BARIS:
                raise HTTPException(422, f"Maksimal {_BATAS_EXCEL_BARIS} baris per file Excel. Pecah filenya.")
        return rekaman
    finally:
        wb.close()


_KOLOM_CARI = (
    TiketBaris.ticket_no, TiketBaris.kode_vendor, TiketBaris.nama_vendor_asli,
    TiketBaris.vehicle_no, TiketBaris.item_code, TiketBaris.provinsi,
    TiketBaris.kabupaten, TiketBaris.kecamatan, TiketBaris.desa,
)


def _baris(row: TiketBaris) -> dict:
    return {
        "id": row.id,
        "ticket_no": row.ticket_no,
        "line_seq": row.line_seq,
        "ticket_date": row.ticket_date.isoformat() if row.ticket_date else None,
        "kode_vendor": row.kode_vendor,
        "nama_vendor_asli": row.nama_vendor_asli,
        "vehicle_no": row.vehicle_no,
        "item_code": row.item_code,
        "drc_date": row.drc_date.isoformat() if row.drc_date else None,
        "wet_kg": float(row.wet_kg) if row.wet_kg is not None else None,
        "sample_kg": float(row.sample_kg) if row.sample_kg is not None else None,
        "reject_kg": float(row.reject_kg) if row.reject_kg is not None else None,
        "drc_pct": row.drc_pct,
        "dry_kg": float(row.dry_kg) if row.dry_kg is not None else None,
        "provinsi": row.provinsi,
        "kabupaten": row.kabupaten,
        "kecamatan": row.kecamatan,
        "desa": row.desa,
        "asal_getah": row.asal_getah,
        "bin": row.bin,
        "location": row.location,
        "peringatan": row.peringatan,
    }


def pasang_router_intake(app, ambil_session):
    router = APIRouter(prefix="/api/intake")
    dep = Depends(ambil_session)

    def filter_provinsi(query, provinsi: str):
        kunci = normalisasi_teks_wilayah(provinsi).replace(" ", "")
        return query.where(
            func.replace(func.upper(func.trim(TiketBaris.provinsi)), " ", "") == kunci)

    @router.get("/options/provinsi")
    def pilihan_provinsi(session: Session = dep):
        """Opsi dropdown provinsi hanya dari nilai yang benar-benar ada di intake."""
        nilai = func.trim(TiketBaris.provinsi)
        rows = session.scalars(select(nilai).where(
            TiketBaris.provinsi.is_not(None), nilai != "")
            .distinct().order_by(nilai).limit(100)).all()
        return {"options": [str(x) for x in rows if x]}

    @router.get("/options/supplier")
    def pilihan_supplier(q: str = Query(min_length=2, max_length=100),
                         tahun: int | None = Query(default=None, ge=1900, le=2200),
                         provinsi: str | None = Query(default=None, max_length=100),
                         session: Session = dep):
        """Opsi supplier autocomplete: prefix search, maksimum 50 nama."""
        query = select(TiketBaris.nama_vendor_asli).where(
            TiketBaris.nama_vendor_asli.is_not(None),
            func.trim(TiketBaris.nama_vendor_asli) != "",
            TiketBaris.nama_vendor_asli.ilike(f"{q.strip()}%"))
        if tahun is not None:
            query = query.where(
                TiketBaris.ticket_date >= dt.date(tahun, 1, 1),
                TiketBaris.ticket_date <= dt.date(tahun, 12, 31))
        if provinsi and provinsi.strip():
            query = filter_provinsi(query, provinsi)
        rows = session.scalars(query.distinct()
                               .order_by(TiketBaris.nama_vendor_asli).limit(51)).all()
        return {"options": [str(x) for x in rows[:50]], "has_more": len(rows) > 50}

    def pastikan_referensi_scdf(session: Session) -> None:
        # Pakai referensi SCDF yang sama dengan Traceability; tidak mengambil
        # provinsi dari intake maupun data collector. Crosswalk resmi dipasang
        # di sini (idempoten) bila tabel referensi sudah skala penuh.
        muat_referensi_bawaan(session)

    def provinsi_tersedia(session: Session) -> bool:
        return session.scalar(select(ReferensiWilayahTrace.id).where(
            ReferensiWilayahTrace.provinsi_norm.is_not(None),
            ReferensiWilayahTrace.provinsi.is_not(None)).limit(1)) is not None

    def filter_provinsi_scdf(query, provinsi: str | None, tersedia: bool):
        """Ikat dropdown ke Provinsi crosswalk, tanpa menyembunyikan baris SCDF
        yang memang belum punya pemetaan resmi (mis. `BANJAR`, `DANAU`)."""
        if provinsi and provinsi.strip() and tersedia:
            norm = normalisasi_teks_wilayah(provinsi)
            return query.where(or_(
                ReferensiWilayahTrace.provinsi_norm == norm,
                ReferensiWilayahTrace.provinsi_norm.is_(None)))
        return query

    def _validasi_perubahan(row: TiketBaris, perubahan: dict, session: Session) -> dict:
        """Validasi koreksi tanpa mengubah baris. Mengembalikan perubahan ternormalisasi."""
        if not perubahan:
            raise HTTPException(422, "Tidak ada perubahan untuk disimpan.")
        if "ticket_date" in perubahan and perubahan["ticket_date"] is None:
            raise HTTPException(422, "Tanggal tiket wajib diisi.")
        if "kode_vendor" in perubahan:
            kode = (perubahan["kode_vendor"] or "").strip().upper()
            if not kode:
                raise HTTPException(422, "Kode supplier wajib diisi.")
            perubahan["kode_vendor"] = kode

        kolom_wilayah = ("provinsi", "kabupaten", "kecamatan", "desa")
        wilayah_baru = {
            kolom: (perubahan.get(kolom, getattr(row, kolom)) or "").strip()
            for kolom in kolom_wilayah
        }
        wilayah_berubah = any(
            kolom in perubahan and wilayah_baru[kolom] != (getattr(row, kolom) or "").strip()
            for kolom in kolom_wilayah
        )
        if wilayah_berubah:
            pastikan_referensi_scdf(session)
            ada_provinsi_scdf = provinsi_tersedia(session)
            provinsi_norm = normalisasi_teks_wilayah(wilayah_baru["provinsi"])
            kabupaten_norm = normalisasi_kabupaten(wilayah_baru["kabupaten"])
            kecamatan_norm = normalisasi_teks_wilayah(wilayah_baru["kecamatan"])
            desa_norm = normalisasi_teks_wilayah(wilayah_baru["desa"])

            # Provinsi hanya dianggap sah bila benar-benar ada pada crosswalk
            # resmi, bukan sekadar nilai lama pada baris intake.
            provinsi_resmi = bool(ada_provinsi_scdf and provinsi_norm and
                session.scalar(select(ReferensiWilayahTrace.id).where(
                    ReferensiWilayahTrace.provinsi_norm == provinsi_norm).limit(1)) is not None)
            kabupaten_terhubung = bool(ada_provinsi_scdf and kabupaten_norm and
                kabupaten_memiliki_provinsi(session, kabupaten_norm))
            # Baris SCDF yang tidak punya pemetaan (BANJAR, DANAU, dsb.) tidak
            # ditebak provinsinya; ikatan hierarki dipakai hanya bila kedua
            # kunci memang berasal dari crosswalk.
            ikat_provinsi = provinsi_resmi and kabupaten_terhubung

            provinsi_diubah = (
                "provinsi" in perubahan and
                wilayah_baru["provinsi"] != (row.provinsi or "").strip()
            )
            if provinsi_diubah and wilayah_baru["provinsi"]:
                if not ada_provinsi_scdf:
                    raise HTTPException(422,
                        "Provinsi tidak dapat dikoreksi: referensi SCDF yang termuat belum menyediakan Provinsi.")
                if not provinsi_resmi:
                    raise HTTPException(422, "Provinsi tidak ditemukan pada referensi SCDF.")
                if kabupaten_norm and not kabupaten_terhubung:
                    raise HTTPException(422,
                        "Provinsi tidak dapat dikoreksi: Kabupaten/Kota ini belum memiliki "
                        "pemetaan Provinsi pada crosswalk resmi SCDF.")

            if kabupaten_norm:
                q_ref = select(ReferensiWilayahTrace.id).where(
                    ReferensiWilayahTrace.kabupaten_norm == kabupaten_norm)
                if ikat_provinsi:
                    q_ref = q_ref.where(ReferensiWilayahTrace.provinsi_norm == provinsi_norm)
                if session.scalar(q_ref.limit(1)) is None:
                    raise HTTPException(422,
                        "Kabupaten/Kota tidak ditemukan pada referensi SCDF untuk Provinsi tersebut."
                        if ikat_provinsi else
                        "Kabupaten/Kota tidak ditemukan pada referensi SCDF.")

                if kecamatan_norm:
                    q_ref = select(ReferensiWilayahTrace.id).where(
                        ReferensiWilayahTrace.kabupaten_norm == kabupaten_norm,
                        ReferensiWilayahTrace.kecamatan_norm == kecamatan_norm)
                    if ikat_provinsi:
                        q_ref = q_ref.where(ReferensiWilayahTrace.provinsi_norm == provinsi_norm)
                    if session.scalar(q_ref.limit(1)) is None:
                        raise HTTPException(422, "Kecamatan tidak ditemukan pada Kabupaten/Kota di referensi SCDF.")

                    if desa_norm:
                        q_ref = select(ReferensiWilayahTrace.id).where(
                            ReferensiWilayahTrace.kabupaten_norm == kabupaten_norm,
                            ReferensiWilayahTrace.kecamatan_norm == kecamatan_norm,
                            ReferensiWilayahTrace.desa_norm == desa_norm)
                        if ikat_provinsi:
                            q_ref = q_ref.where(ReferensiWilayahTrace.provinsi_norm == provinsi_norm)
                        if session.scalar(q_ref.limit(1)) is None:
                            raise HTTPException(422, "Desa tidak ditemukan pada pasangan Kabupaten/Kecamatan di referensi SCDF.")
        return perubahan

    def _terapkan_perubahan(row: TiketBaris, perubahan: dict, session: Session):
        """Terapkan koreksi tervalidasi; kembalikan (sebelumnya, sesudah) untuk audit."""
        perubahan = _validasi_perubahan(row, perubahan, session)
        sebelumnya: dict[str, object] = {}
        sesudah: dict[str, object] = {}
        for kolom, nilai in perubahan.items():
            lama = getattr(row, kolom)
            if isinstance(lama, Decimal):
                lama = float(lama)
            nilai = _nilai_akhir(kolom, nilai)
            sebelumnya[kolom] = _nilai_tampil(lama)
            sesudah[kolom] = _nilai_tampil(nilai)
            setattr(row, kolom, _nilai_db(kolom, nilai))

        if "wet_kg" in perubahan:
            row.tiket_nol = row.wet_kg is not None and float(row.wet_kg) == 0
        if any(k in perubahan for k in ("kabupaten", "kecamatan", "desa")):
            row.kabupaten_norm = normalisasi_kabupaten(row.kabupaten)
            row.kecamatan_norm = normalisasi_teks_wilayah(row.kecamatan)
            row.desa_norm = normalisasi_teks_wilayah(row.desa)
        return sebelumnya, sesudah

    @router.get("/options/scdf/provinsi")
    def pilihan_scdf_provinsi(session: Session = dep):
        pastikan_referensi_scdf(session)
        tersedia = provinsi_tersedia(session)
        rows = session.execute(
            select(ReferensiWilayahTrace.provinsi_norm,
                   func.min(ReferensiWilayahTrace.provinsi).label("label"))
            .where(ReferensiWilayahTrace.provinsi_norm.is_not(None),
                   ReferensiWilayahTrace.provinsi.is_not(None))
            .group_by(ReferensiWilayahTrace.provinsi_norm)
            .order_by(ReferensiWilayahTrace.provinsi_norm)
        ).all()
        return {
            "options": [{"value": label, "label": label} for _, label in rows if label],
            "available": tersedia,
            "catatan": None if tersedia else
                "Referensi SCDF yang termuat belum menyediakan Provinsi; nilai intake yang ada tidak digunakan sebagai opsi.",
        }

    @router.get("/options/scdf/kabupaten")
    def pilihan_scdf_kabupaten(provinsi: str | None = Query(default=None, max_length=120),
                               session: Session = dep):
        pastikan_referensi_scdf(session)
        tersedia = provinsi_tersedia(session)
        query = select(ReferensiWilayahTrace.kabupaten_norm,
                       func.min(ReferensiWilayahTrace.kabupaten).label("label"))
        query = filter_provinsi_scdf(query, provinsi, tersedia)
        rows = session.execute(
            query.group_by(ReferensiWilayahTrace.kabupaten_norm)
            .order_by(ReferensiWilayahTrace.kabupaten_norm)
        ).all()
        return {
            "options": [{"value": label, "label": label} for _, label in rows if label],
            "province_linked": tersedia,
        }

    @router.get("/options/scdf/kecamatan")
    def pilihan_scdf_kecamatan(kabupaten: str = Query(min_length=1, max_length=120),
                               provinsi: str | None = Query(default=None, max_length=120),
                               session: Session = dep):
        pastikan_referensi_scdf(session)
        tersedia = provinsi_tersedia(session)
        query = select(ReferensiWilayahTrace.kecamatan_norm,
                       func.min(ReferensiWilayahTrace.kecamatan).label("label")).where(
            ReferensiWilayahTrace.kabupaten_norm == normalisasi_kabupaten(kabupaten))
        query = filter_provinsi_scdf(query, provinsi, tersedia)
        rows = session.execute(
            query.group_by(ReferensiWilayahTrace.kecamatan_norm)
            .order_by(ReferensiWilayahTrace.kecamatan_norm)
        ).all()
        return {"options": [{"value": label, "label": label} for _, label in rows if label]}

    @router.get("/options/scdf/desa")
    def pilihan_scdf_desa(kabupaten: str = Query(min_length=1, max_length=120),
                          kecamatan: str = Query(min_length=1, max_length=120),
                          provinsi: str | None = Query(default=None, max_length=120),
                          session: Session = dep):
        pastikan_referensi_scdf(session)
        tersedia = provinsi_tersedia(session)
        query = select(ReferensiWilayahTrace.desa_norm,
                       func.min(ReferensiWilayahTrace.desa).label("label")).where(
            ReferensiWilayahTrace.kabupaten_norm == normalisasi_kabupaten(kabupaten),
            ReferensiWilayahTrace.kecamatan_norm == normalisasi_teks_wilayah(kecamatan))
        query = filter_provinsi_scdf(query, provinsi, tersedia)
        rows = session.execute(
            query.group_by(ReferensiWilayahTrace.desa_norm)
            .order_by(ReferensiWilayahTrace.desa_norm)
        ).all()
        return {"options": [{"value": label, "label": label} for _, label in rows if label]}

    @router.get("")
    def daftar_intake(tahun: int | None = Query(default=None, ge=1900, le=2200),
                      provinsi: str | None = Query(default=None, max_length=100),
                      supplier: str | None = Query(default=None, max_length=200),
                      q: str = Query(default="", max_length=200),
                      page: int = Query(default=1, ge=1),
                      page_size: int = Query(default=50, ge=1, le=100),
                      session: Session = dep):
        """Cari intake server-side; minimal satu dari tiga filter utama wajib."""
        if tahun is None and not (provinsi or "").strip() and not (supplier or "").strip():
            raise HTTPException(422,
                "Terapkan minimal satu filter: tahun, provinsi, atau nama supplier.")
        query = select(TiketBaris)
        if tahun is not None:
            query = query.where(
                TiketBaris.ticket_date >= dt.date(tahun, 1, 1),
                TiketBaris.ticket_date <= dt.date(tahun, 12, 31))
        if provinsi and provinsi.strip():
            query = filter_provinsi(query, provinsi)
        if supplier and supplier.strip():
            query = query.where(TiketBaris.nama_vendor_asli == supplier.strip())
        kata = q.strip()
        if kata:
            pola = f"%{kata}%"
            query = query.where(or_(*(kolom.ilike(pola) for kolom in _KOLOM_CARI)))
        total = int(session.scalar(
            select(func.count()).select_from(query.subquery())) or 0)
        baris = list(session.scalars(
            query.order_by(TiketBaris.ticket_date.desc(), TiketBaris.id.desc())
            .offset((page - 1) * page_size).limit(page_size)))
        return {
            "baris": [_baris(row) for row in baris],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    @router.post("/quick-fill/pratinjau")
    def pratinjau_quick_fill(data: QuickFillMasuk, request: Request,
                             session: Session = dep):
        """Hitung diff untuk satu kolom pada banyak baris; belum ada data disimpan."""
        wajib_admin(request)
        _bersih_pratinjau()
        kolom = (data.kolom or "").strip()
        if kolom not in _KOLOM_CEPAT:
            raise HTTPException(422, "Kolom quick-fill tidak dikenal.")
        ids = list(dict.fromkeys(data.ids))
        if any(i <= 0 for i in ids):
            raise HTTPException(422, "ID baris intake tidak valid.")
        if data.kosongkan and kolom in _KOLOM_WAJIB:
            raise HTTPException(422, f"Kolom {kolom} wajib diisi, tidak boleh dikosongkan.")
        nilai_mentah = None if data.kosongkan else (data.nilai or "").strip()
        if not data.kosongkan and nilai_mentah == "":
            raise HTTPException(422, "Isi nilai baru atau centang 'Kosongkan nilai'.")
        try:
            model = IntakeUbah(**{kolom: nilai_mentah})
        except ValidationError as e:
            pesan = e.errors()[0].get("msg", "nilai tidak valid") if e.errors() else "nilai tidak valid"
            raise HTTPException(422, f"Nilai untuk kolom {kolom} tidak valid: {pesan}") from e
        perubahan = model.model_dump(exclude_unset=True)

        rows = []
        hilang = []
        for row_id in ids:
            row = session.get(TiketBaris, row_id)
            if row is None:
                hilang.append(row_id)
            else:
                rows.append(row)
        if hilang:
            raise HTTPException(404, f"Baris intake tidak ditemukan: {hilang[:5]}")

        baris = []
        galat = []
        for row in rows:
            perubahan_baris = dict(perubahan)
            try:
                _validasi_perubahan(row, perubahan_baris, session)
            except HTTPException as e:
                galat.append({
                    "id": row.id, "ticket_no": row.ticket_no, "line_seq": row.line_seq,
                    "alasan": str(e.detail),
                })
                continue
            lama = _nilai_tampil(getattr(row, kolom))
            baru = _nilai_tampil(_nilai_akhir(kolom, perubahan_baris[kolom]))
            baris.append({
                "id": row.id, "ticket_no": row.ticket_no, "line_seq": row.line_seq,
                "sebelumnya": lama, "sesudah": baru, "berubah": lama != baru,
            })

        if galat:
            return {
                "status": "ada_galat", "token": None, "kolom": kolom,
                "jumlah": len(ids), "berubah": sum(1 for b in baris if b["berubah"]),
                "baris": baris, "galat": galat,
                "pesan": f"{len(galat)} baris ditolak pada pratinjau; tidak ada perubahan disimpan.",
            }

        token = secrets.token_urlsafe(18)
        with _KUNCI_QUICK_FILL:
            _PRATINJAU_QUICK_FILL[token] = {
                "ids": ids, "kolom": kolom, "perubahan": perubahan,
                "sebelumnya": {b["id"]: b["sebelumnya"] for b in baris},
                "dibuat": time.time(),
            }
        return {
            "status": "siap", "token": token, "kolom": kolom,
            "jumlah": len(ids), "berubah": sum(1 for b in baris if b["berubah"]),
            "baris": baris, "galat": [],
            "kedaluwarsa_detik": _UMUR_PRATINJAU,
            "pesan": f"Pratinjau {len(ids)} baris siap. {sum(1 for b in baris if b['berubah'])} baris akan berubah; konfirmasi untuk menyimpan.",
        }

    @router.post("/quick-fill/terapkan")
    def terapkan_quick_fill(data: QuickFillTerapkan, request: Request,
                            session: Session = dep):
        """Simpan seluruh pratinjau dalam satu transaksi; token hanya sekali pakai."""
        wajib_admin(request)
        _bersih_pratinjau()
        with _KUNCI_QUICK_FILL:
            entri = _PRATINJAU_QUICK_FILL.pop(data.token, None)
        if entri is None:
            raise HTTPException(404, "Pratinjau tidak ditemukan, kedaluwarsa, atau sudah diterapkan. Buat pratinjau baru.")

        ids = entri["ids"]
        kolom = entri["kolom"]
        perubahan = entri["perubahan"]
        sebelumnya = entri["sebelumnya"]
        rows = []
        for row_id in ids:
            row = session.get(TiketBaris, row_id)
            if row is None:
                raise HTTPException(409, f"Baris {row_id} sudah tidak ada. Buat pratinjau baru.")
            if _nilai_tampil(getattr(row, kolom)) != sebelumnya.get(row_id):
                raise HTTPException(409, f"Data baris {row_id} berubah sejak pratinjau. Buat pratinjau baru.")
            rows.append(row)

        pengguna = info_pengguna(request) or {}
        siapa = pengguna.get("sub") or "pengguna aplikasi"
        for row in rows:
            sebelum_baris, sesudah_baris = _terapkan_perubahan(row, dict(perubahan), session)
            catat_audit(session, siapa, "ubah_massal", "intake_tiket", {
                "token": data.token, "kolom": kolom,
                "id": row.id, "ticket_no": row.ticket_no, "line_seq": row.line_seq,
                "sebelumnya": sebelum_baris, "sesudah": sesudah_baris,
            })
        bangun_mart(session)
        evaluasi_alarm(session)
        session.commit()
        return {
            "status": "tersimpan", "jumlah": len(rows), "kolom": kolom,
            "pesan": f"{len(rows)} baris intake diperbarui lewat quick-fill; ringkasan dan alarm disegarkan.",
        }

    @router.delete("/quick-fill/pratinjau/{token}")
    def batalkan_quick_fill(token: str, request: Request):
        wajib_admin(request)
        _bersih_pratinjau()
        with _KUNCI_QUICK_FILL:
            ada = _PRATINJAU_QUICK_FILL.pop(token, None) is not None
        return {
            "status": "dibatalkan" if ada else "tidak_ada",
            "pesan": "Pratinjau dibatalkan." if ada else "Pratinjau sudah tidak tersedia.",
        }

    @router.get("/excel-diff/template")
    def template_excel_diff(tahun: int | None = Query(default=None, ge=1900, le=2200),
                            provinsi: str | None = Query(default=None, max_length=100),
                            supplier: str | None = Query(default=None, max_length=200),
                            q: str = Query(default="", max_length=200),
                            kosong: bool = Query(default=False),
                            session: Session = dep):
        """Unduh Excel koreksi: berisi baris filter saat ini, atau template kosong."""
        if not kosong and tahun is None and not (provinsi or "").strip() and not (supplier or "").strip():
            raise HTTPException(422,
                "Terapkan minimal satu filter: tahun, provinsi, atau nama supplier.")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Koreksi"
        judul = ["ID", "Ticket No", "Baris"] + [_LABEL_EXCEL[k] for k in _KOLOM_UBAH]
        ws.append(judul)
        tebal = Font(bold=True)
        biru = PatternFill("solid", fgColor="D7E7FF")
        for sel in ws[1]:
            sel.font, sel.fill = tebal, biru
            sel.alignment = Alignment(vertical="top", wrap_text=True)
        for i, _ in enumerate(judul, start=1):
            ws.column_dimensions[get_column_letter(i)].width = 22 if i > 3 else 14
        ws.freeze_panes = "A2"

        total = 0
        terpotong = False
        jumlah = 0
        if not kosong:
            query = select(TiketBaris)
            if tahun is not None:
                query = query.where(
                    TiketBaris.ticket_date >= dt.date(tahun, 1, 1),
                    TiketBaris.ticket_date <= dt.date(tahun, 12, 31))
            if provinsi and provinsi.strip():
                query = filter_provinsi(query, provinsi)
            if supplier and supplier.strip():
                query = query.where(TiketBaris.nama_vendor_asli == supplier.strip())
            kata = q.strip()
            if kata:
                pola = f"%{kata}%"
                query = query.where(or_(*(kolom.ilike(pola) for kolom in _KOLOM_CARI)))
            total = int(session.scalar(
                select(func.count()).select_from(query.subquery())) or 0)
            baris = list(session.scalars(
                query.order_by(TiketBaris.ticket_date.desc(), TiketBaris.id.desc())
                .limit(_BATAS_EXCEL_BARIS)))
            jumlah = len(baris)
            terpotong = total > _BATAS_EXCEL_BARIS
            for row in baris:
                ws.append([row.id, row.ticket_no, row.line_seq] + [
                    _nilai_tampil(getattr(row, kolom)) for kolom in _KOLOM_UBAH
                ])

        petunjuk = wb.create_sheet("Petunjuk")
        petunjuk.append(["Alur Excel diff koreksi intake"])
        if kosong:
            keterangan = [
                "Ini TEMPLATE KOSONG hanya untuk melihat format header.",
                "Jangan langsung dipakai untuk pratinjau: sel kosong pada 17 kolom akan diartikan menghapus nilai opsional.",
                "Gunakan tombol 'Unduh Excel baris filter ini' agar semua nilai lama ikut terisi, lalu ubah hanya sel yang perlu.",
            ]
        else:
            keterangan = [
                f"File berisi {jumlah} dari {total} baris yang cocok dengan filter (maksimal {_BATAS_EXCEL_BARIS} baris).",
                "Nilai 17 kolom sudah terisi sesuai database. Ubah hanya sel yang ingin dikoreksi.",
                "Kosongkan sel untuk menghapus nilai opsional; jangan mengosongkan Tanggal tiket atau Kode supplier.",
            ]
            if terpotong:
                keterangan.append("Filter menghasilkan lebih dari 500 baris; persempit filter untuk mengambil sisanya.")
        for teks in keterangan + [
            "Kolom ID wajib. Ticket No dan Baris hanya penanda; bila diisi harus cocok dengan database.",
            "17 kolom operasional bisa diubah: " + ", ".join(_LABEL_EXCEL[k] for k in _KOLOM_UBAH) + ".",
            "Unggah .xlsx, tekan Pratinjau. Belum ada data tersimpan sampai konfirmasi.",
            "Blok hijau 'Konfirmasi pratinjau' → 'Konfirmasi & terapkan X perubahan' → OK pada dialog browser.",
            f"Maksimal {_BATAS_EXCEL_BARIS} baris / {_MAKS_EXCEL_MB} MB; token {_UMUR_PRATINJAU // 60} menit sekali pakai; hanya admin.",
            "ticket_no, line_seq, asal_getah, source_fingerprint, unggahan_id, peringatan, dan raw unggahan tidak diubah.",
            "Quick-fill tetap tersedia untuk nilai yang seragam; Excel diff untuk nilai berbeda-beda per baris.",
        ]:
            petunjuk.append([teks])
        petunjuk["A1"].font = tebal
        petunjuk.column_dimensions["A"].width = 120
        for baris in petunjuk.iter_rows(min_row=2):
            baris[0].alignment = Alignment(vertical="top", wrap_text=True)

        buffer = io.BytesIO()
        wb.save(buffer)
        nama_file = ("template_koreksi_intake_kosong.xlsx" if kosong
                     else "koreksi_intake_filter.xlsx")
        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{nama_file}"'},
        )

    @router.post("/excel-diff/pratinjau")
    async def pratinjau_excel(request: Request, file: UploadFile = File(...),
                              session: Session = dep):
        """Baca Excel koreksi, validasi per baris, kembalikan diff sebelum → sesudah."""
        wajib_admin(request)
        _bersih_pratinjau()
        nama = (file.filename or "koreksi.xlsx").replace("\\", "/").split("/")[-1]
        if not nama.lower().endswith(".xlsx"):
            raise HTTPException(422, "Hanya file .xlsx yang diterima. Simpan/ekspor ulang sebagai .xlsx.")
        isi = await file.read()
        if not isi:
            raise HTTPException(422, "File kosong. Pilih file Excel yang benar.")
        if len(isi) > _MAKS_EXCEL_MB * 1024 * 1024:
            raise HTTPException(413, f"File melebihi {_MAKS_EXCEL_MB} MB. Pecah filenya.")
        rekaman = _baca_excel_koreksi(isi)
        if not rekaman:
            raise HTTPException(422, "Sheet 'Koreksi' hanya berisi header. Isi minimal satu baris ID.")

        baris_hasil: list[dict] = []
        galat: list[dict] = []
        per_baris: dict[int, dict] = {}
        sebelum: dict[int, dict] = {}
        terlihat: set[int] = set()
        jumlah_perubahan = 0

        for rek in rekaman:
            nomor = rek["_no_baris"]
            row_id = _ke_int_excel(rek.get("id"))
            if row_id is None or row_id <= 0:
                galat.append({"id": 0, "ticket_no": "-", "line_seq": 0,
                              "alasan": f"Baris {nomor}: ID tidak valid."})
                continue
            if row_id in terlihat:
                galat.append({"id": row_id, "ticket_no": "-", "line_seq": 0,
                              "alasan": f"Baris {nomor}: ID {row_id} muncul lebih dari sekali."})
                continue
            terlihat.add(row_id)
            row = session.get(TiketBaris, row_id)
            if row is None:
                galat.append({"id": row_id, "ticket_no": "-", "line_seq": 0,
                              "alasan": f"Baris {nomor}: ID {row_id} tidak ditemukan di database."})
                continue

            identitas_cocok = True
            if rek.get("ticket_no") is not None and str(rek["ticket_no"]).strip():
                if str(rek["ticket_no"]).strip() != (row.ticket_no or "").strip():
                    identitas_cocok = False
            if rek.get("line_seq") is not None and _ke_int_excel(rek["line_seq"]) != row.line_seq:
                identitas_cocok = False
            if not identitas_cocok:
                galat.append({"id": row.id, "ticket_no": row.ticket_no, "line_seq": row.line_seq,
                              "alasan": f"Baris {nomor}: Ticket No/Baris pada Excel tidak cocok dengan database."})
                continue

            mentah: dict[str, object] = {}
            for kolom in _KOLOM_UBAH:
                if kolom in rek:
                    try:
                        mentah[kolom] = _sel_ke_mentah(rek[kolom])
                    except ValueError as e:
                        galat.append({"id": row.id, "ticket_no": row.ticket_no,
                                      "line_seq": row.line_seq,
                                      "alasan": f"Baris {nomor}, kolom {_LABEL_EXCEL[kolom]}: {e}"})
                        mentah = {}
                        break
            if not mentah and any(k in rek for k in _KOLOM_UBAH):
                continue
            try:
                model = IntakeUbah(**mentah)
            except ValidationError as e:
                pesan = e.errors()[0].get("msg", "nilai tidak valid") if e.errors() else "nilai tidak valid"
                galat.append({"id": row.id, "ticket_no": row.ticket_no, "line_seq": row.line_seq,
                              "alasan": f"Baris {nomor}: nilai tidak valid — {pesan}"})
                continue
            parsed = model.model_dump(exclude_unset=True)
            if "kode_vendor" in parsed and isinstance(parsed["kode_vendor"], str):
                parsed["kode_vendor"] = parsed["kode_vendor"].strip().upper()

            perubahan: dict[str, object] = {}
            for kolom, nilai in parsed.items():
                lama = _nilai_tampil(getattr(row, kolom))
                baru = _nilai_tampil(_nilai_akhir(kolom, nilai))
                if lama != baru:
                    perubahan[kolom] = nilai
            if not perubahan:
                baris_hasil.append({"id": row.id, "ticket_no": row.ticket_no,
                                    "line_seq": row.line_seq, "perubahan": [], "berubah": False})
                continue
            try:
                tervalidasi = _validasi_perubahan(row, dict(perubahan), session)
            except HTTPException as e:
                galat.append({"id": row.id, "ticket_no": row.ticket_no, "line_seq": row.line_seq,
                              "alasan": f"Baris {nomor}: {e.detail}"})
                continue

            tampil: list[dict] = []
            for kolom, nilai in tervalidasi.items():
                lama = _nilai_tampil(getattr(row, kolom))
                baru = _nilai_tampil(_nilai_akhir(kolom, nilai))
                tampil.append({"kolom": kolom, "label": _LABEL_EXCEL[kolom],
                               "sebelumnya": lama, "sesudah": baru})
                sebelum.setdefault(row.id, {})[kolom] = lama
            per_baris[row.id] = tervalidasi
            jumlah_perubahan += len(tampil)
            baris_hasil.append({"id": row.id, "ticket_no": row.ticket_no,
                                "line_seq": row.line_seq, "perubahan": tampil, "berubah": True})

        berubah = sum(1 for b in baris_hasil if b["berubah"])
        if galat:
            return {
                "status": "ada_galat", "token": None, "nama_file": nama,
                "jumlah": len(rekaman), "berubah": berubah,
                "jumlah_perubahan": jumlah_perubahan,
                "baris": baris_hasil, "galat": galat,
                "pesan": f"{len(galat)} baris ditolak pada pratinjau; tidak ada perubahan disimpan.",
            }
        if not per_baris:
            return {
                "status": "kosong", "token": None, "nama_file": nama,
                "jumlah": len(rekaman), "berubah": 0, "jumlah_perubahan": 0,
                "baris": baris_hasil, "galat": [],
                "pesan": "Tidak ada nilai yang berubah. Samakan/isikan nilai baru pada Excel lalu pratinjau ulang.",
            }

        token = secrets.token_urlsafe(18)
        with _KUNCI_EXCEL:
            _PRATINJAU_EXCEL[token] = {
                "per_baris": per_baris, "sebelumnya": sebelum,
                "nama_file": nama, "dibuat": time.time(),
            }
        return {
            "status": "siap", "token": token, "nama_file": nama,
            "jumlah": len(rekaman), "berubah": berubah,
            "jumlah_perubahan": jumlah_perubahan,
            "baris": baris_hasil, "galat": [],
            "kedaluwarsa_detik": _UMUR_PRATINJAU,
            "pesan": f"Pratinjau {len(rekaman)} baris siap: {jumlah_perubahan} perubahan pada {berubah} baris. Konfirmasi untuk menyimpan.",
        }

    @router.post("/excel-diff/terapkan")
    def terapkan_excel(data: ExcelTerapkan, request: Request, session: Session = dep):
        """Simpan seluruh diff Excel dalam satu transaksi; token sekali pakai."""
        wajib_admin(request)
        _bersih_pratinjau()
        with _KUNCI_EXCEL:
            entri = _PRATINJAU_EXCEL.pop(data.token, None)
        if entri is None:
            raise HTTPException(404, "Pratinjau tidak ditemukan, kedaluwarsa, atau sudah diterapkan. Buat pratinjau baru.")

        pasangan: list[tuple[TiketBaris, dict]] = []
        for row_id, perubahan in entri["per_baris"].items():
            row = session.get(TiketBaris, row_id)
            if row is None:
                raise HTTPException(409, f"Baris {row_id} sudah tidak ada. Buat pratinjau baru.")
            for kolom, lama in entri["sebelumnya"].get(row_id, {}).items():
                if _nilai_tampil(getattr(row, kolom)) != lama:
                    raise HTTPException(409, f"Data baris {row_id} kolom {kolom} berubah sejak pratinjau. Buat pratinjau baru.")
            pasangan.append((row, perubahan))

        pengguna = info_pengguna(request) or {}
        siapa = pengguna.get("sub") or "pengguna aplikasi"
        jumlah_perubahan = 0
        try:
            for row, perubahan in pasangan:
                sebelum_baris, sesudah_baris = _terapkan_perubahan(row, dict(perubahan), session)
                jumlah_perubahan += len(sesudah_baris)
                catat_audit(session, siapa, "ubah_massal", "intake_tiket", {
                    "token": data.token, "sumber": "excel",
                    "nama_file": entri["nama_file"],
                    "id": row.id, "ticket_no": row.ticket_no, "line_seq": row.line_seq,
                    "sebelumnya": sebelum_baris, "sesudah": sesudah_baris,
                })
            bangun_mart(session)
            evaluasi_alarm(session)
            session.commit()
        except Exception as e:
            session.rollback()
            if isinstance(e, HTTPException):
                raise HTTPException(409, f"Validasi ulang gagal: {e.detail}. Buat pratinjau baru.") from e
            raise
        return {
            "status": "tersimpan", "jumlah": len(pasangan),
            "jumlah_perubahan": jumlah_perubahan, "nama_file": entri["nama_file"],
            "pesan": f"{jumlah_perubahan} perubahan pada {len(pasangan)} baris tersimpan lewat Excel; ringkasan dan alarm disegarkan.",
        }

    @router.delete("/excel-diff/pratinjau/{token}")
    def batalkan_excel(token: str, request: Request):
        wajib_admin(request)
        _bersih_pratinjau()
        with _KUNCI_EXCEL:
            ada = _PRATINJAU_EXCEL.pop(token, None) is not None
        return {
            "status": "dibatalkan" if ada else "tidak_ada",
            "pesan": "Pratinjau Excel dibatalkan." if ada else "Pratinjau sudah tidak tersedia.",
        }

    @router.put("/{row_id}")
    def ubah_intake(row_id: int, data: IntakeUbah, request: Request,
                    session: Session = dep):
        row = session.get(TiketBaris, row_id)
        if row is None:
            raise HTTPException(404, "Baris intake tidak ditemukan.")

        perubahan = data.model_dump(exclude_unset=True)
        sebelumnya, sesudah = _terapkan_perubahan(row, perubahan, session)

        pengguna = info_pengguna(request) or {}
        siapa = pengguna.get("sub") or "pengguna aplikasi"
        catat_audit(session, siapa, "ubah", "intake_tiket", {
            "id": row.id,
            "ticket_no": row.ticket_no,
            "line_seq": row.line_seq,
            "sebelumnya": sebelumnya,
            "sesudah": sesudah,
        })
        bangun_mart(session)
        evaluasi_alarm(session)
        session.commit()
        session.refresh(row)
        return {"status": "tersimpan", "baris": _baris(row),
                "pesan": "Perubahan intake tersimpan; ringkasan dan status wilayah diperbarui."}

    @router.delete("/{row_id}")
    def hapus_intake(row_id: int, request: Request, session: Session = dep):
        row = session.get(TiketBaris, row_id)
        if row is None:
            raise HTTPException(404, "Baris intake tidak ditemukan.")

        pengguna = info_pengguna(request) or {}
        siapa = pengguna.get("sub") or "pengguna aplikasi"
        info = {"id": row.id, "ticket_no": row.ticket_no, "line_seq": row.line_seq,
                "ticket_date": row.ticket_date.isoformat() if row.ticket_date else None,
                "kode_vendor": row.kode_vendor, "dry_kg": float(row.dry_kg) if row.dry_kg is not None else None,
                "source_fingerprint": row.source_fingerprint}
        catat_audit(session, siapa, "hapus", "intake_tiket", info)
        session.delete(row)
        bangun_mart(session)
        evaluasi_alarm(session)
        session.commit()
        return {"status": "dihapus", "id": row_id,
                "pesan": f"Baris tiket {info['ticket_no']} (baris {info['line_seq']}) dihapus; ringkasan diperbarui."}

    app.include_router(router)
