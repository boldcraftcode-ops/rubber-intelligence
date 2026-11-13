"""Master Data → SCDF: katalog lokasi Indonesia, baca saja.

Sumbernya tetap `traceability_wilayah` (ID_AUX) dan crosswalk Provinsi resmi
yang sudah dipakai Traceability/Intake. Endpoint tidak menerima input, impor,
atau perubahan dari pengguna; inisialisasi referensi bawaan yang sudah ada
hanya dijalankan bila katalog belum terisi/terpetakan. Kolom pencarian juga
hanya membaca. Modul ini tidak menebak Provinsi dan tidak menyediakan
CRUD/ekspor sesuai pilihan pengguna.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, distinct, func, or_, select
from sqlalchemy.orm import Session

from .api_traceability import muat_referensi_bawaan
from .core.traceability import (normalisasi_kabupaten,
                                normalisasi_teks_wilayah)
from .models import ReferensiWilayahTrace

TINGKAT = ("provinsi", "kabupaten", "kecamatan", "desa")
LABEL = {
    "provinsi": "Provinsi",
    "kabupaten": "Kabupaten/Kota",
    "kecamatan": "Kecamatan",
    "desa": "Desa/Kelurahan",
}
BERIKUTNYA = {
    "provinsi": "kabupaten",
    "kabupaten": "kecamatan",
    "kecamatan": "desa",
    "desa": None,
}
CATATAN = (
    "Sumber: traceability_wilayah dari ID_AUX; Provinsi berasal dari crosswalk "
    "resmi Kepmendagri. Baris tanpa padanan Provinsi tetap tampil sebagai "
    "'Belum dipetakan' dan tidak ditebak. Modul ini baca saja."
)
CATATAN_PENCARIAN = (
    "Pencarian baca saja mencakup 4 nama resmi, 4 normalized key, dan status "
    "Provinsi pada traceability_wilayah, case-insensitive. Baris tanpa "
    "Provinsi tetap tampil sebagai 'Belum dipetakan' dan tidak ditebak."
)


def _norm(nilai: str | None, kabupaten: bool = False) -> str:
    if nilai is None:
        return ""
    return (normalisasi_kabupaten(nilai) if kabupaten
            else normalisasi_teks_wilayah(nilai))


def _status(provinsi_norm: str | None) -> str:
    return "terpetakan" if provinsi_norm else "belum_dipetakan"


def _pola_like(teks: str) -> str:
    """Aman untuk LIKE: `%`, `_`, dan `\` dari pengguna bukan wildcard."""
    bersih = (teks.replace("\\", "\\\\")
                  .replace("%", "\\%")
                  .replace("_", "\\_"))
    return f"%{bersih.lower()}%"


def _cocok(kolom, pola: str):
    return func.lower(func.coalesce(kolom, "")).like(pola, escape="\\")


def _kondisi_pencarian(R, kata: str):
    """Cari di 4 nama resmi, 4 normalized key, dan label status Provinsi."""
    pola = _pola_like(kata)
    label_status = case(
        (R.provinsi_norm.is_not(None), "Terpetakan"),
        else_="Belum dipetakan")
    syarat = [
        func.lower(func.coalesce(R.provinsi, "Belum dipetakan"))
        .like(pola, escape="\\"),
        _cocok(R.kabupaten, pola),
        _cocok(R.kecamatan, pola),
        _cocok(R.desa, pola),
        func.lower(label_status).like(pola, escape="\\"),
    ]
    norm_teks = _norm(kata)
    if norm_teks:
        pola_teks = _pola_like(norm_teks)
        syarat.extend([
            _cocok(R.provinsi_norm, pola_teks),
            _cocok(R.kecamatan_norm, pola_teks),
            _cocok(R.desa_norm, pola_teks),
        ])
    norm_kab = _norm(kata, True)
    if norm_kab:
        syarat.append(_cocok(R.kabupaten_norm, _pola_like(norm_kab)))
    return or_(*syarat)


def _format_baris(rows) -> list[dict]:
    return [{
        "provinsi": r["provinsi"] or "Belum dipetakan",
        "provinsi_norm": r["provinsi_norm"] or "",
        "kabupaten": r["kabupaten"],
        "kabupaten_norm": r["kabupaten_norm"],
        "kecamatan": r["kecamatan"],
        "kecamatan_norm": r["kecamatan_norm"],
        "desa": r["desa"],
        "desa_norm": r["desa_norm"],
        "status_provinsi": _status(r["provinsi_norm"]),
    } for r in rows]


def _pastikan_referensi_siap(session: Session) -> None:
    """Pastikan katalog bawaan ada tanpa menerima input dari pengguna.

    Memakai mekanisme yang sama dengan Traceability/Intake. Bila tabel sudah
    berisi dan sebagian barisnya sudah punya Provinsi, seed/crosswalk tidak
    dipanggil lagi sehingga GET pada data normal murni membaca.
    """
    R = ReferensiWilayahTrace
    if (session.scalar(select(func.count(R.id))) == 0
            or session.scalar(
                select(func.count(R.id))
                .where(R.provinsi_norm.is_not(None))) == 0):
        muat_referensi_bawaan(session)


def _kondisi_provinsi(provinsi_norm: str | None):
    """None = belum ada induk; '' = baris dengan provinsi_norm NULL."""
    if provinsi_norm is None:
        return []
    if provinsi_norm == "":
        return [ReferensiWilayahTrace.provinsi_norm.is_(None)]
    return [ReferensiWilayahTrace.provinsi_norm == provinsi_norm]


def _kondisi_lengkap(provinsi_norm: str | None,
                     kabupaten_norm: str | None = None,
                     kecamatan_norm: str | None = None,
                     desa_norm: str | None = None):
    R = ReferensiWilayahTrace
    kondisi = _kondisi_provinsi(provinsi_norm)
    if kabupaten_norm is not None:
        kondisi.append(R.kabupaten_norm == _norm(kabupaten_norm, True))
    if kecamatan_norm is not None:
        kondisi.append(R.kecamatan_norm == _norm(kecamatan_norm))
    if desa_norm is not None:
        kondisi.append(R.desa_norm == _norm(desa_norm))
    return kondisi


def _validasi_induk(tingkat: str, provinsi_norm: str | None,
                    kabupaten_norm: str | None,
                    kecamatan_norm: str | None,
                    minta_kabupaten: bool = False,
                    minta_kecamatan: bool = False,
                    minta_desa: bool = False,
                    desa_norm: str | None = None) -> tuple[str, str, str, str]:
    if provinsi_norm is None:
        raise HTTPException(422, "Provinsi induk wajib diisi untuk tingkat ini.")
    p = _norm(provinsi_norm)
    k = _norm(kabupaten_norm, True) if kabupaten_norm is not None else ""
    kec = _norm(kecamatan_norm) if kecamatan_norm is not None else ""
    d = _norm(desa_norm) if desa_norm is not None else ""
    if (minta_kabupaten or tingkat in ("kecamatan", "desa")) and not k:
        raise HTTPException(422, "Kabupaten/Kota induk wajib diisi.")
    if (minta_kecamatan or tingkat == "desa") and not kec:
        raise HTTPException(422, "Kecamatan induk wajib diisi.")
    if minta_desa and not d:
        raise HTTPException(422, "Desa/Kelurahan wajib diisi.")
    return p, k, kec, d


def _simpul(tingkat: str, norm: str | None, nama: str | None,
            jumlah_anak: int, jumlah_baris: int,
            status_provinsi: str) -> dict:
    norm_pakai = norm or ""
    if tingkat == "provinsi" and not norm_pakai:
        nama_pakai = "Belum dipetakan"
    else:
        nama_pakai = nama or (norm_pakai.title() if norm_pakai else "—")
    return {
        "tingkat": tingkat,
        "label_tingkat": LABEL[tingkat],
        "name": nama_pakai,
        "norm": norm_pakai,
        "jumlah_anak": int(jumlah_anak or 0),
        "jumlah_baris": int(jumlah_baris or 0),
        "status_provinsi": status_provinsi,
    }


def pasang_router_master_scdf(app, ambil_session):
    router = APIRouter(prefix="/api/master/scdf", tags=["Master SCDF"])
    dep = Depends(ambil_session)

    @router.get("/ringkasan")
    def ringkasan(session: Session = dep):
        _pastikan_referensi_siap(session)
        R = ReferensiWilayahTrace
        pasangan_kec = select(R.kabupaten_norm, R.kecamatan_norm)\
            .distinct().subquery()
        return {
            "provinsi": int(session.scalar(
                select(func.count(distinct(R.provinsi_norm)))
                .where(R.provinsi_norm.is_not(None))) or 0),
            "kabupaten_kota": int(session.scalar(
                select(func.count(distinct(R.kabupaten_norm)))) or 0),
            "kecamatan": int(session.scalar(
                select(func.count()).select_from(pasangan_kec)) or 0),
            "desa_kelurahan": int(session.scalar(
                select(func.count(R.id))) or 0),
            "baris": int(session.scalar(select(func.count(R.id))) or 0),
            "baris_tanpa_provinsi": int(session.scalar(
                select(func.count(R.id))
                .where(R.provinsi_norm.is_(None))) or 0),
            "kunci_tanpa_provinsi": int(session.scalar(
                select(func.count(distinct(R.kabupaten_norm)))
                .where(R.provinsi_norm.is_(None))) or 0),
            "catatan": CATATAN,
        }

    @router.get("/pohon")
    def pohon(tingkat: str = Query(..., pattern="^(provinsi|kabupaten|kecamatan|desa)$"),
              provinsi_norm: str | None = Query(default=None, max_length=120),
              kabupaten_norm: str | None = Query(default=None, max_length=120),
              kecamatan_norm: str | None = Query(default=None, max_length=120),
              session: Session = dep):
        _pastikan_referensi_siap(session)
        R = ReferensiWilayahTrace
        if tingkat == "provinsi":
            rows = session.execute(
                select(R.provinsi_norm,
                       func.min(R.provinsi).label("nama"),
                       func.count(distinct(R.kabupaten_norm)).label("anak"),
                       func.count(R.id).label("baris"))
                .group_by(R.provinsi_norm)
                .order_by(R.provinsi_norm.is_(None), R.provinsi_norm)).all()
            nodes = [_simpul(tingkat, r[0], r[1], r[2], r[3],
                             _status(r[0])) for r in rows]
            induk: dict = {}
        else:
            p, k, kec, _ = _validasi_induk(
                tingkat, provinsi_norm, kabupaten_norm, kecamatan_norm)
            kondisi = _kondisi_lengkap(
                p, k if tingkat in ("kecamatan", "desa") else None,
                kec if tingkat == "desa" else None)
            status = _status(p)
            if tingkat == "kabupaten":
                rows = session.execute(
                    select(R.kabupaten_norm,
                           func.min(R.kabupaten).label("nama"),
                           func.count(distinct(R.kecamatan_norm)).label("anak"),
                           func.count(R.id).label("baris"))
                    .where(*kondisi).group_by(R.kabupaten_norm)
                    .order_by(R.kabupaten_norm)).all()
                nodes = [_simpul(tingkat, r[0], r[1], r[2], r[3], status)
                         for r in rows]
            elif tingkat == "kecamatan":
                rows = session.execute(
                    select(R.kecamatan_norm,
                           func.min(R.kecamatan).label("nama"),
                           func.count(distinct(R.desa_norm)).label("anak"),
                           func.count(R.id).label("baris"))
                    .where(*kondisi).group_by(R.kecamatan_norm)
                    .order_by(R.kecamatan_norm)).all()
                nodes = [_simpul(tingkat, r[0], r[1], r[2], r[3], status)
                         for r in rows]
            else:
                rows = session.execute(
                    select(R.desa_norm,
                           func.min(R.desa).label("nama"),
                           func.count(R.id).label("baris"))
                    .where(*kondisi).group_by(R.desa_norm)
                    .order_by(R.desa_norm)).all()
                nodes = [_simpul(tingkat, r[0], r[1], 0, r[2], status)
                         for r in rows]
            induk = {"provinsi_norm": p, "kabupaten_norm": k,
                     "kecamatan_norm": kec}
        return {
            "tingkat": tingkat,
            "label_tingkat": LABEL[tingkat],
            "tingkat_anak": BERIKUTNYA[tingkat],
            "label_tingkat_anak": LABEL[BERIKUTNYA[tingkat]]
            if BERIKUTNYA[tingkat] else None,
            "induk": induk,
            "jumlah_node": len(nodes),
            "nodes": nodes,
            "catatan": CATATAN,
        }

    @router.get("/detail")
    def detail(tingkat: str = Query(..., pattern="^(provinsi|kabupaten|kecamatan|desa)$"),
               provinsi_norm: str | None = Query(default=None, max_length=120),
               kabupaten_norm: str | None = Query(default=None, max_length=120),
               kecamatan_norm: str | None = Query(default=None, max_length=120),
               desa_norm: str | None = Query(default=None, max_length=120),
               limit: int = Query(50, ge=1, le=200),
               offset: int = Query(0, ge=0),
               session: Session = dep):
        _pastikan_referensi_siap(session)
        p, k, kec, d = _validasi_induk(
            tingkat, provinsi_norm, kabupaten_norm, kecamatan_norm,
            minta_kabupaten=tingkat in ("kabupaten", "kecamatan", "desa"),
            minta_kecamatan=tingkat in ("kecamatan", "desa"),
            minta_desa=tingkat == "desa", desa_norm=desa_norm)
        R = ReferensiWilayahTrace
        kondisi = _kondisi_lengkap(
            p,
            k if tingkat in ("kabupaten", "kecamatan", "desa") else None,
            kec if tingkat in ("kecamatan", "desa") else None,
            d if tingkat == "desa" else None)
        total = int(session.scalar(
            select(func.count(R.id)).where(*kondisi)) or 0)
        rows = session.execute(
            select(R.provinsi, R.provinsi_norm,
                   R.kabupaten, R.kabupaten_norm,
                   R.kecamatan, R.kecamatan_norm,
                   R.desa, R.desa_norm)
            .where(*kondisi)
            .order_by(R.provinsi_norm.is_(None), R.provinsi_norm,
                      R.kabupaten_norm, R.kecamatan_norm, R.desa_norm, R.id)
            .limit(limit).offset(offset)).mappings()
        baris = _format_baris(rows)
        return {
            "tingkat": tingkat,
            "label_tingkat": LABEL[tingkat],
            "induk": {"provinsi_norm": p, "kabupaten_norm": k,
                      "kecamatan_norm": kec, "desa_norm": d},
            "total": total,
            "limit": limit,
            "offset": offset,
            "halaman": offset // limit + 1,
            "jumlah_halaman": (total + limit - 1) // limit if total else 0,
            "baris": baris,
            "catatan": CATATAN,
        }

    def _cari(q: str | None, cari_param: str | None, limit: int,
              offset: int, session: Session) -> dict:
        kata = (q or cari_param or "").strip()
        if not kata:
            raise HTTPException(422, "Kata pencarian wajib diisi.")
        _pastikan_referensi_siap(session)
        R = ReferensiWilayahTrace
        kondisi = _kondisi_pencarian(R, kata)
        total = int(session.scalar(
            select(func.count(R.id)).where(kondisi)) or 0)
        rows = session.execute(
            select(R.provinsi, R.provinsi_norm,
                   R.kabupaten, R.kabupaten_norm,
                   R.kecamatan, R.kecamatan_norm,
                   R.desa, R.desa_norm)
            .where(kondisi)
            .order_by(R.provinsi_norm.is_(None), R.provinsi_norm,
                      R.kabupaten_norm, R.kecamatan_norm, R.desa_norm, R.id)
            .limit(limit).offset(offset)).mappings()
        return {
            "kata": kata,
            "total": total,
            "limit": limit,
            "offset": offset,
            "halaman": offset // limit + 1,
            "jumlah_halaman": (total + limit - 1) // limit if total else 0,
            "baris": _format_baris(rows),
            "catatan": CATATAN_PENCARIAN,
        }

    @router.get("/cari")
    @router.get("/pencarian")
    def cari(q: str | None = Query(default=None, max_length=120),
             cari_param: str | None = Query(default=None, alias="cari",
                                            max_length=120),
             limit: int = Query(50, ge=1, le=200),
             offset: int = Query(0, ge=0),
             session: Session = dep):
        return _cari(q, cari_param, limit, offset, session)

    app.include_router(router)
