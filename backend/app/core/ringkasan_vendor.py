"""Laporan Ringkasan Vendor berbasis **Trip**, mengikuti
`Intake-2025_Ringkasan-Vendor.xlsx`.

Perhitungan murni tanpa SQL, supaya aturan bisa diuji tanpa fixture database.
Beda dengan modul `konsistensi_intake` (yang menilai kedisiplinan hari
kalender), modul ini menjawab "siapa paling banyak mengirim trip, kapan, dan
berapa kg keringnya" dengan susunan tiga laporan:

1. **Ringkasan Vendor** — peringkat semua vendor: Total Trip, % Trip,
   Hari Aktif, Rata² Trip/Hari Operasional, Rata² Trip/Bulan, Dry (kg).
2. **Vendor per Bulan** — matriks Trip per vendor per bulan.
3. **Vendor Harian** — matriks Trip per vendor per **semua hari kalender**
   pada rentang terpilih; hari tanpa intake bernilai 0.

Keputusan pemilik (ask_user): metrik basis Trip; ekspor Excel 3 sheet + 3
chart native; semua vendor ditulis sebagai baris detail tanpa "Lainnya";
periode mengikuti filter `Dari/Sampai`; baris harian memakai semua hari
kalender. Rentang panjang tetap diterima penuh, tetapi rincian harian di
layar diminimalisir menjadi rentang tanggal + rekap per bulan; Excel tetap
memuat satu baris per tanggal.
"""
from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from typing import Iterable

NAMA_HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
NAMA_BULAN_SINGKAT = ("", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                      "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
NAMA_BULAN_INGGRIS = ("", "January", "February", "March", "April", "May",
                      "June", "July", "August", "September", "October",
                      "November", "December")

#: Batas keamanan absolut, BUKAN batas data. Seluruh rentang tiket nyata
#: (misal 1.766 hari) tetap boleh; hanya tanggal ekstrem ±100 tahun ditolak.
MAKS_HARI = 366 * 100
#: Di atas panjang ini JSON layar memakai mode ringkas; Excel tetap penuh.
AMBANG_RINGKAS_HARI = 366
#: Pengaman jumlah kolom bulan (100 tahun ≈ 1.200 bulan).
MAKS_BULAN = 1_200


def label_hari(tanggal: dt.date) -> str:
    return NAMA_HARI[tanggal.weekday()]


def kode_bulan(tanggal: dt.date) -> str:
    return f"{tanggal.year}-{tanggal.month:02d}"


def label_bulan(th: int, bl: int) -> str:
    return f"{NAMA_BULAN_SINGKAT[bl]}-{str(th)[2:]}"


def label_bulan_pendek(th: int, bl: int) -> str:
    return NAMA_BULAN_SINGKAT[bl]


def label_tanggal(tanggal: dt.date) -> str:
    """`Senin, 03/01/2025` — dipakai di tabel layar & rentang ringkas."""
    return (f"{label_hari(tanggal)}, {tanggal.day:02d}/"
            f"{tanggal.month:02d}/{tanggal.year}")


def label_tanggal_pendek(tanggal: dt.date) -> str:
    """`Sen, 03-Jan-25` — dipakai pada judul rentang ringkas."""
    return (f"{NAMA_HARI[tanggal.weekday()][:3]}, {tanggal.day:02d}-"
            f"{NAMA_BULAN_SINGKAT[tanggal.month]}-{str(tanggal.year)[2:]}")


def label_periode_inggris(awal: dt.date, akhir: dt.date) -> str:
    """`01-Jan-2025 to  31-Dec-2025` — mengikuti baris 4 contoh."""
    def satu(h: dt.date) -> str:
        return f"{h.day:02d}-{NAMA_BULAN_INGGRIS[h.month][:3]}-{h.year}"
    return f"{satu(awal)} to  {satu(akhir)}"


def label_periode_judul(awal: dt.date, akhir: dt.date) -> str:
    if awal.year == akhir.year:
        return str(awal.year)
    return f"{awal.year}–{akhir.year}"


def _bulan_berikut(pasangan: tuple[int, int]) -> tuple[int, int]:
    th, bl = pasangan
    return (th + 1, 1) if bl == 12 else (th, bl + 1)


def daftar_bulan(awal: dt.date, akhir: dt.date) -> list[dict]:
    """Semua bulan yang tersentuh rentang, berikut batas kalendernya."""
    hasil: list[dict] = []
    ym = (awal.year, awal.month)
    batas = (akhir.year, akhir.month)
    while ym <= batas and len(hasil) < MAKS_BULAN + 1:
        th, bl = ym
        akhir_bulan = dt.date(th, bl, calendar.monthrange(th, bl)[1])
        t0, t1 = max(awal, dt.date(th, bl, 1)), min(akhir, akhir_bulan)
        hasil.append({
            "ym": f"{th}-{bl:02d}",
            "label": label_bulan_pendek(th, bl),
            "label_ym": label_bulan(th, bl),
            "tahun": th, "bulan": bl,
            "awal": t0.isoformat(), "akhir": t1.isoformat(),
            "jumlah_hari": (t1 - t0).days + 1,
        })
        ym = _bulan_berikut(ym)
    if len(hasil) > MAKS_BULAN:
        raise ValueError(
            f"Periode {len(hasil)} bulan melebihi batas {MAKS_BULAN} bulan.")
    return hasil


def daftar_hari(awal: dt.date, akhir: dt.date) -> list[dt.date]:
    """Semua tanggal kalender inklusif, termasuk Sabtu/Minggu/libur."""
    return [awal + dt.timedelta(days=i)
            for i in range((akhir - awal).days + 1)]


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


def _kategori_hari(h: dt.date, ada_trip: bool,
                   batas_data: tuple[dt.date, dt.date] | None) -> str:
    if batas_data and (h < batas_data[0] or h > batas_data[1]):
        return "di_luar_data"
    return "ada_intake" if ada_trip else "sepi_pabrik"


def _rentang_harian(hari: list[dt.date], total_per_hari: list[int],
                    kategori: list[str]) -> list[dict]:
    """Kelompokkan tanggal berurutan dengan kategori sama (mode ringkas)."""
    if not hari:
        return []
    hasil: list[dict] = []
    a = z = 0
    for i in range(1, len(hari) + 1):
        putus = (i == len(hari) or kategori[i] != kategori[a])
        if putus:
            z = i - 1
            d, s = hari[a], hari[z]
            hasil.append({
                "dari": d.isoformat(), "sampai": s.isoformat(),
                "label_dari": label_tanggal_pendek(d),
                "label_sampai": label_tanggal_pendek(s),
                "label": (label_tanggal_pendek(d) if a == z else
                          f"{label_tanggal_pendek(d)} → {label_tanggal_pendek(s)}"),
                "jumlah_hari": z - a + 1,
                "kategori": kategori[a],
                "teks": (d.isoformat() if a == z else
                         f"{d.isoformat()} s.d. {s.isoformat()}"),
            })
            a = i
    return hasil


def hitung_ringkasan_vendor(mentah: Iterable[tuple], awal: dt.date,
                            akhir: dt.date, nama_vendor: dict[str, str],
                            batas_data: tuple[dt.date, dt.date] | None = None
                            ) -> dict:
    """Bangun seluruh data tiga laporan dari baris tiket mentah.

    `mentah` = iterable `(ticket_date, kode_vendor, ticket_no, dry_kg)`.
    `Trip` dihitung sebagai **Ticket No unik** (baris ke-2/3 dari nomor
    tiket yang sama tidak menambah Trip), persis helper `Trip (helper)` pada
    berkas contoh. `Dry (kg)` tetap menjumlahkan semua baris.
    """
    if awal > akhir:
        raise ValueError("Periode terbalik: awal lebih akhir daripada akhir.")
    if (akhir - awal).days + 1 > MAKS_HARI:
        raise ValueError(f"Rentang melebihi batas keamanan {MAKS_HARI} hari.")

    # ---- normalisasi & urutkan supaya "tiket pertama" deterministik
    def norm_kode(kode) -> str:
        return " ".join((kode or "(kosong)").split()).upper()

    nama_vendor = {norm_kode(k): v for k, v in (nama_vendor or {}).items()}
    baris_mentah: list[tuple[dt.date, str, str, float]] = []
    for i, (tgl, kode, no, kg) in enumerate(mentah):
        if isinstance(tgl, dt.datetime):
            tgl = tgl.date()
        if not isinstance(tgl, dt.date) or not (awal <= tgl <= akhir):
            continue
        kode = norm_kode(kode)
        no = str(no) if no is not None else f"__tanpa_nomor_{i}"
        try:
            kg = float(kg or 0)
        except (TypeError, ValueError):
            kg = 0.0
        baris_mentah.append((tgl, kode, no, kg))
    baris_mentah.sort(key=lambda x: (x[0], x[2], x[1]))

    # ---- satu Trip per Ticket No; tanggal & vendor mengikuti kemunculan pertama
    pertama: dict[str, tuple[dt.date, str]] = {}
    dry: dict[str, float] = defaultdict(float)
    for tgl, kode, no, kg in baris_mentah:
        dry[kode] += kg
        if no not in pertama:
            pertama[no] = (tgl, kode)

    trip: dict[str, int] = defaultdict(int)
    hari_vendor: dict[str, set[dt.date]] = defaultdict(set)
    trip_bulan: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    trip_hari: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for no, (tgl, kode) in pertama.items():
        trip[kode] += 1
        hari_vendor[kode].add(tgl)
        trip_bulan[kode][f"{tgl.year}-{tgl.month:02d}"] += 1
        trip_hari[kode][tgl.isoformat()] += 1

    semua_kode = set(nama_vendor) | set(trip) | set(dry)
    hari_operasional_set = {tgl for tgl, _kode in pertama.values()}
    hari_operasional = len(hari_operasional_set)
    total_trip = sum(trip.values())
    total_dry = sum(dry.values())

    bulan = daftar_bulan(awal, akhir)
    hari = daftar_hari(awal, akhir)
    jumlah_bulan = len(bulan)
    jumlah_hari = len(hari)
    if jumlah_bulan > MAKS_BULAN:
        raise ValueError(f"Periode {jumlah_bulan} bulan melebihi batas.")

    def nama_dari(kode: str) -> str:
        return (nama_vendor.get(kode) or kode).strip()

    def label_dari(kode: str) -> str:
        return nama_dari(kode)

    # ---- 1. Ringkasan Vendor (semua vendor, termasuk yang 0 Trip)
    urut = sorted(semua_kode,
                  key=lambda k: (-trip[k], -dry[k], label_dari(k)))
    baris_ringkasan: list[dict] = []
    for i, kode in enumerate(urut, start=1):
        t = trip[kode]
        baris_ringkasan.append({
            "peringkat": i,
            "kode": kode,
            "nama": nama_dari(kode),
            "label": label_dari(kode),
            "total_trip": t,
            "porsi_trip": (t / total_trip) if total_trip else 0.0,
            "porsi_trip_pct": (100.0 * t / total_trip) if total_trip else 0.0,
            "hari_aktif": len(hari_vendor.get(kode, ())),
            "rata_trip_per_hari_operasional":
                (t / hari_operasional) if hari_operasional else 0.0,
            "rata_trip_per_bulan":
                (t / jumlah_bulan) if jumlah_bulan else 0.0,
            "dry_kg": round(dry[kode], 1),
        })
    vendor_tanpa_intake = [
        {"kode": b["kode"], "label": b["label"]}
        for b in baris_ringkasan if b["total_trip"] == 0]
    paling_sering = baris_ringkasan[0] if baris_ringkasan else None
    seri = ([b["kode"] for b in baris_ringkasan
             if b["total_trip"] == (paling_sering or {}).get("total_trip")]
            if paling_sering else [])

    # ---- 2. Vendor per Bulan
    indeks_bulan = {b["ym"]: i for i, b in enumerate(bulan)}
    vendor_per_bulan: list[dict] = []
    total_per_bulan = [0] * jumlah_bulan
    for b in baris_ringkasan:
        kode = b["kode"]
        deret = [0] * jumlah_bulan
        for ym, n in trip_bulan.get(kode, {}).items():
            i = indeks_bulan.get(ym)
            if i is not None:
                deret[i] = n
                total_per_bulan[i] += n
        vendor_per_bulan.append({
            "kode": kode, "label": b["label"],
            "trip_per_bulan": deret, "total_trip": sum(deret),
        })
    vendor_utama_bulan: list[str] = []
    trip_utama_bulan: list[int] = []
    share_utama_bulan: list[float] = []
    for i in range(jumlah_bulan):
        if not vendor_per_bulan:
            vendor_utama_bulan.append("–")
            trip_utama_bulan.append(0)
            share_utama_bulan.append(0.0)
            continue
        j = max(range(len(vendor_per_bulan)),
                key=lambda k: (vendor_per_bulan[k]["trip_per_bulan"][i],
                               -baris_ringkasan[k]["peringkat"]))
        n = vendor_per_bulan[j]["trip_per_bulan"][i]
        vendor_utama_bulan.append(vendor_per_bulan[j]["label"] if n else "–")
        trip_utama_bulan.append(n)
        share_utama_bulan.append(
            (n / total_per_bulan[i]) if total_per_bulan[i] else 0.0)

    # ---- 3. Vendor Harian (SEMUA hari kalender)
    indeks_hari = {h.isoformat(): i for i, h in enumerate(hari)}
    vendor_harian: list[dict] = []
    for b in baris_ringkasan:
        kode = b["kode"]
        deret = [0] * jumlah_hari
        for iso, n in trip_hari.get(kode, {}).items():
            i = indeks_hari.get(iso)
            if i is not None:
                deret[i] = n
        vendor_harian.append({
            "kode": kode, "label": b["label"], "trip_per_hari": deret,
        })
    total_per_hari = [0] * jumlah_hari
    for v in vendor_harian:
        for i, n in enumerate(v["trip_per_hari"]):
            total_per_hari[i] += n

    peringkat_kode = {b["kode"]: b["peringkat"] for b in baris_ringkasan}
    vendor_utama_harian: list[str] = []
    trip_utama_harian: list[int] = []
    for i in range(jumlah_hari):
        if not vendor_harian:
            vendor_utama_harian.append("–")
            trip_utama_harian.append(0)
            continue
        j = max(range(len(vendor_harian)),
                key=lambda k: (vendor_harian[k]["trip_per_hari"][i],
                               -peringkat_kode[vendor_harian[k]["kode"]]))
        n = vendor_harian[j]["trip_per_hari"][i]
        vendor_utama_harian.append(vendor_harian[j]["label"] if n else "–")
        trip_utama_harian.append(n)

    info_hari: list[dict] = []
    kategori_hari: list[str] = []
    for i, h in enumerate(hari):
        luar = bool(batas_data and (h < batas_data[0] or h > batas_data[1]))
        kategori = _kategori_hari(h, total_per_hari[i] > 0, batas_data)
        info_hari.append({
            "tanggal": h.isoformat(),
            "label": label_tanggal(h),
            "label_pendek": label_tanggal_pendek(h),
            "hari": label_hari(h),
            "ym": kode_bulan(h),
            "di_luar_data": luar,
            "kategori": kategori,
            "sepi_pabrik": kategori == "sepi_pabrik",
            "total_trip": total_per_hari[i],
        })
        kategori_hari.append(kategori)
    rentang_hari = _rentang_harian(hari, total_per_hari, kategori_hari)

    rekap_per_bulan: list[dict] = []
    for b in bulan:
        awal_b = dt.date.fromisoformat(b["awal"])
        akhir_b = dt.date.fromisoformat(b["akhir"])
        nomor: list[int] = []
        total_b = 0
        hari_ber_intake = 0
        for h in daftar_hari(awal_b, akhir_b):
            i = indeks_hari.get(h.isoformat())
            if i is None:
                continue
            total_b += total_per_hari[i]
            if total_per_hari[i] > 0:
                hari_ber_intake += 1
                nomor.append(h.day)
        rekap_per_bulan.append({
            "ym": b["ym"], "label": b["label_ym"],
            "jumlah_hari_kalender": b["jumlah_hari"],
            "hari_ber_intake": hari_ber_intake,
            "total_trip": total_b,
            "rata_trip_per_hari": (total_b / b["jumlah_hari"])
                                  if b["jumlah_hari"] else 0.0,
            "ringkasan": _ringkasan_angka(nomor),
        })

    mode_ringkas = jumlah_hari > AMBANG_RINGKAS_HARI
    peringatan: list[str] = []
    if not baris_mentah:
        peringatan.append("Tidak ada tiket intake pada rentang ini.")
    if mode_ringkas:
        peringatan.append(
            f"Periode panjang ({jumlah_hari} hari) tetap dihitung penuh. "
            "Rincian harian di layar DIMINIMALISIR menjadi rentang tanggal "
            "berurutan dan rekap per bulan; Ekspor Excel memuat seluruh "
            "baris harian tanpa potongan.")
    if batas_data:
        luar = sum(1 for h in hari
                   if h < batas_data[0] or h > batas_data[1])
        if luar:
            peringatan.append(
                f"{luar} hari berada di luar rentang tiket yang tersedia "
                "dan tetap ditampilkan bernilai 0 Trip.")

    return {
        "status": "ok",
        "periode": {
            "dari": awal.isoformat(), "sampai": akhir.isoformat(),
            "jumlah_hari": jumlah_hari, "jumlah_bulan": jumlah_bulan,
            "mode_rincian": "ringkas" if mode_ringkas else "rinci",
            "ringkas_otomatis": mode_ringkas,
            "dari_otomatis": False, "sampai_otomatis": False,
            "label_inggris": label_periode_inggris(awal, akhir),
            "label_judul": label_periode_judul(awal, akhir),
        },
        "batas_data": ({
            "tersedia": True,
            "dari": batas_data[0].isoformat(),
            "sampai": batas_data[1].isoformat(),
            "jumlah_hari": (batas_data[1] - batas_data[0]).days + 1,
        } if batas_data else {"tersedia": False, "dari": None,
                              "sampai": None, "jumlah_hari": 0}),
        "dasar": {
            "hari": "kalender",
            "urutan": "jumlah_trip",
            "label_hari": "Semua hari kalender dalam rentang tetap ditampilkan",
            "label_urutan": "Jumlah Trip (Ticket No unik)",
        },
        "ringkasan": {
            "total_vendor": len(baris_ringkasan),
            "total_trip": total_trip,
            "total_dry_kg": round(total_dry, 1),
            "hari_operasional": hari_operasional,
            "hari_kalender": jumlah_hari,
            "jumlah_bulan": jumlah_bulan,
            "vendor_tanpa_intake": len(vendor_tanpa_intake),
        },
        "total": {
            "total_trip": total_trip,
            "total_dry_kg": round(total_dry, 1),
            "hari_operasional": hari_operasional,
            "hari_kalender": jumlah_hari,
            "jumlah_bulan": jumlah_bulan,
        },
        "baris": baris_ringkasan,
        "paling_sering": paling_sering,
        "seri_paling_sering": seri,
        "vendor_tanpa_intake": vendor_tanpa_intake,
        "bulan": bulan,
        "vendor_per_bulan": vendor_per_bulan,
        "total_per_bulan": total_per_bulan,
        "vendor_utama_bulan": vendor_utama_bulan,
        "trip_utama_bulan": trip_utama_bulan,
        "share_utama_bulan": share_utama_bulan,
        "hari": info_hari,
        "vendor_harian": vendor_harian,
        "total_per_hari": total_per_hari,
        "vendor_utama_harian": vendor_utama_harian,
        "trip_utama_harian": trip_utama_harian,
        "rata_vendor_per_hari": [
            (sum(v["trip_per_hari"]) / jumlah_hari) if jumlah_hari else 0.0
            for v in vendor_harian],
        "rata_total_per_hari": (total_trip / jumlah_hari)
                               if jumlah_hari else 0.0,
        "rentang_hari": rentang_hari,
        "rekap_per_bulan": rekap_per_bulan,
        "peringatan": peringatan,
        "sumber": ("tiket_baris (Ticket Date, tanpa tiket nol); "
                   "Trip = Ticket No unik; dasar hari = semua hari kalender; "
                   "urutan = jumlah Trip"),
        "catatan_metode": {
            "sumber": "Sumber: tiket_baris, Ticket Date, tanpa tiket nol.",
            "trip": "Trip = Ticket No unik; baris tambahan pada nomor tiket "
                    "yang sama tidak menambah Trip, tetapi Dry (kg) tetap "
                    "dijumlahkan.",
            "dasar_hari": "Semua hari kalender Dari–Sampai ditampilkan, "
                          "termasuk Sabtu/Minggu/libur; hari tanpa intake "
                          "bernilai 0 Trip.",
            "dasar_urutan": "Peringkat memakai jumlah Trip, lalu Dry (kg), "
                            "lalu nama vendor.",
            "hari_operasional": "Hari Operasional = jumlah tanggal unik yang "
                                "memiliki minimal satu Trip (pabrik aktif).",
            "rata": "Rata² Trip/Hari Operasional = Total Trip ÷ Hari "
                    "Operasional; Rata² Trip/Bulan = Total Trip ÷ jumlah "
                    "bulan pada rentang.",
            "minimalisir": "Batas 731 hari dihapus: seluruh rentang data "
                           "boleh dipilih. Periode panjang diminimalisir di "
                           "layar menjadi rentang tanggal + rekap per bulan; "
                           "Excel tetap memuat satu baris per tanggal.",
            "di_luar_data": "Tanggal di luar rentang tiket tersedia tetap "
                            "ditampilkan bernilai 0 Trip.",
            "sepi_pabrik": "Hari tanpa intake dari vendor mana pun (pabrik tutup) "
                           "bernilai 0 Trip dan tetap masuk baris harian.",
            "batas": f"Batas keamanan {MAKS_HARI} hari (±100 tahun) hanya "
                     "menolak tanggal ekstrem, bukan membatasi data.",
        },
    }


def ringkas_untuk_layar(hasil: dict) -> dict:
    """Pangkas matriks harian untuk JSON layar bila periode sangat panjang.

    `baris`, `vendor_per_bulan`, dan `bulan` tetap lengkap; hanya matriks
    per tanggal yang diganti rentang + rekap per bulan. Excel memakai
    `hasil` asli, jadi tidak kehilangan satu baris pun.
    """
    d = dict(hasil)
    if not hasil["periode"]["ringkas_otomatis"]:
        return d
    d["hari"] = []
    d["vendor_harian"] = []
    d["total_per_hari"] = []
    d["vendor_utama_harian"] = []
    d["trip_utama_harian"] = []
    d["peringatan"] = list(hasil["peringatan"])
    return d
