"""API Traceability: volume Dry teragregasi di server, referensi wilayah dan ekspor."""
from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import openpyxl
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import (String, and_, case, cast, distinct, func, or_, select, tuple_)
from sqlalchemy.orm import Session, aliased

from .auth_lokal import info_pengguna, wajib_admin
from .core.alarm import catat_audit
from .core.deteksi_salah_ketik import (ambang_untuk, indeks_kandidat,
                                       norma_mirip, skor_kemiripan,
                                       skor_pasangan)
from .core.kelas_intake import (KELAS_URUTAN, batas_untuk_layar,
                                 distribusi as distribusi_kelas,
                                 kelas as kelas_intake, kelas_tertinggi)
from .core.klasifikasi_vendor import label as label_klasifikasi
from .core.sourcing_type import (bakukan as bakukan_sourcing,
                                 daftar_untuk_layar as daftar_sourcing,
                                 label as label_sourcing)
from .core.traceability import (normalisasi_kabupaten, normalisasi_teks_wilayah,
                                persen_traceable, rentang_periode)
from .models import (Collector, KoreksiWilayahTrace, PengaturanTraceability,
                     ReferensiWilayahTrace, TiketBaris, Vendor)


def _desa_norm(teks: str | None) -> str:
    return normalisasi_teks_wilayah(teks) or ""

NAMA_FILE_REFERENSI = Path(__file__).resolve().parents[1] / "data" / "ID_AUX.xlsx"


def muat_referensi_bawaan(session: Session, path: Path | None = None) -> int:
    """Seed ID_AUX satu kali; file tidak membawa kode wilayah, jadi Code NULL."""
    if (session.scalar(select(func.count()).select_from(ReferensiWilayahTrace)) or 0) > 0:
        return 0
    sumber = path or NAMA_FILE_REFERENSI
    if not sumber.exists():
        return 0
    wb = openpyxl.load_workbook(sumber, read_only=True, data_only=True)
    try:
        ws = wb["ID AUX"] if "ID AUX" in wb.sheetnames else wb[wb.sheetnames[0]]
        seen: set[tuple[str, str, str]] = set()
        batch: list[dict] = []
        jumlah = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            kab_kec = str(row[0] or "").strip()
            desa = str(row[1] or "").strip()
            match = row[3] if len(row) > 3 else None
            if not kab_kec or not desa or match not in (1, True, "1"):
                continue
            kabupaten, pemisah, kecamatan = kab_kec.partition("_")
            if not pemisah or not kabupaten.strip() or not kecamatan.strip():
                continue
            kabupaten, kecamatan, desa = kabupaten.strip(), kecamatan.strip(), desa.strip()
            kunci = (normalisasi_kabupaten(kabupaten),
                     normalisasi_teks_wilayah(kecamatan),
                     normalisasi_teks_wilayah(desa))
            if not all(kunci) or kunci in seen:
                continue
            seen.add(kunci)
            batch.append({
                "provinsi_norm": None, "provinsi": None,
                "kabupaten_norm": kunci[0], "kecamatan_norm": kunci[1],
                "desa_norm": kunci[2], "kabupaten": kabupaten,
                "kecamatan": kecamatan, "desa": desa, "code": None,
            })
            if len(batch) >= 2000:
                session.execute(ReferensiWilayahTrace.__table__.insert(), batch)
                jumlah += len(batch)
                batch.clear()
        if batch:
            session.execute(ReferensiWilayahTrace.__table__.insert(), batch)
            jumlah += len(batch)
        session.commit()
        return jumlah
    finally:
        wb.close()


class SourcingTypeMasuk(BaseModel):
    """Pilihan sourcing type yang diisi dari tabel Supplier Actors."""
    sourcing_type: str | None = None
    pengisi: str = "?"


class PengaturanMasuk(BaseModel):
    accounting: str = Field(min_length=1, max_length=120)
    scope: str = Field(min_length=1, max_length=120)


class KoreksiLokasiMasuk(BaseModel):
    source_kabupaten_norm: str = Field(max_length=120)
    source_kecamatan_norm: str = Field(max_length=120)
    source_desa_norm: str = Field(max_length=120)
    target_kabupaten_norm: str | None = Field(default=None, max_length=120)
    target_kecamatan_norm: str | None = Field(default=None, max_length=120)
    target_desa_norm: str | None = Field(default=None, max_length=120)


def _dedup_ids():
    """Satu baris per sidik-SHA seluruh kolom; baris lama tanpa sidik tetap utuh."""
    kunci = case(
        (TiketBaris.source_fingerprint.is_not(None), TiketBaris.source_fingerprint),
        else_=cast(TiketBaris.id, String),
    )
    return select(
        TiketBaris.id.label("id"),
        func.row_number().over(partition_by=kunci,
                               order_by=TiketBaris.id).label("urutan"),
    ).subquery()


def _filter_base(session: Session, tahun: int | None, periode: str,
                 supplier: str | None, eudr: str, include_latex: bool):
    dedup = _dedup_ids()
    q = (select(TiketBaris)
         .join(dedup, dedup.c.id == TiketBaris.id)
         .where(dedup.c.urutan == 1,
                TiketBaris.ticket_no.is_not(None),
                func.trim(TiketBaris.ticket_no) != "",
                TiketBaris.ticket_date.is_not(None),
                TiketBaris.dry_kg.is_not(None), TiketBaris.dry_kg > 0,
                TiketBaris.wet_kg.is_not(None), TiketBaris.wet_kg > 0,
                TiketBaris.drc_pct.is_not(None),
                TiketBaris.drc_pct >= 20, TiketBaris.drc_pct <= 95,
                TiketBaris.tiket_nol.is_(False),
                func.abs(TiketBaris.dry_kg -
                         TiketBaris.wet_kg * TiketBaris.drc_pct / 100) <= 1.5))
    if tahun is not None:
        mulai, akhir = rentang_periode(tahun, periode)
        q = q.where(TiketBaris.ticket_date >= mulai,
                    TiketBaris.ticket_date <= akhir)
    if supplier:
        q = q.where(TiketBaris.kode_vendor == supplier)
    if eudr == "eudr":
        q = q.where(func.upper(func.trim(TiketBaris.item_code)).like("%TTSR"))
    elif eudr == "non_eudr":
        q = q.where(~func.upper(func.trim(TiketBaris.item_code)).like("%TTSR"))
    elif eudr != "all":
        raise HTTPException(422, "Filter EUDR harus all, eudr, atau non_eudr.")
    if not include_latex:
        q = q.where(func.upper(func.trim(TiketBaris.item_code)) != "LATEX OP")
    return q.subquery()


def _supplier_bulan(session: Session, base,
                    supplier_code: str | None = None) -> list[dict]:
    """Agregat Dry per (bulan, supplier) dari baris intake terfilter.

    SQL mengelompokkan per tanggal + vendor, lalu bulan dirangkum di Python.
    Ini sengaja tidak memakai ``strftime`` agar tetap jalan di SQLite maupun
    PostgreSQL. Klasifikasi memakai MT sebelum dibulatkan.
    """
    T = TiketBaris
    q = (select(T.ticket_date.label("tanggal"), T.kode_vendor,
                func.sum(T.dry_kg).label("dry"))
         .select_from(T).join(base, base.c.id == T.id)
         .group_by(T.ticket_date, T.kode_vendor))
    if supplier_code:
        q = q.where(T.kode_vendor == supplier_code)
    kumpul: dict[tuple[str, str], float] = {}
    for r in session.execute(q):
        bulan = str(r.tanggal)[:7]
        kunci = (bulan, r.kode_vendor)
        kumpul[kunci] = kumpul.get(kunci, 0.0) + float(r.dry or 0)
    hasil = []
    for (bulan, kode), kg in sorted(kumpul.items()):
        mt = kg / 1000.0
        hasil.append({"bulan": bulan, "supplier_code": kode,
                      "dry_mt": round(mt, 3), "kelas": kelas_intake(mt)})
    return hasil


def _koreksi_kunci(T, K):
    return and_(
        func.coalesce(K.source_kabupaten_norm, "") == func.coalesce(T.kabupaten_norm, ""),
        func.coalesce(K.source_kecamatan_norm, "") == func.coalesce(T.kecamatan_norm, ""),
        func.coalesce(K.source_desa_norm, "") == func.coalesce(T.desa_norm, ""),
    )


def _rentang_tahun(session: Session) -> list[int]:
    dialect = session.get_bind().dialect.name
    tahun_sql = (func.strftime("%Y", TiketBaris.ticket_date)
                 if dialect == "sqlite" else func.extract("year", TiketBaris.ticket_date))
    rows = session.scalars(select(tahun_sql).where(
        TiketBaris.ticket_date.is_not(None)).distinct())
    hasil = set()
    for row in rows:
        try:
            hasil.add(int(str(row)[:4]))
        except (ValueError, TypeError):
            continue
    return sorted(hasil, reverse=True)


def _pengaturan(session: Session) -> dict:
    row = session.get(PengaturanTraceability, 1)
    return {"accounting": row.accounting if row else "Paper records (all)",
            "scope": row.scope if row else "Client-specific"}


def _wilayah(session: Session, base, include_rows: bool = True) -> tuple[dict, list[dict]]:
    T = TiketBaris
    K = KoreksiWilayahTrace
    target = aliased(ReferensiWilayahTrace)
    kab_ref = (select(ReferensiWilayahTrace.kabupaten_norm.label("kabupaten_norm"),
                      func.min(ReferensiWilayahTrace.id).label("id"))
              .group_by(ReferensiWilayahTrace.kabupaten_norm).subquery())
    kec_ref = (select(ReferensiWilayahTrace.kabupaten_norm.label("kabupaten_norm"),
                      ReferensiWilayahTrace.kecamatan_norm.label("kecamatan_norm"),
                      func.min(ReferensiWilayahTrace.id).label("id"))
              .group_by(ReferensiWilayahTrace.kabupaten_norm,
                        ReferensiWilayahTrace.kecamatan_norm).subquery())
    desa_ref = (select(ReferensiWilayahTrace.kabupaten_norm.label("kabupaten_norm"),
                       ReferensiWilayahTrace.kecamatan_norm.label("kecamatan_norm"),
                       ReferensiWilayahTrace.desa_norm.label("desa_norm"),
                       func.min(ReferensiWilayahTrace.id).label("id"))
                .group_by(ReferensiWilayahTrace.kabupaten_norm,
                          ReferensiWilayahTrace.kecamatan_norm,
                          ReferensiWilayahTrace.desa_norm).subquery())
    kab = func.coalesce(target.kabupaten_norm, T.kabupaten_norm)
    kec = func.coalesce(target.kecamatan_norm, T.kecamatan_norm)
    desa = func.coalesce(target.desa_norm, T.desa_norm)
    kunci_koreksi = and_(
        func.coalesce(K.source_kabupaten_norm, "") == func.coalesce(T.kabupaten_norm, ""),
        func.coalesce(K.source_kecamatan_norm, "") == func.coalesce(T.kecamatan_norm, ""),
        func.coalesce(K.source_desa_norm, "") == func.coalesce(T.desa_norm, ""),
    )
    manual_match = K.id.is_not(None)
    valid_sumber = T.asal_getah_valid.is_(True)
    reg_ok = and_(or_(manual_match, valid_sumber), kab_ref.c.id.is_not(None))
    kec_ok = and_(or_(manual_match, valid_sumber), kec_ref.c.id.is_not(None))
    desa_ok = and_(or_(manual_match, valid_sumber), desa_ref.c.id.is_not(None))
    q = (select(kab.label("kabupaten_norm"), kec.label("kecamatan_norm"),
                desa.label("desa_norm"),
                func.sum(T.dry_kg).label("dry"),
                func.sum(case((reg_ok, T.dry_kg), else_=0)).label("dry_reg"),
                func.sum(case((kec_ok, T.dry_kg), else_=0)).label("dry_kec"),
                func.sum(case((desa_ok, T.dry_kg), else_=0)).label("dry_desa"),
                func.count(T.id).label("ticket_lines"))
         .select_from(T).join(base, base.c.id == T.id)
         .outerjoin(K, kunci_koreksi)
         .outerjoin(target, target.id == K.target_ref_id)
         .outerjoin(kab_ref, kab_ref.c.kabupaten_norm == kab)
         .outerjoin(kec_ref, and_(kec_ref.c.kabupaten_norm == kab,
                                  kec_ref.c.kecamatan_norm == kec))
         .outerjoin(desa_ref, and_(desa_ref.c.kabupaten_norm == kab,
                                   desa_ref.c.kecamatan_norm == kec,
                                   desa_ref.c.desa_norm == desa))
         .group_by(kab, kec, desa))
    kelompok = list(session.execute(q).mappings())
    total = sum(float(r["dry"] or 0) for r in kelompok)
    traced_reg = sum(float(r["dry_reg"] or 0) for r in kelompok)
    traced_kec = sum(float(r["dry_kec"] or 0) for r in kelompok)
    traced_desa = sum(float(r["dry_desa"] or 0) for r in kelompok)
    tiket = session.scalar(select(func.count(distinct(T.ticket_no)))
                           .select_from(T).join(base, base.c.id == T.id)) or 0

    pohon: dict[str, dict] = {}
    for r in kelompok:
        kabupaten = r["kabupaten_norm"] or "(BELUM DIISI)"
        kecamatan = r["kecamatan_norm"] or "(BELUM DIISI)"
        desa_name = r["desa_norm"] or "(BELUM DIISI)"
        kg = float(r["dry"] or 0)
        regkg, keckg, desakg = (float(r["dry_reg"] or 0),
                                float(r["dry_kec"] or 0), float(r["dry_desa"] or 0))
        tix = int(r["ticket_lines"] or 0)
        if kabupaten not in pohon:
            pohon[kabupaten] = {"name": kabupaten, "level": "Kabupaten/Kota", "code": "",
                                "dry_kg": 0.0, "trace_kg": 0.0, "ticket_lines": 0,
                                "status_code": "belum termapping", "children": {}}
        a = pohon[kabupaten]
        a["dry_kg"] += kg; a["trace_kg"] += regkg; a["ticket_lines"] += tix
        if kecamatan not in a["children"]:
            a["children"][kecamatan] = {"name": kecamatan, "level": "Kecamatan", "code": "",
                                        "dry_kg": 0.0, "trace_kg": 0.0, "ticket_lines": 0,
                                        "status_code": "belum termapping", "children": {}}
        b = a["children"][kecamatan]
        b["dry_kg"] += kg; b["trace_kg"] += keckg; b["ticket_lines"] += tix
        if desa_name not in b["children"]:
            b["children"][desa_name] = {"name": desa_name, "level": "Desa/Kelurahan", "code": "",
                                         "dry_kg": 0.0, "trace_kg": 0.0, "ticket_lines": 0,
                                         "status_code": "belum termapping", "children": {}}
        c = b["children"][desa_name]
        c["dry_kg"] += kg; c["trace_kg"] += desakg; c["ticket_lines"] += tix

    def serialize(node: dict) -> dict:
        dry = node.pop("dry_kg")
        trace = node.pop("trace_kg")
        children = node.pop("children")
        node["dry_mt"] = round(dry / 1000, 3)
        node["traceable_mt"] = round(trace / 1000, 3)
        node["traceability_pct"] = persen_traceable(trace, dry)
        node["traceability_status"] = (
            "traceable" if dry > 0 and trace >= dry - 0.001
            else "partial" if trace > 0 else "unmatched")
        node["children"] = [serialize(children[k]) for k in sorted(children)]
        node["code"] = ""
        return node

    baris = [serialize(pohon[k]) for k in sorted(pohon)] if include_rows else []
    return ({"dry_kg": total, "trace_reg_kg": traced_reg,
             "trace_kec_kg": traced_kec, "trace_desa_kg": traced_desa,
             "tickets": int(tiket), "regencies": len(pohon)}, baris)


def _buat_xlsx(utama: dict, aktor: list[dict], unmapped: list[dict] | None = None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Traceability"
    ws.append(["Level", "Wilayah", "Code", "Dry (MT)", "Dry traceable (MT)",
               "Traceability (%)", "Ticket lines", "Status Code"])
    def tambah(nodes):
        for node in nodes:
            ws.append([node["level"], node["name"], "", node["dry_mt"],
                       node["traceable_mt"], node["traceability_pct"],
                       node["ticket_lines"], "belum termapping"])
            tambah(node["children"])
    tambah(utama["wilayah"])
    wa = wb.create_sheet("Supplier Actors")
    wa.append(["Supplier Code", "Supplier", "Direct Producer", "Tickets", "Dry (MT)",
               "Regencies", "Traceable Dry (MT)", "Sourcing type",
               "Sourcing type source"])
    for a in aktor:
        wa.append([a["supplier_code"], a["supplier"], "Yes" if a["is_direct_producer"] else "No",
                   a["tickets"], a["dry_mt"], a["regencies"], a["traceable_mt"],
                   a.get("sourcing_type"), a.get("sourcing_type_source")])
    if unmapped is not None:
        wu = wb.create_sheet("Unmapped Records")
        wu.append(["Ticket No", "Date", "Supplier Code", "Supplier", "Item Code",
                   "Asal Getah", "Kabupaten/Kota", "Kecamatan", "Desa", "Dry (kg)", "Reason"])
        for r in unmapped:
            wu.append([r.get(k) for k in ("ticket_no", "ticket_date", "supplier_code",
                       "supplier", "item_code", "asal_getah", "kabupaten", "kecamatan",
                       "desa", "dry_kg", "reason")])
    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    return StreamingResponse(buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="traceability.xlsx"'})


def _buat_unmapped_xlsx(rows: list[dict]):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Unmapped Records"
    ws.append(["Ticket No", "Date", "Supplier Code", "Supplier", "Item Code",
               "Asal Getah", "Kabupaten/Kota", "Kecamatan", "Desa",
               "SCDF District", "SCDF Sub-district", "Dry (kg)", "Reason"])
    for r in rows:
        ws.append([r.get(k) for k in ("ticket_no", "ticket_date", "supplier_code",
                   "supplier", "item_code", "asal_getah", "kabupaten", "kecamatan",
                   "desa")]
                   + [None, None, r.get("dry_kg"), r.get("reason")])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.column_dimensions["J"].width = 24
    ws.column_dimensions["K"].width = 28
    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    return StreamingResponse(buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="traceability-unmapped.xlsx"'})


def pasang_router_traceability(app, ambil_session):
    router = APIRouter(prefix="/api/traceability", tags=["Traceability"])
    dep = Depends(ambil_session)

    def filter_data(session: Session, tahun: int | None, periode: str,
                    supplier: str | None, eudr: str, include_latex: bool):
        muat_referensi_bawaan(session)
        years = _rentang_tahun(session)
        tahun_pakai = tahun if tahun is not None else (years[0] if years else None)
        if tahun_pakai is not None:
            try:
                rentang_periode(tahun_pakai, periode)
            except ValueError as exc:
                raise HTTPException(422, str(exc))
        base = _filter_base(session, tahun_pakai, periode, supplier, eudr, include_latex)
        return years, tahun_pakai, base

    def actors(session: Session, base) -> list[dict]:
        """Vendor dan kolektor yang terafiliasi pada desa sumber intake.

        Vendor adalah actor T1. Kolektor T2 digabung ke baris vendor hanya
        bila kode kolektor berasal dari desa sumber intake yang sama dan
        berafiliasi dengan vendor tersebut. Intake tanpa kecocokan kolektor
        tetap tampil sebagai actor vendor saja.
        """
        T = TiketBaris
        K = KoreksiWilayahTrace
        C = Collector
        target = aliased(ReferensiWilayahTrace)
        raw_ref = aliased(ReferensiWilayahTrace)
        reg = select(ReferensiWilayahTrace.kabupaten_norm).distinct().subquery()
        kab_eff = func.coalesce(target.kabupaten_norm, T.kabupaten_norm)
        reg_ok = reg.c.kabupaten_norm == kab_eff
        trace_ok = and_(or_(K.id.is_not(None), T.asal_getah_valid.is_(True)), reg_ok)
        q = (select(T.kode_vendor, C.kode.label("collector_code"),
                    Vendor.nama_baku, Vendor.klasifikasi,
                    Vendor.is_direct_producer, Vendor.sourcing_type,
                    func.min(T.nama_vendor_asli).label("nama_intake"),
                    func.min(C.nama).label("collector_name"),
                    func.count(distinct(T.ticket_no)).label("tickets"),
                    func.sum(T.dry_kg).label("dry"),
                    func.count(distinct(case((reg_ok, kab_eff), else_=None))).label("regencies"),
                    func.sum(case((trace_ok, T.dry_kg), else_=0)).label("trace"))
             .select_from(T).join(base, base.c.id == T.id)
             .outerjoin(K, _koreksi_kunci(T, K))
             .outerjoin(target, target.id == K.target_ref_id)
             .outerjoin(Vendor, Vendor.kode == T.kode_vendor)
             .outerjoin(C, and_(C.kode_vendor == T.kode_vendor,
                                or_(
                                    func.coalesce(C.desa, "") == "",
                                    func.upper(func.replace(func.coalesce(C.desa, ""),
                                                            "_", " ")) == func.coalesce(T.desa_norm, ""),
                                    func.upper(func.replace(func.coalesce(C.desa, ""),
                                                            "_", " ")) == func.coalesce(T.desa, ""),
                                    func.upper(func.replace(func.coalesce(C.desa, ""),
                                                            "_", " ")) == func.coalesce(target.desa_norm, ""))))
             .outerjoin(reg, reg.c.kabupaten_norm == kab_eff)
             .group_by(T.kode_vendor, C.kode, Vendor.nama_baku, Vendor.klasifikasi,
                       Vendor.is_direct_producer, Vendor.sourcing_type)
             .order_by(func.sum(T.dry_kg).desc(), T.kode_vendor, C.kode))
        result: dict[str, dict] = {}
        for r in session.execute(q).mappings():
            code = r["kode_vendor"]
            collector_code = r["collector_code"]
            direct = bool(r["is_direct_producer"])
            klasifikasi = label_klasifikasi(r["klasifikasi"])
            kode_sourcing = r["sourcing_type"]
            label_s = label_sourcing(kode_sourcing)
            if label_s:
                sourcing = label_s
                sumber_sourcing = "Supplier Actors"
            elif direct:
                sourcing = "Direct producer (provisional)"
                sumber_sourcing = "Master Vendor"
            elif klasifikasi:
                sourcing = klasifikasi
                sumber_sourcing = "Master Vendor"
            else:
                sourcing = "Belum diklasifikasi"
                sumber_sourcing = "Belum tersedia pada data intake/master"
            actor = result.setdefault(code, {
                "supplier_code": code,
                "supplier": r["nama_baku"] or r["nama_intake"] or code,
                "is_direct_producer": direct,
                "is_collector": False,
                "collector_code": None,
                "collector_name": None,
                "classification": klasifikasi,
                "tier": "T1",
                "activity_type": klasifikasi,
                "terminal_status": None,
                "sourcing_type": sourcing,
                "sourcing_type_code": kode_sourcing,
                "sourcing_type_source": sumber_sourcing,
                "tickets": 0,
                "dry_mt": 0.0,
                "period_turnover_mt": 0.0,
                "traceable_mt": 0.0,
                "regencies": 0,
                "country": None, "regency": None, "district": None,
                "source_from": 0, "sell_to": None,
            })
            actor["tickets"] += int(r["tickets"] or 0)
            actor["dry_mt"] = round(actor["dry_mt"] + float(r["dry"] or 0) / 1000, 3)
            actor["period_turnover_mt"] = actor["dry_mt"]
            actor["traceable_mt"] = round(actor["traceable_mt"] + float(r["trace"] or 0) / 1000, 3)
            actor["regencies"] = max(actor["regencies"], int(r["regencies"] or 0))
            if collector_code and not actor["is_collector"]:
                actor["is_collector"] = True
                actor["collector_code"] = collector_code
                actor["collector_name"] = r["collector_name"] or collector_code
                actor["tier"] = "T2"

        region_q = (select(
                        T.kode_vendor,
                        T.kabupaten_norm.label("source_kabupaten_norm"),
                        T.kecamatan_norm.label("source_kecamatan_norm"),
                        T.desa_norm.label("source_desa_norm"),
                        func.coalesce(target.kabupaten_norm, T.kabupaten_norm).label("kabupaten_norm"),
                        func.coalesce(target.kecamatan_norm, T.kecamatan_norm).label("kecamatan_norm"),
                        func.coalesce(target.desa_norm, T.desa_norm).label("desa_norm"),
                        func.coalesce(target.kabupaten, raw_ref.kabupaten).label("ref_kabupaten"),
                        func.coalesce(target.kecamatan, raw_ref.kecamatan).label("ref_kecamatan"),
                        func.sum(T.dry_kg).label("dry"))
                    .select_from(T).join(base, base.c.id == T.id)
                    .outerjoin(K, _koreksi_kunci(T, K))
                    .outerjoin(target, target.id == K.target_ref_id)
                    .outerjoin(raw_ref, and_(
                        raw_ref.kabupaten_norm == T.kabupaten_norm,
                        raw_ref.kecamatan_norm == T.kecamatan_norm,
                        raw_ref.desa_norm == T.desa_norm))
                    .group_by(T.kode_vendor, T.kabupaten_norm, T.kecamatan_norm,
                              T.desa_norm, target.kabupaten_norm, target.kecamatan_norm,
                              target.desa_norm, target.kabupaten, target.kecamatan,
                              raw_ref.kabupaten, raw_ref.kecamatan))
        origins: dict[str, list[dict]] = {}
        for r in session.execute(region_q).mappings():
            if not any((r["kabupaten_norm"], r["kecamatan_norm"], r["desa_norm"])):
                continue
            origins.setdefault(r["kode_vendor"], []).append({
                "kabupaten_norm": r["kabupaten_norm"],
                "kecamatan_norm": r["kecamatan_norm"],
                "desa_norm": r["desa_norm"],
                "kabupaten": r["ref_kabupaten"], "kecamatan": r["ref_kecamatan"],
                "dry_kg": float(r["dry"] or 0),
            })
        for code, rows in origins.items():
            rows.sort(key=lambda row: row["dry_kg"], reverse=True)
            best = rows[0]
            actor = result.get(code)
            if not actor:
                continue
            actor["source_from"] = len(rows)
            actor["country"] = "Indonesia"
            actor["regency"] = (best["kabupaten"] or
                                 (best["kabupaten_norm"].title() if best["kabupaten_norm"] else None))
            actor["district"] = (best["kecamatan"] or
                                 (best["kecamatan_norm"].title() if best["kecamatan_norm"] else None))
        return list(result.values())


    @router.get("")
    def ringkasan(tahun: int | None = None, periode: str = "ALL",
                  supplier: str | None = None,
                  eudr: str = Query("all", pattern="^(all|eudr|non_eudr)$"),
                  include_latex: bool = False, format: str | None = None,
                  session: Session = dep):
        years, effective_year, base = filter_data(session, tahun, periode,
                                                  supplier, eudr, include_latex)
        info, tree = _wilayah(session, base)
        supplier_base = _filter_base(session, effective_year, periode, None, "all", True)
        label_supplier = func.coalesce(Vendor.nama_baku, TiketBaris.nama_vendor_asli,
                                       TiketBaris.kode_vendor)
        suppliers = session.execute(
            select(TiketBaris.kode_vendor, label_supplier.label("nama"))
            .select_from(TiketBaris).join(supplier_base, supplier_base.c.id == TiketBaris.id)
            .outerjoin(Vendor, Vendor.kode == TiketBaris.kode_vendor)
            .group_by(TiketBaris.kode_vendor, label_supplier)
            .order_by(label_supplier)
        ).all()
        data = {
            "years": years, "year": effective_year, "period": periode.upper(),
            "filters": {"supplier": supplier, "eudr": eudr,
                        "include_latex": include_latex},
            "kpis": {
                "dry_mt": round(info["dry_kg"] / 1000, 3),
                "trace_reg_mt": round(info["trace_reg_kg"] / 1000, 3),
                "trace_kec_mt": round(info["trace_kec_kg"] / 1000, 3),
                "trace_desa_mt": round(info["trace_desa_kg"] / 1000, 3),
                "trace_reg_pct": persen_traceable(info["trace_reg_kg"], info["dry_kg"]),
                "trace_kec_pct": persen_traceable(info["trace_kec_kg"], info["dry_kg"]),
                "trace_desa_pct": persen_traceable(info["trace_desa_kg"], info["dry_kg"]),
                "tickets": info["tickets"], "regencies": info["regencies"],
            },
            "wilayah": tree,
            "suppliers": [{"kode": kode, "nama": nama or kode}
                          for kode, nama in suppliers],
            "settings": _pengaturan(session),
            "catatan": "Volume menggunakan Dry dari tiket tervalidasi; baris identik pada semua kolom sumber dihitung satu kali. Code belum tersedia pada referensi SCDF sehingga ditampilkan kosong/belum termapping.",
        }
        if format == "xlsx":
            base_for_actors = _filter_base(session, effective_year, periode, supplier,
                                           eudr, include_latex)
            return _buat_xlsx(data, actors(session, base_for_actors))
        return data

    @router.get("/kelas-intake")
    def kelas_intake_supplier(tahun: int | None = None, periode: str = "ALL",
                              supplier: str | None = None,
                              eudr: str = Query("all", pattern="^(all|eudr|non_eudr)$"),
                              include_latex: bool = False, session: Session = dep):
        """Distribusi kelas supplier dari Dry (MT) per supplier per bulan.

        Ringkasan hanya menghitung kode supplier yang punya baris Master
        Vendor; kode yang hanya ada di intake tetap mendapat kelas pada detail
        supplier, dan jumlahnya dilaporkan terpisah agar tidak tersembunyi.
        """
        years, effective_year, base = filter_data(
            session, tahun, periode, supplier, eudr, include_latex)
        semua = _supplier_bulan(session, base, supplier)
        kode_master = set(session.scalars(select(Vendor.kode)))
        terdaftar = [b for b in semua if b["supplier_code"] in kode_master]
        tanpa_master = sorted({b["supplier_code"] for b in semua
                               if b["supplier_code"] not in kode_master})
        return {
            "batas": batas_untuk_layar(),
            "urutan": KELAS_URUTAN,
            "distribusi": distribusi_kelas(b["kelas"] for b in terdaftar),
            "total_supplier_bulan": len(terdaftar),
            "total_dry_mt": round(sum(b["dry_mt"] for b in terdaftar), 3),
            "bulan_tersedia": sorted({b["bulan"] for b in terdaftar}),
            "supplier_bulan_tanpa_master": len(semua) - len(terdaftar),
            "kode_tanpa_master": tanpa_master,
            "catatan": (
                "Kelas dihitung dari Dry (MT) per supplier per bulan dengan tanda ≥ "
                "pada setiap batas. Distribusi hanya menghitung kode supplier yang "
                "terdaftar di Master Vendor; kode yang hanya ada pada tiket intake "
                "tetap mendapat kelas di detail supplier tetapi tidak masuk ringkasan."
            ),
            "filters": {"year": effective_year, "period": periode.upper(),
                        "eudr": eudr, "include_latex": include_latex},
            "years": years,
        }

    @router.get("/actors")
    def supplier_actors(tahun: int | None = None, periode: str = "ALL",
                        supplier: str | None = None,
                        eudr: str = Query("all", pattern="^(all|eudr|non_eudr)$"),
                        include_latex: bool = False, session: Session = dep):
        _, _, base = filter_data(session, tahun, periode, supplier, eudr, include_latex)
        return {"baris": actors(session, base),
                "sourcing_type_options": daftar_sourcing()}

    def _actor_origins(session: Session, base, supplier_code: str) -> list[dict]:
        T = TiketBaris
        K = KoreksiWilayahTrace
        target = aliased(ReferensiWilayahTrace)
        raw_ref = aliased(ReferensiWilayahTrace)
        q = (select(T.kabupaten_norm.label("source_kabupaten_norm"),
                    T.kecamatan_norm.label("source_kecamatan_norm"),
                    T.desa_norm.label("source_desa_norm"),
                    func.min(T.kabupaten).label("source_kabupaten"),
                    func.min(T.kecamatan).label("source_kecamatan"),
                    func.min(T.desa).label("source_desa"),
                    K.id.label("correction_id"),
                    func.coalesce(target.id, raw_ref.id).label("ref_id"),
                    func.coalesce(target.kabupaten, raw_ref.kabupaten).label("ref_kabupaten"),
                    func.coalesce(target.kecamatan, raw_ref.kecamatan).label("ref_kecamatan"),
                    func.coalesce(target.kecamatan_norm, raw_ref.kecamatan_norm).label("ref_kecamatan_norm"),
                    func.coalesce(target.desa, raw_ref.desa).label("ref_desa"),
                    func.coalesce(target.desa_norm, raw_ref.desa_norm).label("ref_desa_norm"),
                    func.sum(T.dry_kg).label("dry"),
                    func.sum(case((or_(K.id.is_not(None),
                                       and_(T.asal_getah_valid.is_(True), raw_ref.id.is_not(None))),
                                   T.dry_kg), else_=0)).label("trace_dry"),
                    func.count(distinct(T.ticket_no)).label("tickets"))
             .select_from(T).join(base, base.c.id == T.id)
             .outerjoin(K, _koreksi_kunci(T, K))
             .outerjoin(target, target.id == K.target_ref_id)
             .outerjoin(raw_ref, and_(raw_ref.kabupaten_norm == T.kabupaten_norm,
                                      raw_ref.kecamatan_norm == T.kecamatan_norm,
                                      raw_ref.desa_norm == T.desa_norm))
             .where(T.kode_vendor == supplier_code)
             .group_by(T.kabupaten_norm, T.kecamatan_norm, T.desa_norm,
                       K.id, target.id, raw_ref.id, target.kabupaten, raw_ref.kabupaten,
                       target.kecamatan, raw_ref.kecamatan, target.kecamatan_norm,
                       raw_ref.kecamatan_norm, target.desa, raw_ref.desa,
                       target.desa_norm, raw_ref.desa_norm)
             .order_by(func.sum(T.dry_kg).desc()))
        raw = list(session.execute(q).mappings())
        total_kg = sum(float(r["dry"] or 0) for r in raw)
        origins = []
        for r in raw:
            kg = float(r["dry"] or 0)
            if kg <= 0:
                continue
            traced = float(r["trace_dry"] or 0)
            matched = bool(r["ref_id"] and traced >= kg - 0.001)
            origins.append({
                "country": "Indonesia",
                "regency": r["ref_kabupaten"] or
                (r["source_kabupaten_norm"].title() if r["source_kabupaten_norm"] else None),
                "district": r["ref_kecamatan"] or
                (r["source_kecamatan_norm"].title() if r["source_kecamatan_norm"] else None),
                "sub_district": r["ref_desa"] or
                (r["source_desa_norm"].title() if r["source_desa_norm"] else None),
                "target_district_norm": r["ref_kecamatan_norm"] or r["source_kecamatan_norm"] or "",
                "target_subdistrict_norm": r["ref_desa_norm"] or r["source_desa_norm"] or "",
                "source_regency": r["source_kabupaten"] or r["source_kabupaten_norm"],
                "source_district": r["source_kecamatan"] or r["source_kecamatan_norm"],
                "source_sub_district": r["source_desa"] or r["source_desa_norm"],
                "source_key": {
                    "kabupaten_norm": r["source_kabupaten_norm"] or "",
                    "kecamatan_norm": r["source_kecamatan_norm"] or "",
                    "desa_norm": r["source_desa_norm"] or "",
                },
                "dry_mt": round(kg / 1000, 3),
                "share_pct": persen_traceable(kg, total_kg),
                "traceable_mt": round(traced / 1000, 3),
                "traceability_pct": persen_traceable(traced, kg),
                "matched_to_id_aux": matched,
                "manual_correction": bool(r["correction_id"]),
                "tickets": int(r["tickets"] or 0),
            })
        return origins

    def _supply_chain_lanes(session: Session, supplier_code: str,
                            origins: list[dict]) -> dict:
        """Lintasan rantai: Asal Getah -> Kolektor (T2) -> Vendor (T1).

        Kolektor bukan aktor terpisah. Satu lintasan = satu kelompok lokasi
        sumber dari ``_actor_origins``; kolektor dicocokkan lewat afiliasi
        vendor yang sama dan kesamaan desa (nama asli maupun hasil koreksi
        SCDF). Kolektor tanpa desa berlaku untuk semua desa. Volume diambil
        langsung dari kelompok lokasi, sehingga tidak dihitung berulang
        ketika beberapa kolektor cocok.
        """
        terdaftar = list(session.scalars(
            select(Collector).where(Collector.kode_vendor == supplier_code)
            .order_by(Collector.kode)))
        lanes: list[dict] = []
        kode_cocok: set[str] = set()
        for origin in origins:
            kunci = origin.get("source_key") or {}
            desa_sumber = {
                _desa_norm(origin.get("source_sub_district")),
                _desa_norm(origin.get("sub_district")),
                _desa_norm(origin.get("target_subdistrict_norm")),
                _desa_norm(kunci.get("desa_norm")),
            }
            desa_sumber.discard("")
            cocok: list[dict] = []
            for c in terdaftar:
                c_desa = _desa_norm(c.desa)
                if c_desa and c_desa not in desa_sumber:
                    continue
                cocok.append({
                    "kode": c.kode,
                    "nama": c.nama,
                    "desa": c.desa,
                    "match": "desa" if c_desa else "semua_desa",
                })
                kode_cocok.add(c.kode)
            # Kolektor dengan desa spesifik didahulukan daripada wildcard.
            cocok.sort(key=lambda x: (x["match"] == "semua_desa", x["kode"]))
            lanes.append({
                "origin": origin,
                "mode": "T2" if cocok else "T1",
                "collector": cocok[0] if cocok else None,
                "collectors": cocok,
                "ambiguous": len(cocok) > 1,
                "dry_mt": origin["dry_mt"],
                "tickets": origin["tickets"],
                "traceable_mt": origin["traceable_mt"],
            })
        return {
            "nodes": ["Asal Getah", "Kolektor (T2)", "Vendor (T1)"],
            "lane_count": len(lanes),
            "lanes": lanes,
            "ambiguous_lane_count": sum(1 for l in lanes if l["ambiguous"]),
            "registered_collectors": len(terdaftar),
            "matched_collectors": sorted(kode_cocok),
            "collector_count": len(kode_cocok),
            "total_dry_mt": round(sum(l["dry_mt"] for l in lanes), 3),
            "note": (
                "Satu baris Supplier Actors = satu rantai. Lintasan disusun dari "
                "kesamaan desa Asal Getah dan afiliasi kolektor ke vendor; ini "
                "inferensi dari data intake, bukan catatan transaksi jual-beli. "
                "Pabrik/titik terima tidak tercatat pada data sehingga tidak "
                "ditampilkan sebagai simpul."
            ),
            "ticket_note": (
                "Tiket dihitung per kelompok lokasi sumber. Satu tiket yang "
                "memuat beberapa desa dapat muncul di lebih dari satu lintasan; "
                "pakai total tiket unik pada ringkasan untuk angka keseluruhan."
            ),
        }

    @router.get("/tree")
    @router.get("/pohon", include_in_schema=False)
    def pohon_rantai_pasok(
        tahun: int | None = None,
        periode: str = "ALL",
        supplier: str | None = None,
        eudr: str = Query("all", pattern="^(all|eudr|non_eudr)$"),
        include_latex: bool = False,
        batas: int = Query(8, ge=0, le=100,
                           description="Jumlah T1 terbesar; 0 = semua vendor"),
        session: Session = dep):
        """Pohon rantai pasok dari data intake + master, bukan contoh statis.

        Kode tier sengaja dipertahankan: **T1 = vendor**, **T2 = kolektor**.
        Pabrik hanya simpul akar visual; volumenya adalah jumlah Dry (kg)
        vendor T1 yang tampil. Volume T2 berasal dari lintasan
        ``_supply_chain_lanes`` sehingga tidak dihitung berulang saat satu
        desa cocok dengan beberapa kolektor.
        """
        years, effective_year, base = filter_data(
            session, tahun, periode, supplier, eudr, include_latex)
        semua = actors(session, base)
        semua.sort(key=lambda a: (
            -float(a.get("period_turnover_mt") or 0),
            str(a.get("supplier_code") or "")))
        dipilih = semua if batas == 0 else semua[:batas]

        nodus: list[dict] = [{
            "id": "PABRIK", "kode": "PABRIK", "nama": "Pabrik",
            "tier": "PABRIK", "label": "Pabrik", "volume_kg": 0.0,
            "tickets": 0, "parents": [],
        }]
        sambungan: list[dict] = []
        t2_map: dict[str, dict] = {}
        anak_t1: dict[str, list[str]] = {}
        ambiguous = 0
        langsung_kg = 0.0

        for a in dipilih:
            kode = str(a.get("supplier_code") or "")
            if not kode:
                continue
            nama = str(a.get("supplier") or kode)
            kg = round(float(a.get("period_turnover_mt") or 0) * 1000, 1)
            if kg <= 0:
                continue
            tiket = int(a.get("tickets") or 0)
            nodus.append({
                "id": kode, "kode": kode, "nama": nama, "tier": "T1",
                "label": kode, "volume_kg": kg, "tickets": tiket,
                "parents": ["PABRIK"],
            })
            sambungan.append({"dari": "PABRIK", "ke": kode, "volume_kg": kg})

            origins = _actor_origins(session, base, kode)
            rantai = _supply_chain_lanes(session, kode, origins)
            ambiguous += int(rantai.get("ambiguous_lane_count") or 0)
            per_kolektor: dict[str, float] = {}
            info_kolektor: dict[str, dict] = {}
            for lane in rantai.get("lanes") or []:
                for c in lane.get("collectors") or []:
                    ck_info = str(c.get("kode") or "")
                    if ck_info:
                        info_kolektor.setdefault(ck_info, {
                            "nama": c.get("nama") or ck_info,
                            "desa": c.get("desa"),
                            "match": c.get("match"),
                        })
                c = lane.get("collector")
                if not c:
                    continue
                ck = str(c.get("kode") or "")
                if not ck:
                    continue
                per_kolektor[ck] = (per_kolektor.get(ck, 0.0)
                                    + float(lane.get("dry_mt") or 0) * 1000)

            anak: list[str] = []
            for ck, nilai in sorted(per_kolektor.items(), key=lambda x: -x[1]):
                kg_c = round(nilai, 1)
                if kg_c <= 0:
                    continue
                info = info_kolektor.get(ck, {})
                rek = t2_map.setdefault(ck, {
                    "id": ck, "kode": ck,
                    "nama": info.get("nama") or ck,
                    "tier": "T2", "label": ck,
                    "volume_kg": 0.0, "desa": info.get("desa"),
                    "match": info.get("match"), "parents": [],
                })
                rek["volume_kg"] = round(rek["volume_kg"] + kg_c, 1)
                if kode not in rek["parents"]:
                    rek["parents"].append(kode)
                sambungan.append({"dari": kode, "ke": ck, "volume_kg": kg_c})
                anak.append(ck)
            anak_t1[kode] = anak
            langsung_kg += max(0.0, kg - sum(per_kolektor.values()))

        t2_nodes = sorted(t2_map.values(),
                          key=lambda n: (-float(n["volume_kg"]), str(n["kode"])))
        nodus.extend(t2_nodes)
        root_kg = round(sum(float(n["volume_kg"]) for n in nodus
                            if n["tier"] == "T1"), 1)
        nodus[0]["volume_kg"] = root_kg
        nodus[0]["tickets"] = sum(int(n.get("tickets") or 0) for n in nodus
                                  if n["tier"] == "T1")
        return {
            "sumber": "tiket_baris + Master Vendor + Master Collector",
            "filters": {
                "year": effective_year, "period": periode.upper(),
                "supplier": supplier, "eudr": eudr,
                "include_latex": include_latex, "batas": batas,
            },
            "years": years,
            "kode_tier": {"PABRIK": "Pabrik", "T1": "Vendor", "T2": "Kolektor"},
            "nodes": nodus,
            "edges": sambungan,
            "anak_t1": anak_t1,
            "meta": {
                "total_t1": len([n for n in nodus if n["tier"] == "T1"]),
                "total_t2": len(t2_nodes),
                "total_t1_semua": len(semua),
                "terpotong": max(0, len(semua) - len(dipilih)),
                "volume_pabrik_kg": root_kg,
                "volume_tanpa_kolektor_kg": round(langsung_kg, 1),
                "ambiguous_lane_count": ambiguous,
            },
            "catatan": (
                "Data asli dari tiket intake dan master; T1 tetap vendor, T2 tetap "
                "kolektor. Pabrik adalah simpul akar visual. Volume memakai Dry (kg) "
                "pada filter halaman. Sebagian volume T1 dapat langsung masuk tanpa "
                "kolektor tercatat; volume T2 adalah jumlah lintasan yang mempunyai "
                "kolektor, bukan volume vendor yang diduplikasi."
            ),
        }

    @router.get("/actors/{supplier_code}")
    def detail_supplier_actor(supplier_code: str, tahun: int | None = None,
                              periode: str = "ALL", eudr: str = "all",
                              include_latex: bool = False,
                              session: Session = dep):
        years, effective_year, base = filter_data(
            session, tahun, periode, supplier_code, eudr, include_latex)
        origins = _actor_origins(session, base, supplier_code)
        T = TiketBaris
        nama_intake = session.scalar(select(func.min(T.nama_vendor_asli))
            .select_from(T).join(base, base.c.id == T.id)
            .where(T.kode_vendor == supplier_code))
        vendor = session.get(Vendor, supplier_code)
        if vendor is None and nama_intake is None:
            raise HTTPException(404, f"Supplier '{supplier_code}' tidak ditemukan pada intake.")

        total_kg = sum(float(r["dry_mt"] * 1000) for r in origins)
        ticket_count = session.scalar(
            select(func.count(distinct(T.ticket_no)))
            .select_from(T).join(base, base.c.id == T.id)
            .where(T.kode_vendor == supplier_code)
        ) or 0
        classification = label_klasifikasi(vendor.klasifikasi) if vendor else None
        direct = bool(vendor.is_direct_producer) if vendor else False
        kode_sourcing = vendor.sourcing_type if vendor else None
        label_s = label_sourcing(kode_sourcing)
        has_collector = bool(session.scalar(
            select(Collector.kode).where(Collector.kode_vendor == supplier_code)
            .limit(1)))
        origin_desas = {_desa_norm(row["source_sub_district"])
                       or _desa_norm(row["sub_district"])
                       or _desa_norm(row["source_key"]["desa_norm"]) for row in origins}
        matched_collector = next(
            (c for c in session.scalars(
                select(Collector).where(Collector.kode_vendor == supplier_code)
                .order_by(Collector.kode))
             if _desa_norm(c.desa) in origin_desas or not _desa_norm(c.desa)), None)
        has_collector = matched_collector is not None
        rantai = _supply_chain_lanes(session, supplier_code, origins)
        rantai["tier"] = "T2" if has_collector else "T1"
        bulan_kelas = _supplier_bulan(session, base, supplier_code)
        supplier_class = kelas_tertinggi([b["kelas"] for b in bulan_kelas])
        return {
            "supplier_code": supplier_code,
            "supplier": (vendor.nama_baku if vendor else None) or nama_intake or supplier_code,
            "alt_id": vendor.varian_nama if vendor else None,
            "product": vendor.kategori if vendor else None,
            "activity_type": classification,
            "is_collector": has_collector,
            "collector_code": matched_collector.kode if matched_collector else None,
            "collector_name": matched_collector.nama if matched_collector else None,
            "terminal_status": None,
            "tier": "T2" if has_collector else "T1",
            "period_turnover_mt": round(total_kg / 1000, 3),
            "tickets": int(ticket_count),
            "country": "Indonesia" if origins else None,
            "top_geography": origins[0] if origins else None,
            "origins": origins,
            "supply_chain": rantai,
            "supplier_class": supplier_class,
            "class_by_month": bulan_kelas,
            "class_thresholds": batas_untuk_layar(),
            "class_basis": (
                "Kelas tertinggi yang dicapai pada periode terpilih, dihitung dari "
                "Dry (MT) per supplier per bulan dengan tanda ≥ pada setiap batas. "
                "Bukan klasifikasi Master Vendor dan bukan sourcing type."
            ),
            "classification": classification,
            "is_direct_producer": direct,
            "sourcing_type_code": kode_sourcing,
            "sourcing_type_label": (label_s or
                                    ("Direct producer (provisional)" if direct
                                     else (classification or "Belum diklasifikasi"))),
            "sourcing_type_source": ("Supplier Actors" if label_s
                                     else ("Master Vendor" if classification or direct
                                           else "Belum tersedia pada data intake/master")),
            "sourcing_type_options": daftar_sourcing(),
            "coordinates": None,
            "coordinates_note": "Koordinat tidak tersedia pada referensi SCDF atau data intake.",
            "source_from": origins,
            "sell_to": [],
            "supply_chain_note": "Intake mencatat wilayah Asal Getah, bukan hubungan upstream/downstream supplier-ke-pabrik.",
            "filters": {"year": effective_year, "period": periode.upper(),
                        "eudr": eudr, "include_latex": include_latex},
            "years": years,
        }

    @router.put("/actors/{supplier_code}/sourcing-type")
    def ubah_sourcing_type(supplier_code: str, data: SourcingTypeMasuk,
                           request: Request, session: Session = dep):
        """Simpan sourcing type yang dipilih langsung di tabel Supplier Actors.

        Field `klasifikasi` Master Vendor sengaja tidak disentuh. Bila kode
        supplier hanya ada di intake (belum punya baris master), baris master
        minimal disiapkan memakai nama vendor asli dari tiket.
        """
        kode = (supplier_code or "").strip().upper()
        try:
            baru = bakukan_sourcing(data.sourcing_type)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        vendor = session.get(Vendor, kode)
        if vendor is None:
            nama = session.scalar(
                select(func.min(TiketBaris.nama_vendor_asli))
                .where(TiketBaris.kode_vendor == kode))
            if not nama:
                raise HTTPException(
                    404, f"Supplier '{kode}' tidak ditemukan pada intake/master.")
            vendor = Vendor(kode=kode, nama_baku=nama, status="aktif")
            session.add(vendor)
        lama = vendor.sourcing_type
        vendor.sourcing_type = baru
        pengguna = info_pengguna(request) or {}
        catat_audit(session, pengguna.get("sub") or data.pengisi or "?",
                    "ubah", "vendor", {
                        "kode": kode, "field": "sourcing_type",
                        "lama": lama, "baru": baru,
                        "catatan": "Diisi dari form Supplier Actors; klasifikasi tidak diubah"})
        session.commit()
        return {"status": "tersimpan",
                "pesan": f"Sourcing type {kode}: "
                         f"{label_sourcing(baru) or 'Belum diisi'}.",
                "supplier_code": kode,
                "sourcing_type_code": baru,
                "sourcing_type_label": label_sourcing(baru)}

    @router.get("/locations/districts")
    def pilihan_district(kabupaten_norm: str, session: Session = dep):
        """Daftar District resmi SCDF di dalam Kabupaten/Kota yang dipilih."""
        muat_referensi_bawaan(session)
        kab = normalisasi_kabupaten(kabupaten_norm)
        rows = session.execute(
            select(ReferensiWilayahTrace.kecamatan_norm,
                   func.min(ReferensiWilayahTrace.kecamatan).label("label"))
            .where(ReferensiWilayahTrace.kabupaten_norm == kab)
            .group_by(ReferensiWilayahTrace.kecamatan_norm)
            .order_by(ReferensiWilayahTrace.kecamatan_norm)
        ).all()
        return {"options": [{"value": norm, "label": label}
                             for norm, label in rows if norm and label]}

    @router.get("/locations/subdistricts")
    def pilihan_subdistrict(kabupaten_norm: str, kecamatan_norm: str,
                            session: Session = dep):
        muat_referensi_bawaan(session)
        kab = normalisasi_kabupaten(kabupaten_norm)
        kec = normalisasi_teks_wilayah(kecamatan_norm)
        rows = session.execute(
            select(ReferensiWilayahTrace.desa_norm,
                   func.min(ReferensiWilayahTrace.desa).label("label"))
            .where(ReferensiWilayahTrace.kabupaten_norm == kab,
                   ReferensiWilayahTrace.kecamatan_norm == kec)
            .group_by(ReferensiWilayahTrace.desa_norm)
            .order_by(ReferensiWilayahTrace.desa_norm)
        ).all()
        return {"options": [{"value": norm, "label": label}
                             for norm, label in rows if norm and label]}

    @router.get("/actors/{supplier_code}/origin-recommendations")
    def rekomendasi_subdistrict(supplier_code: str, source_kabupaten_norm: str,
                                source_kecamatan_norm: str, tahun: int | None = None,
                                eudr: str = "all", include_latex: bool = False,
                                session: Session = dep):
        muat_referensi_bawaan(session)
        years = _rentang_tahun(session)
        year = tahun if tahun is not None else (years[0] if years else None)
        if year is None:
            return {"recommendations": [], "history_through": None,
                    "basis": "Belum ada tahun intake yang dapat dijadikan dasar."}
        kab = normalisasi_kabupaten(source_kabupaten_norm) or ""
        kec = normalisasi_teks_wilayah(source_kecamatan_norm) or ""
        if not kab or not kec:
            return {"recommendations": [], "history_through": year - 1,
                    "basis": "Regency/District sumber belum cukup lengkap untuk rekomendasi."}

        T = TiketBaris
        K = KoreksiWilayahTrace
        target = aliased(ReferensiWilayahTrace)
        raw_ref = aliased(ReferensiWilayahTrace)
        history_base = _filter_base(session, None, "ALL", supplier_code,
                                    eudr, include_latex)
        tahun_sql = (func.strftime("%Y", T.ticket_date)
                     if session.get_bind().dialect.name == "sqlite"
                     else func.extract("year", T.ticket_date))
        kab_eff = func.coalesce(target.kabupaten_norm, T.kabupaten_norm)
        kec_eff = func.coalesce(target.kecamatan_norm, T.kecamatan_norm)
        desa_eff = func.coalesce(target.desa_norm, T.desa_norm)
        tahun_lalu = dt.date(year, 1, 1)
        q = (select(desa_eff.label("desa_norm"),
                    func.coalesce(target.desa, raw_ref.desa).label("desa"),
                    func.sum(T.dry_kg).label("dry"),
                    func.count(distinct(T.ticket_no)).label("tickets"),
                    func.count(distinct(tahun_sql)).label("years"))
             .select_from(T).join(history_base, history_base.c.id == T.id)
             .outerjoin(K, _koreksi_kunci(T, K))
             .outerjoin(target, target.id == K.target_ref_id)
             .outerjoin(raw_ref, and_(raw_ref.kabupaten_norm == T.kabupaten_norm,
                                      raw_ref.kecamatan_norm == T.kecamatan_norm,
                                      raw_ref.desa_norm == T.desa_norm))
             .where(T.kode_vendor == supplier_code,
                    T.ticket_date < tahun_lalu,
                    kab_eff == kab, kec_eff == kec,
                    or_(K.id.is_not(None),
                        and_(T.asal_getah_valid.is_(True), raw_ref.id.is_not(None))))
             .group_by(desa_eff, target.desa, raw_ref.desa)
             .order_by(func.sum(T.dry_kg).desc()))
        rows = list(session.execute(q).mappings())
        total_dry = sum(float(r["dry"] or 0) for r in rows)
        recommendations = [{
            "sub_district_norm": r["desa_norm"],
            "sub_district": r["desa"],
            "confidence_pct": persen_traceable(float(r["dry"] or 0), total_dry),
            "historical_dry_mt": round(float(r["dry"] or 0) / 1000, 3),
            "historical_tickets": int(r["tickets"] or 0),
            "historical_years": int(r["years"] or 0),
        } for r in rows if r["desa_norm"] and r["desa"]]
        return {
            "recommendations": recommendations,
            "history_through": year - 1,
            "basis": ("Persentase adalah porsi Dry historis supplier ini pada Regency "
                      "dan District yang sama; ini indikator rekomendasi, bukan "
                      "probabilitas bahwa lokasi saat ini pasti benar."),
        }

    @router.get("/actors/{supplier_code}/origin-typo-check")
    def deteksi_salah_ketik_asal(
            supplier_code: str,
            source_kabupaten_norm: str = Query(..., max_length=120),
            source_kecamatan_norm: str = Query(..., max_length=120),
            source_desa_norm: str = Query(..., max_length=120),
            source_kecamatan: str | None = Query(default=None, max_length=120),
            source_desa: str | None = Query(default=None, max_length=120),
            session: Session = dep):
        """Bandingkan District/Sub-district sumber dengan ejaan resmi SCDF.

        Ini PELENGKAP rekomendasi intake tahun sebelumnya, bukan turunan dari
        riwayat pembelian. Tidak ada data yang disimpan. Kandidat boleh berada
        di Kabupaten/Kota SCDF lain; induk sumber tidak ditebak salah ketik,
        tetapi pemetaan lintas induk tetap bisa dipilih secara eksplisit.
        """
        muat_referensi_bawaan(session)
        kab_sumber = normalisasi_kabupaten(source_kabupaten_norm) or ""
        kec_sumber = normalisasi_teks_wilayah(source_kecamatan_norm) or ""
        desa_sumber = normalisasi_teks_wilayah(source_desa_norm) or ""
        sumber = {
            "supplier_code": supplier_code,
            "kabupaten_norm": kab_sumber,
            "kecamatan_norm": kec_sumber,
            "desa_norm": desa_sumber,
            "kecamatan": source_kecamatan or kec_sumber,
            "desa": source_desa or desa_sumber,
        }
        dasar = (
            "Membandingkan ejaan District dan Sub-district sumber dengan nama "
            "resmi pada referensi SCDF. Huruf, spasi, tanda baca, dan awalan "
            "umum seperti Gampong/Keuchik dibakukan terlebih dahulu. Ini "
            "bukan rekomendasi pembelian/intake tahun sebelumnya."
        )
        catatan = (
            "Skor kemiripan bukan probabilitas dan bukan vonis lokasi benar. "
            "Tombol Pakai hanya mengisi pilihan; data tersimpan setelah Simpan. "
            "Intake asli tetap tidak diubah."
        )
        if not kec_sumber or not desa_sumber:
            return {"status": "sumber_tidak_lengkap", "source": sumber,
                    "checks": {}, "candidates": [], "basis": dasar,
                    "catatan": catatan}
        jumlah_ref = session.scalar(
            select(func.count()).select_from(ReferensiWilayahTrace)) or 0
        if not jumlah_ref:
            return {"status": "referensi_kosong", "source": sumber,
                    "checks": {}, "candidates": [], "basis": dasar,
                    "pesan": "Referensi SCDF belum termuat.", "catatan": catatan}

        ada_district = session.scalar(
            select(ReferensiWilayahTrace.id)
            .where(ReferensiWilayahTrace.kabupaten_norm == kab_sumber,
                   ReferensiWilayahTrace.kecamatan_norm == kec_sumber)
            .limit(1)) is not None
        ada_subdistrict = session.scalar(
            select(ReferensiWilayahTrace.id)
            .where(ReferensiWilayahTrace.kabupaten_norm == kab_sumber,
                   ReferensiWilayahTrace.kecamatan_norm == kec_sumber,
                   ReferensiWilayahTrace.desa_norm == desa_sumber)
            .limit(1)) is not None

        baris_kec = session.execute(
            select(ReferensiWilayahTrace.kecamatan_norm,
                   func.min(ReferensiWilayahTrace.kecamatan).label("label"))
            .group_by(ReferensiWilayahTrace.kecamatan_norm)).all()
        baris_desa = session.execute(
            select(ReferensiWilayahTrace.desa_norm,
                   func.min(ReferensiWilayahTrace.desa).label("label"))
            .group_by(ReferensiWilayahTrace.desa_norm)).all()
        label_kec = {r[0]: r[1] for r in baris_kec if r[0] and r[1]}
        label_desa = {r[0]: r[1] for r in baris_desa if r[0] and r[1]}
        indeks_kec = indeks_kandidat(list(label_kec.items()))
        indeks_desa = indeks_kandidat(list(label_desa.items()))
        kec_mirip = norma_mirip(kec_sumber, indeks_kec, maksimal=18)
        desa_mirip = norma_mirip(desa_sumber, indeks_desa, maksimal=24)
        if kec_sumber in label_kec:
            kec_mirip[kec_sumber] = 100.0
        if desa_sumber in label_desa:
            desa_mirip[desa_sumber] = 100.0
        kec_mirip = dict(sorted(kec_mirip.items(),
                                key=lambda kv: (-kv[1], kv[0]))[:18])
        desa_mirip = dict(sorted(desa_mirip.items(),
                                 key=lambda kv: (-kv[1], kv[0]))[:24])

        def ringkasan(norm: str, peta: dict[str, str],
                      mirip: dict[str, float], exact: bool) -> dict:
            daftar = [{"norm": k, "label": peta.get(k, k), "score_pct": v}
                      for k, v in list(mirip.items())[:3]]
            return {"input": norm, "exact": exact, "best": daftar[0] if daftar else None,
                    "candidates": daftar}

        checks = {
            "district": ringkasan(kec_sumber, label_kec, kec_mirip, ada_district),
            "subdistrict": ringkasan(desa_sumber, label_desa, desa_mirip,
                                     ada_subdistrict),
        }
        if ada_subdistrict:
            return {"status": "cocok", "source": sumber, "checks": checks,
                    "candidates": [], "basis": dasar,
                    "pesan": "District dan Sub-district sumber sudah persis ada "
                             "pada referensi SCDF untuk induk ini.",
                    "catatan": catatan}

        kandidat: list[dict] = []
        if kec_mirip and desa_mirip:
            calon = session.execute(
                select(ReferensiWilayahTrace.id,
                       ReferensiWilayahTrace.kabupaten_norm,
                       ReferensiWilayahTrace.kabupaten,
                       ReferensiWilayahTrace.kecamatan_norm,
                       ReferensiWilayahTrace.kecamatan,
                       ReferensiWilayahTrace.desa_norm,
                       ReferensiWilayahTrace.desa)
                .where(ReferensiWilayahTrace.kecamatan_norm.in_(list(kec_mirip)),
                       ReferensiWilayahTrace.desa_norm.in_(list(desa_mirip)))
                .limit(6000)).mappings()
            ambang_kec = ambang_untuk(kec_sumber)
            ambang_desa = ambang_untuk(desa_sumber)
            seen: set[int] = set()
            for r in calon:
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                skor_kec = skor_kemiripan(kec_sumber, r["kecamatan_norm"])
                skor_desa = skor_kemiripan(desa_sumber, r["desa_norm"])
                if skor_kec < ambang_kec and skor_desa < ambang_desa:
                    continue
                skor = skor_pasangan(skor_kec, skor_desa)
                if skor < 60.0:
                    continue
                kandidat.append({
                    "ref_id": r["id"],
                    "kabupaten": r["kabupaten"],
                    "kabupaten_norm": r["kabupaten_norm"],
                    "kecamatan": r["kecamatan"],
                    "kecamatan_norm": r["kecamatan_norm"],
                    "desa": r["desa"],
                    "desa_norm": r["desa_norm"],
                    "district_score_pct": skor_kec,
                    "subdistrict_score_pct": skor_desa,
                    "score_pct": skor,
                    "same_regency": r["kabupaten_norm"] == kab_sumber,
                    "dapat_dipakai": True,
                    "alasan": (f"District {skor_kec:.1f}% · "
                               f"Sub-district {skor_desa:.1f}%"),
                })
        kandidat.sort(key=lambda c: (
            not c["same_regency"], -c["score_pct"],
            -c["subdistrict_score_pct"], c["kabupaten"], c["kecamatan"], c["desa"]))
        total_kandidat = len(kandidat)
        kandidat = kandidat[:6]
        return {
            "status": "potensi_salah_ketik" if kandidat else "tidak_ada_kandidat",
            "source": sumber, "checks": checks, "candidates": kandidat,
            "candidate_count": total_kandidat, "basis": dasar,
            "pesan": ("Ditemukan ejaan SCDF yang mirip; periksa sebelum memakai."
                      if kandidat else
                      "Tidak ada ejaan SCDF yang cukup mirip untuk ditawarkan."),
            "catatan": catatan,
        }

    @router.put("/actors/{supplier_code}/origin-correction")
    def simpan_koreksi_asal(supplier_code: str, data: KoreksiLokasiMasuk,
                            request: Request, tahun: int | None = None,
                            periode: str = "ALL", eudr: str = "all",
                            include_latex: bool = False,
                            session: Session = dep):
        _, _, base = filter_data(session, tahun, periode, supplier_code, eudr, include_latex)
        source_kab = normalisasi_kabupaten(data.source_kabupaten_norm) or ""
        source_kec = normalisasi_teks_wilayah(data.source_kecamatan_norm) or ""
        source_desa = normalisasi_teks_wilayah(data.source_desa_norm) or ""
        T = TiketBaris
        ada_sumber = session.scalar(
            select(T.id).select_from(T).join(base, base.c.id == T.id)
            .where(T.kode_vendor == supplier_code,
                   func.coalesce(T.kabupaten_norm, "") == source_kab,
                   func.coalesce(T.kecamatan_norm, "") == source_kec,
                   func.coalesce(T.desa_norm, "") == source_desa).limit(1))
        if not ada_sumber:
            raise HTTPException(404, "Lokasi sumber tidak ditemukan pada tiket supplier/filter ini.")
        koreksi = session.scalar(select(KoreksiWilayahTrace).where(
            KoreksiWilayahTrace.source_kabupaten_norm == source_kab,
            KoreksiWilayahTrace.source_kecamatan_norm == source_kec,
            KoreksiWilayahTrace.source_desa_norm == source_desa))
        sebelumnya = koreksi.target_ref_id if koreksi else None
        target_kab_norm = normalisasi_kabupaten(
            data.target_kabupaten_norm) or source_kab
        target_kec_norm = normalisasi_teks_wilayah(
            data.target_kecamatan_norm or source_kec)
        target_norm = normalisasi_teks_wilayah(data.target_desa_norm)
        if target_norm:
            target = session.scalar(select(ReferensiWilayahTrace).where(
                ReferensiWilayahTrace.kabupaten_norm == target_kab_norm,
                ReferensiWilayahTrace.kecamatan_norm == target_kec_norm,
                ReferensiWilayahTrace.desa_norm == target_norm))
            if target is None:
                raise HTTPException(422,
                    "Pilih pasangan Kabupaten/Kota, District, dan Sub-district resmi SCDF.")
            if koreksi is None:
                koreksi = KoreksiWilayahTrace(
                    source_kabupaten_norm=source_kab,
                    source_kecamatan_norm=source_kec,
                    source_desa_norm=source_desa,
                    target_ref_id=target.id)
                session.add(koreksi)
            else:
                koreksi.target_ref_id = target.id
            pengguna = info_pengguna(request) or {}
            koreksi.updated_by = pengguna.get("sub") or "pengguna aplikasi"
            koreksi.updated_at = dt.datetime.utcnow()
            aksi = "ubah" if sebelumnya else "tambah"
            catat_audit(session, koreksi.updated_by, aksi, "traceability_wilayah_koreksi", {
                "supplier_code": supplier_code,
                "source": {"kabupaten": source_kab, "kecamatan": source_kec,
                           "desa": source_desa},
                "target": {"id": target.id, "kabupaten": target.kabupaten,
                           "kabupaten_norm": target_kab_norm,
                           "kecamatan": target.kecamatan, "desa": target.desa,
                           "berbeda_dari_induk_sumber": target_kab_norm != source_kab},
                "sebelumnya_ref_id": sebelumnya,
            })
            session.commit()
            return {"status": "tersimpan", "manual_correction": True,
                    "target": {"kabupaten": target.kabupaten,
                               "kecamatan": target.kecamatan, "desa": target.desa},
                    "induk_scdf": {"kabupaten": target.kabupaten,
                                   "berbeda_dari_sumber": target_kab_norm != source_kab},
                    "scope": "Semua tiket dengan kombinasi lokasi sumber yang sama."}

        if koreksi:
            target_id = koreksi.target_ref_id
            session.delete(koreksi)
            pengguna = info_pengguna(request) or {}
            catat_audit(session, pengguna.get("sub") or "pengguna aplikasi",
                        "hapus", "traceability_wilayah_koreksi", {
                            "supplier_code": supplier_code,
                            "source": {"kabupaten": source_kab, "kecamatan": source_kec,
                                       "desa": source_desa},
                            "target_ref_id": target_id,
                        })
            session.commit()
        return {"status": "tersimpan", "manual_correction": False,
                "pesan": "Koreksi manual dihapus; pencocokan kembali memakai nilai intake."}

    @router.get("/unmapped")
    def ekspor_unmapped(tahun: int | None = None, periode: str = "ALL",
                        supplier: str | None = None,
                        eudr: str = Query("all", pattern="^(all|eudr|non_eudr)$"),
                        include_latex: bool = False, session: Session = dep):
        _, _, base = filter_data(session, tahun, periode, supplier, eudr, include_latex)
        T = TiketBaris
        K = KoreksiWilayahTrace
        desa_ref = (select(ReferensiWilayahTrace.kabupaten_norm,
                           ReferensiWilayahTrace.kecamatan_norm,
                           ReferensiWilayahTrace.desa_norm).distinct().subquery())
        q = (select(T.ticket_no, T.ticket_date, T.kode_vendor, Vendor.nama_baku,
                    T.item_code, T.asal_getah,
                    func.coalesce(T.kabupaten, T.kabupaten_norm).label("kabupaten"),
                    func.coalesce(T.kecamatan, T.kecamatan_norm).label("kecamatan"),
                    func.coalesce(T.desa, T.desa_norm).label("desa"),
                    T.dry_kg, T.asal_getah_valid)
             .select_from(T).join(base, base.c.id == T.id)
             .outerjoin(Vendor, Vendor.kode == T.kode_vendor)
             .outerjoin(K, _koreksi_kunci(T, K))
             .outerjoin(desa_ref, and_(desa_ref.c.kabupaten_norm == T.kabupaten_norm,
                                       desa_ref.c.kecamatan_norm == T.kecamatan_norm,
                                       desa_ref.c.desa_norm == T.desa_norm))
             .where(K.id.is_(None),
                    or_(T.asal_getah_valid.is_not(True), desa_ref.c.desa_norm.is_(None)))
             .order_by(T.ticket_date, T.ticket_no))
        rows = []
        for r in session.execute(q).mappings():
            valid_asal = bool(r["asal_getah_valid"])
            rows.append({"ticket_no": r["ticket_no"],
                         "ticket_date": r["ticket_date"].isoformat() if r["ticket_date"] else None,
                         "supplier_code": r["kode_vendor"], "supplier": r["nama_baku"],
                         "item_code": r["item_code"], "asal_getah": r["asal_getah"],
                         "kabupaten": r["kabupaten"], "kecamatan": r["kecamatan"],
                         "desa": r["desa"], "dry_kg": float(r["dry_kg"] or 0),
                         "reason": ("Asal Getah tidak valid" if not valid_asal
                                    else "Wilayah tidak cocok dengan referensi SCDF")})
        return _buat_unmapped_xlsx(rows)

    @router.post("/unmapped/import")
    async def impor_mapping_unmapped(request: Request, file: UploadFile = File(...),
                                     session: Session = dep):
        """Impor pasangan District/Sub-district SCDF dari workbook belum termapping.

        Hanya menulis koreksi terkontrol; intake asli dan referensi SCDF tidak
        diubah. Semua baris divalidasi dahulu agar impor bersifat atomik.
        """
        nama_file = (file.filename or "").lower()
        if not nama_file.endswith(".xlsx"):
            raise HTTPException(422, "Unggah file Excel .xlsx hasil unduhan Traceability.")
        isi = await file.read(10 * 1024 * 1024 + 1)
        if not isi:
            raise HTTPException(422, "File Excel kosong.")
        if len(isi) > 10 * 1024 * 1024:
            raise HTTPException(413, "Ukuran file maksimal 10 MB.")
        try:
            wb = openpyxl.load_workbook(io.BytesIO(isi), read_only=True, data_only=True)
        except Exception as exc:
            raise HTTPException(422, "File tidak dapat dibaca sebagai workbook Excel .xlsx.") from exc
        try:
            if "Unmapped Records" not in wb.sheetnames:
                raise HTTPException(422, "Sheet 'Unmapped Records' tidak ditemukan.")
            ws = wb["Unmapped Records"]
            header = [str(v or "").strip() for v in next(
                ws.iter_rows(min_row=1, max_row=1, values_only=True), ())]
            wajib = ("Kabupaten/Kota", "Kecamatan", "Desa",
                     "SCDF District", "SCDF Sub-district")
            if any(name not in header for name in wajib):
                raise HTTPException(422,
                    "Kolom wajib tidak lengkap. Gunakan template unduhan dan isi 'SCDF District' serta 'SCDF Sub-district'.")
            posisi = {name: header.index(name) for name in wajib}
            sumber: dict[tuple[str, str, str], dict] = {}
            masalah: list[str] = []
            jumlah_baris = 0
            baris_mapping_diisi = 0
            for nomor, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                jumlah_baris += 1
                if jumlah_baris > 5000:
                    raise HTTPException(413, "Maksimal 5.000 baris Excel per unggahan.")
                nilai_district = row[posisi["SCDF District"]] if posisi["SCDF District"] < len(row) else None
                nilai_subdistrict = row[posisi["SCDF Sub-district"]] if posisi["SCDF Sub-district"] < len(row) else None
                isi_district = bool(nilai_district is not None and str(nilai_district).strip())
                isi_subdistrict = bool(nilai_subdistrict is not None and str(nilai_subdistrict).strip())
                if not isi_district and not isi_subdistrict:
                    continue
                if isi_district != isi_subdistrict:
                    masalah.append(f"Baris {nomor}: SCDF District dan SCDF Sub-district harus diisi bersama.")
                    continue
                baris_mapping_diisi += 1
                def sel(kolom: str) -> str:
                    i = posisi[kolom]
                    return str(row[i]).strip() if i < len(row) and row[i] is not None else ""
                source_kab = normalisasi_kabupaten(sel("Kabupaten/Kota")) or ""
                source_kec = normalisasi_teks_wilayah(sel("Kecamatan")) or ""
                source_desa = normalisasi_teks_wilayah(sel("Desa")) or ""
                target_kec = normalisasi_teks_wilayah(str(nilai_district)) or ""
                target_desa = normalisasi_teks_wilayah(str(nilai_subdistrict)) or ""
                if not source_kab or not source_kec or not source_desa or not target_kec or not target_desa:
                    masalah.append(f"Baris {nomor}: Kabupaten/Kota, Kecamatan, Desa, SCDF District, dan SCDF Sub-district harus terisi.")
                    continue
                source_key = (source_kab, source_kec, source_desa)
                sebelumnya = sumber.get(source_key)
                if sebelumnya and (sebelumnya["target_kecamatan_norm"] != target_kec or
                                   sebelumnya["target_desa_norm"] != target_desa):
                    masalah.append(f"Baris {nomor}: satu lokasi sumber diberi lebih dari satu pasangan District/Sub-district SCDF.")
                    continue
                sumber[source_key] = {"target_kecamatan_norm": target_kec,
                                      "target_desa_norm": target_desa, "row": nomor}
            if not sumber and not masalah:
                raise HTTPException(422, "Tidak ada pasangan SCDF District dan SCDF Sub-district yang diisi.")

            # Pastikan semua sumber memang ada di tiket dan tujuan adalah nama
            # resmi SCDF di Kabupaten/Kecamatan yang sama.
            T = TiketBaris
            source_keys = list(sumber)
            sumber_ada: set[tuple[str, str, str]] = set()
            for awal in range(0, len(source_keys), 250):
                potongan = source_keys[awal:awal + 250]
                q_sumber = select(T.kabupaten_norm, T.kecamatan_norm, T.desa_norm).where(
                    tuple_(T.kabupaten_norm, T.kecamatan_norm, T.desa_norm).in_(potongan)
                ).distinct()
                sumber_ada.update(tuple(r) for r in session.execute(q_sumber).all())
            for key, item in sumber.items():
                if key not in sumber_ada:
                    masalah.append(f"Baris {item['row']}: lokasi sumber tidak ditemukan pada data intake.")

            tujuan_keys = [(kab, item["target_kecamatan_norm"], item["target_desa_norm"])
                           for (kab, _, _), item in sumber.items()]
            tujuan_map: dict[tuple[str, str, str], ReferensiWilayahTrace] = {}
            for awal in range(0, len(tujuan_keys), 250):
                potongan = tujuan_keys[awal:awal + 250]
                q_tujuan = select(ReferensiWilayahTrace).where(
                    tuple_(ReferensiWilayahTrace.kabupaten_norm,
                           ReferensiWilayahTrace.kecamatan_norm,
                           ReferensiWilayahTrace.desa_norm).in_(potongan)
                )
                for ref in session.scalars(q_tujuan):
                    tujuan_map[(ref.kabupaten_norm, ref.kecamatan_norm, ref.desa_norm)] = ref
            for (kab, _, _), item in sumber.items():
                target_key = (kab, item["target_kecamatan_norm"], item["target_desa_norm"])
                if target_key not in tujuan_map:
                    masalah.append(
                        f"Baris {item['row']}: pasangan '{item['target_kecamatan_norm']} / "
                        f"{item['target_desa_norm']}' bukan pasangan SCDF terdaftar pada Kabupaten/Kota sumber.")
            if masalah:
                ringkas = "\n".join(masalah[:20])
                if len(masalah) > 20:
                    ringkas += f"\n…dan {len(masalah) - 20} masalah lain."
                raise HTTPException(422, f"Tidak ada perubahan disimpan. Periksa Excel:\n{ringkas}")

            existing_map: dict[tuple[str, str, str], KoreksiWilayahTrace] = {}
            for awal in range(0, len(source_keys), 250):
                potongan = source_keys[awal:awal + 250]
                q_koreksi = select(KoreksiWilayahTrace).where(
                    tuple_(KoreksiWilayahTrace.source_kabupaten_norm,
                           KoreksiWilayahTrace.source_kecamatan_norm,
                           KoreksiWilayahTrace.source_desa_norm).in_(potongan)
                )
                for koreksi_ada in session.scalars(q_koreksi):
                    existing_map[(koreksi_ada.source_kabupaten_norm,
                                  koreksi_ada.source_kecamatan_norm,
                                  koreksi_ada.source_desa_norm)] = koreksi_ada

            pengguna = info_pengguna(request) or {}
            diubah_oleh = pengguna.get("sub") or "pengguna aplikasi"
            dibuat = 0
            diperbarui = 0
            tidak_berubah = 0
            for (kab, kec, desa), item in sumber.items():
                target = tujuan_map[(kab, item["target_kecamatan_norm"], item["target_desa_norm"])]
                koreksi = existing_map.get((kab, kec, desa))
                aksi = "ubah" if koreksi else "tambah"
                if koreksi is None:
                    koreksi = KoreksiWilayahTrace(
                        source_kabupaten_norm=kab,
                        source_kecamatan_norm=kec,
                        source_desa_norm=desa,
                        target_ref_id=target.id,
                    )
                    session.add(koreksi)
                    dibuat += 1
                elif koreksi.target_ref_id == target.id:
                    tidak_berubah += 1
                    continue
                else:
                    koreksi.target_ref_id = target.id
                    diperbarui += 1
                koreksi.updated_by = diubah_oleh
                koreksi.updated_at = dt.datetime.utcnow()
                catat_audit(session, diubah_oleh, aksi, "traceability_wilayah_koreksi", {
                    "source": {"kabupaten": kab, "kecamatan": kec, "desa": desa},
                    "target": {"id": target.id, "kabupaten": target.kabupaten,
                               "kecamatan": target.kecamatan, "desa": target.desa},
                    "sumber": "unggah Excel belum termapping",
                    "nama_file": file.filename,
                })
            session.commit()
            direvisi = dibuat + diperbarui
            return {"status": "tersimpan", "baris_mapping_diisi": baris_mapping_diisi,
                    "lokasi_dipetakan": len(sumber), "baris_direvisi": direvisi,
                    "koreksi_baru": dibuat, "koreksi_diperbarui": diperbarui,
                    "koreksi_tidak_berubah": tidak_berubah,
                    "pesan": "Koreksi tersimpan; intake asli tidak diubah."}
        finally:
            wb.close()

    @router.put("/settings")
    def ubah_pengaturan(data: PengaturanMasuk, request: Request,
                        session: Session = dep):
        wajib_admin(request)
        row = session.get(PengaturanTraceability, 1)
        if row is None:
            row = PengaturanTraceability(id=1)
            session.add(row)
        row.accounting = data.accounting.strip()
        row.scope = data.scope.strip()
        session.commit()
        return {"status": "tersimpan", "settings": _pengaturan(session)}

    app.include_router(router)
