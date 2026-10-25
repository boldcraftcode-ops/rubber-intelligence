"""Narasi "Jelaskan ke saya" untuk setiap kartu di layar.

Prinsip (diminta pengguna): **jawaban dulu, bukti kemudian**
(What -> So what -> Now what), analogi sederhana, dan HANYA SATU angka utama
per kartu — untuk kartu OP Margin vs target angka utamanya adalah selisih
terhadap target, bukan angka lain.

Aturan tambahan:
- Angka dibulatkan ("sekitar 2 sen"), tidak pernah empat desimal.
- Hindari istilah teknis (variance, bridge, MoM); pakai "selisih dari target"
  dan "dibanding bulan lalu".
- Lapisan kedua (detail angka + rumus) disimpan di `detail` dan hanya dibuka
  bila pengguna menanyakannya.

Narasi dihasilkan dari data nyata, bukan teks tempelan: bila data tidak ada,
kartu menyatakan itu dengan jujur (`ada_data = False`).
"""
from __future__ import annotations

import datetime as dt
import pathlib
from collections import defaultdict

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .api_analisis import _bulan_ym, _bulan_sebelum, _status_target
from .models import MartBulanan, MartHarian, ParameterPabrik

NAMA_BULAN = ("", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
              "Juli", "Agustus", "September", "Oktober", "November", "Desember")
NAMA_BULAN_SINGKAT = ("", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                      "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

ANALOGI_UMUM = ("Margin itu untung per kilo: seperti warung yang membeli karet "
                "Rp 9.000 lalu menjualnya Rp 10.000 — untungnya Rp 1.000 per kilo. "
                "Target adalah batas minimal agar usaha tetap sehat, seperti nilai "
                "kelulusan: di bawahnya bukan berarti rugi, tetapi belum sehat.")


# ---------------------------------------------------------------------------
# Pembulatan ramah orang awam
# ---------------------------------------------------------------------------
def sen(n: float | None) -> str:
    """Selalu dibulatkan: >= 1 sen jadi bulat ('sekitar 2 sen'),
    di bawah 1 sen jadi satu desimal ('0,4 sen'). Tidak pernah empat desimal."""
    if n is None:
        return "tidak tersedia"
    a = abs(n)
    if a >= 1:
        return f"sekitar {round(a)} sen"
    return f"{a:.1f} sen".replace(".", ",")


def arah(n: float) -> str:
    """'naik' / 'turun' / 'praktis tidak berubah'."""
    if abs(n) < 0.05:
        return "praktis tidak berubah"
    return "naik" if n > 0 else "turun"


def angka(n: float | None, desimal: int = 0) -> str:
    if n is None:
        return "–"
    return f"{n:,.{desimal}f}".replace(",", "×").replace(".", ",").replace("×", ".")


def label_bulan(th: int, bl: int) -> str:
    return f"{NAMA_BULAN_SINGKAT[bl]}-{str(th)[2:]}"


def _metrics() -> dict:
    path = pathlib.Path(__file__).resolve().parents[1] / "semantic" / "metrics.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _kartu_metrik(kartu: str) -> dict:
    isi = _metrics().get("kartu", {}).get(kartu) or {}
    return isi


def _dasar(kartu: str) -> dict:
    """Kerangka balasan: judul + analogi + lapisan kedua (rumus asli)."""
    m = _kartu_metrik(kartu)
    return {
        "kartu": kartu,
        "judul": m.get("judul") or kartu.replace("_", " "),
        "ada_data": True,
        "angka_utama": None,
        "what": [],
        "so_what": [],
        "now_what": [],
        "analogi": ANALOGI_UMUM,
        "cara_baca": "",
        "detail": [],
        "catatan": [],
        "rumus": (m.get("cara_dihitung") or "").strip(),
    }


def _bulan_mart(session: Session, dari, sampai, tahun=None):
    """Baris mart bulanan terfilter, plus nilai bulan sebelumnya."""
    semua = list(session.scalars(select(MartBulanan).order_by(
        MartBulanan.tahun, MartBulanan.bulan)))
    if tahun is not None:
        return [b for b in semua if b.tahun == tahun], semua
    keluar = [b for b in semua
              if (dari is None or (b.tahun, b.bulan) >= dari)
              and (sampai is None or (b.tahun, b.bulan) <= sampai)]
    return keluar, semua


def _data_kurs(session: Session) -> dict[tuple[int, int], float]:
    rp: dict[tuple[int, int], float] = defaultdict(float)
    usd: dict[tuple[int, int], float] = defaultdict(float)
    cadangan: dict[tuple[int, int], list[float]] = defaultdict(list)
    for h in session.scalars(select(MartHarian)):
        kunci = (h.tanggal.year, h.tanggal.month)
        if h.kurs:
            cadangan[kunci].append(h.kurs)
            if h.qty_kering_kg and h.kurs and h.amount_rp:
                rp[kunci] += float(h.amount_rp)
                usd[kunci] += float(h.amount_rp) / h.kurs
    hasil = {}
    for kunci in cadangan:
        hasil[kunci] = (rp[kunci] / usd[kunci]) if usd.get(kunci) \
            else sum(cadangan[kunci]) / len(cadangan[kunci])
    return hasil


# ---------------------------------------------------------------------------
# 1) OP Margin bulanan vs target — kasus utama (narasi 60 detik)
# ---------------------------------------------------------------------------
def _jelaskan_margin_bulanan(session: Session, dari, sampai, **_):
    d = _dasar("margin_bulanan")
    baris, semua = _bulan_mart(session, dari, sampai)
    berstatus = [b for b in baris
                 if b.target_usc is not None and b.op_margin_usc is not None]
    if not berstatus:
        d["ada_data"] = False
        d["what"] = ["Belum ada bulan yang punya target dan margin sekaligus, "
                     "jadi belum bisa dibandingkan."]
        d["now_what"] = ["Isi target margin bulanan di menu Perencanaan lebih dulu."]
        return d

    akhir = berstatus[-1]
    selisih_akhir = akhir.op_margin_usc - akhir.target_usc
    # berapa bulan berturut-turut statusnya sama dengan bulan terakhir?
    status_akhir = _status_target(akhir.op_margin_usc, akhir.target_usc)
    rentet = 0
    for b in reversed(berstatus):
        if _status_target(b.op_margin_usc, b.target_usc) == status_akhir:
            rentet += 1
        else:
            break
    mulai_rentet = berstatus[-rentet]
    di_bawah = [b for b in berstatus if (b.op_margin_usc - b.target_usc) < 0]
    di_atas = [b for b in berstatus if (b.op_margin_usc - b.target_usc) >= 0]

    # ---- ANGKA UTAMA: satu saja (selisih terhadap target / jumlah bulan)
    if status_akhir == "di bawah target" and rentet >= 2:
        d["angka_utama"] = {
            "nilai": f"{rentet} bulan",
            "label": f"berturut-turut di bawah target sejak "
                     f"{label_bulan(mulai_rentet.tahun, mulai_rentet.bulan)}",
        }
    else:
        arah_selisih = "di atas" if selisih_akhir >= 0 else "di bawah"
        d["angka_utama"] = {
            "nilai": sen(selisih_akhir),
            "label": f"{arah_selisih} target pada "
                     f"{label_bulan(akhir.tahun, akhir.bulan)}",
        }

    # ---- WHAT: kesimpulan lebih dulu
    if status_akhir == "di bawah target" and rentet >= 2:
        d["what"].append(
            f"Sejak {label_bulan(mulai_rentet.tahun, mulai_rentet.bulan)} kita "
            f"{rentet} bulan berturut-turut di bawah batas. Bulan terakhir "
            f"({label_bulan(akhir.tahun, akhir.bulan)}) {sen(selisih_akhir)} "
            f"di bawah target.")
    elif status_akhir == "tipis":
        d["what"].append(
            f"Bulan terakhir ({label_bulan(akhir.tahun, akhir.bulan)}) hanya "
            f"{sen(selisih_akhir)} di atas target — praktis pas-pasan.")
    elif selisih_akhir >= 0:
        d["what"].append(
            f"Bulan terakhir ({label_bulan(akhir.tahun, akhir.bulan)}) "
            f"{sen(selisih_akhir)} di atas target. Dari {len(berstatus)} bulan, "
            f"{len(di_atas)} bulan mencapai target.")
    else:
        d["what"].append(
            f"Bulan terakhir ({label_bulan(akhir.tahun, akhir.bulan)}) "
            f"{sen(selisih_akhir)} di bawah target.")
    if di_bawah and di_atas:
        d["what"].append(
            f"Pola umumnya: {len(di_atas)} bulan aman, {len(di_bawah)} bulan "
            f"di bawah batas.")
    elif di_bawah and not di_atas:
        d["what"].append("Seluruh bulan dalam periode ini masih di bawah batas.")

    # ---- SO WHAT: penyebab (harga acuan vs harga beli), tanpa istilah teknis
    idx = semua.index(akhir)
    pembanding = semua[idx - 1] if idx > 0 else None
    if pembanding and pembanding.sicom_usc and akhir.sicom_usc:
        d_sicom = akhir.sicom_usc - pembanding.sicom_usc
        d_beli = (akhir.harga_beli_usc or 0) - (pembanding.harga_beli_usc or 0)
        if d_sicom < 0 and abs(d_beli) < abs(d_sicom):
            d["so_what"].append(
                f"Harga acuan dunia turun {sen(d_sicom)}, sedangkan harga yang "
                f"kita bayar ke pemasok hanya turun {sen(d_beli)}. Karena "
                f"selisih keduanya itulah untung per kilo, mengecilnya harga "
                f"beli tidak cukup menutup turunnya harga acuan.")
        elif d_sicom < 0 and d_beli > 0:
            d["so_what"].append(
                f"Harga acuan turun {sen(d_sicom)} tetapi harga beli kita justru "
                f"naik {sen(d_beli)} — dua-duanya menekan untung per kilo.")
        elif d_sicom > 0 and d_beli < 0:
            d["so_what"].append(
                f"Harga acuan naik {sen(d_sicom)} dan harga beli turun "
                f"{sen(d_beli)} — keduanya menolong margin.")
        else:
            d["so_what"].append(
                f"Dibanding {label_bulan(pembanding.tahun, pembanding.bulan)}, "
                f"harga acuan {arah(d_sicom)} {sen(d_sicom)} dan harga beli "
                f"{arah(d_beli)} {sen(d_beli)}.")
        if abs(d_sicom) > 0.005:
            rasio = d_beli / d_sicom
            if rasio < 0:
                d["so_what"].append(
                    "Harga beli justru bergerak berlawanan arah dengan harga "
                    "acuan, sehingga tekanan pasar tidak tertahan.")
            elif rasio > 1.02:
                d["so_what"].append(
                    f"Harga beli bergerak {rasio * 100:.0f}% dari gerakan harga "
                    f"acuan — lebih besar daripada pasarnya, jadi margin justru "
                    f"terpengaruh dua kali.")
            elif rasio >= 0.98:
                d["so_what"].append(
                    "Harga beli mengikuti hampir seluruh gerakan harga acuan, "
                    "jadi untung per kilo nyaris tidak berubah karena harga — "
                    "selisihnya lahir dari selisih target.")
            else:
                d["so_what"].append(
                    f"Harga beli hanya mengikuti sekitar {rasio * 100:.0f}% dari "
                    f"gerakan harga acuan, jadi sisanya langsung terasa di "
                    f"untung per kilo.")
    if akhir.target_usc is not None:
        d["sumber_target"] = (
            f"Target bulan ini {angka(akhir.target_usc, 1)} sen/kg berasal dari "
            f"tabel target margin (menu Perencanaan), bukan angka perkiraan.")

    # ---- NOW WHAT: tindakan, bukan sekadar temuan
    if selisih_akhir < 0:
        batas_beli = (akhir.sicom_usc - akhir.target_usc) \
            if (akhir.sicom_usc and akhir.target_usc is not None) else None
        d["now_what"] = [
            (f"Tahan harga beli di bawah {angka(batas_beli, 1)} sen/kg "
             f"(harga acuan {angka(akhir.sicom_usc, 1)} dikurangi target "
             f"{angka(akhir.target_usc, 1)}) agar kembali ke target.")
            if batas_beli is not None else
            "Tahan harga beli agar tidak melebihi harga acuan.",
            "Cari pemasok dengan harga lebih rendah untuk menutup selisihnya.",
            f"Tinjau ulang target {angka(akhir.target_usc, 1)} sen bila pasar "
            "memang sedang turun — target yang tidak realistis menyembunyikan "
            "masalah sebenarnya."
            if akhir.target_usc is not None else
            "Tinjau ulang target bila kondisi pasar memang sedang turun.",
        ]
    else:
        d["now_what"] = [
            "Pertahankan pola pembelian yang sekarang — harga beli bergerak "
            "searah kebutuhan.",
            "Kunci sebagian pembelian saat harga acuan sedang tinggi agar "
            "margin tidak tergerus bulan berikutnya.",
            "Perhatikan bulan yang hanya tipis di atas target: marginnya mudah "
            "berbalik bila harga acuan turun sedikit.",
        ]

    d["cara_baca"] = ("Satu batang = satu bulan. Makin tinggi batangnya, makin "
                      "besar untung per kilo. Tanda putih pada tiap batang "
                      "adalah batas aman (target) bulan itu, bukan garis rata.")
    d["detail"] = [{
        "judul": "Angka di balik narasi (6 bulan terakhir)",
        "kolom": ["Bulan", "Margin (sen/kg)", "Target", "Selisih", "Status"],
        "baris": [[label_bulan(b.tahun, b.bulan),
                   angka(b.op_margin_usc, 2), angka(b.target_usc, 1),
                   ("+" if (b.op_margin_usc - b.target_usc) >= 0 else "−")
                   + angka(abs(b.op_margin_usc - b.target_usc), 2),
                   _status_target(b.op_margin_usc, b.target_usc)]
                  for b in berstatus[-6:]],
    }]
    if pembanding and akhir.sicom_usc:
        d["detail"].append({
            "judul": f"Penyebab: {label_bulan(pembanding.tahun, pembanding.bulan)} "
                     f"→ {label_bulan(akhir.tahun, akhir.bulan)}",
            "kolom": ["Komponen", "Perubahan"],
            "baris": [["Harga acuan (SICOM)",
                       ("+" if (akhir.sicom_usc - pembanding.sicom_usc) >= 0 else "−")
                       + angka(abs(akhir.sicom_usc - pembanding.sicom_usc), 2) + " sen"],
                      ["Harga beli (OP Price)",
                       ("+" if (akhir.harga_beli_usc or 0) - (pembanding.harga_beli_usc or 0) >= 0 else "−")
                       + angka(abs((akhir.harga_beli_usc or 0)
                                   - (pembanding.harga_beli_usc or 0)), 2) + " sen"],
                      ["Untung per kilo (margin)",
                       ("+" if selisih_akhir >= 0 else "−")
                       + angka(abs((akhir.op_margin_usc or 0)
                                   - (pembanding.op_margin_usc or 0)), 2) + " sen"]],
        })
    # Perubahan target dalam periode: pertanyaan "kenapa target bulan itu X?"
    for i in range(1, len(berstatus)):
        kini, lalu = berstatus[i], berstatus[i - 1]
        if kini.target_usc != lalu.target_usc:
            d["catatan"].append(
                f"Target berubah pada {label_bulan(kini.tahun, kini.bulan)}: "
                f"{angka(lalu.target_usc, 1)} → {angka(kini.target_usc, 1)} sen/kg "
                f"(dari tabel target margin, bukan taksiran).")
    d["catatan"].append("Angka dibulatkan untuk dibicarakan; angka persis ada di "
                        "lapisan detail dan file ekspor Excel.")
    return d


# ---------------------------------------------------------------------------
# 2) Ringkasan OP Margin per tahun
# ---------------------------------------------------------------------------
def _jelaskan_ringkasan(session: Session, tahun=None, **_):
    d = _dasar("ringkasan")
    if tahun is None:
        akhir = session.scalars(select(MartBulanan).order_by(
            MartBulanan.tahun.desc(), MartBulanan.bulan.desc()).limit(1)).first()
        tahun = akhir.tahun if akhir else None
    baris, _ = _bulan_mart(session, None, None, tahun=tahun)
    if not baris:
        d["ada_data"] = False
        d["what"] = [f"Belum ada data bulanan untuk {tahun}."]
        return d

    margin = [b.op_margin_usc for b in baris if b.op_margin_usc is not None]
    rata = sum(margin) / len(margin) if margin else None
    target = [b.target_usc for b in baris if b.target_usc is not None]
    rata_target = sum(target) / len(target) if target else None
    terbaik = max(baris, key=lambda b: b.op_margin_usc or -1e9)
    terburuk = min(baris, key=lambda b: b.op_margin_usc or 1e9)

    d["angka_utama"] = {"nilai": sen(rata), "label": f"rata-rata untung per kilo {tahun}"}
    d["what"].append(
        f"Sepanjang {tahun} rata-rata untung per kilo {sen(rata)}"
        + (f", sedangkan target rata-rata {sen(rata_target)}." if rata_target else "."))
    d["what"].append(
        f"Bulan terbaik {label_bulan(terbaik.tahun, terbaik.bulan)} "
        f"({sen(terbaik.op_margin_usc)}), terburuk "
        f"{label_bulan(terburuk.tahun, terburuk.bulan)} "
        f"({sen(terburuk.op_margin_usc)}).")
    if rata is not None and rata_target:
        d["so_what"].append(
            "Rata-rata setahun " + ("di atas" if rata >= rata_target else "di bawah")
            + f" target, jadi " + ("usaha dalam kondisi sehat."
                                   if rata >= rata_target else
                                   "perlu perbaikan harga beli atau target."))
        d["now_what"] = [
            "Pakai bulan terburuk sebagai pelajaran: cek apa yang terjadi pada "
            "harga acuan bulan itu.",
            "Bandingkan dengan tahun lalu di grafik 'Banding antar tahun' untuk "
            "melihat apakah polanya berulang.",
            "Bila rata-rata di bawah target, tinjau target dan strategi beli.",
        ]
    d["cara_baca"] = ("Tabel ini membaca per bulan: baris SICOM (harga acuan), "
                      "OP Price (harga beli kita), dan OP Margin (untung per kilo).")
    d["detail"] = [{
        "judul": f"Angka {tahun} per bulan",
        "kolom": ["Bulan", "Margin", "Target", "Status"],
        "baris": [[label_bulan(b.tahun, b.bulan), angka(b.op_margin_usc, 2),
                   angka(b.target_usc, 1),
                   _status_target(b.op_margin_usc, b.target_usc)] for b in baris],
    }]
    return d


# ---------------------------------------------------------------------------
# 3) RM Stock – Intake vs Pricing
# ---------------------------------------------------------------------------
def _jelaskan_elemen(session: Session, dari=None, sampai=None, **_):
    d = _dasar("elemen_op_margin")
    baris, _ = _bulan_mart(session, dari, sampai)
    dengan_stok = [b for b in baris]
    stok = {}
    for h in session.scalars(select(MartHarian).where(
            MartHarian.stok_ton != None).order_by(MartHarian.tanggal)):  # noqa: E711
        stok[(h.tanggal.year, h.tanggal.month)] = h
    if not dengan_stok:
        d["ada_data"] = False
        d["what"] = ["Belum ada data bulanan pada periode ini."]
        return d
    # bulan terakhir yang PUNYA data stok (bulan berjalan sering belum ada)
    punya_stok = [b for b in dengan_stok if (b.tahun, b.bulan) in stok]
    akhir = punya_stok[-1] if punya_stok else dengan_stok[-1]
    kunci = (akhir.tahun, akhir.bulan)
    stok_akhir = stok.get(kunci)
    rasio = stok_akhir.rasio_stok if stok_akhir else None
    d["angka_utama"] = {
        "nilai": f"{rasio * 100:.0f}%" if rasio is not None else "–",
        "label": "stok dibanding batas aman (100% = pas di batas)",
    }
    if rasio is None:
        d["what"].append(
            f"Batas aman stok belum bisa dibandingkan pada "
            f"{label_bulan(*kunci)} karena parameternya belum berlaku di tanggal itu.")
    if rasio is not None:
        d["what"].append(
            f"Stok akhir {label_bulan(*kunci)} setara {rasio * 100:.0f}% dari "
            f"batas aman ({angka(stok_akhir.safety_ton)} ton) — "
            + ("aman." if rasio >= 1 else "di bawah batas aman."))
    d["what"].append(
        f"Pada bulan yang sama margin {angka(akhir.op_margin_usc, 1)} sen/kg "
        f"(target {angka(akhir.target_usc, 1)}).")
    # intake vs pemakaian implisit (stok bulan lalu + intake - stok akhir)
    idx = dengan_stok.index(akhir)
    sebelum = dengan_stok[idx - 1] if idx > 0 else None
    if sebelum and stok_akhir:
        st_sebelum = stok.get((sebelum.tahun, sebelum.bulan))
        masuk = (akhir.qty_ton or 0) * 1000
        if st_sebelum and masuk:
            pakai = st_sebelum.stok_ton + masuk / 1000 - stok_akhir.stok_ton
            d["so_what"].append(
                f"Bulan itu masuk {angka(masuk / 1000)} ton dan terpakai sekitar "
                f"{angka(pakai)} ton, sehingga stok "
                + ("menipis" if stok_akhir.stok_ton < st_sebelum.stok_ton
                   else "menebal") + ".")
    d["so_what"].append(
        "Batang menunjukkan jumlah karet (ton), garis menunjukkan harga: bila "
        "garis harga acuan turun sementara batang masuk tetap, untung per kilo "
        "menyempit walau pasokan lancar.")
    d["now_what"] = [
        "Jaga stok di atas batas aman; stok tipis membuat posisi beli lemah.",
        "Saat harga acuan turun, negosiasi harga beli harus turun lebih dulu.",
        "Buka tombol Margin Bridge di kartu ini untuk melihat penyebab "
        "perubahan margin bulan ke bulan.",
    ]
    d["cara_baca"] = ("Batang biru = karet yang masuk, batang tosca = stok "
                      "tersisa, garis kuning = batas aman stok; garis putih dan "
                      "merah muda = harga acuan dan harga beli kita.")
    d["detail"] = [{
        "judul": "Angka pendukung (6 bulan terakhir)",
        "kolom": ["Bulan", "Stok (ton)", "Intake (ton)", "Margin"],
        "baris": [[label_bulan(b.tahun, b.bulan),
                   angka(stok.get((b.tahun, b.bulan)).stok_ton, 0)
                   if stok.get((b.tahun, b.bulan)) else "–",
                   angka(b.qty_ton, 0), angka(b.op_margin_usc, 2)]
                  for b in dengan_stok[-6:]],
    }]
    return d


# ---------------------------------------------------------------------------
# 4) Margin Bridge
# ---------------------------------------------------------------------------
def _jelaskan_margin_bridge(session: Session, dari=None, sampai=None, **_):
    d = _dasar("margin_bridge")
    baris, semua = _bulan_mart(session, dari, sampai)
    if not baris:
        d["ada_data"] = False
        d["what"] = ["Belum ada data pada periode ini."]
        return d
    akhir = baris[-1]
    idx = semua.index(akhir)
    pembanding = semua[idx - 1] if idx > 0 else None
    if pembanding is None:
        d["ada_data"] = False
        d["what"] = ["Butuh minimal dua bulan berurutan untuk menjelaskan "
                     "perubahan."]
        return d
    d_margin = (akhir.op_margin_usc or 0) - (pembanding.op_margin_usc or 0)
    d_sicom = (akhir.sicom_usc or 0) - (pembanding.sicom_usc or 0)
    d_beli = (akhir.harga_beli_usc or 0) - (pembanding.harga_beli_usc or 0)
    d["angka_utama"] = {
        "nilai": sen(d_margin),
        "label": f"perubahan untung per kilo dibanding "
                 f"{label_bulan(pembanding.tahun, pembanding.bulan)}",
    }
    d["what"].append(
        f"Untung per kilo {'naik' if d_margin >= 0 else 'turun'} {sen(d_margin)} "
        f"pada {label_bulan(akhir.tahun, akhir.bulan)} dibanding bulan sebelumnya.")
    if d_sicom < 0:
        d["so_what"].append(
            f"Harga acuan turun {sen(d_sicom)} — ini di luar kendali kita dan "
            f"menekan untung.")
    else:
        d["so_what"].append(
            f"Harga acuan naik {sen(d_sicom)} — ini menolong untung.")
    if d_beli < 0:
        d["so_what"].append(
            f"Harga beli turun {sen(d_beli)} — ini yang bisa kita atur, dan "
            f"menolong untung.")
    elif d_beli > 0:
        d["so_what"].append(
            f"Harga beli naik {sen(d_beli)} — keputusan pembelian ini menekan "
            f"untung.")
    d["now_what"] = [
        "Bila harga acuan turun, pastikan harga beli turun lebih dulu.",
        "Bila harga acuan naik, kunci pembelian sebelum harga pemasok ikut naik.",
        "Periksa tabel di bawah: bulan dengan penurunan terbesar biasanya "
        "berasal dari gerakan pasar, bukan keputusan kita.",
    ]
    d["cara_baca"] = ("Batang pertama = untung bulan awal, batang tengah = "
                      "penyebabnya (harga acuan dan harga beli), batang terakhir "
                      "= untung bulan akhir. Turun berwarna merah, naik hijau.")
    d["detail"] = [{
        "judul": "Rincian perubahan",
        "kolom": ["Komponen", "Perubahan"],
        "baris": [["Harga acuan", ("+" if d_sicom >= 0 else "−") + angka(abs(d_sicom), 2)],
                  ["Harga beli", ("+" if d_beli >= 0 else "−") + angka(abs(d_beli), 2)],
                  ["Untung per kilo", ("+" if d_margin >= 0 else "−") + angka(abs(d_margin), 2)]],
    }]
    return d


# ---------------------------------------------------------------------------
# 5) Days of Cover & stok
# ---------------------------------------------------------------------------
def _jelaskan_days_of_cover(session: Session, dari=None, sampai=None, **_):
    d = _dasar("days_of_cover")
    stok: dict[tuple[int, int], MartHarian] = {}
    intake: dict[tuple[int, int], float] = defaultdict(float)
    for h in session.scalars(select(MartHarian).order_by(MartHarian.tanggal)):
        kunci = (h.tanggal.year, h.tanggal.month)
        if h.stok_ton is not None:
            stok[kunci] = h
        if h.qty_kering_kg:
            intake[kunci] += h.qty_kering_kg / 1000.0
    if not stok:
        d["ada_data"] = False
        d["what"] = ["Belum ada data stok harian."]
        return d
    kunci_akhir = sorted(stok)[-1] if (dari is None and sampai is None) \
        else max([k for k in sorted(stok)
                  if (dari is None or k >= dari) and (sampai is None or k <= sampai)],
                 default=sorted(stok)[-1])
    akhir = stok[kunci_akhir]
    sebelum_kunci = (kunci_akhir[0] - 1, 12) if kunci_akhir[1] == 1 \
        else (kunci_akhir[0], kunci_akhir[1] - 1)
    baris = []
    if sebelum_kunci in stok:
        awal = stok[sebelum_kunci].stok_ton
        masuk = intake.get(kunci_akhir, 0.0)
        pakai = awal + masuk - akhir.stok_ton
        hari = 30
        per_hari = pakai / hari if pakai > 0 else None
        doc = akhir.stok_ton / per_hari if per_hari else None
        prm = session.scalars(select(ParameterPabrik).where(
            ParameterPabrik.berlaku_dari <= dt.date(kunci_akhir[0], kunci_akhir[1], 1)
        ).order_by(ParameterPabrik.berlaku_dari.desc())).first()
        safety_hari = (prm.safety_stock_ton / per_hari
                       if prm and prm.safety_stock_ton and per_hari else None)
        if doc is not None:
            d["angka_utama"] = {"nilai": f"{doc:.0f} hari",
                                "label": "stok cukup untuk produksi"}
            d["what"].append(
                f"Stok akhir {label_bulan(*kunci_akhir)} cukup untuk sekitar "
                f"{doc:.0f} hari produksi"
                + (f", sedangkan batas aman sekitar {safety_hari:.0f} hari."
                   if safety_hari else "."))
            d["so_what"].append(
                f"Bulan itu masuk {angka(masuk)} ton dan terpakai sekitar "
                f"{angka(pakai)} ton. DoC dipakai karena mengikuti kecepatan "
                f"pemakaian, bukan sekadar jumlah ton di gudang.")
            if safety_hari and doc < safety_hari:
                d["now_what"] = [
                    "Percepat penerimaan karet: stok di bawah batas aman membuat "
                    "posisi tawar melemah.",
                    "Hitung ulang batas aman bila pemakaian memang sedang tinggi.",
                    "Prioritaskan pemasok yang bisa kirim cepat walau harga "
                    "sedikit lebih tinggi.",
                ]
            else:
                d["now_what"] = [
                    "Pertahankan jadwal penerimaan sekarang.",
                    "Waspadai lonjakan pemakaian: DoC bisa turun cepat walau "
                    "stok terlihat cukup.",
                    "Tinjau batas aman secara berkala mengikuti pemakaian.",
                ]
        baris = [["Stok akhir", f"{angka(akhir.stok_ton)} ton"],
                 ["Pemasukan bulan itu", f"{angka(masuk)} ton"],
                 ["Terpakai (perkiraan)", f"{angka(pakai)} ton"],
                 ["Pemakaian per hari", f"{angka(per_hari)} ton"
                  if per_hari else "–"]]
    d["cara_baca"] = ("Batang = sisa hari produksi tiap bulan; garis kuning = "
                      "batas aman dalam hari. Batang di bawah garis berarti "
                      "stok tidak cukup sampai pengiriman berikutnya.")
    d["detail"] = [{"judul": "Angka pendukung", "kolom": ["Komponen", "Nilai"],
                    "baris": baris}] if baris else []
    if not d["what"]:
        d["ada_data"] = False
        d["what"] = ["Stok bulan sebelumnya belum ada di data, sehingga "
                     "pemakaian belum bisa dihitung."]
    return d


# ---------------------------------------------------------------------------
# 6) Kartu lain: kerangka sama, memakai definisi di metrics.yaml
# ---------------------------------------------------------------------------
def _jelaskan_umum(session: Session, kartu: str, **_) -> dict:
    d = _dasar(kartu)
    rumus = d["rumus"]
    kalimat = rumus.split(". ")[0].strip() if rumus else ""
    d["what"] = [f"Kartu ini menjawab: {d['judul']}."]
    if kalimat:
        d["so_what"] = [kalimat if kalimat.endswith(".") else kalimat + "."]
    d["now_what"] = ["Buka detail perhitungan bila ada angka yang perlu "
                     "dipertanyakan; semua angka berasal dari data yang "
                     "diunggah ke sistem."]
    d["cara_baca"] = ("Grafik dan tabel pada kartu ini memakai satuan yang "
                      "tertulis pada sumbu; angka kecil adalah pembanding, "
                      "angka besar adalah kesimpulan.")
    return d


_PENJELAS = {
    "margin_bulanan": _jelaskan_margin_bulanan,
    "ringkasan": _jelaskan_ringkasan,
    "elemen_op_margin": _jelaskan_elemen,
    "margin_bridge": _jelaskan_margin_bridge,
    "days_of_cover": _jelaskan_days_of_cover,
    "stok": _jelaskan_days_of_cover,
}


def pasang_router(app, ambil_session):
    router = APIRouter(prefix="/api")
    dep = Depends(ambil_session)

    @router.get("/jelaskan/{kartu}")
    def jelaskan(kartu: str, dari: str | None = None, sampai: str | None = None,
                 tahun: int | None = None, session: Session = dep):
        """Narasi 'Jelaskan ke saya': jawaban dulu, bukti kemudian.

        Struktur balasan: angka_utama (satu angka), what (kesimpulan),
        so_what (penyebab), now_what (tindakan), analogi, cara_baca, dan
        detail (lapisan kedua, hanya dibuka bila ditanyakan).
        """
        kd = _bulan_ym(dari, "dari")
        ks = _bulan_ym(sampai, "sampai")
        if kd and ks and kd > ks:
            raise HTTPException(422, "Periode 'dari' harus sebelum atau sama "
                                     "dengan 'sampai'.")
        kartu_bersih = (kartu or "").strip().lower()
        if not kartu_bersih:
            raise HTTPException(422, "Nama kartu wajib diisi.")
        fungsi = _PENJELAS.get(kartu_bersih)
        if fungsi is not None:
            hasil = fungsi(session, dari=kd, sampai=ks, tahun=tahun)
        else:
            if kartu_bersih not in _metrics().get("kartu", {}):
                raise HTTPException(404, f"Kartu '{kartu}' tidak dikenal.")
            hasil = _jelaskan_umum(session, kartu_bersih, dari=kd, sampai=ks,
                                   tahun=tahun)
        hasil["kartu"] = kartu_bersih
        return hasil

    app.include_router(router)
    return router
