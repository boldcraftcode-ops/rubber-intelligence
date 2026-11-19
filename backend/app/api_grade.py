"""API master grade & daftar harga beli per grade (Fase 7).

- Master grade: tambah/ubah lewat menu (kode, kelompok, flag EUDR, keterangan).
- Harga per grade: form harian (bulk per tanggal) + bulk import .xlsx lewat
  tab Unggah Data (sheet 'Harga_Grade'); template unduhan disediakan.
- Nilai pembelian resmi dihitung ulang dari berat kering intake × harga
  grade yang berlaku; hari yang belum lengkap harganya tidak dihitung.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core import rumus
from .mart import bangun_mart
from .core.alarm import catat_audit
from .core.harga_grade import perluas_harga_slab
from .core.lookup import PencariBerlaku, kurs_pada, sicom_pada
from .models import Grade, HargaGrade, TiketBaris

CATATAN_INDIKATIF = ("Nilai pembelian harian resmi dihitung dari berat kering intake × "
                     "harga grade yang berlaku pada tanggal tersebut; hari dengan "
                     "grade tanpa harga tidak dihitung. Margin per grade yang tampil "
                     "di sini tetap INDIKATIF karena memakai kurs dan SICOM yang tersedia.")


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
    berlaku_sampai: dt.date | None = None
    baris: list[BarisHarga] = Field(min_length=1)
    pengisi: str = "?"


def pasang_router_grade(app, ambil_session):
    router = APIRouter(prefix="/api")

    def _rekap_pembelian(session: Session, dari: dt.date, sampai: dt.date) -> dict:
        tiket = session.scalars(select(TiketBaris).where(
            TiketBaris.ticket_date >= dari, TiketBaris.ticket_date <= sampai,
            TiketBaris.dry_kg > 0).order_by(TiketBaris.ticket_date, TiketBaris.item_code))
        berat: dict[dt.date, dict[str, Decimal]] = {}
        for row in tiket:
            grade = (row.item_code or "").strip().upper() or "GRADE_KOSONG"
            berat.setdefault(row.ticket_date, {})[grade] = (
                berat.setdefault(row.ticket_date, {}).get(grade, Decimal(0))
                + Decimal(str(row.dry_kg)))
        kode = {g.item_code.upper(): g.item_code for g in session.scalars(select(Grade))}
        harga_rows: dict[str, list[tuple[dt.date, HargaGrade]]] = {}
        for h in session.scalars(select(HargaGrade).where(HargaGrade.tanggal <= sampai)):
            harga_rows.setdefault(h.item_code.upper(), []).append((h.tanggal, h))
        cari = {g: PencariBerlaku(rows) for g, rows in harga_rows.items()}
        harian = []
        total_qty = Decimal(0)
        total_amount = Decimal(0)
        hari_lengkap = 0
        for tanggal, grades in sorted(berat.items()):
            rincian = []
            hilang = []
            qty_hari = sum(grades.values(), Decimal(0))
            amount_hari = Decimal(0)
            for item, qty in sorted(grades.items()):
                item_asli = kode.get(item, item)
                peta = cari.get(item)
                price = peta.pada(tanggal) if peta else None
                if price and price.berlaku_sampai and tanggal > price.berlaku_sampai:
                    price = None
                if price is None:
                    hilang.append(item_asli)
                    harga_rp = amount_grade = None
                else:
                    harga_rp = float(price.harga_rp_per_kg)
                    amount_grade = qty * price.harga_rp_per_kg
                    amount_hari += amount_grade
                    amount_grade = float(amount_grade)
                rincian.append({"grade": item_asli, "qty_kering_kg": float(qty),
                                "harga_rp_per_kg": harga_rp, "estimasi_rp": amount_grade})
            lengkap = not hilang
            if lengkap:
                hari_lengkap += 1
                total_qty += qty_hari
                total_amount += amount_hari
            harian.append({
                "tanggal": tanggal.isoformat(), "lengkap": lengkap,
                "qty_kering_kg": float(qty_hari) if lengkap else None,
                "estimasi_rp": float(amount_hari) if lengkap else None,
                "harga_rata_rp_per_kg": float(amount_hari / qty_hari) if lengkap and qty_hari else None,
                "grade_tanpa_harga": hilang, "rincian": rincian,
            })
        return {"total_hari": len(harian), "hari_lengkap": hari_lengkap,
                "hari_belum_lengkap": len(harian) - hari_lengkap,
                "qty_kering_kg": float(total_qty), "estimasi_rp": float(total_amount),
                "harga_rata_rp_per_kg": float(total_amount / total_qty) if total_qty else None,
                "harian": harian}

    @router.get("/pembelian/ringkasan")
    def ringkasan_pembelian(dari: dt.date, sampai: dt.date, session: Session = Depends(ambil_session)):
        if sampai < dari:
            raise HTTPException(422, "Tanggal sampai harus sama atau setelah tanggal dari.")
        panjang = (sampai - dari).days + 1
        if panjang > 180:
            raise HTTPException(422, "Rentang maksimum ringkasan adalah 180 hari.")
        periode = _rekap_pembelian(session, dari, sampai)
        sebelum_sampai = dari - dt.timedelta(days=1)
        sebelumnya = _rekap_pembelian(session, sebelum_sampai - dt.timedelta(days=panjang - 1), sebelum_sampai)
        return {"dari": dari.isoformat(), "sampai": sampai.isoformat(),
                "periode": periode, "sebelumnya": sebelumnya}
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
            "tanggal": h.tanggal.isoformat(),
            "berlaku_sampai": h.berlaku_sampai.isoformat() if h.berlaku_sampai else None,
            "item_code": h.item_code,
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
            if h and h.berlaku_sampai is not None and tanggal > h.berlaku_sampai:
                h = None
            harga_rp = float(h.harga_rp_per_kg) if h else None
            harga_usc = rumus.rp_ke_usc(harga_rp, kurs) if (harga_rp and kurs) else None
            hasil.append({
                "item_code": g.item_code, "kelompok": g.kelompok, "eudr": g.eudr,
                "harga_rp_per_kg": harga_rp,
                "berlaku_sejak": h.tanggal.isoformat() if h else None,
                "berlaku_sampai": h.berlaku_sampai.isoformat() if h and h.berlaku_sampai else None,
                "harga_usc_per_kg": round(harga_usc, 4) if harga_usc else None,
                "margin_indikatif_usc": round(sicom - harga_usc, 4)
                if (harga_usc and sicom is not None) else None,
            })
        return {"tanggal": tanggal.isoformat(), "kurs": kurs, "sicom_usc": sicom,
                "baris": hasil, "catatan": CATATAN_INDIKATIF}

    @router.post("/harga-grade")
    def simpan_harga(data: HargaGradeMasuk, session: Session = dep):
        if data.berlaku_sampai is not None and data.berlaku_sampai < data.tanggal:
            raise HTTPException(422, "Berlaku sampai tidak boleh sebelum tanggal berlaku sejak.")
        kode_sah = {g.item_code for g in session.scalars(select(Grade))}
        for b in data.baris:
            if b.item_code not in kode_sah:
                raise HTTPException(422, f"Grade '{b.item_code}' tidak ada di master. "
                                         "Tambahkan dulu lewat form master grade di "
                                         "halaman ini, lalu simpan harga lagi.")
        harga_input = {b.item_code: Decimal(str(b.harga_rp_per_kg)) for b in data.baris}
        try:
            perluasan = perluas_harga_slab(harga_input, kode_sah)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        n = 0
        for item_code, harga_rp in perluasan.items():
            hg = session.scalar(select(HargaGrade).where(
                HargaGrade.tanggal == data.tanggal,
                HargaGrade.item_code == item_code))
            if hg is None:
                hg = HargaGrade(tanggal=data.tanggal, berlaku_sampai=data.berlaku_sampai,
                                item_code=item_code, harga_rp_per_kg=harga_rp)
                session.add(hg)
            hg.harga_rp_per_kg = harga_rp
            hg.berlaku_sampai = data.berlaku_sampai
            hg.catatan = "Harga turunan otomatis dari SLAB" if item_code not in harga_input else next(
                (b.catatan for b in data.baris if b.item_code == item_code), None)
            hg.diisi_oleh = data.pengisi
            n += 1
        catat_audit(session, data.pengisi, "ubah", "harga_grade", {
            "tanggal": data.tanggal.isoformat(),
            "berlaku_sampai": data.berlaku_sampai.isoformat() if data.berlaku_sampai else None,
            "baris": [{"item_code": kode, "harga_rp_per_kg": str(nilai)}
                      for kode, nilai in perluasan.items()]})
        session.commit()
        bangun_mart(session)
        session.commit()
        rincian_slab = (" SLAB1=harga Slab; SLAB2=Slab−Rp300/kg; "
                        "SLAB3=SLAB2−Rp2.000/kg (termasuk TTSR)."
                        if any(b.item_code.strip().upper() == "SLAB" for b in data.baris) else "")
        return {"status": "tersimpan",
                "pesan": f"{n} harga grade untuk "
                         f"{data.tanggal.strftime('%d/%m/%Y')} tersimpan. "
                         "Mengisi tanggal yang sama menimpa, tidak menggandakan." + rincian_slab}

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
        ws.append(["Tanggal", "Item_Code", "Harga_Rp_per_Kg", "Berlaku_Sampai", "Catatan"])
        hari_ini = dt.date.today()
        for g in session.scalars(select(Grade).order_by(Grade.item_code)):
            if g.item_code != "ALL":
                ws.append([hari_ini, g.item_code, None, None, None])
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
