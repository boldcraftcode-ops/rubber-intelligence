"""API Traceability: volume Dry teragregasi di server, referensi wilayah dan ekspor."""
from __future__ import annotations

import io
from pathlib import Path

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import (String, and_, case, cast, distinct, func, or_, select)
from sqlalchemy.orm import Session

from .auth_lokal import wajib_admin
from .core.traceability import (normalisasi_kabupaten, normalisasi_teks_wilayah,
                                persen_traceable, rentang_periode)
from .models import (PengaturanTraceability, ReferensiWilayahTrace, TiketBaris,
                     Vendor)

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


class PengaturanMasuk(BaseModel):
    accounting: str = Field(min_length=1, max_length=120)
    scope: str = Field(min_length=1, max_length=120)


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
    T = TiketBaris
    reg_ok = and_(T.asal_getah_valid.is_(True), kab_ref.c.id.is_not(None))
    kec_ok = and_(T.asal_getah_valid.is_(True), kec_ref.c.id.is_not(None))
    desa_ok = and_(T.asal_getah_valid.is_(True), desa_ref.c.id.is_not(None))
    q = (select(T.kabupaten_norm, T.kecamatan_norm, T.desa_norm,
                func.sum(T.dry_kg).label("dry"),
                func.sum(case((reg_ok, T.dry_kg), else_=0)).label("dry_reg"),
                func.sum(case((kec_ok, T.dry_kg), else_=0)).label("dry_kec"),
                func.sum(case((desa_ok, T.dry_kg), else_=0)).label("dry_desa"),
                func.count(T.id).label("ticket_lines"))
         .select_from(T).join(base, base.c.id == T.id)
         .outerjoin(kab_ref, kab_ref.c.kabupaten_norm == T.kabupaten_norm)
         .outerjoin(kec_ref, and_(kec_ref.c.kabupaten_norm == T.kabupaten_norm,
                                  kec_ref.c.kecamatan_norm == T.kecamatan_norm))
         .outerjoin(desa_ref, and_(desa_ref.c.kabupaten_norm == T.kabupaten_norm,
                                   desa_ref.c.kecamatan_norm == T.kecamatan_norm,
                                   desa_ref.c.desa_norm == T.desa_norm))
         .group_by(T.kabupaten_norm, T.kecamatan_norm, T.desa_norm))
    kelompok = list(session.execute(q).mappings())
    total = sum(float(r["dry"] or 0) for r in kelompok)
    traced_reg = sum(float(r["dry_reg"] or 0) for r in kelompok)
    traced_kec = sum(float(r["dry_kec"] or 0) for r in kelompok)
    traced_desa = sum(float(r["dry_desa"] or 0) for r in kelompok)
    tiket = session.scalar(select(func.count(distinct(T.ticket_no)))
                           .select_from(T).join(base, base.c.id == T.id)) or 0

    pohon: dict[str, dict] = {}
    for r in kelompok:
        kab = r["kabupaten_norm"] or "(BELUM DIISI)"
        kec = r["kecamatan_norm"] or "(BELUM DIISI)"
        desa = r["desa_norm"] or "(BELUM DIISI)"
        kg = float(r["dry"] or 0)
        regkg, keckg, desakg = (float(r["dry_reg"] or 0),
                                float(r["dry_kec"] or 0), float(r["dry_desa"] or 0))
        tix = int(r["ticket_lines"] or 0)
        if kab not in pohon:
            pohon[kab] = {"name": kab, "level": "Kabupaten/Kota", "code": "",
                          "dry_kg": 0.0, "trace_kg": 0.0, "ticket_lines": 0,
                          "status_code": "belum termapping", "children": {}}
        a = pohon[kab]
        a["dry_kg"] += kg; a["trace_kg"] += regkg; a["ticket_lines"] += tix
        if kec not in a["children"]:
            a["children"][kec] = {"name": kec, "level": "Kecamatan", "code": "",
                                  "dry_kg": 0.0, "trace_kg": 0.0, "ticket_lines": 0,
                                  "status_code": "belum termapping", "children": {}}
        b = a["children"][kec]
        b["dry_kg"] += kg; b["trace_kg"] += keckg; b["ticket_lines"] += tix
        if desa not in b["children"]:
            b["children"][desa] = {"name": desa, "level": "Desa/Kelurahan", "code": "",
                                    "dry_kg": 0.0, "trace_kg": 0.0, "ticket_lines": 0,
                                    "status_code": "belum termapping", "children": {}}
        c = b["children"][desa]
        c["dry_kg"] += kg; c["trace_kg"] += desakg; c["ticket_lines"] += tix

    def serialize(node: dict) -> dict:
        dry = node.pop("dry_kg")
        trace = node.pop("trace_kg")
        children = node.pop("children")
        node["dry_mt"] = round(dry / 1000, 3)
        node["traceable_mt"] = round(trace / 1000, 3)
        node["traceability_pct"] = persen_traceable(trace, dry)
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
               "Regencies", "Traceable Dry (MT)"])
    for a in aktor:
        wa.append([a["supplier_code"], a["supplier"], "Yes" if a["is_direct_producer"] else "No",
                   a["tickets"], a["dry_mt"], a["regencies"], a["traceable_mt"]])
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
               "Asal Getah", "Kabupaten/Kota", "Kecamatan", "Desa", "Dry (kg)", "Reason"])
    for r in rows:
        ws.append([r.get(k) for k in ("ticket_no", "ticket_date", "supplier_code",
                   "supplier", "item_code", "asal_getah", "kabupaten", "kecamatan",
                   "desa", "dry_kg", "reason")])
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
        T = TiketBaris
        reg = select(ReferensiWilayahTrace.kabupaten_norm).distinct().subquery()
        q = (select(T.kode_vendor, Vendor.nama_baku, Vendor.is_direct_producer,
                    func.count(distinct(T.ticket_no)).label("tickets"),
                    func.sum(T.dry_kg).label("dry"),
                    func.count(distinct(case((reg.c.kabupaten_norm == T.kabupaten_norm,
                                              T.kabupaten_norm), else_=None))).label("regencies"),
                    func.sum(case((and_(T.asal_getah_valid.is_(True),
                                       reg.c.kabupaten_norm == T.kabupaten_norm),
                                   T.dry_kg), else_=0)).label("trace"))
             .select_from(T).join(base, base.c.id == T.id)
             .outerjoin(Vendor, Vendor.kode == T.kode_vendor)
             .outerjoin(reg, reg.c.kabupaten_norm == T.kabupaten_norm)
             .group_by(T.kode_vendor, Vendor.nama_baku, Vendor.is_direct_producer)
             .order_by(func.sum(T.dry_kg).desc()))
        result = []
        for r in session.execute(q).mappings():
            result.append({"supplier_code": r["kode_vendor"],
                           "supplier": r["nama_baku"] or r["kode_vendor"],
                           "is_direct_producer": bool(r["is_direct_producer"]),
                           "tickets": int(r["tickets"] or 0),
                           "dry_mt": round(float(r["dry"] or 0) / 1000, 3),
                           "traceable_mt": round(float(r["trace"] or 0) / 1000, 3),
                           "regencies": int(r["regencies"] or 0)})
        return result

    def actors_export(rows: list[dict]):
        return rows

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
            "catatan": "Volume menggunakan Dry dari tiket tervalidasi; baris identik pada semua kolom sumber dihitung satu kali. Code belum tersedia pada ID_AUX sehingga ditampilkan kosong/belum termapping.",
        }
        if format == "xlsx":
            base_for_actors = _filter_base(session, effective_year, periode, supplier,
                                           eudr, include_latex)
            return _buat_xlsx(data, actors(session, base_for_actors))
        return data

    @router.get("/actors")
    def supplier_actors(tahun: int | None = None, periode: str = "ALL",
                        supplier: str | None = None,
                        eudr: str = Query("all", pattern="^(all|eudr|non_eudr)$"),
                        include_latex: bool = False, session: Session = dep):
        _, _, base = filter_data(session, tahun, periode, supplier, eudr, include_latex)
        return {"baris": actors(session, base)}

    @router.get("/unmapped")
    def ekspor_unmapped(tahun: int | None = None, periode: str = "ALL",
                        supplier: str | None = None,
                        eudr: str = Query("all", pattern="^(all|eudr|non_eudr)$"),
                        include_latex: bool = False, session: Session = dep):
        _, _, base = filter_data(session, tahun, periode, supplier, eudr, include_latex)
        T = TiketBaris
        desa_ref = (select(ReferensiWilayahTrace.kabupaten_norm,
                           ReferensiWilayahTrace.kecamatan_norm,
                           ReferensiWilayahTrace.desa_norm).distinct().subquery())
        q = (select(T.ticket_no, T.ticket_date, T.kode_vendor, Vendor.nama_baku,
                    T.item_code, T.asal_getah, T.kabupaten, T.kecamatan, T.desa,
                    T.dry_kg, T.asal_getah_valid)
             .select_from(T).join(base, base.c.id == T.id)
             .outerjoin(Vendor, Vendor.kode == T.kode_vendor)
             .outerjoin(desa_ref, and_(desa_ref.c.kabupaten_norm == T.kabupaten_norm,
                                       desa_ref.c.kecamatan_norm == T.kecamatan_norm,
                                       desa_ref.c.desa_norm == T.desa_norm))
             .where(or_(T.asal_getah_valid.is_not(True), desa_ref.c.desa_norm.is_(None)))
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
                                    else "Wilayah tidak cocok dengan ID_AUX")})
        return _buat_unmapped_xlsx(rows)

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
