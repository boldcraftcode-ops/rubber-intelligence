"""API Fase 4: stok & Days, mesin aturan stok->harga (berversi + audit),
simulasi (tanpa menyimpan), analisis stok vs margin, perencanaan, alarm.
"""
from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core import rumus
from .core.alarm import catat_audit, evaluasi_alarm, pastikan_pengaturan
from .core.lookup import kurs_pada, parameter_pada, sicom_pada
from .core.perencanaan import hitung_rencana
from .core.rekomendasi import rekomendasi_harga
from .core.stok_margin import analisis_stok_margin
from .mart import bangun_mart
from .models import (
    Alarm,
    AturanStokHarga,
    AuditLog,
    MartHarian,
    ParameterPabrik,
    PengaturanAlarm,
    Perencanaan,
    TargetMargin,
)


# ----------------------------------------------------------------------------
# Skema masukan
# ----------------------------------------------------------------------------
class BarisAturanMasuk(BaseModel):
    batas_bawah: float | None = Field(None, ge=0)
    batas_atas: float | None = Field(None, ge=0)
    penyesuaian_usc: float
    keterangan: str | None = None


class AturanMasuk(BaseModel):
    berlaku_dari: dt.date
    baris: list[BarisAturanMasuk] = Field(min_length=1)
    alasan: str | None = None
    pengisi: str = "?"


class ParameterMasuk(BaseModel):
    berlaku_dari: dt.date
    kapasitas_ton_per_hari: float = Field(gt=0)
    safety_stock_ton: float | None = Field(None, gt=0)
    safety_stock_hari: float | None = Field(None, gt=0)
    catatan: str | None = None
    pengisi: str = "?"


class RencanaMasuk(BaseModel):
    tahun_target: int
    bulan: int = Field(ge=1, le=12)
    penyesuaian_manual_usc: float = 0.0
    effort_usc: float = 0.0
    alasan: str | None = None
    pengisi: str = "?"


class PengaturanAlarmMasuk(BaseModel):
    kode: str
    aktif: bool
    ambang: float | None = None
    pengisi: str = "?"


def _rekom_dict(r) -> dict:
    return {
        "status": r.status,
        "tanggal": r.tanggal.isoformat() if r.tanggal else None,
        "alasan": r.alasan,
        "rasio_stok": r.rasio_stok,
        "aturan_contoh": r.aturan_contoh,
        "penyesuaian_usc": r.penyesuaian_usc,
        "target_bulan_usc": r.target_bulan_usc,
        "target_efektif_usc": r.target_efektif_usc,
        "sicom_usc": r.sicom_usc,
        "kurs": r.kurs,
        "harga_beli_maks_usc": r.harga_beli_maks_usc,
        "harga_beli_maks_rp_kg": r.harga_beli_maks_rp_kg,
        "harga_beli_aktual_terakhir_usc": r.harga_beli_aktual_terakhir_usc,
        "tanggal_harga_aktual": r.tanggal_harga_aktual.isoformat()
        if r.tanggal_harga_aktual else None,
    }


def pasang_router_fase4(app, ambil_session):
    router = APIRouter(prefix="/api")
    dep = Depends(ambil_session)

    # ------------------------------------------------------------ stok & days
    @router.get("/stok")
    def stok_harian(dari: dt.date | None = None, sampai: dt.date | None = None,
                    session: Session = dep):
        q = select(MartHarian).where(MartHarian.stok_ton != None)  # noqa: E711
        if dari:
            q = q.where(MartHarian.tanggal >= dari)
        if sampai:
            q = q.where(MartHarian.tanggal <= sampai)
        baris = [{
            "tanggal": h.tanggal.isoformat(),
            "stok_ton": round(h.stok_ton, 3),
            "safety_ton": h.safety_ton,
            "kapasitas_ton": h.kapasitas_ton,
            "days": round(h.days, 3) if h.days is not None else None,
            "rasio_stok": round(h.rasio_stok, 4) if h.rasio_stok is not None else None,
            "status": ("di bawah safety" if h.rasio_stok is not None and h.rasio_stok < 1
                       else "aman" if h.rasio_stok is not None else "tanpa safety"),
        } for h in session.scalars(q.order_by(MartHarian.tanggal))]
        di_bawah = [b for b in baris if b["status"] == "di bawah safety"]
        return {"baris": baris, "jumlah_hari": len(baris),
                "jumlah_hari_di_bawah_safety": len(di_bawah),
                "terakhir": baris[-1] if baris else None}

    # ------------------------------------------------------------ aturan stok->harga
    @router.get("/aturan")
    def daftar_aturan(session: Session = dep):
        semua = list(session.scalars(select(AturanStokHarga).order_by(
            AturanStokHarga.berlaku_dari.desc(), AturanStokHarga.urutan)))
        versi: dict[str, list] = defaultdict(list)
        for a in semua:
            versi[a.berlaku_dari.isoformat()].append({
                "urutan": a.urutan, "batas_bawah": a.batas_bawah,
                "batas_atas": a.batas_atas, "penyesuaian_usc": a.penyesuaian_usc,
                "keterangan": a.keterangan, "aktif": a.aktif,
                "dibuat_oleh": a.dibuat_oleh,
            })
        urut = sorted(versi, reverse=True)
        return {"kosong": not semua,
                "versi": [{"berlaku_dari": v, "baris": versi[v],
                           "contoh": any("CONTOH" in (b["keterangan"] or "").upper()
                                         for b in versi[v])}
                          for v in urut]}

    @router.post("/aturan")
    def simpan_aturan(data: AturanMasuk, session: Session = dep):
        # Validasi rentang
        for i, b in enumerate(data.baris, start=1):
            if b.batas_bawah is not None and b.batas_atas is not None \
                    and b.batas_bawah >= b.batas_atas:
                raise HTTPException(422, f"Baris {i}: batas bawah ({b.batas_bawah}) "
                                         f"harus lebih kecil dari batas atas "
                                         f"({b.batas_atas}).")
        ada = session.scalar(select(AturanStokHarga).where(
            AturanStokHarga.berlaku_dari == data.berlaku_dari))
        if ada:
            raise HTTPException(422, f"Sudah ada versi aturan dengan tanggal berlaku "
                                     f"{data.berlaku_dari.strftime('%d/%m/%Y')}. "
                                     "Pilih tanggal berlaku lain (riwayat tidak ditimpa).")
        for i, b in enumerate(data.baris, start=1):
            session.add(AturanStokHarga(
                berlaku_dari=data.berlaku_dari, urutan=i,
                batas_bawah=b.batas_bawah, batas_atas=b.batas_atas,
                penyesuaian_usc=b.penyesuaian_usc, keterangan=b.keterangan,
                dibuat_oleh=data.pengisi))
        catat_audit(session, data.pengisi, "tambah", "aturan_stok_harga", {
            "berlaku_dari": data.berlaku_dari.isoformat(),
            "baris": [b.model_dump() for b in data.baris],
            "alasan": data.alasan,
        })
        evaluasi_alarm(session)
        session.commit()
        return {"status": "tersimpan",
                "pesan": f"Versi aturan baru berlaku sejak "
                         f"{data.berlaku_dari.strftime('%d/%m/%Y')}. Versi lama tetap "
                         "dipakai untuk tanggal sebelum itu (riwayat tersimpan)."}

    # ------------------------------------------------------------ parameter pabrik
    @router.get("/parameter")
    def daftar_parameter(session: Session = dep):
        return [{
            "berlaku_dari": p.berlaku_dari.isoformat(),
            "kapasitas_ton_per_hari": p.kapasitas_ton_per_hari,
            "safety_stock_ton": p.safety_stock_ton,
            "safety_stock_hari": p.safety_stock_hari,
            "catatan": p.catatan,
        } for p in session.scalars(select(ParameterPabrik).order_by(
            ParameterPabrik.berlaku_dari.desc()))]

    @router.post("/parameter")
    def simpan_parameter(data: ParameterMasuk, session: Session = dep):
        if data.safety_stock_ton is None and data.safety_stock_hari is None:
            raise HTTPException(422, "Isi Safety_Stock_Ton atau Safety_Stock_Hari "
                                     "(salah satu).")
        ada = session.get(ParameterPabrik, data.berlaku_dari)
        if ada:
            raise HTTPException(422, f"Sudah ada parameter dengan tanggal berlaku "
                                     f"{data.berlaku_dari.strftime('%d/%m/%Y')}. "
                                     "Pilih tanggal lain (riwayat tidak ditimpa).")
        session.add(ParameterPabrik(
            berlaku_dari=data.berlaku_dari,
            kapasitas_ton_per_hari=data.kapasitas_ton_per_hari,
            safety_stock_ton=data.safety_stock_ton,
            safety_stock_hari=data.safety_stock_hari,
            catatan=data.catatan))
        catat_audit(session, data.pengisi, "tambah", "parameter_pabrik",
                    data.model_dump())
        session.flush()
        bangun_mart(session)  # Days/rasio sejak tanggal berlaku ikut berubah
        evaluasi_alarm(session)
        session.commit()
        return {"status": "tersimpan",
                "pesan": "Parameter baru berlaku sejak tanggal itu; hasil historis "
                         "sebelum tanggal berlaku tidak berubah."}

    # ------------------------------------------------------------ rekomendasi & simulasi
    @router.get("/rekomendasi")
    def rekomendasi(tanggal: dt.date | None = None, session: Session = dep):
        return _rekom_dict(rekomendasi_harga(session, tanggal))

    @router.get("/simulasi")
    def simulasi(sicom: float | None = None, kurs: float | None = None,
                 stok_ton: float | None = None, tanggal: dt.date | None = None,
                 session: Session = dep):
        """Simulasi dampak SICOM/kurs/stok. TIDAK menyimpan apa pun."""
        tanggal = tanggal or dt.date.today()
        # Nilai awal = data aktual terakhir
        h_stok = session.scalars(select(MartHarian).where(
            MartHarian.stok_ton != None)  # noqa: E711
            .order_by(MartHarian.tanggal.desc())).first()
        h_beli = session.scalars(select(MartHarian).where(
            MartHarian.harga_rp_per_kg != None)  # noqa: E711
            .order_by(MartHarian.tanggal.desc())).first()
        s_akt = sicom_pada(session, tanggal)
        k_akt = kurs_pada(session, tanggal)

        sicom_sim = sicom if sicom is not None else (s_akt.usc_per_kg if s_akt else None)
        kurs_sim = kurs if kurs is not None else (float(k_akt.idr_per_usd) if k_akt else None)
        stok_sim = stok_ton if stok_ton is not None else (h_stok.stok_ton if h_stok else None)
        if sicom_sim is None or kurs_sim is None or stok_sim is None:
            raise HTTPException(422, "Data awal belum lengkap untuk simulasi "
                                     "(SICOM/kurs/stok).")

        prm = parameter_pada(session, tanggal)
        if prm is None:
            raise HTTPException(422, "Belum ada parameter pabrik yang berlaku.")
        kapasitas = prm.kapasitas_ton_per_hari
        safety = rumus.hitung_safety_ton(prm.safety_stock_ton, prm.safety_stock_hari,
                                         kapasitas)
        days = rumus.hitung_days(stok_sim, kapasitas)
        rasio = rumus.rasio_stok(stok_sim, safety)

        target = session.scalar(select(TargetMargin).where(
            TargetMargin.tahun == tanggal.year, TargetMargin.bulan == tanggal.month))

        semua = list(session.scalars(select(AturanStokHarga).where(
            AturanStokHarga.aktif == True,  # noqa: E712
            AturanStokHarga.berlaku_dari <= tanggal,
        ).order_by(AturanStokHarga.berlaku_dari.desc(), AturanStokHarga.urutan)))
        hasil: dict = {
            "tanggal": tanggal.isoformat(),
            "masukan": {"sicom_usc": sicom_sim, "kurs": kurs_sim,
                        "stok_ton": round(stok_sim, 3)},
            "days": round(days, 3) if days is not None else None,
            "rasio_stok": round(rasio, 4) if rasio is not None else None,
            "safety_ton": safety, "kapasitas_ton": kapasitas,
            "catatan": "Simulasi — tidak ada yang disimpan.",
        }
        if not semua:
            hasil["status"] = "ATURAN BELUM DIISI"
            return hasil
        versi = semua[0].berlaku_dari
        aturan = [rumus.BarisAturan(a.batas_bawah, a.batas_atas, a.penyesuaian_usc,
                                    a.keterangan)
                  for a in semua if a.berlaku_dari == versi]
        kena = rumus.cari_aturan(sorted(aturan, key=lambda a: (a.batas_bawah or 0)),
                                 rasio) if rasio is not None else None
        if kena is None or target is None:
            hasil["status"] = "DATA KURANG"
            hasil["pesan"] = ("Tidak ada baris aturan untuk rasio ini."
                              if target else "Target bulan ini belum ada.")
            return hasil

        target_ef = rumus.target_efektif(target.target_usc_per_kg, kena.penyesuaian_usc)
        maks_usc = rumus.harga_beli_maks_usc(sicom_sim, target_ef)
        hasil.update({
            "status": "OK",
            "aturan_contoh": any("CONTOH" in (a.keterangan or "").upper()
                                 for a in aturan),
            "penyesuaian_usc": kena.penyesuaian_usc,
            "target_bulan_usc": target.target_usc_per_kg,
            "target_efektif_usc": target_ef,
            "harga_beli_maks_usc": round(maks_usc, 4),
            "harga_beli_maks_rp_kg": round(rumus.usc_ke_rp(maks_usc, kurs_sim), 2),
        })
        if h_beli and h_beli.harga_rp_per_kg:
            harga_usc_sim = rumus.rp_ke_usc(h_beli.harga_rp_per_kg, kurs_sim)
            hasil["harga_aktual"] = {
                "tanggal": h_beli.tanggal.isoformat(),
                "harga_rp_per_kg": round(h_beli.harga_rp_per_kg, 2),
                "harga_usc_dengan_kurs_simulasi": round(harga_usc_sim, 4),
                "margin_jika_harga_sama": round(sicom_sim - harga_usc_sim, 4),
            }
        return hasil

    # ------------------------------------------------------------ analisis stok vs margin
    @router.get("/analisis/stok-margin")
    def stok_vs_margin(tahun: int | None = None, format: str | None = None,
                       session: Session = dep):
        """Hubungan rasio stok vs OP Margin, siap dibaca.

        `tahun` menyaring titik & ringkasan yang ditampilkan (perbandingan antar
        tahun tetap dikirim di `per_tahun`). `format=xlsx` untuk ekspor Excel.
        """
        hasil = analisis_stok_margin(session, tahun)
        if format == "xlsx":
            return _xlsx_stok_margin(hasil)
        return hasil
    
    def _xlsx_stok_margin(hasil: dict):
        import io

        import openpyxl
        from fastapi.responses import StreamingResponse

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data bulanan"
        ws.append(["Tahun", "Bulan", "Rasio stok / safety",
                   "OP Margin (USc/kg)", "Ton"])
        for t in hasil["titik"]:
            ws.append([t["tahun"], t["bulan"], t["rasio_stok"],
                       t["op_margin"], t["ton"]])

        ws2 = wb.create_sheet("Ringkasan")
        ws2.append(["Keterangan", "Nilai"])
        ws2.append(["Bulan berdata", hasil["jumlah_bulan"]])
        ws2.append(["Korelasi (Pearson)", hasil["korelasi"]])
        ws2.append(["Rasio stok rata-rata", hasil["rasio_rata"]])
        ws2.append(["Margin rata-rata (USc/kg)", hasil["margin_rata"]])
        for k in hasil["kelompok"]:
            ws2.append([k["label"] + " - jumlah bulan", k["jumlah_bulan"]])
            ws2.append([k["label"] + " - margin rata-rata", k["margin_rata"]])
        ws2.append([])
        ws2.append(["Korelasi per tahun", "Korelasi"])
        for p in hasil["per_tahun"]:
            ws2.append([p["tahun"], p["korelasi"]])
        ws2.append([])
        ws2.append(["Catatan", hasil["catatan"]])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        nama = ("stok_vs_margin_" + str(hasil["tahun"]) + ".xlsx"
                if hasil["tahun"] else "stok_vs_margin.xlsx")
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument."
                       "spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{nama}"'})

    # ------------------------------------------------------------ perencanaan
    @router.get("/rencana/{tahun_target}")
    def rencana(tahun_target: int, tahun_dasar: str | None = None,
                session: Session = dep):
        dipilih = None
        if tahun_dasar:
            try:
                dipilih = [int(t) for t in tahun_dasar.split(",") if t.strip()]
            except ValueError:
                raise HTTPException(422, "tahun_dasar harus daftar tahun dipisah "
                                         "koma, contoh: 2023,2024,2025,2026")
        hasil = hitung_rencana(session, tahun_target, dipilih)
        return {"tahun_target": tahun_target,
                "tahun_dasar": dipilih or [tahun_target - 4, tahun_target - 3,
                                           tahun_target - 2, tahun_target - 1],
                "bulan": [{
                    "bulan": r.bulan,
                    "margin_per_tahun": {str(t): round(v, 4)
                                         for t, v in r.margin_per_tahun.items()},
                    "rata_rata_dasar": round(r.rata_rata_dasar, 4)
                    if r.rata_rata_dasar is not None else None,
                    "penyesuaian_manual": r.penyesuaian_manual,
                    "sebelum_effort": round(r.sebelum_effort, 4)
                    if r.sebelum_effort is not None else None,
                    "effort": r.effort,
                    "net_margin": round(r.net_margin, 4)
                    if r.net_margin is not None else None,
                    "alasan": r.alasan,
                    "perkiraan": r.perkiraan,
                } for r in hasil]}

    @router.post("/rencana")
    def simpan_rencana(data: RencanaMasuk, session: Session = dep):
        r = session.scalar(select(Perencanaan).where(
            Perencanaan.tahun_target == data.tahun_target,
            Perencanaan.bulan == data.bulan))
        lama = {"penyesuaian": r.penyesuaian_manual_usc, "effort": r.effort_usc,
                "alasan": r.alasan} if r else None
        if r is None:
            r = Perencanaan(tahun_target=data.tahun_target, bulan=data.bulan)
            session.add(r)
        r.penyesuaian_manual_usc = data.penyesuaian_manual_usc
        r.effort_usc = data.effort_usc
        r.alasan = data.alasan
        catat_audit(session, data.pengisi, "ubah" if lama else "tambah",
                    "perencanaan", {"baru": data.model_dump(), "lama": lama})
        session.commit()
        return {"status": "tersimpan",
                "pesan": f"Perencanaan {data.bulan:02d}/{data.tahun_target} disimpan. "
                         "Nilai dasar tetap tertaut otomatis ke aktual."}

    # ------------------------------------------------------------ alarm
    @router.get("/alarm")
    def daftar_alarm(session: Session = dep):
        pastikan_pengaturan(session)
        session.commit()
        return {
            "alarm": [{
                "kode": a.kode, "pesan": a.pesan,
                "tanggal_data": a.tanggal_data.isoformat() if a.tanggal_data else None,
                "dievaluasi_pada": a.dievaluasi_pada.isoformat(timespec="seconds"),
            } for a in session.scalars(select(Alarm).order_by(Alarm.kode))],
            "pengaturan": [{
                "kode": p.kode, "aktif": p.aktif, "ambang": p.ambang,
                "satuan": p.satuan, "keterangan": p.keterangan,
            } for p in session.scalars(select(PengaturanAlarm).order_by(
                PengaturanAlarm.kode))],
        }

    @router.post("/alarm/pengaturan")
    def ubah_pengaturan_alarm(data: PengaturanAlarmMasuk, session: Session = dep):
        pastikan_pengaturan(session)
        p = session.get(PengaturanAlarm, data.kode)
        if p is None:
            raise HTTPException(422, f"Kode alarm '{data.kode}' tidak dikenal.")
        lama = {"aktif": p.aktif, "ambang": p.ambang}
        p.aktif = data.aktif
        p.ambang = data.ambang
        catat_audit(session, data.pengisi, "ubah", "pengaturan_alarm",
                    {"kode": data.kode, "lama": lama,
                     "baru": {"aktif": data.aktif, "ambang": data.ambang}})
        evaluasi_alarm(session)
        session.commit()
        return {"status": "tersimpan", "pesan": f"Pengaturan {data.kode} diperbarui "
                                                "dan alarm dievaluasi ulang."}

    @router.post("/alarm/evaluasi")
    def evaluasi_ulang(session: Session = dep):
        hasil = evaluasi_alarm(session)
        session.commit()
        return {"status": "selesai", "jumlah_alarm": len(hasil)}

    # ------------------------------------------------------------ audit log
    @router.get("/audit")
    def audit(objek: str | None = None, limit: int = 50, session: Session = dep):
        q = select(AuditLog).order_by(AuditLog.waktu.desc(), AuditLog.id.desc())
        if objek:
            q = q.where(AuditLog.objek == objek)
        return [{
            "waktu": a.waktu.isoformat(timespec="seconds"), "siapa": a.siapa,
            "aksi": a.aksi, "objek": a.objek,
            "detail": json.loads(a.detail) if a.detail else None,
        } for a in session.scalars(q.limit(min(limit, 200)))]

    app.include_router(router)
