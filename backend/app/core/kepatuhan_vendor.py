"""Pembaca laporan "Kepatuhan vendor sampling" dari workbook GitHub.

Modul ini sengaja **hanya membaca** workbook dan menampilkan nilai yang sudah
tersimpan di dalamnya. Tidak ada normalisasi status, tidak ada koreksi
otomatis, dan tidak ada penulisan ke database. Hal itu penting karena berkas
sumber memakai dua aturan yang berbeda:

* Log Agustus/September: ``selisih >= 40 menit`` berarti **Tepat Waktu**.
* Log Oktober/November: ``selisih >= 40 menit`` berarti **Terlambat**.

Header kedua format menulis "Min. 30 menit", tetapi formula yang tersimpan
memakai ambang 40 menit. Karena pemilik meminta laporan "seperti" workbook,
nilai dari workbook dipertahankan apa adanya; perbedaan aturan hanya dijelaskan
di UI/dokumentasi.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re
from typing import Any

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

AKAR = pathlib.Path(__file__).resolve().parents[3]
BERKAS_BAWAAN = AKAR / "Laporan_Monitoring_Vendor_RM_Purchasing (1).xlsx"

NAMA_BULAN = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober",
    11: "November", 12: "Desember",
}

# Token bulan pada judul sheet / baris periode. Diurutkan berdasarkan panjang
# saat dipakai agar "SEPTEMBER" tidak terbaca sebagai "SEP" lebih dulu.
TOKEN_BULAN = {
    "JANUARI": 1, "JAN": 1, "FEBRUARI": 2, "FEB": 2, "MARET": 3, "MAR": 3,
    "APRIL": 4, "APR": 4, "MEI": 5, "JUNI": 6, "JUN": 6, "JULI": 7, "JUL": 7,
    "AGUSTUS": 8, "AGU": 8, "AUGUST": 8, "AUG": 8,
    "SEPTEMBER": 9, "SEPT": 9, "SEP": 9,
    "OKTOBER": 10, "OKT": 10, "OCTOBER": 10, "OCT": 10,
    "NOVEMBER": 11, "NOV": 11, "DESEMBER": 12, "DES": 12, "DEC": 12,
}

CATATAN_ATURAN = [
    "Nilai, status, dan TOTAL ditampilkan persis dari workbook; modul tidak menghitung ulang.",
    "Header log menulis 'Min. 30 menit', tetapi formula Agu/Sep memakai ambang 40 menit dengan selisih ≥ 40 = Tepat Waktu, sedangkan Okt/Nov memakai selisih ≥ 40 = Terlambat.",
    "Baris tanpa perwakilan / tanpa data waktu tetap masuk Total Kunjungan, tetapi tidak masuk pembilang % Tepat Waktu.",
]


def _ke_json(nilai: Any) -> Any:
    """Ubah nilai sel Excel menjadi nilai yang aman dikirim sebagai JSON."""
    if nilai is None:
        return None
    if isinstance(nilai, dt.datetime):
        if nilai.time() == dt.time(0, 0):
            return nilai.date().isoformat()
        return nilai.isoformat(timespec="minutes")
    if isinstance(nilai, dt.date):
        return nilai.isoformat()
    if isinstance(nilai, dt.time):
        return nilai.strftime("%H:%M")
    if isinstance(nilai, str):
        teks = nilai.strip()
        if not teks:
            return None
        cocok = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", teks)
        if cocok:
            hari, bulan, tahun = (int(x) for x in cocok.groups())
            try:
                return dt.date(tahun, bulan, hari).isoformat()
            except ValueError:
                return teks
        return teks
    return nilai


def _angka(nilai: Any) -> int | float:
    if isinstance(nilai, bool):
        return 0
    if isinstance(nilai, (int, float)):
        return nilai
    return 0


def _bersih_label(nilai: Any) -> str:
    if nilai is None:
        return ""
    return " ".join(str(nilai).replace("\n", " ").split())


def _tahun_dari_teks(teks: str) -> int | None:
    cocok = re.search(r"\b(20\d{2})\b", teks or "")
    return int(cocok.group(1)) if cocok else None


def _bulan_dari_teks(teks: str) -> int | None:
    atas = (teks or "").upper()
    for token in sorted(TOKEN_BULAN, key=len, reverse=True):
        if re.search(rf"\b{re.escape(token)}\b", atas):
            return TOKEN_BULAN[token]
    return None


def _pasangan_lembar(wb_nilai: openpyxl.Workbook) -> dict[tuple[int, int], tuple[str, str]]:
    """Pasangkan sheet Log dan Summary menurut tahun+bulan yang terbaca."""
    log: dict[tuple[int, int], str] = {}
    ringkas: dict[tuple[int, int], str] = {}
    for ws in wb_nilai.worksheets:
        judul = ws.title
        if judul.lower().startswith("log monitoring"):
            teks = str(_ke_json(ws.cell(2, 1).value) or "")
            tahun = _tahun_dari_teks(teks) or 2026
            bulan = _bulan_dari_teks(judul) or _bulan_dari_teks(teks)
            if bulan:
                log[(tahun, bulan)] = judul
        elif judul.lower().startswith("summary"):
            teks = str(_ke_json(ws.cell(1, 1).value) or "")
            tahun = _tahun_dari_teks(teks) or 2026
            bulan = _bulan_dari_teks(teks) or _bulan_dari_teks(judul)
            if bulan:
                ringkas[(tahun, bulan)] = judul
    return {
        kunci: (log[kunci], ringkas[kunci])
        for kunci in sorted(set(log) & set(ringkas))
    }


def _aturan_dari_formula(ws_formula: Worksheet | None, bulan: int) -> str:
    """Baca ambang dan arah status dari formula baris log pertama."""
    if ws_formula is not None:
        header = [_bersih_label(ws_formula.cell(4, c).value).upper()
                  for c in range(1, ws_formula.max_column + 1)]
        indeks = next((i + 1 for i, h in enumerate(header)
                       if "STATUS KETEPATAN" in h), None)
        if indeks:
            rumus = ws_formula.cell(5, indeks).value
            if isinstance(rumus, str) and rumus.startswith("="):
                cocok = re.search(r">=\s*(\d+)", rumus)
                ambang = int(cocok.group(1)) if cocok else 40
                pos_tepat = rumus.find('"Tepat Waktu"')
                pos_telat = rumus.find('"Terlambat"')
                hasil = ("Tepat Waktu" if pos_tepat >= 0
                         and (pos_telat < 0 or pos_tepat < pos_telat)
                         else "Terlambat")
                return f"Formula sheet: selisih ≥ {ambang} menit = {hasil}."
    # Fallback bila status sudah diketik manual, bukan formula.
    hasil = "Tepat Waktu" if bulan <= 9 else "Terlambat"
    return f"Aturan sheet: selisih ≥ 40 menit = {hasil}."


def _baca_log(ws: Worksheet) -> tuple[list[str], list[list[Any]]]:
    kolom = [_bersih_label(ws.cell(4, c).value)
             for c in range(1, ws.max_column + 1)]
    baris: list[list[Any]] = []
    for r in range(5, ws.max_row + 1):
        nilai = [_ke_json(ws.cell(r, c).value)
                 for c in range(1, ws.max_column + 1)]
        if all(v is None or v == "" for v in nilai[1:]):
            continue
        # Baris bernomor tetapi kosong (mis. template November) tidak dihitung.
        if not nilai[1] and not nilai[2]:
            continue
        baris.append(nilai)
    return kolom, baris


def _baca_summary(ws: Worksheet) -> tuple[
        list[str], list[dict[str, Any]], dict[str, Any] | None]:
    kolom = [_bersih_label(ws.cell(3, c).value)
             for c in range(1, ws.max_column + 1)]
    baris: list[dict[str, Any]] = []
    total: dict[str, Any] | None = None
    for r in range(4, ws.max_row + 1):
        nilai = [_ke_json(ws.cell(r, c).value)
                 for c in range(1, ws.max_column + 1)]
        if len(nilai) < 2 or nilai[1] is None:
            continue
        vendor = str(nilai[1]).strip()
        if not vendor:
            continue
        rekaman = {
            "no": nilai[0],
            "vendor": vendor,
            "tepat": nilai[2],
            "terlambat": nilai[3],
            "tanpa_data": nilai[4],
            "total": nilai[5],
            "persen": nilai[6],
            "keterangan": nilai[7],
            "kata_kunci": nilai[8] if len(nilai) > 8 else None,
        }
        if vendor.upper() == "TOTAL":
            total = rekaman
        else:
            baris.append(rekaman)
    return kolom, baris, total


def _ringkasan(total: dict[str, Any] | None,
               baris_summary: list[dict[str, Any]],
               jumlah_log: int) -> dict[str, Any]:
    if total:
        tepat = _angka(total.get("tepat"))
        terlambat = _angka(total.get("terlambat"))
        tanpa_data = _angka(total.get("tanpa_data"))
        kunjungan = _angka(total.get("total"))
        persen = total.get("persen")
        keterangan = total.get("keterangan") or ""
    else:
        tepat = sum(_angka(b.get("tepat")) for b in baris_summary)
        terlambat = sum(_angka(b.get("terlambat")) for b in baris_summary)
        tanpa_data = sum(_angka(b.get("tanpa_data")) for b in baris_summary)
        kunjungan = sum(_angka(b.get("total")) for b in baris_summary)
        terukur = tepat + terlambat
        persen = (tepat / terukur) if terukur else None
        keterangan = ("Ringkasan dihitung dari baris vendor karena baris TOTAL "
                      "tidak ditemukan.")
    if not isinstance(persen, (int, float)) or isinstance(persen, bool):
        persen = None
    return {
        "tepat": tepat,
        "terlambat": terlambat,
        "tanpa_data": tanpa_data,
        "total_kunjungan": kunjungan,
        "terukur": tepat + terlambat,
        "persen_tepat": persen,
        "vendor_tercatat": len(baris_summary),
        "baris_log": jumlah_log,
        "keterangan": keterangan,
    }


def baca_laporan(path: str | pathlib.Path | None = None) -> dict[str, Any]:
    """Baca seluruh workbook menjadi struktur siap pakai API/UI.

    ``path`` disediakan untuk pengujian; produksi memakai berkas bawaan yang
    disalin dari GitHub ke akar repo.
    """
    berkas = pathlib.Path(path or BERKAS_BAWAAN)
    if not berkas.is_file():
        raise FileNotFoundError(
            f"Berkas laporan tidak ditemukan: {berkas.name}. "
            "Salin Laporan_Monitoring_Vendor_RM_Purchasing (1).xlsx dari GitHub "
            "ke akar repo.")
    wb_nilai = openpyxl.load_workbook(berkas, data_only=True, read_only=False)
    wb_rumus = openpyxl.load_workbook(berkas, data_only=False, read_only=False)
    lembar_rumus = {ws.title: ws for ws in wb_rumus.worksheets}
    try:
        pasangan = _pasangan_lembar(wb_nilai)
        if not pasangan:
            raise ValueError("Workbook tidak memiliki pasangan sheet Log/Summary.")
        daftar: list[dict[str, Any]] = []
        for (tahun, bulan), (nama_log, nama_summary) in pasangan.items():
            ws_log = wb_nilai[nama_log]
            ws_sum = wb_nilai[nama_summary]
            kolom_log, log = _baca_log(ws_log)
            kolom_summary, summary, total = _baca_summary(ws_sum)
            ringkasan = _ringkasan(total, summary, len(log))
            daftar.append({
                "kunci": f"{tahun}-{bulan:02d}",
                "tahun": tahun,
                "bulan": bulan,
                "label": f"{NAMA_BULAN[bulan]} {tahun}",
                "sheet_log": nama_log,
                "sheet_summary": nama_summary,
                "judul": str(_ke_json(ws_log.cell(1, 1).value) or ""),
                "judul_summary": str(_ke_json(ws_sum.cell(1, 1).value) or ""),
                "periode_teks": str(_ke_json(ws_log.cell(2, 1).value) or ""),
                "aturan": _aturan_dari_formula(lembar_rumus.get(nama_log), bulan),
                "kolom_log": kolom_log,
                "log": log,
                "kolom_summary": kolom_summary,
                "summary": summary,
                "total": total,
                "ringkasan": ringkasan,
            })
        stat = berkas.stat()
        return {
            "sumber": {
                "nama_file": berkas.name,
                "ukuran": stat.st_size,
                "diubah": dt.datetime.fromtimestamp(
                    stat.st_mtime, tz=dt.timezone.utc).isoformat(timespec="seconds"),
                "jumlah_lembar": len(wb_nilai.sheetnames),
            },
            "catatan_aturan": CATATAN_ATURAN,
            "daftar_periode": [
                {k: p[k] for k in ("kunci", "tahun", "bulan", "label",
                                   "sheet_log", "sheet_summary", "ringkasan")}
                for p in daftar
            ],
            "periode": {p["kunci"]: p for p in daftar},
        }
    finally:
        wb_nilai.close()
        wb_rumus.close()
