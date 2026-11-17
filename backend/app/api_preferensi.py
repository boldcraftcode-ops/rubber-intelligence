"""Preferensi tampilan pengguna dan bawaan perusahaan."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt
from sqlalchemy.orm import Session

from .auth_lokal import info_pengguna, wajib_admin
from .models import PreferensiBawaan, PreferensiPengguna

BAWAAN = {"desimal_angka": 3, "desimal_persen": 1, "satuan_berat": "otomatis"}
KUNCI = frozenset(BAWAAN)


class PreferensiMasuk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    desimal_angka: StrictInt | None = None
    desimal_persen: StrictInt | None = None
    satuan_berat: Literal["kg", "ton", "otomatis"] | None = None


class BawaanMasuk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nilai: PreferensiMasuk
    terkunci: dict[str, StrictBool] | None = None


def _validasi(nilai: dict, boleh_kosong: bool = False) -> dict:
    for kunci, isi in nilai.items():
        if kunci not in KUNCI:
            raise HTTPException(422, f"Pengaturan '{kunci}' tidak dikenal.")
        if isi is None and boleh_kosong:
            continue
        if kunci == "desimal_angka" and (type(isi) is not int or not 0 <= isi <= 4):
            raise HTTPException(422, "Desimal angka harus berupa bilangan 0 sampai 4.")
        if kunci == "desimal_persen" and (type(isi) is not int or not 0 <= isi <= 2):
            raise HTTPException(422, "Desimal persen harus berupa bilangan 0 sampai 2.")
        if kunci == "satuan_berat" and isi not in ("kg", "ton", "otomatis"):
            raise HTTPException(422, "Satuan berat harus kg, ton, atau otomatis.")
    return nilai


def pasang_router_preferensi(app, ambil_session) -> None:
    router = APIRouter(prefix="/api/preferensi", tags=["Preferensi"])
    dep = Depends(ambil_session)

    def _bawaan(session: Session) -> PreferensiBawaan:
        row = session.get(PreferensiBawaan, 1)
        if row is None:
            row = PreferensiBawaan(id=1, nilai=dict(BAWAAN), terkunci={})
            session.add(row)
            session.flush()
        return row

    def _gabung(session: Session, username: str) -> dict:
        company = _bawaan(session)
        pribadi = session.get(PreferensiPengguna, username)
        custom = pribadi.nilai if pribadi and isinstance(pribadi.nilai, dict) else {}
        defaults = {**BAWAAN, **(company.nilai or {})}
        locks = company.terkunci or {}
        effective = {
            key: defaults[key] if locks.get(key) else custom.get(key, defaults[key])
            for key in KUNCI
        }
        return {"efektif": effective, "pribadi": custom,
                "bawaan": defaults, "terkunci": {key: bool(locks.get(key)) for key in KUNCI}}

    @router.get("")
    def baca(request: Request, session: Session = dep):
        pengguna = info_pengguna(request)
        if not pengguna:
            raise HTTPException(401, "Sesi pengguna tidak ditemukan.")
        result = _gabung(session, pengguna["sub"])
        session.commit()
        return result

    @router.put("")
    def simpan(data: PreferensiMasuk, request: Request, session: Session = dep):
        pengguna = info_pengguna(request)
        if not pengguna:
            raise HTTPException(401, "Sesi pengguna tidak ditemukan.")
        isi = _validasi(data.model_dump(exclude_unset=True), boleh_kosong=True)
        company = _bawaan(session)
        row = session.get(PreferensiPengguna, pengguna["sub"])
        if row is None:
            row = PreferensiPengguna(username=pengguna["sub"], nilai={})
            session.add(row)
        current = dict(row.nilai or {})
        for key, value in isi.items():
            if company.terkunci and company.terkunci.get(key):
                continue
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value
        row.nilai = current
        session.commit()
        return _gabung(session, pengguna["sub"])

    @router.get("/bawaan")
    def baca_bawaan(request: Request, session: Session = dep):
        pengguna = info_pengguna(request)
        if not pengguna:
            raise HTTPException(401, "Sesi pengguna tidak ditemukan.")
        row = _bawaan(session)
        result = {"nilai": {**BAWAAN, **(row.nilai or {})},
                  "terkunci": {key: bool((row.terkunci or {}).get(key)) for key in KUNCI}}
        session.commit()
        return result

    @router.put("/bawaan")
    def simpan_bawaan(data: BawaanMasuk, request: Request, session: Session = dep):
        wajib_admin(request)
        row = _bawaan(session)
        values = _validasi(data.nilai.model_dump(exclude_unset=True))
        row.nilai = {**BAWAAN, **(row.nilai or {}), **values}
        if data.terkunci is not None:
            unknown = set(data.terkunci) - KUNCI
            if unknown:
                raise HTTPException(422, f"Kunci pengaturan tidak dikenal: {', '.join(sorted(unknown))}.")
            row.terkunci = {**(row.terkunci or {}), **data.terkunci}
        session.commit()
        return {"nilai": row.nilai, "terkunci": {key: bool((row.terkunci or {}).get(key)) for key in KUNCI}}

    app.include_router(router)
