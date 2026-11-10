"""Konsistensi intake harian/bulanan per vendor — perhitungan murni, tanpa SQL.

Menjawab tiga pertanyaan pemilik pada satu kartu Intake Analisis:

1. Vendor mana yang masuk **setiap hari kalender** dan **setiap bulan** pada
   rentang terpilih, dan pada rentang kapan ia paling konsisten.
2. Bila ada hari/bulan kosong, **hari dan bulan apa saja** yang kosong.
3. Vendor mana yang **paling sering masuk** (jumlah tanggal unik ber-intake).

Semua angka memakai `Ticket Date` pada baris tiket. Modul ini sengaja tidak
menyentuh database supaya aturannya bisa diuji tanpa fixture SQL.

Sejak koreksi pemilik "harus bisa menampilkan semua rentang data, jika data
terlalu panjang coba minimalisir", batas 731 hari dihapus. Periode panjang
tetap dihitung penuh, tetapi hari kosong disimpan sebagai **rentang tanggal
berurutan** plus **rekap per bulan**, bukan jutaan objek per tanggal. Rincian
per tanggal lengkap tetap bisa dibangkitkan untuk ekspor Excel.
"""
from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from typing import Iterable

NAMA_HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
NAMA_BULAN_SINGKAT = ("", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                      "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

#: Batas keamanan absolut, BUKAN batas data. Seluruh rentang tiket nyata
#: (misal 1.766 hari) tetap boleh; ini hanya menolak tanggal ekstrem seperti
#: 0001-01-01 s.d. 9999-12-31 yang mustahil berisi data intake.
MAKS_HARI = 366 * 100  # ≈ 100 tahun kalender

#: Di atas panjang ini layar memakai mode ringkas (rentang + rekap per bulan).
AMBANG_RINGKAS_HARI = 366
#: Maksimal chip/detail per tanggal yang dikirim ke JSON layar.
MAKS_RINCIAN_LAYAR = 31
MAKS_BULAN_LAYAR = 24
MAKS_RENTANG_LAYAR = 60
MAKS_REKAP_BULAN_LAYAR = 120


def label_hari(tanggal: dt.date) -> str:
    return NAMA_HARI[tanggal.weekday()]


def kode_bulan(tanggal: dt.date) -> str:
    return f"{tanggal.year}-{tanggal.month:02d}"


def label_bulan(th: int, bl: int) -> str:
    return f"{NAMA_BULAN_SINGKAT[bl]}-{str(th)[2:]}"


def label_tanggal(tanggal: dt.date) -> str:
    return (f"{label_hari(tanggal)}, {tanggal.day:02d}/"
            f"{tanggal.month:02d}/{tanggal.year}")


def daftar_hari(awal: dt.date, akhir: dt.date) -> list[dt.date]:
    """Semua tanggal kalender dari `awal` sampai `akhir`, inklusif.

    Dipertahankan untuk pengujian/kebutuhan kecil; `hitung_konsistensi` tidak
    memakainya lagi supaya rentang panjang tidak perlu dialokasikan per hari.
    """
    return [awal + dt.timedelta(days=i)
            for i in range((akhir - awal).days + 1)]


def _bulan_berikut(pasangan: tuple[int, int]) -> tuple[int, int]:
    th, bl = pasangan
    return (th + 1, 1) if bl == 12 else (th, bl + 1)


def _meta_bulan(awal: dt.date, akhir: dt.date) -> list[dict]:
    """Bulan yang tersentuh rentang, tanpa membuat daftar semua tanggal."""
    hasil: list[dict] = []
    ym = (awal.year, awal.month)
    batas = (akhir.year, akhir.month)
    while ym <= batas:
        th, bl = ym
        akhir_bulan = dt.date(th, bl, calendar.monthrange(th, bl)[1])
        t0, t1 = max(awal, dt.date(th, bl, 1)), min(akhir, akhir_bulan)
        hasil.append({
            "ym": f"{th}-{bl:02d}",
            "label": label_bulan(th, bl),
            "tahun": th,
            "bulan": bl,
            "jumlah_hari": (t1 - t0).days + 1,
            "tanggal_awal": t0.isoformat(),
            "tanggal_akhir": t1.isoformat(),
        })
        ym = _bulan_berikut(ym)
    return hasil


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


def _interval_kosong(hadir: set[dt.date], awal: dt.date,
                     akhir: dt.date) -> list[tuple[dt.date, dt.date]]:
    """Komplemen tanggal hadir dalam `[awal, akhir]` sebagai interval inklusif.

    Ini kunci pemadatan: 1.766 hari kosong sebelum tiket pertama cukup satu
    pasang tanggal, bukan 1.766 objek.
    """
    hasil: list[tuple[dt.date, dt.date]] = []
    kini = awal
    for h in sorted(x for x in hadir if awal <= x <= akhir):
        if h < kini:
            continue
        if h > kini:
            hasil.append((kini, h - dt.timedelta(days=1)))
        kini = h + dt.timedelta(days=1)
        if kini > akhir:
            break
    if kini <= akhir:
        hasil.append((kini, akhir))
    return hasil


def _panjang_interval(interval: Iterable[tuple[dt.date, dt.date]]) -> int:
    return sum((z - a).days + 1 for a, z in interval)


def _uraikan_interval(interval: Iterable[tuple[dt.date, dt.date]]):
    """Bangkitkan kembali tiap tanggal dari interval (dipakai Excel/sepi)."""
    for a, z in interval:
        h = a
        while h <= z:
            yield h
            h += dt.timedelta(days=1)


def _ringkasan_angka(angka: list[int]) -> str:
    """`[1,2,3,5,8,9]` → `"01-03, 05, 08-09"`."""
    if not angka:
        return "–"
    urut = sorted(set(angka))
    kelompok: list[tuple[int, int]] = []
    a = z = urut[0]
    for n in urut[1:]:
        if n == z + 1:
            z = n
        else:
            kelompok.append((a, z))
            a = z = n
    kelompok.append((a, z))
    return ", ".join(f"{a:02d}" if a == z else f"{a:02d}-{z:02d}"
                     for a, z in kelompok)


def _urutan_bulan(ym: str) -> int:
    th, bl = (int(x) for x in ym.split("-"))
    return th * 12 + bl


def _pasangan_dari_urutan(n: int) -> tuple[int, int]:
    return (n - 1) // 12, (n - 1) % 12 + 1


def kelompok_rentang_bulan(daftar: list[dict]) -> list[dict]:
    """Gabungkan bulan kosong/lengkap berurutan jadi satu rentang."""
    if not daftar:
        return []
    urut = sorted((_urutan_bulan(x["ym"]), x) for x in daftar)
    hasil: list[dict] = []

    def susun(n_awal: int, n_akhir: int, awal: dict, akhir: dict,
              jumlah: int) -> dict:
        tha, bla = _pasangan_dari_urutan(n_awal)
        thz, blz = _pasangan_dari_urutan(n_akhir)
        return {
            "dari": awal["ym"], "sampai": akhir["ym"],
            "label": (awal["label"] if jumlah == 1
                      else f"{awal['label']} → {akhir['label']}"),
            "label_dari": label_bulan(tha, bla),
            "label_sampai": label_bulan(thz, blz),
            "jumlah_bulan": jumlah,
        }

    n_awal = n_akhir = urut[0][0]
    awal = akhir = urut[0][1]
    jumlah = 1
    for n, item in urut[1:]:
        if n == n_akhir + 1:
            n_akhir, akhir, jumlah = n, item, jumlah + 1
        else:
            hasil.append(susun(n_awal, n_akhir, awal, akhir, jumlah))
            n_awal = n_akhir = n
            awal = akhir = item
            jumlah = 1
    hasil.append(susun(n_awal, n_akhir, awal, akhir, jumlah))
    return hasil


def _kategori_hari(h: dt.date, sepi: set[dt.date],
                   batas_data: tuple[dt.date, dt.date] | None) -> str:
    if batas_data and (h < batas_data[0] or h > batas_data[1]):
        return "di_luar_data"
    if h in sepi:
        return "pabrik tutup"
    return "kosong vendor"


def _rincian_interval(interval: list[tuple[dt.date, dt.date]],
                      sepi: set[dt.date],
                      batas_data: tuple[dt.date, dt.date] | None,
                      maks_detail: int = MAKS_RINCIAN_LAYAR) -> tuple:
    """Dari interval kosong hasilkan: chip awal, grup rentang, rekap per bulan.

    Tetap menyebut tanggal pasti (awal/akhir rentang + nomor tanggal per
    bulan), tetapi jumlah objek tidak membengkak mengikuti panjang periode.
    """
    detail: list[dict] = []
    grup: list[dict] = []
    per_bulan: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"hari": [], "sepi": 0, "luar": 0, "vendor": 0})

    for a, z in interval:
        n = (z - a).days + 1
        j_sepi = j_luar = j_vendor = 0
        h = a
        while h <= z:
            kategori = _kategori_hari(h, sepi, batas_data)
            if kategori == "di_luar_data":
                j_luar += 1
            elif kategori == "pabrik tutup":
                j_sepi += 1
            else:
                j_vendor += 1
            if len(detail) < maks_detail:
                detail.append({
                    "tanggal": h.isoformat(),
                    "hari": label_hari(h),
                    "bulan": kode_bulan(h),
                    "label": label_tanggal(h),
                    "sepi_pabrik": kategori == "pabrik tutup",
                    "di_luar_data": kategori == "di_luar_data",
                    "kategori": kategori,
                })
            isi = per_bulan[(h.year, h.month)]
            isi["hari"].append(h.day)
            isi[{"di_luar_data": "luar", "pabrik tutup": "sepi",
                 "kosong vendor": "vendor"}[kategori]] += 1
            h += dt.timedelta(days=1)
        if j_luar == n:
            kategori_grup = "di_luar_data"
        elif j_sepi == n:
            kategori_grup = "pabrik tutup"
        elif j_vendor == n:
            kategori_grup = "kosong vendor"
        else:
            kategori_grup = "campuran"
        label = (label_tanggal(a) if n == 1
                 else f"{label_tanggal(a)} → {label_tanggal(z)}")
        grup.append({
            "dari": a.isoformat(), "sampai": z.isoformat(),
            "jumlah_hari": n,
            "label": label,
            "teks": f"{label} · {n} hari",
            "label_dari": label_tanggal(a),
            "label_sampai": label_tanggal(z),
            "jumlah_sepi_pabrik": j_sepi,
            "jumlah_di_luar_data": j_luar,
            "jumlah_kosong_vendor": j_vendor,
            "sepi_pabrik": kategori_grup == "pabrik tutup",
            "di_luar_data": kategori_grup == "di_luar_data",
            "kategori": kategori_grup,
        })

    rekap: list[dict] = []
    for (th, bl), isi in sorted(per_bulan.items()):
        ringkasan = _ringkasan_angka(isi["hari"])
        rekap.append({
            "ym": f"{th}-{bl:02d}",
            "label": label_bulan(th, bl),
            "tahun": th, "bulan": bl,
            "jumlah_hari": len(isi["hari"]),
            "ringkasan": ringkasan,
            "teks": f"{label_bulan(th, bl)}: {len(isi['hari'])} hari "
                    f"({ringkasan})",
            "jumlah_sepi_pabrik": isi["sepi"],
            "jumlah_di_luar_data": isi["luar"],
            "jumlah_kosong_vendor": isi["vendor"],
        })
    return detail, grup, rekap


def _norm_kode(nilai: str | None) -> str:
    return " ".join((nilai or "").split()).upper() or "(KOSONG)"


def hitung_konsistensi(
    tiket: Iterable[tuple[dt.date, str | None, str | None, float | None]],
    awal: dt.date,
    akhir: dt.date,
    nama_vendor: dict[str, str] | None = None,
    batas_data: tuple[dt.date, dt.date] | None = None,
) -> dict:
    """Hitung rekap konsistensi untuk rentang PENUH, dengan rincian padat.

    `tiket` berisi `(tanggal, kode_vendor, ticket_no, dry_kg)`. Tanggal di luar
    rentang diabaikan. `batas_data` (tanggal tiket paling awal/akhir) dipakai
    untuk menandai hari yang memang belum ada datanya, bukan pabrik tutup.
    """
    nama_vendor = {_norm_kode(k): v for k, v in (nama_vendor or {}).items()}
    meta_bulan = _meta_bulan(awal, akhir)
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

    interval_sepi = _interval_kosong(hari_berintake, awal, akhir)
    hari_sepi = list(_uraikan_interval(interval_sepi))
    sepi_set = set(hari_sepi)
    n_hari, n_bulan = (akhir - awal).days + 1, len(meta_bulan)
    sebelum = (max(0, (batas_data[0] - awal).days)
               if batas_data and awal < batas_data[0] else 0)
    sesudah = (max(0, (akhir - batas_data[1]).days)
               if batas_data and akhir > batas_data[1] else 0)
    hari_luar_data = sebelum + sesudah

    baris: list[dict] = []
    for kunci, isi in per.items():
        hadir = isi["hari"]
        hadir_per_bulan: dict[tuple[int, int], int] = defaultdict(int)
        for h in hadir:
            hadir_per_bulan[(h.year, h.month)] += 1
        bulan_hadir = {(h.year, h.month) for h in hadir}
        interval_kosong = _interval_kosong(hadir, awal, akhir)
        detail, grup, rekap_bulan = _rincian_interval(
            interval_kosong, sepi_set, batas_data)
        kosong_bulan = [m for m in meta_bulan
                        if (m["tahun"], m["bulan"]) not in bulan_hadir]
        bulan_lengkap = [m for m in meta_bulan
                         if hadir_per_bulan[(m["tahun"], m["bulan"])]
                         == m["jumlah_hari"]]
        ringkas_bulan = lambda daftar: [{
            "ym": m["ym"], "label": m["label"],
            "jumlah_hari": m["jumlah_hari"]} for m in daftar]
        kosong_bulan_r = ringkas_bulan(kosong_bulan)
        lengkap_bulan_r = ringkas_bulan(bulan_lengkap)
        nama = nama_vendor.get(kunci) or kunci
        jumlah_kosong = _panjang_interval(interval_kosong)
        baris.append({
            "peringkat": 0,
            "kode": kunci,
            "nama": nama,
            "label": f"{kunci} — {nama}" if nama != kunci else kunci,
            "jumlah_hari_masuk": len(hadir),
            "jumlah_hari_wajib": n_hari,
            "cakupan_hari_pct": round(len(hadir) / n_hari * 100, 2) if n_hari else 0.0,
            "status_harian": ("lengkap" if not interval_kosong
                              else "ada hari kosong"),
            "jumlah_bulan_masuk": len(bulan_hadir),
            "jumlah_bulan_wajib": n_bulan,
            "cakupan_bulan_pct": (round(len(bulan_hadir) / n_bulan * 100, 2)
                                  if n_bulan else 0.0),
            "status_bulanan": ("lengkap" if not kosong_bulan
                               else "ada bulan kosong"),
            "rentang_harian_terpanjang": rentang_harian_terpanjang(hadir),
            "rentang_bulanan_terpanjang": rentang_bulan_terpanjang(bulan_hadir),
            "bulan_lengkap": lengkap_bulan_r,
            "bulan_lengkap_rentang": kelompok_rentang_bulan(lengkap_bulan_r),
            "jumlah_tiket": len(isi["tiket"]),
            "total_kg": round(isi["kg"], 1),
            "jumlah_hari_kosong": jumlah_kosong,
            "jumlah_bulan_kosong": len(kosong_bulan),
            "hari_kosong": detail,
            "hari_kosong_terpotong": jumlah_kosong > len(detail),
            "hari_kosong_rentang": grup,
            "hari_kosong_per_bulan": rekap_bulan,
            "bulan_kosong": kosong_bulan_r,
            "bulan_kosong_rentang": kelompok_rentang_bulan(kosong_bulan_r),
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

    vendor_tanpa_intake = sorted(k for k in nama_vendor if k not in per)
    lengkap_harian = sum(1 for b in baris if b["status_harian"] == "lengkap")
    lengkap_bulanan = sum(1 for b in baris if b["status_bulanan"] == "lengkap")
    mode_ringkas = (n_hari > AMBANG_RINGKAS_HARI or
                    any(b["jumlah_hari_kosong"] > MAKS_RINCIAN_LAYAR
                        for b in baris))

    peringatan: list[str] = []
    if not baris:
        peringatan.append(
            "Tidak ada tiket intake pada rentang ini; belum ada vendor yang "
            "bisa dinilai konsistensinya.")
    if hari_luar_data:
        peringatan.append(
            f"{hari_luar_data} hari pada rentang yang dipilih berada di luar "
            "rentang tiket yang tersedia. Sesuai dasar 'semua hari kalender', "
            "hari itu TETAP dihitung kosong, tetapi ditandai 'di luar rentang "
            "data' agar tidak diartikan sebagai pabrik tutup.")
    if hari_sepi:
        peringatan.append(
            f"Ada {len(hari_sepi)} hari kalender tanpa intake dari vendor mana "
            "pun (akhir pekan/hari libur/operasional sepi/belum ada data). "
            "Sesuai dasar 'semua hari kalender', hari itu TETAP tercatat "
            "kosong untuk setiap vendor; kolom kategori di Excel "
            "membedakannya.")
    if baris and lengkap_harian == 0:
        peringatan.append(
            "Belum ada vendor yang masuk pada setiap hari kalender periode ini.")
    if vendor_tanpa_intake:
        peringatan.append(
            f"{len(vendor_tanpa_intake)} vendor pada Master Vendor tidak punya "
            "tiket sama sekali pada periode ini, sehingga tidak masuk tabel.")
    if mode_ringkas:
        peringatan.append(
            "Periode panjang: rincian hari kosong di layar otomatis "
            "DIMINIMALISIR menjadi rentang tanggal berurutan dan rekap per "
            "bulan. Ekspor Excel memuat seluruh rincian tanpa potongan.")

    _, grup_sepi, rekap_sepi = _rincian_interval(
        interval_sepi, sepi_set, batas_data, maks_detail=0)

    return {
        "status": "ok",
        "periode": {
            "dari": awal.isoformat(), "sampai": akhir.isoformat(),
            "jumlah_hari": n_hari, "jumlah_bulan": n_bulan,
            "dari_otomatis": False, "sampai_otomatis": False,
            "mode_rincian": "ringkas" if mode_ringkas else "per_hari",
            "ringkas_otomatis": mode_ringkas,
        },
        "batas_data": {
            "tersedia": bool(batas_data),
            "dari": batas_data[0].isoformat() if batas_data else None,
            "sampai": batas_data[1].isoformat() if batas_data else None,
            "jumlah_hari": ((batas_data[1] - batas_data[0]).days + 1
                            if batas_data else 0),
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
            "hari_di_luar_rentang_data": hari_luar_data,
            "vendor_lengkap_harian": lengkap_harian,
            "vendor_lengkap_bulanan": lengkap_bulanan,
            "vendor_tanpa_intake": len(vendor_tanpa_intake),
            "mode_rincian": "ringkas" if mode_ringkas else "per_hari",
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
            "bulan": kode_bulan(h), "label": label_tanggal(h),
            "di_luar_data": (_kategori_hari(h, sepi_set, batas_data)
                             == "di_luar_data"),
            "kategori": _kategori_hari(h, sepi_set, batas_data),
        } for h in hari_sepi],
        "hari_sepi_pabrik_rentang": grup_sepi,
        "hari_sepi_pabrik_per_bulan": rekap_sepi,
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
            "sepi_pabrik": "Hari pabrik tutup = tanggal tanpa tiket dari vendor "
                           "mana pun; tetap dihitung kosong, tetapi ditandai.",
            "di_luar_data": "Hari sebelum tiket paling awal atau sesudah tiket "
                            "paling akhir ditandai 'di luar rentang data', "
                            "bukan 'pabrik tutup', agar tidak menyesatkan.",
            "vendor_tidak_aktif": "Vendor tanpa tiket sama sekali pada periode "
                                  "tidak masuk tabel, tetapi jumlahnya dilaporkan.",
            "minimalisir": "Batas 731 hari dihapus: seluruh rentang data boleh "
                           "dipilih. Periode panjang otomatis dipadatkan di "
                           "layar menjadi rentang tanggal berurutan dan rekap "
                           "nomor tanggal per bulan; Excel tetap memuat baris "
                           "per tanggal lengkap.",
            "batas": f"Batas keamanan {MAKS_HARI} hari (±100 tahun) hanya "
                     "untuk tanggal ekstrem, bukan pembatas data intake.",
        },
    }
