"""API modul Kepatuhan vendor sampling (menu Pengawasan & Kontrol).

Sumber data adalah workbook `Laporan_Monitoring_Vendor_RM_Purchasing (1).xlsx`
yang disalin dari GitHub ke akar repo. Endpoint bersifat baca-saja: ia
mengembalikan ringkasan per bulan dan log detail, atau ekspor XLSX untuk
periode yang dipilih. Tidak ada tabel database, unggahan, atau perubahan nilai.
"""
from __future__ import annotations

import io
import re
from typing import Literal

import openpyxl
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from .core.kepatuhan_vendor import baca_laporan

router = APIRouter(prefix="/api/kepatuhan-vendor-sampling",
                   tags=["Kepatuhan vendor sampling"])


def _respon_xlsx(periode: dict) -> StreamingResponse:
    """Ekspor satu periode: sheet Summary + Log Monitoring."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(periode["kolom_summary"])
    kunci_summary = ("no", "vendor", "tepat", "terlambat", "tanpa_data",
                     "total", "persen", "keterangan", "kata_kunci")
    for b in periode["summary"]:
        ws.append([b.get(k) for k in kunci_summary])
    if periode.get("total"):
        ws.append([periode["total"].get(k) for k in kunci_summary])

    ws_log = wb.create_sheet("Log Monitoring")
    ws_log.append(periode["kolom_log"])
    for baris in periode["log"]:
        ws_log.append(baris)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    nama = f"Kepatuhan_vendor_sampling_{periode['kunci']}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nama}"'},
    )


@router.get("")
def laporan(
    bulan: str | None = Query(default=None,
                              description="Periode yyyy-mm; kosong = bulan terbaru"),
    format: Literal["json", "xlsx"] = Query(default="json"),
):
    try:
        data = baca_laporan()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # workbook rusak / tidak bisa dibaca
        raise HTTPException(status_code=500,
                            detail="Workbook Kepatuhan vendor sampling tidak dapat dibaca."
                            ) from exc

    if bulan is not None and not re.fullmatch(r"\d{4}-\d{2}", bulan):
        raise HTTPException(status_code=422,
                            detail="Parameter bulan harus berformat yyyy-mm.")
    kunci = bulan or max(data["periode"])
    if kunci not in data["periode"]:
        raise HTTPException(status_code=404,
                            detail=f"Periode {kunci} tidak ada dalam workbook.")
    dipilih = data["periode"][kunci]
    if format == "xlsx":
        return _respon_xlsx(dipilih)
    return {
        "sumber": data["sumber"],
        "catatan_aturan": data["catatan_aturan"],
        "daftar_periode": data["daftar_periode"],
        "kunci": kunci,
        "periode": dipilih,
    }


def pasang_router_kepatuhan(app, ambil_session=None) -> None:
    """Dipanggil dari `buat_app`; `ambil_session` tidak dipakai (baca berkas)."""
    app.include_router(router)
