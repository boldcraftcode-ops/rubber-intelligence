"""Analisa otomatis 5W1H untuk grafik RM Stock - Intake vs Pricing.

Prinsip:
- Semua angka dihitung dari data periode yang difilter (bukan teks tetap).
- FAKTA dipisahkan dari HIPOTESIS (hipotesis selalu ditandai).
- Keterbatasan data disebut jujur (mis. Where/Who butuh data tiket).
- Asosiasi bukan bukti sebab-akibat.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MartBulanan, TiketBaris, Vendor

NAMA_BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
              "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def _f(n, d=0) -> str:
    """Format angka gaya Indonesia."""
    if n is None:
        return "-"
    teks = f"{n:,.{d}f}"
    return teks.replace(",", "_").replace(".", ",").replace("_", ".")


def _rata(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def analisa_5w1h(baris: list[dict], session: Session) -> dict:
    """baris = keluaran ringkasan-elemen (sudah terfilter periode)."""
    hasil = {"what": [], "when": [], "where": [], "who": [], "why": [], "how": []}

    b_stok = [b for b in baris if b["rm_stock_ton"] is not None and b["safety_ton"]]
    b_margin = [b for b in baris if b["op_margin"] is not None]
    b_intake = [b for b in baris if b["intake_ton"] is not None]
    if len(b_margin) < 2 and len(b_stok) < 2:
        return {**hasil, "ringkas": "Data pada periode ini terlalu sedikit untuk "
                "dianalisa (butuh minimal 2 bulan berdata).",
                "catatan": []}

    periode = f"{baris[0]['label']} s.d. {baris[-1]['label']}"

    # ================= WHAT =================
    if b_stok:
        safety = b_stok[-1]["safety_ton"]
        bawah = [b for b in b_stok if b["rm_stock_ton"] < b["safety_ton"]]
        atas = [b["label"] for b in b_stok if b["rm_stock_ton"] >= b["safety_ton"]]
        terendah = min(b_stok, key=lambda b: b["rm_stock_ton"])
        akhir = b_stok[-1]
        if len(bawah) > len(b_stok) / 2:
            kalimat = (f"Stok kronis di bawah safety. RM Stock hanya di atas safety "
                       f"({_f(safety, 0)} ton) pada {', '.join(atas) if atas else 'tidak ada bulan'}; "
                       f"{len(bawah)} dari {len(b_stok)} bulan di bawahnya.")
        else:
            kalimat = (f"Stok relatif terjaga: {len(bawah)} dari {len(b_stok)} bulan "
                       f"di bawah safety ({_f(safety, 0)} ton).")
        hasil["what"].append(
            kalimat + f" Titik terendah di {terendah['label']} "
            f"({_f(terendah['rm_stock_ton'], 0)} ton, sekitar "
            f"{_f(terendah['rm_stock_ton'] / terendah['safety_ton'] * 100, 0)}% dari safety); "
            f"posisi akhir {akhir['label']} {_f(akhir['rm_stock_ton'], 0)} ton "
            f"(sekitar {_f(akhir['rm_stock_ton'] / akhir['safety_ton'] * 100, 0)}%).")
    if len(b_margin) >= 2:
        puncak = max(b_margin, key=lambda b: b["op_margin"])
        akhir_m = b_margin[-1]
        n = len(b_margin)
        awal_avg = _rata([b["op_margin"] for b in b_margin[:max(1, n // 4)]])
        akhir_avg = _rata([b["op_margin"] for b in b_margin[-max(1, n // 4):]])
        arah = "terkikis" if akhir_avg < awal_avg else "membaik"
        hasil["what"].append(
            f"Margin {arah}. Puncak OP Margin {_f(puncak['op_margin'], 2)} "
            f"({puncak['label']}); posisi akhir {_f(akhir_m['op_margin'], 2)} "
            f"({akhir_m['label']}). Rata-rata awal periode sekitar {_f(awal_avg, 1)} "
            f"vs akhir periode sekitar {_f(akhir_avg, 1)} US¢/kg.")
    if len(b_intake) >= 2:
        total = sum(b["intake_ton"] for b in b_intake)
        h1 = _rata([b["intake_ton"] for b in b_intake[:len(b_intake) // 2]])
        h2 = _rata([b["intake_ton"] for b in b_intake[len(b_intake) // 2:]])
        tren = "melemah" if h2 < h1 else "menguat"
        hasil["what"].append(
            f"Intake {tren}. Total intake periode ini sekitar {_f(total, 0)} ton; "
            f"rata-rata paruh pertama {_f(h1, 0)} ton/bulan vs paruh kedua "
            f"{_f(h2, 0)} ton/bulan.")

    # ================= WHEN =================
    sicoms = [b for b in baris if b["sicom"] is not None]
    if len(sicoms) >= 2:
        delta = [(sicoms[i], sicoms[i]["sicom"] - sicoms[i - 1]["sicom"])
                 for i in range(1, len(sicoms))]
        jatuh = min(delta, key=lambda x: x[1])
        if jatuh[1] < 0:
            b = jatuh[0]
            hasil["when"].append(
                f"{b['label']}: SICOM turun {_f(abs(jatuh[1]), 1)} poin ke "
                f"{_f(b['sicom'], 0)}"
                + (f", intake {_f(b['intake_ton'], 0)} ton" if b["intake_ton"] else "")
                + (f", stok {_f(b['rm_stock_ton'], 0)} ton" if b["rm_stock_ton"] else "") + ".")
    if b_intake:
        i_min = min(b_intake, key=lambda b: b["intake_ton"])
        i_max = max(b_intake, key=lambda b: b["intake_ton"])
        hasil["when"].append(
            f"Intake tertinggi {i_max['label']} ({_f(i_max['intake_ton'], 0)} ton); "
            f"terendah {i_min['label']} ({_f(i_min['intake_ton'], 0)} ton).")
    if b_stok:
        terendah = min(b_stok, key=lambda b: b["rm_stock_ton"])
        hasil["when"].append(
            f"Stok terendah di {terendah['label']} ({_f(terendah['rm_stock_ton'], 0)} ton).")
    # deret margin turun beruntun di ujung periode
    runtun = [b_margin[-1]] if b_margin else []
    for b in reversed(b_margin[:-1]):
        if b["op_margin"] > runtun[0]["op_margin"]:
            runtun.insert(0, b)
        else:
            break
    if len(runtun) >= 3:
        hasil["when"].append(
            f"{runtun[0]['label']}-{runtun[-1]['label']}: margin turun beruntun, "
            + " → ".join(_f(b["op_margin"], 2) for b in runtun) + ".")

    # ================= WHERE & WHO (butuh data tiket) =================
    awal = dt.date(baris[0]["tahun"], baris[0]["bulan"], 1)
    th_a, bl_a = baris[-1]["tahun"], baris[-1]["bulan"]
    akhir_tgl = (dt.date(th_a + (bl_a == 12), (bl_a % 12) + 1, 1) - dt.timedelta(days=1))
    tiket = list(session.scalars(select(TiketBaris).where(
        TiketBaris.ticket_date >= awal, TiketBaris.ticket_date <= akhir_tgl,
        TiketBaris.tiket_nol == False)))  # noqa: E712
    sumber = {b["sumber_intake"] for b in b_intake if b["sumber_intake"]}

    if tiket:
        per_prov: dict[str, float] = defaultdict(float)
        per_vendor: dict[str, float] = defaultdict(float)
        for t in tiket:
            if t.dry_kg:
                per_prov[t.provinsi or "(kosong)"] += float(t.dry_kg) / 1000
                per_vendor[t.kode_vendor] += float(t.dry_kg) / 1000
        total_t = sum(per_prov.values())
        top_prov = sorted(per_prov.items(), key=lambda x: -x[1])[:3]
        hasil["where"].append(
            "Berdasarkan data tiket pada periode ini, wilayah penyumbang terbesar: "
            + "; ".join(f"{p} {_f(v, 0)} ton ({_f(v / total_t * 100, 0)}%)"
                        for p, v in top_prov) + ".")
        if not sumber <= {"tiket"}:
            hasil["where"].append(
                "Catatan: sebagian bulan masih memakai angka pembelian/referensi, "
                "jadi rincian wilayah belum mencakup seluruh periode.")
        nama = {v.kode: v.nama_baku for v in session.scalars(select(Vendor))}
        top_v = sorted(per_vendor.items(), key=lambda x: -x[1])[:3]
        hasil["who"].append(
            "Pemasok terbesar periode ini (dari tiket): "
            + "; ".join(f"{k} ({nama.get(k, '?')}) {_f(v, 0)} ton"
                        for k, v in top_v)
            + ". Pihak terkait lain: tim intake dan tim pricing (penetap OP Price).")
    else:
        hasil["where"].append(
            "Seluruh bulan pada periode ini bersumber dari angka \"pembelian\" "
            "(total per hari), sehingga belum terlihat wilayah mana yang menyumbang "
            "atau melemah. Ini keterbatasan terbesar analisa ini — unggah ekspor "
            "\"Master Data\" tiket di tab Unggah Data untuk membukanya.")
        hasil["who"].append(
            "Pihak terkait: pemasok (penjual bahan baku), tim intake, dan tim "
            "pricing yang menetapkan OP Price. Untuk menunjuk pemasok tertentu "
            "dibutuhkan data intake per vendor (dari tiket).")

    # ================= WHY =================
    if b_stok and len(b_margin) >= 2:
        terendah = min(b_stok, key=lambda b: b["rm_stock_ton"])
        jendela = [b for b in b_margin
                   if (b["tahun"], b["bulan"]) >= (terendah["tahun"], terendah["bulan"])]
        if len(jendela) >= 2:
            a, z = jendela[0], jendela[-1]
            ds = z["sicom"] - a["sicom"]
            dp = z["op_price"] - a["op_price"]
            kal = (f"Fakta dari data: {a['label']} → {z['label']}, SICOM berubah "
                   f"{_f(ds, 1)} poin ({_f(a['sicom'], 2)} → {_f(z['sicom'], 2)}) "
                   f"sedangkan OP Price berubah {_f(dp, 1)} poin "
                   f"({_f(a['op_price'], 2)} → {_f(z['op_price'], 2)}).")
            if dp > ds:
                kal += (" Harga beli naik lebih cepat daripada harga acuan — itulah "
                        "penekan langsung margin.")
                ia = next((b["intake_ton"] for b in jendela if b["intake_ton"]), None)
                iz = next((b["intake_ton"] for b in reversed(jendela) if b["intake_ton"]), None)
                if ia and iz:
                    kal += (f" Intake pada jendela yang sama berubah sekitar "
                            f"{_f((iz - ia) / ia * 100, 0)}% "
                            f"({_f(ia, 0)} → {_f(iz, 0)} ton).")
                hasil["why"].append(kal)
                hasil["why"].append(
                    "HIPOTESIS 1 — harga beli dinaikkan untuk menarik volume; "
                    "margin dikorbankan tetapi stok belum tentu pulih. Perlu "
                    "konfirmasi tim pricing.")
            else:
                hasil["why"].append(kal)
    # hipotesis musiman: bandingkan bulan intake terendah dengan tahun-tahun lain
    if b_intake:
        i_min = min(b_intake, key=lambda b: b["intake_ton"])
        lain = [m.qty_ton for m in session.scalars(select(MartBulanan).where(
            MartBulanan.bulan == i_min["bulan"], MartBulanan.tahun != i_min["tahun"]))]
        semua = [m.qty_ton for m in session.scalars(select(MartBulanan).where(
            MartBulanan.tahun != i_min["tahun"]))]
        if lain and semua:
            r_lain, r_semua = _rata(lain), _rata(semua)
            dukungan = ("pola serupa terlihat di tahun-tahun lain (mendukung)"
                        if r_lain < r_semua else
                        "TIDAK terlihat di tahun-tahun lain (lemah)")
            hasil["why"].append(
                f"HIPOTESIS 2 — faktor musiman: intake terendah jatuh di bulan "
                f"{NAMA_BULAN[i_min['bulan']]}. Rata-rata historis bulan "
                f"{NAMA_BULAN[i_min['bulan']]} di tahun lain {_f(r_lain, 0)} ton vs "
                f"rata-rata semua bulan {_f(r_semua, 0)} ton — {dukungan}.")
        # harga bukan satu-satunya penyebab
        i_max = max(b_intake, key=lambda b: b["intake_ton"])
        median_p = sorted(b["op_price"] for b in b_margin)[len(b_margin) // 2] \
            if b_margin else None
        if median_p and i_max.get("op_price") and i_max["op_price"] < median_p:
            hasil["why"].append(
                f"Harga bukan satu-satunya penyebab: intake tertinggi "
                f"({i_max['label']}, {_f(i_max['intake_ton'], 0)} ton) justru terjadi "
                f"saat OP Price relatif rendah ({_f(i_max['op_price'], 1)} vs median "
                f"{_f(median_p, 1)}). Ada faktor lain (kampanye pembelian, stok "
                f"pemasok) — asosiasi, bukan bukti sebab-akibat.")
    # konsumsi implisit
    if len(b_stok) >= 3:
        pakai = []
        for i in range(1, len(b_stok)):
            if b_stok[i]["intake_ton"] is not None:
                pakai.append(b_stok[i]["intake_ton"] -
                             (b_stok[i]["rm_stock_ton"] - b_stok[i - 1]["rm_stock_ton"]))
        if pakai:
            p_avg = _rata(pakai)
            i_avg = _rata([b["intake_ton"] for b in b_stok if b["intake_ton"]])
            akhir = b_stok[-1]
            gap = akhir["safety_ton"] - akhir["rm_stock_ton"]
            kal = (f"Konsumsi implisit (perubahan stok = intake − pemakaian): "
                   f"pemakaian sekitar {_f(p_avg, 0)} ton/bulan vs rata-rata intake "
                   f"{_f(i_avg, 0)} ton/bulan.")
            if gap > 0:
                kal += (f" Jarak ke safety ({_f(gap, 0)} ton) hanya tertutup bila "
                        f"intake melebihi pemakaian sebesar itu secara kumulatif.")
            hasil["why"].append(kal)

    # ================= HOW =================
    if b_margin and b_stok:
        akhir_m, akhir_s = b_margin[-1], b_stok[-1]
        rasio = akhir_s["rm_stock_ton"] / akhir_s["safety_ton"] * 100
        hasil["how"].append(
            f"Tentukan trade-off secara eksplisit: margin {_f(akhir_m['op_margin'], 2)} "
            f"dengan stok {_f(rasio, 0)}% dari safety adalah posisi yang perlu "
            f"keputusan — prioritaskan margin atau volume, atau cari sumber yang "
            f"lebih murah.")
    hasil["how"].append(
        "Beri batas pada kenaikan OP Price: gunakan tab Aturan Harga (aturan "
        "stok→harga berversi) agar kenaikan hanya terjadi bila SICOM ikut "
        "bergerak; isi aturan resmi bila masih CONTOH.")
    if b_stok and len([b for b in b_stok if b["rm_stock_ton"] < b["safety_ton"]]) \
            > len(b_stok) / 2:
        hasil["how"].append(
            f"Tinjau ulang level safety stock: stok di bawah "
            f"{_f(b_stok[-1]['safety_ton'], 0)} ton selama "
            f"{len([b for b in b_stok if b['rm_stock_ton'] < b['safety_ton']])} bulan — "
            f"apakah angka itu realistis, atau perlu rencana pemulihan bertahap "
            f"(ubah lewat Parameter Pabrik, berversi tanggal).")
    if not tiket:
        hasil["how"].append(
            "Pecah data intake per wilayah/vendor/tipe pemasok untuk menjawab "
            "Where dan Who: unggah ekspor \"Master Data\" tiket di tab Unggah Data; "
            "kartu Penerimaan di tab Analisis akan langsung terisi.")

    return {
        "periode": periode,
        "ringkas": None,
        **hasil,
        "catatan": [
            "Analisa ini dihasilkan otomatis dari data pada periode terfilter. "
            "Butir berlabel HIPOTESIS perlu konfirmasi; hubungan yang disebut "
            "adalah asosiasi, bukan bukti sebab-akibat.",
        ],
    }


# ============================================================================
# Analisa 5W1H untuk SELURUH data halaman Analisis (penerimaan, konsentrasi
# vendor, bauran grade/EUDR, reject%, margin). Periode opsional (tahun,bulan).
# ============================================================================
def analisa_analitik(session: Session, dari: tuple[int, int] | None = None,
                     sampai: tuple[int, int] | None = None) -> dict:
    from ..models import HargaGrade, Pembelian

    hasil = {"what": [], "when": [], "where": [], "who": [], "why": [], "how": []}

    # ---- rentang tanggal tiket
    t_awal = dt.date(dari[0], dari[1], 1) if dari else dt.date(2000, 1, 1)
    if sampai:
        t_akhir = (dt.date(sampai[0] + (sampai[1] == 12), (sampai[1] % 12) + 1, 1)
                   - dt.timedelta(days=1))
    else:
        t_akhir = dt.date(2100, 1, 1)

    tiket = list(session.scalars(select(TiketBaris).where(
        TiketBaris.ticket_date >= t_awal, TiketBaris.ticket_date <= t_akhir,
        TiketBaris.tiket_nol == False)))  # noqa: E712
    bulanan = [m for m in session.scalars(select(MartBulanan).order_by(
        MartBulanan.tahun, MartBulanan.bulan))
        if (not dari or (m.tahun, m.bulan) >= dari)
        and (not sampai or (m.tahun, m.bulan) <= sampai)]

    label_periode = "semua data"
    if dari or sampai:
        a = f"{NAMA_BULAN[dari[1]]}-{str(dari[0])[2:]}" if dari else "awal"
        z = f"{NAMA_BULAN[sampai[1]]}-{str(sampai[0])[2:]}" if sampai else "sekarang"
        label_periode = f"{a} s.d. {z}"

    # ================= WHAT =================
    from ..models import Grade as _G
    kode_eudr = {g.item_code for g in session.scalars(select(_G).where(_G.eudr == True))}  # noqa: E712

    if tiket:
        total_kg = sum(float(t.dry_kg or 0) for t in tiket)
        eudr_kg = sum(float(t.dry_kg or 0) for t in tiket
                      if (t.item_code in kode_eudr) or ("TTSR" in (t.item_code or "").upper()))
        vendor_set = {t.kode_vendor for t in tiket}
        tiket_set = {t.ticket_no for t in tiket}
        hasil["what"].append(
            f"Penerimaan (tiket): {_f(total_kg, 0)} kg kering dari "
            f"{len(tiket_set)} tiket / {len(vendor_set)} vendor. Porsi EUDR "
            f"{_f(eudr_kg, 0)} kg ({_f(eudr_kg / total_kg * 100, 1)}%).")
        per_grade: dict[str, float] = defaultdict(float)
        for t in tiket:
            per_grade[t.item_code or "(kosong)"] += float(t.dry_kg or 0)
        top_g = sorted(per_grade.items(), key=lambda x: -x[1])[:3]
        hasil["what"].append(
            "Bauran grade teratas: " + "; ".join(
                f"{g} {_f(v / total_kg * 100, 1)}%" for g, v in top_g) + ".")
        wet = sum(float(t.wet_kg or 0) for t in tiket)
        reject = sum(float(t.reject_kg or 0) for t in tiket)
        if wet:
            hasil["what"].append(
                f"Reject {_f(reject / wet * 100, 2)}% dari Wet "
                f"({_f(reject, 0)} kg dari {_f(wet, 0)} kg).")
    else:
        hasil["what"].append(
            f"Tidak ada data tiket pada periode ini ({label_periode}) — kartu "
            "penerimaan/bauran grade/reject kosong. Angka di bawah memakai "
            "data pembelian & margin bulanan.")
    if bulanan:
        margins = [m.op_margin_usc for m in bulanan if m.op_margin_usc is not None]
        if margins:
            terbaik = max(bulanan, key=lambda m: m.op_margin_usc or -999)
            terburuk = min(bulanan, key=lambda m: m.op_margin_usc or 999)
            hasil["what"].append(
                f"Margin bulanan periode ini: rata-rata {_f(_rata(margins), 2)} US¢/kg; "
                f"terbaik {NAMA_BULAN[terbaik.bulan]}-{str(terbaik.tahun)[2:]} "
                f"({_f(terbaik.op_margin_usc, 2)}), terburuk "
                f"{NAMA_BULAN[terburuk.bulan]}-{str(terburuk.tahun)[2:]} "
                f"({_f(terburuk.op_margin_usc, 2)}).")

    # ================= WHEN =================
    if tiket:
        per_bulan_t: dict[tuple[int, int], float] = defaultdict(float)
        for t in tiket:
            per_bulan_t[(t.ticket_date.year, t.ticket_date.month)] += float(t.dry_kg or 0)
        if len(per_bulan_t) >= 2:
            mx = max(per_bulan_t, key=per_bulan_t.get)
            mn = min(per_bulan_t, key=per_bulan_t.get)
            hasil["when"].append(
                f"Penerimaan tiket tertinggi {NAMA_BULAN[mx[1]]}-{str(mx[0])[2:]} "
                f"({_f(per_bulan_t[mx] / 1000, 0)} ton); terendah "
                f"{NAMA_BULAN[mn[1]]}-{str(mn[0])[2:]} ({_f(per_bulan_t[mn] / 1000, 0)} ton).")
        else:
            k = next(iter(per_bulan_t))
            hasil["when"].append(
                f"Data tiket baru mencakup {NAMA_BULAN[k[1]]}-{str(k[0])[2:]} — belum "
                "cukup untuk melihat pola waktu penerimaan.")
    if len(bulanan) >= 3:
        turun = [m for m in bulanan[-3:] if m.selisih_vs_target is not None
                 and m.selisih_vs_target < 0]
        if len(turun) >= 2:
            hasil["when"].append(
                f"{len(turun)} dari 3 bulan terakhir periode berada di bawah target "
                "margin — perhatikan tren akhir.")

    # ================= WHERE =================
    if tiket:
        per_prov: dict[str, float] = defaultdict(float)
        per_kab: dict[str, float] = defaultdict(float)
        for t in tiket:
            per_prov[t.provinsi or "(kosong)"] += float(t.dry_kg or 0)
            per_kab[f"{t.kabupaten or '(kosong)'} ({t.provinsi or '-'})"] += float(t.dry_kg or 0)
        tot = sum(per_prov.values())
        top_p = sorted(per_prov.items(), key=lambda x: -x[1])[:3]
        top_k = sorted(per_kab.items(), key=lambda x: -x[1])[:3]
        hasil["where"].append(
            "Provinsi penyumbang terbesar: " + "; ".join(
                f"{p} {_f(v / tot * 100, 0)}%" for p, v in top_p) + ".")
        hasil["where"].append(
            "Kabupaten teratas: " + "; ".join(
                f"{k} {_f(v / 1000, 1)} ton" for k, v in top_k)
            + ". Drill-down sampai desa tersedia di kartu Penerimaan/Tonase.")
    else:
        hasil["where"].append(
            "Belum bisa dijawab: tidak ada data tiket pada periode ini. Unggah "
            "ekspor \"Master Data\" di tab Unggah Data.")

    # ================= WHO =================
    if tiket:
        per_vendor: dict[str, float] = defaultdict(float)
        for t in tiket:
            per_vendor[t.kode_vendor] += float(t.dry_kg or 0)
        tot = sum(per_vendor.values())
        urut = sorted(per_vendor.items(), key=lambda x: -x[1])
        nama = {v.kode: v.nama_baku for v in session.scalars(select(Vendor))}
        top5 = urut[:5]
        porsi5 = sum(v for _, v in top5) / tot * 100 if tot else 0
        hasil["who"].append(
            f"Konsentrasi vendor: top {min(5, len(urut))} menguasai "
            f"{_f(porsi5, 0)}% tonase. Teratas: " + "; ".join(
                f"{k} ({nama.get(k, '?')}) {_f(v / tot * 100, 0)}%" for k, v in top5[:3]) + ".")
        pemasok_eudr = sorted(
            {t.kode_vendor for t in tiket
             if (t.item_code in kode_eudr) or ("TTSR" in (t.item_code or "").upper())})
        hasil["who"].append(
            ("Pemasok karet EUDR: " + ", ".join(
                f"{k} ({nama.get(k, '?')})" for k in pemasok_eudr) + ".")
            if pemasok_eudr else "Belum ada pemasok karet EUDR pada periode ini.")
    else:
        hasil["who"].append(
            "Belum bisa dijawab per pemasok: butuh data tiket. Pihak terkait "
            "umum: pemasok, tim intake, tim pricing.")

    # ================= WHY =================
    if tiket:
        per_vendor = defaultdict(float)
        for t in tiket:
            per_vendor[t.kode_vendor] += float(t.dry_kg or 0)
        tot = sum(per_vendor.values())
        urut = sorted(per_vendor.values(), reverse=True)
        porsi5 = sum(urut[:5]) / tot * 100 if tot else 0
        if porsi5 > 60:
            hasil["why"].append(
                f"Fakta: {_f(porsi5, 0)}% pasokan bergantung pada ≤5 vendor. "
                "HIPOTESIS — ketergantungan tinggi membuat posisi tawar harga "
                "lemah dan pasokan rentan; perlu dicek apakah vendor-vendor itu "
                "juga yang menentukan harga tertinggi.")
        wet = sum(float(t.wet_kg or 0) for t in tiket)
        reject = sum(float(t.reject_kg or 0) for t in tiket)
        if wet and reject:
            hasil["why"].append(
                f"Fakta: Reject {_f(reject / wet * 100, 2)}% dari Wet dan BELUM "
                "dikurangkan dari Dry [TERBUKA]. Bila Amount dibayar atas berat "
                "bersih, harga/kg terlihat terlalu rendah dan margin terlalu "
                "tinggi sekitar 2-3 US¢/kg.")
    ada_harga_grade = session.scalar(select(HargaGrade)) is not None
    ada_rinci = session.scalar(select(Pembelian).where(
        Pembelian.item_code != "ALL")) is not None
    if not ada_rinci:
        kal = ("Fakta: Amount pembelian tersedia total per hari (hasil kalkulasi "
               "pembayaran intake), sehingga margin per grade/vendor resmi belum "
               "bisa dihitung — kartu menampilkan \"data harga belum tersedia\".")
        if ada_harga_grade:
            kal += (" Daftar harga grade yang Anda isi memberi margin INDIKATIF "
                    "di tab Grade & Harga.")
        hasil["why"].append(kal)

    # ================= HOW =================
    if not tiket:
        hasil["how"].append(
            "Unggah ekspor \"Master Data\" tiket (tab Unggah Data) — seluruh kartu "
            "halaman ini (penerimaan, tonase, konsentrasi, reject) langsung terisi.")
    else:
        hasil["how"].append(
            "Perluas cakupan tiket historis agar pola waktu/wilayah/vendor makin "
            "tepercaya; pantau konsentrasi top 5 vendor secara berkala.")
    hasil["how"].append(
        "Putuskan perlakuan Reject [TERBUKA]: bila Amount dibayar atas berat "
        "bersih, Quantity perlu disesuaikan agar margin tidak tampak terlalu tinggi.")
    hasil["how"].append(
        "Untuk margin per grade resmi, tetapkan apakah daftar harga grade boleh "
        "dipakai mengalokasikan Amount harian [TERBUKA #4]; sementara itu gunakan "
        "margin indikatif di tab Grade & Harga.")

    return {
        "periode": label_periode,
        "ringkas": None,
        **hasil,
        "catatan": [
            "Analisa otomatis dari seluruh data halaman Analisis pada periode "
            "terpilih. Butir HIPOTESIS perlu konfirmasi; hubungan yang disebut "
            "adalah asosiasi, bukan bukti sebab-akibat.",
        ],
    }
