"""API daftar dan koreksi baris intake.

Perubahan pada tiket dicatat ke audit log. Ticket No, nomor urut, Asal Getah
asli, sidik sumber, dan hubungan ke unggahan sengaja tidak dapat diubah dari
layar ini; koreksi hanya memperbarui kolom operasional yang dipilih.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .auth_lokal import info_pengguna
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
        # provinsi dari intake maupun data collector.
        from .api_traceability import muat_referensi_bawaan
        muat_referensi_bawaan(session)

    def provinsi_tersedia(session: Session) -> bool:
        return session.scalar(select(ReferensiWilayahTrace.id).where(
            ReferensiWilayahTrace.provinsi_norm.is_not(None),
            ReferensiWilayahTrace.provinsi.is_not(None)).limit(1)) is not None

    def filter_provinsi_scdf(query, provinsi: str | None, tersedia: bool):
        if provinsi and provinsi.strip() and tersedia:
            norm = normalisasi_teks_wilayah(provinsi)
            return query.where(ReferensiWilayahTrace.provinsi_norm == norm)
        return query

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

    @router.put("/{row_id}")
    def ubah_intake(row_id: int, data: IntakeUbah, request: Request,
                    session: Session = dep):
        row = session.get(TiketBaris, row_id)
        if row is None:
            raise HTTPException(404, "Baris intake tidak ditemukan.")

        perubahan = data.model_dump(exclude_unset=True)
        if not perubahan:
            raise HTTPException(422, "Tidak ada perubahan untuk disimpan.")

        # Kolom kunci harus tetap tersedia dan tidak boleh dikosongkan.
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

            provinsi_diubah = (
                "provinsi" in perubahan and
                wilayah_baru["provinsi"] != (row.provinsi or "").strip()
            )
            if provinsi_diubah and wilayah_baru["provinsi"]:
                if not ada_provinsi_scdf:
                    raise HTTPException(422,
                        "Provinsi tidak dapat dikoreksi: referensi SCDF yang termuat belum menyediakan Provinsi.")
                if session.scalar(select(ReferensiWilayahTrace.id).where(
                        ReferensiWilayahTrace.provinsi_norm == provinsi_norm).limit(1)) is None:
                    raise HTTPException(422, "Provinsi tidak ditemukan pada referensi SCDF.")

            if kabupaten_norm:
                q_ref = select(ReferensiWilayahTrace.id).where(
                    ReferensiWilayahTrace.kabupaten_norm == kabupaten_norm)
                if ada_provinsi_scdf and provinsi_norm:
                    q_ref = q_ref.where(ReferensiWilayahTrace.provinsi_norm == provinsi_norm)
                if session.scalar(q_ref.limit(1)) is None:
                    raise HTTPException(422, "Kabupaten/Kota tidak ditemukan pada referensi SCDF untuk Provinsi tersebut.")

                if kecamatan_norm:
                    q_ref = select(ReferensiWilayahTrace.id).where(
                        ReferensiWilayahTrace.kabupaten_norm == kabupaten_norm,
                        ReferensiWilayahTrace.kecamatan_norm == kecamatan_norm)
                    if ada_provinsi_scdf and provinsi_norm:
                        q_ref = q_ref.where(ReferensiWilayahTrace.provinsi_norm == provinsi_norm)
                    if session.scalar(q_ref.limit(1)) is None:
                        raise HTTPException(422, "Kecamatan tidak ditemukan pada Kabupaten/Kota di referensi SCDF.")

                    if desa_norm:
                        q_ref = select(ReferensiWilayahTrace.id).where(
                            ReferensiWilayahTrace.kabupaten_norm == kabupaten_norm,
                            ReferensiWilayahTrace.kecamatan_norm == kecamatan_norm,
                            ReferensiWilayahTrace.desa_norm == desa_norm)
                        if ada_provinsi_scdf and provinsi_norm:
                            q_ref = q_ref.where(ReferensiWilayahTrace.provinsi_norm == provinsi_norm)
                        if session.scalar(q_ref.limit(1)) is None:
                            raise HTTPException(422, "Desa tidak ditemukan pada pasangan Kabupaten/Kecamatan di referensi SCDF.")

        sebelumnya: dict[str, object] = {}
        sesudah: dict[str, object] = {}
        for kolom, nilai in perubahan.items():
            lama = getattr(row, kolom)
            if isinstance(lama, Decimal):
                lama = float(lama)
            if isinstance(nilai, str):
                nilai = nilai.strip() or None
            sebelumnya[kolom] = lama.isoformat() if isinstance(lama, dt.date) else lama
            sesudah[kolom] = nilai.isoformat() if isinstance(nilai, dt.date) else nilai
            nilai_db = (Decimal(str(nilai)) if nilai is not None and kolom in
                        {"wet_kg", "sample_kg", "reject_kg", "dry_kg"} else nilai)
            setattr(row, kolom, nilai_db)

        if "wet_kg" in perubahan:
            row.tiket_nol = row.wet_kg is not None and float(row.wet_kg) == 0
        if any(k in perubahan for k in ("kabupaten", "kecamatan", "desa")):
            # Kunci wilayah ikut diperbarui agar kartu penerimaan dan
            # Regional Traceability membaca koreksi yang sama setelah disimpan.
            row.kabupaten_norm = normalisasi_kabupaten(row.kabupaten)
            row.kecamatan_norm = normalisasi_teks_wilayah(row.kecamatan)
            row.desa_norm = normalisasi_teks_wilayah(row.desa)

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
