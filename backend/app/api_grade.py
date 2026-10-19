"""API master grade & daftar harga beli per grade (Fase 7).

- Master grade: tambah/ubah lewat menu (kode, kelompok, flag EUDR, keterangan).
- Harga per grade: form harian (bulk per tanggal) + bulk import .xlsx lewat
  tab Unggah Data (sheet 'Harga_Grade'); template unduhan disediakan.
- Margin per grade dari daftar harga berlabel INDIKATIF — Amount resmi tetap
  total pembayaran per hari [lihat ASUMSI.md].
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core import rumus
from .core.alarm import catat_audit
from .core.lookup import kurs_pada, sicom_pada
from .models import Grade, HargaGrade

CATATAN_INDIKATIF = ("Margin per grade di sini INDIKATIF: dihitung dari daftar "
                     "harga grade yang Anda isi, bukan dari Amount pembayaran "
                     "aktual (Amount resmi = total per hari).")


class GradeMasuk(BaseModel):
    item_code: str = Field(min_length=1, max_length=50)
    kelompok: str | None = None
    eudr: bool = False
    keterangan: str | None = None
    pengisi: str = "?"


class BarisHarga(BaseModel):
    item_code: str
    harga_rp_per_kg: float = Field(gt=0)
    catatan: str | None = None


class HargaGradeMasuk(BaseModel):
    tanggal: dt.date
    baris: list[BarisHarga] = Field(min_length=1)
    pengisi: str = "?"


def pasang_router_grade(app, ambil_session):
    router = APIRouter(prefix="/api")
    dep = Depends(ambil_session)

    # ------------------------------------------------------------ master grade
    @router.get("/grade")
    def daftar_grade(session: Session = dep):
        return [{
            "item_code": g.item_code, "kelompok": g.kelompok,
            "eudr": g.eudr, "keterangan": g.keterangan,
        } for g in session.scalars(select(Grade).order_by(Grade.item_code))]

    @router.post("/grade")
    def simpan_grade(data: GradeMasuk, session: Session = dep):
        kode = data.item_code.strip()
        if not kode:
            raise HTTPException(422, "Item Code tidak boleh kosong.")
        g = session.get(Grade, kode)
        baru = g is None
        lama = None if baru else {"kelompok": g.kelompok, "eudr": g.eudr,
                                  "keterangan": g.keterangan}
        if baru:
            g = Grade(item_code=kode)
            session.add(g)
        g.kelompok = (data.kelompok or "").strip() or None
        g.eudr = data.eudr or ("TTSR" in kode.upper())  # kode TTSR otomatis EUDR
        g.keterangan = (data.keterangan or "").strip() or None
        catat_audit(session, data.pengisi, "tambah" if baru else "ubah", "grade",
                    {"item_code": kode, "lama": lama,
                     "baru": {"kelompok": g.kelompok, "eudr": g.eudr,
                              "keterangan": g.keterangan}})
        session.commit()
        return {"status": "tersimpan",
                "pesan": f"Grade {kode} {'ditambahkan' if baru else 'diperbarui'}."
                + (" Ditandai EUDR karena mengandung kode TTSR."
                   if g.eudr and not data.eudr else "")}

    # ------------------------------------------------------------ harga per grade
    @router.get("/harga-grade")
    def riwayat_harga(limit: int = 60, session: Session = dep):
        baris = session.scalars(select(HargaGrade).order_by(
            HargaGrade.tanggal.desc(), HargaGrade.item_code).limit(min(limit, 500)))
        return [{
            "tanggal": h.tanggal.isoformat(), "item_code": h.item_code,
            "harga_rp_per_kg": float(h.harga_rp_per_kg),
            "catatan": h.catatan, "diisi_oleh": h.diisi_oleh,
        } for h in baris]

    @router.get("/harga-grade/terkini")
    def harga_terkini(tanggal: dt.date | None = None, session: Session = dep):
        """Harga per grade yang berlaku pada tanggal itu (baris terbaru dengan
        tanggal <= tanggal dicari) + konversi US¢ + margin indikatif."""
        tanggal = tanggal or dt.date.today()
        k = kurs_pada(session, tanggal)
        s = sicom_pada(session, tanggal)
        kurs = float(k.idr_per_usd) if k else None
        sicom = s.usc_per_kg if s else None
        hasil = []
        for g in session.scalars(select(Grade).order_by(Grade.item_code)):
            if g.item_code == "ALL":
                continue
            h = session.scalars(select(HargaGrade).where(
                HargaGrade.item_code == g.item_code,
                HargaGrade.tanggal <= tanggal,
            ).order_by(HargaGrade.tanggal.desc())).first()
            harga_rp = float(h.harga_rp_per_kg) if h else None
            harga_usc = rumus.rp_ke_usc(harga_rp, kurs) if (harga_rp and kurs) else None
            hasil.append({
                "item_code": g.item_code, "kelompok": g.kelompok, "eudr": g.eudr,
                "harga_rp_per_kg": harga_rp,
                "berlaku_sejak": h.tanggal.isoformat() if h else None,
                "harga_usc_per_kg": round(harga_usc, 4) if harga_usc else None,
                "margin_indikatif_usc": round(sicom - harga_usc, 4)
                if (harga_usc and sicom is not None) else None,
            })
        return {"tanggal": tanggal.isoformat(), "kurs": kurs, "sicom_usc": sicom,
                "baris": hasil, "catatan": CATATAN_INDIKATIF}

    @router.post("/harga-grade")
    def simpan_harga(data: HargaGradeMasuk, session: Session = dep):
        kode_sah = {g.item_code for g in session.scalars(select(Grade))}
        for b in data.baris:
            if b.item_code not in kode_sah:
                raise HTTPException(422, f"Grade '{b.item_code}' tidak ada di master. "
                                         "Tambahkan dulu lewat form master grade di "
                                         "halaman ini, lalu simpan harga lagi.")
        n = 0
        for b in data.baris:
            hg = session.scalar(select(HargaGrade).where(
                HargaGrade.tanggal == data.tanggal,
                HargaGrade.item_code == b.item_code))
            if hg is None:
                hg = HargaGrade(tanggal=data.tanggal, item_code=b.item_code,
                                harga_rp_per_kg=Decimal(str(b.harga_rp_per_kg)))
                session.add(hg)
            hg.harga_rp_per_kg = Decimal(str(b.harga_rp_per_kg))
            hg.catatan = b.catatan
            hg.diisi_oleh = data.pengisi
            n += 1
        catat_audit(session, data.pengisi, "ubah", "harga_grade", {
            "tanggal": data.tanggal.isoformat(),
            "baris": [b.model_dump() for b in data.baris]})
        session.commit()
        return {"status": "tersimpan",
                "pesan": f"{n} harga grade untuk "
                         f"{data.tanggal.strftime('%d/%m/%Y')} tersimpan. "
                         "Mengisi tanggal yang sama menimpa, tidak menggandakan."}

    @router.get("/harga-grade/template")
    def template_harga(session: Session = dep):
        """Template .xlsx untuk bulk import (unggah lewat tab Unggah Data).
        Nama sheet HARUS 'Harga_Grade' agar dikenali otomatis saat diunggah."""
        import io

        import openpyxl
        from fastapi.responses import StreamingResponse

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Harga_Grade"
        ws.append(["Tanggal", "Item_Code", "Harga_Rp_per_Kg", "Catatan"])
        hari_ini = dt.date.today()
        for g in session.scalars(select(Grade).order_by(Grade.item_code)):
            if g.item_code != "ALL":
                ws.append([hari_ini, g.item_code, None, None])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument"
                       ".spreadsheetml.sheet",
            headers={"Content-Disposition":
                     'attachment; filename="Harga_Grade_template.xlsx"'})

    app.include_router(router)
