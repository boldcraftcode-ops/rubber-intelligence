"""Data potensi karet per provinsi untuk peta intake.

Angka produksi sentra nasional adalah angka produksi karet kering 2024 dari
Pusdatin Kementan (bersumber dari Ditjenbun). Data Intake dihitung langsung
dari tiket aplikasi (Dry kg). Dataset Satu Data Lampung diambil online saat
refresh dan disajikan terpisah karena satuannya/bentuk hasilnya adalah ton
slab, sehingga tidak boleh dicampur dengan angka karet kering nasional.
"""
from __future__ import annotations

import datetime as dt
import threading
import time
from collections import defaultdict
from typing import Callable

import httpx
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import TiketBaris


URL_KEMENTERAN = (
    "https://satudata.pertanian.go.id/assets/docs/publikasi/"
    "54573f78bc9546a1758ebb09e085990a.pdf"
)
URL_BPS = (
    "https://www.bps.go.id/en/publication/2024/11/29/"
    "dc3b172868ba150cbb77f7bc/statistik-karet-indonesia-2023.html"
)
URL_KEMENTAN_2024 = "https://satudata.pertanian.go.id/assets/docs/publikasi/Kinerja_Karet_2024.pdf"
URL_LAMPUNG = (
    "https://opendata.lampungprov.go.id/api/dataset/"
    "d2876e7f-391c-4bd9-9a89-536ef86f875b/datastore"
)
URL_HALAMAN_LAMPUNG = (
    "https://opendata.lampungprov.go.id/dataset/produksi-karet-20192023"
)

# Nilai 2024 (ton karet kering), tabel produksi provinsi sentra dalam
# Analisis Kinerja Perdagangan Karet 2025, sumber data Ditjenbun. Bengkulu
# mempertahankan angka publikasi sebelumnya karena revisi 2025 tidak
# menyajikan barisnya dalam ekstrak tabel yang tervalidasi.
PRODUKSI_SENTRA_2024 = [
    {"provinsi": "Sumatera Selatan", "ton": 619_546},
    {"provinsi": "Sumatera Utara", "ton": 251_518},
    {"provinsi": "Jambi", "ton": 222_556},
    {"provinsi": "Riau", "ton": 180_742},
    {"provinsi": "Kalimantan Barat", "ton": 158_409},
    {"provinsi": "Kalimantan Selatan", "ton": 127_955},
    {"provinsi": "Kalimantan Tengah", "ton": 108_294},
    {"provinsi": "Sumatera Barat", "ton": 99_666},
    {"provinsi": "Lampung", "ton": 84_832},
    {"provinsi": "Bengkulu", "ton": 71_854, "catatan": "angka publikasi 2024 sebelumnya"},
]

SUMBER = [
    {
        "nama": "Pusdatin Kementerian Pertanian — Analisis Kinerja Perdagangan Karet 2025",
        "url": URL_KEMENTERAN,
        "cakupan": "Produksi karet kering provinsi sentra, termasuk seri nasional 2020–2024; angka peta memakai 2024.",
    },
    {
        "nama": "BPS — Statistik Karet Indonesia 2023",
        "url": URL_BPS,
        "cakupan": "Publikasi tahunan: luas dan produksi menurut provinsi/status pengusahaan; ekspor-impor menurut negara, bukan penjualan per provinsi.",
    },
    {
        "nama": "Pusdatin Kementerian Pertanian — Analisis Kinerja Perdagangan Karet 2024",
        "url": URL_KEMENTAN_2024,
        "cakupan": "Rujukan pembanding; nilai Bengkulu 2024 dipertahankan dari publikasi ini karena baris revisinya belum tersedia pada ekstrak sumber 2025.",
    },
    {
        "nama": "Satu Data Provinsi Lampung — Produksi Karet 2019–2023",
        "url": URL_HALAMAN_LAMPUNG,
        "cakupan": "API dataset kabupaten/kota; ton slab. Ditampilkan terpisah dan tidak dibandingkan langsung dengan karet kering nasional.",
    },
]

_cache_lock = threading.Lock()
_lampung_cache: tuple[float, dict] | None = None
_CACHE_SECONDS = 6 * 60 * 60


def _ambil_lampung(fetch_json: Callable[[str], dict] | None = None) -> dict:
    """Ambil nilai resmi terbaru dari API Lampung; simpan cache 6 jam."""
    global _lampung_cache
    now = time.monotonic()
    with _cache_lock:
        if _lampung_cache and now - _lampung_cache[0] < _CACHE_SECONDS:
            return _lampung_cache[1]

    try:
        if fetch_json is None:
            def fetch_json(url: str) -> dict:
                with httpx.Client(timeout=4.0, follow_redirects=True) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    return response.json()

        payload = fetch_json(URL_LAMPUNG)
        records = payload.get("result", []) if isinstance(payload, dict) else []
        tahun = sorted({
            int(k.removeprefix("tahun_"))
            for row in records if isinstance(row, dict)
            for k in row if k.startswith("tahun_") and k.removeprefix("tahun_").isdigit()
        })
        if not records or not tahun:
            raise ValueError("API Lampung tidak mengembalikan seri produksi yang dikenali.")
        year = tahun[-1]
        jumlah = sum(float(row.get(f"tahun_{year}") or 0) for row in records if isinstance(row, dict))
        data = {
            "status": "tersedia",
            "tahun": year,
            "produksi_ton_slab": round(jumlah, 2),
            "jumlah_kabupaten_kota": len(records),
            "satuan": "ton slab",
            "diperiksa_pada": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "url": URL_HALAMAN_LAMPUNG,
        }
    except Exception as exc:
        # Hindari menyajikan snapshot lama seolah-olah hasil live.
        data = {
            "status": "sumber tidak dapat diakses",
            "tahun": None,
            "produksi_ton_slab": None,
            "jumlah_kabupaten_kota": None,
            "satuan": "ton slab",
            "diperiksa_pada": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "url": URL_HALAMAN_LAMPUNG,
            "pesan": str(exc)[:200],
        }
    with _cache_lock:
        _lampung_cache = (now, data)
    return data


def _intake_tahunan(session: Session) -> list[dict]:
    """Hitung rata-rata penerimaan Dry per tahun dari kolom provinsi tiket."""
    hasil: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for tiket in session.scalars(select(TiketBaris).where(
        TiketBaris.tiket_nol == False,  # noqa: E712
        TiketBaris.dry_kg != None,  # noqa: E711
        TiketBaris.provinsi != None,  # noqa: E711
    )):
        provinsi = " ".join((tiket.provinsi or "").split()).upper()
        if not provinsi or not tiket.ticket_date:
            continue
        hasil[provinsi][tiket.ticket_date.year] += float(tiket.dry_kg or 0)

    return [{
        "provinsi": provinsi,
        "rata_rata_kg_per_tahun": round(sum(per_tahun.values()) / len(per_tahun), 1),
        "tahun_tercakup": sorted(per_tahun),
        "jumlah_tahun": len(per_tahun),
        "kg_per_tahun": {str(tahun): round(kg, 1) for tahun, kg in sorted(per_tahun.items())},
    } for provinsi, per_tahun in hasil.items()]


def pasang_router_potensi(app, ambil_session):
    from fastapi import Depends

    router = APIRouter(prefix="/api")
    dep = Depends(ambil_session)

    @router.get("/kartu/potensi-karet")
    def kartu_potensi_karet(session: Session = dep):
        intake = _intake_tahunan(session)
        return {
            "tahun_produksi": 2024,
            "produksi_sentra": PRODUKSI_SENTRA_2024,
            "rata_rata_intake_tahunan": intake,
            "seri_lampung": _ambil_lampung(),
            "sumber": SUMBER,
            "definisi": {
                "produksi": "Ton karet kering per tahun, data resmi Ditjenbun/Pusdatin; angka 2024.",
                "intake": "Rata-rata tahunan Dry kg dari tiket aplikasi, dikelompokkan per tahun yang memiliki data; bukan seluruh penjualan pasar.",
                "penjualan": "Tidak tersedia per provinsi pada sumber resmi yang ditautkan. Produksi dan intake tidak diberi label sebagai penjualan pasar.",
                "lampung": "Data tambahan langsung dari API Satu Data Lampung; bentuk hasil ton slab, sehingga tidak dijumlahkan/dibandingkan dengan angka karet kering.",
            },
        }

    app.include_router(router)
