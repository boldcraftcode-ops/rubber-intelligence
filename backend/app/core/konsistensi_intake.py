"""Konsistensi intake harian/bulanan per vendor — perhitungan murni, tanpa SQL.

Menjawab tiga pertanyaan pemilik pada satu kartu Intake Analisis:

1. Vendor mana yang masuk **setiap hari kalender** dan **setiap bulan** pada
   rentang terpilih, dan pada rentang kapan ia paling konsisten.
2. Bila ada hari/bulan kosong, **hari dan bulan apa saja** yang kosong.
3. Vendor mana yang **paling sering masuk** (jumlah tanggal unik ber-intake).

Semua angka memakai `Ticket Date` pada baris tiket. Modul ini sengaja tidak
menyentuh database supaya aturannya bisa diuji tanpa fixture SQL.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Iterable

NAMA_HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
NAMA_BULAN_SINGKAT = ("", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                      "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

#: Rentang maksimal yang boleh diminta endpoint (2 tahun kalender).
MAKS_HARI = 731


def label_hari(tanggal: dt.date) -> str:
    return NAMA_HARI[tanggal.weekday()]


def kode_bulan(tanggal: dt.date) -> str:
    return f"{tanggal.year}-{tanggal.month:02d}"


def label_bulan(th: int, bl: int) -> str:
    return f"{NAMA_BULAN_SINGKAT[bl]}-{str(th)[2:]}"


def daftar_hari(awal: dt.date, akhir: dt.date) -> list[dt.date]:
    """Semua tanggal kalender dari `awal` sampai `akhir`, inklusif."""
    return [awal + dt.timedelta(days=i)
            for i in range((akhir - awal).days + 1)]


def _bulan_berikut(pasangan: tuple[int, int]) -> tuple[int, int]:
    th, bl = pasangan
    return (th + 1, 1) if bl == 12 else (th, bl + 1)


def rentang_harian_terpanjang(hari: set[dt.date]) -> dict:
    """Rentang tanggal berurutan terpanjang yang selalu ada intake."""
    if not hari:
        return {"dari": None, "sampai": None, "jumlah_hari": 0}
    terbaik_awal = terbaik_akhir = None
    terbaik = 0
    awal = sebelumnya = None
    panjang = 0
    for h in sorted(hari):
        if sebelumnya is not None and (h - sebelumnya).days == 1:
            panjang += 1
        else:
            awal, panjang = h, 1
        if panjang > terbaik:
            terbaik, terbaik_awal, terbaik_akhir = panjang, awal, h
        sebelumnya = h
    return {"dari": terbaik_awal.isoformat() if terbaik_awal else None,
            "sampai": terbaik_akhir.isoformat() if terbaik_akhir else None,
            "jumlah_hari": terbaik}


def rentang_bulan_terpanjang(bulan: set[tuple[int, int]]) -> dict:
    """Rentang bulan berurutan terpanjang yang selalu ada intake."""
    if not bulan:
        return {"dari": None, "sampai": None, "jumlah_bulan": 0}
    ke_urutan = lambda ym: ym[0] * 12 + ym[1]
    ke_ym = lambda n: ((n - 1) // 12, (n - 1) % 12 + 1)
    urut = sorted(ke_urutan(x) for x in bulan)
    terbaik = 0
    awal = akhir = urut[0]
    kini_awal = sebelumnya = urut[0]
    panjang = 1
    for n in urut[1:]:
        if n - sebelumnya == 1:
            panjang += 1
        else:
            kini_awal, panjang = n, 1
        if panjang > terbaik:
            terbaik, awal, akhir = panjang, kini_awal, n
        sebelumnya = n
    a, z = ke_ym(awal), ke_ym(akhir)
    return {"dari": f"{a[0]}-{a[1]:02d}", "sampai": f"{z[0]}-{z[1]:02d}",
            "jumlah_bulan": terbaik}


def _meta_bulan(semua_hari: list[dt.date]) -> list[dict]:
    """Bulan yang tersentuh rentang, lengkap dengan tanggal di dalam rentang."""
    per_bulan: dict[tuple[int, int], list[dt.date]] = defaultdict(list)
    for h in semua_hari:
        per_bulan[(h.year, h.month)].append(h)
    return [{
        "ym": f"{th}-{bl:02d}",
        "label": label_bulan(th, bl),
        "tahun": th,
        "bulan": bl,
        "jumlah_hari": len(hari),
        "tanggal_awal": hari[0].isoformat(),
        "tanggal_akhir": hari[-1].isoformat(),
        "_hari": set(hari),
    } for (th, bl), hari in sorted(per_bulan.items())]


def _norm_kode(nilai: str | None) -> str:
    return " ".join((nilai or "").split()).upper() or "(KOSONG)"


def hitung_konsistensi(
    tiket: Iterable[tuple[dt.date, str | None, str | None, float | None]],
    awal: dt.date,
    akhir: dt.date,
    nama_vendor: dict[str, str] | None = None,
) -> dict:
    """Hitung rekap konsistensi; kembalikan daftar LENGKAP untuk ekspor Excel.

    `tiket` berisi `(tanggal, kode_vendor, ticket_no, dry_kg)`. Tanggal di luar
    rentang diabaikan. Daftar `hari_kosong` TIDAK dipotong di sini; endpoint
    memangkasnya untuk JSON layar, sedangkan Excel memakai versi penuh.
    """
    nama_vendor = {_norm_kode(k): v for k, v in (nama_vendor or {}).items()}
    semua_hari = daftar_hari(awal, akhir)
    meta_bulan = _meta_bulan(semua_hari)
    per: dict[str, dict] = defaultdict(
        lambda: {"hari": set(), "tiket": set(), "kg": 0.0})
    semua_tiket: set[str] = set()
    hari_berintake: set[dt.date] = set()

    for tanggal, kode, no_tiket, kg in tiket:
        if tanggal is None:
            continue
        # Kolom DATE kadang kembali sebagai datetime pada driver tertentu.
        if isinstance(tanggal, dt.datetime):
            tanggal = tanggal.date()
        if not (awal <= tanggal <= akhir):
            continue
        kunci = _norm_kode(kode)
        isi = per[kunci]
        isi["hari"].add(tanggal)
        if no_tiket:
            isi["tiket"].add(no_tiket)
            semua_tiket.add(no_tiket)
        isi["kg"] += float(kg or 0)
        hari_berintake.add(tanggal)

    hari_sepi = [h for h in semua_hari if h not in hari_berintake]
    sepi_set = set(hari_sepi)
    n_hari, n_bulan = len(semua_hari), len(meta_bulan)

    baris: list[dict] = []
    for kunci, isi in per.items():
        hadir = isi["hari"]
        bulan_hadir = {(h.year, h.month) for h in hadir}
        kosong_hari = [h for h in semua_hari if h not in hadir]
        kosong_bulan = [m for m in meta_bulan
                        if (m["tahun"], m["bulan"]) not in bulan_hadir]
        bulan_lengkap = [m for m in meta_bulan if m["_hari"] <= hadir]
        nama = nama_vendor.get(kunci) or kunci
        baris.append({
            "peringkat": 0,
            "kode": kunci,
            "nama": nama,
            "label": f"{kunci} — {nama}" if nama != kunci else kunci,
            "jumlah_hari_masuk": len(hadir),
            "jumlah_hari_wajib": n_hari,
            "cakupan_hari_pct": round(len(hadir) / n_hari * 100, 2) if n_hari else 0.0,
            "status_harian": "lengkap" if not kosong_hari else "ada hari kosong",
            "jumlah_bulan_masuk": len(bulan_hadir),
            "jumlah_bulan_wajib": n_bulan,
            "cakupan_bulan_pct": (round(len(bulan_hadir) / n_bulan * 100, 2)
                                  if n_bulan else 0.0),
            "status_bulanan": "lengkap" if not kosong_bulan else "ada bulan kosong",
            "rentang_harian_terpanjang": rentang_harian_terpanjang(hadir),
            "rentang_bulanan_terpanjang": rentang_bulan_terpanjang(bulan_hadir),
            "bulan_lengkap": [{
                "ym": m["ym"], "label": m["label"],
                "jumlah_hari": m["jumlah_hari"]} for m in bulan_lengkap],
            "jumlah_tiket": len(isi["tiket"]),
            "total_kg": round(isi["kg"], 1),
            "jumlah_hari_kosong": len(kosong_hari),
            "jumlah_bulan_kosong": len(kosong_bulan),
            "hari_kosong": [{
                "tanggal": h.isoformat(),
                "hari": label_hari(h),
                "bulan": kode_bulan(h),
                "label": f"{label_hari(h)}, {h.day:02d}/{h.month:02d}/{h.year}",
                "sepi_pabrik": h in sepi_set,
            } for h in kosong_hari],
            "bulan_kosong": [{
                "ym": m["ym"], "label": m["label"],
                "jumlah_hari": m["jumlah_hari"]} for m in kosong_bulan],
            "paling_sering": False,
        })

    # Urutan: hari ber-intake (tanggal unik) → tiket → kg → kode.
    baris.sort(key=lambda b: (-b["jumlah_hari_masuk"], -b["jumlah_tiket"],
                              -b["total_kg"], b["kode"]))
    for i, b in enumerate(baris, start=1):
        b["peringkat"] = i
    maks_hari = baris[0]["jumlah_hari_masuk"] if baris else 0
    seri = [b["kode"] for b in baris if b["jumlah_hari_masuk"] == maks_hari]
    for b in baris:
        b["paling_sering"] = b["jumlah_hari_masuk"] == maks_hari

    vendor_tanpa_intake = sorted(
        k for k in nama_vendor if k not in per)
    lengkap_harian = sum(1 for b in baris if b["status_harian"] == "lengkap")
    lengkap_bulanan = sum(1 for b in baris if b["status_bulanan"] == "lengkap")

    peringatan: list[str] = []
    if not baris:
        peringatan.append(
            "Tidak ada tiket intake pada rentang ini; belum ada vendor yang "
            "bisa dinilai konsistensinya.")
    if hari_sepi:
        peringatan.append(
            f"Ada {len(hari_sepi)} hari kalender tanpa intake dari vendor mana "
            "pun (akhir pekan/hari libur/operasional sepi). Sesuai dasar "
            "'semua hari kalender', hari itu TETAP tercatat kosong untuk setiap "
            "vendor; kolom 'Sepi pabrik' di Excel membedakannya.")
    if baris and lengkap_harian == 0:
        peringatan.append(
            "Belum ada vendor yang masuk pada setiap hari kalender periode ini.")
    if vendor_tanpa_intake:
        peringatan.append(
            f"{len(vendor_tanpa_intake)} vendor pada Master Vendor tidak punya "
            "tiket sama sekali pada periode ini, sehingga tidak masuk tabel.")

    return {
        "status": "ok",
        "periode": {
            "dari": awal.isoformat(), "sampai": akhir.isoformat(),
            "jumlah_hari": n_hari, "jumlah_bulan": n_bulan,
            "dari_otomatis": False, "sampai_otomatis": False,
        },
        "dasar": {
            "hari": "kalender",
            "urutan": "jumlah_hari_masuk",
            "label_hari": "Semua hari kalender dalam rentang dihitung wajib ada intake",
            "label_urutan": "Jumlah hari ber-intake (tanggal unik)",
        },
        "ringkasan": {
            "total_vendor": len(baris),
            "total_tiket": len(semua_tiket),
            "total_kg": round(sum(b["total_kg"] for b in baris), 1),
            "jumlah_hari_wajib": n_hari,
            "jumlah_bulan_wajib": n_bulan,
            "hari_tanpa_intake_sama_sekali": len(hari_sepi),
            "vendor_lengkap_harian": lengkap_harian,
            "vendor_lengkap_bulanan": lengkap_bulanan,
            "vendor_tanpa_intake": len(vendor_tanpa_intake),
        },
        "paling_sering": dict(baris[0]) if baris else None,
        "seri_paling_sering": seri,
        "vendor_tanpa_intake": [
            {"kode": k, "label": f"{k} — {nama_vendor[k]}"}
            for k in vendor_tanpa_intake],
        "baris": baris,
        "daftar_bulan": [{
            "ym": m["ym"], "label": m["label"],
            "jumlah_hari": m["jumlah_hari"],
            "tanggal_awal": m["tanggal_awal"],
            "tanggal_akhir": m["tanggal_akhir"]} for m in meta_bulan],
        "hari_sepi_pabrik": [{
            "tanggal": h.isoformat(), "hari": label_hari(h),
            "bulan": kode_bulan(h),
            "label": f"{label_hari(h)}, {h.day:02d}/{h.month:02d}/{h.year}",
        } for h in hari_sepi],
        "peringatan": peringatan,
        "catatan_metode": {
            "dasar_hari": "Semua tanggal kalender dari 'Dari' sampai 'Sampai' "
                          "(inklusif) dihitung wajib. Hari tanpa tiket vendor "
                          "itu = hari kosong, termasuk Sabtu/Minggu/libur.",
            "dasar_urutan": "Peringkat diurutkan menurut jumlah tanggal unik "
                            "dengan intake (beberapa tiket di hari sama = 1 "
                            "hari). Seri dipecah dengan jumlah tiket, lalu kg.",
            "sumber": "tiket_baris memakai Ticket Date; tiket nol (Wet = 0) "
                      "tidak dihitung. Kode vendor dibakukan UPPER/TRIM.",
            "bulan_kosong": "Bulan kosong = bulan dalam rentang yang tidak "
                            "memiliki satu pun tiket vendor itu.",
            "bulan_lengkap": "Bulan lengkap = semua hari kalender bulan itu "
                             "yang berada di dalam rentang memiliki tiket.",
            "rentang_terpanjang": "Rentang terpanjang = deretan hari/bulan "
                                  "berurutan tanpa terputus dengan intake.",
            "sepi_pabrik": "Hari sepi pabrik = tanggal tanpa tiket dari vendor "
                           "mana pun; tetap dihitung kosong, tetapi ditandai.",
            "vendor_tidak_aktif": "Vendor tanpa tiket sama sekali pada periode "
                                  "tidak masuk tabel, tetapi jumlahnya dilaporkan.",
            "batas": f"Rentang maksimal {MAKS_HARI} hari kalender.",
        },
    }
