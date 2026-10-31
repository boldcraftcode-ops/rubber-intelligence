"""Analisa RCA 5-Why untuk kartu RM Stock – Intake vs Pricing.

Hanya memakai angka/teks yang dikirim dari tabel ringkasan. Hubungan antar
indikator ditulis sebagai fakta ko-terukur; penyebab yang tidak ada di data
selalu menjadi hipotesis dengan tingkat keyakinan dan data pembanding.
"""
from __future__ import annotations

from statistics import median


BULAN = ("", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu",
         "Sep", "Okt", "Nov", "Des")


def _n(nilai) -> float | None:
    if nilai is None:
        return None
    try:
        return float(nilai)
    except (TypeError, ValueError):
        return None


def _fmt(nilai: float | None, digit: int = 2) -> str:
    if nilai is None:
        return "tidak tersedia"
    teks = f"{nilai:,.{digit}f}"
    return teks.replace(",", "_").replace(".", ",").replace("_", ".")


def _tanda(nilai: float | None, digit: int = 2) -> str:
    if nilai is None:
        return "tidak tersedia"
    return ("+" if nilai > 0 else "") + _fmt(nilai, digit)


def _key(baris: dict) -> tuple[int, int]:
    return int(baris.get("tahun") or 0), int(baris.get("bulan") or 0)


def _bulan(teks: str | None, key: tuple[int, int]) -> str:
    if teks:
        return str(teks)
    th, bl = key
    return f"{BULAN[bl] if 1 <= bl <= 12 else bl}-{str(th)[-2:]}"


def _berturutan(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return b[0] * 12 + b[1] - (a[0] * 12 + a[1]) == 1


def _perubahan(baru: float | None, lama: float | None) -> dict:
    if baru is None or lama is None:
        return {"delta": None, "persen": None}
    return {"delta": round(baru - lama, 4),
            "persen": round((baru - lama) / lama * 100, 2) if lama else None}


def _referensi(sumber: str | None) -> bool:
    return "referensi" in (sumber or "").casefold()


def analisa_rca(bentuk: list[dict]) -> dict:
    """Hitung perubahan bulanan dan susun RCA dalam format 6 bagian.

    Estimasi nilai margin = Intake (ton) × 1.000 (kg/ton) × Margin (US¢/kg)
    ÷ 100 (US¢/US$), yaitu Intake × Margin × 10 US$. Ini nilai indikatif
    sebelum biaya olah/logistik, bukan laba bersih.
    """
    baris = sorted(bentuk, key=_key)
    if not baris:
        return {
            "ada_data": False,
            "kesimpulan": "Tidak ada baris data pada periode ini.",
            "temuan_data": [], "anomali": [], "root_cause": [],
            "rekomendasi": [],
            "keterbatasan": ["Tidak tersedia data RM Stock – Intake vs Pricing."],
            "per_bulan": [],
        }

    per_bulan: list[dict] = []
    prev = None
    for b in baris:
        key = _key(b)
        label = _bulan(b.get("label"), key)
        intake = _n(b.get("intake_ton"))
        stock = _n(b.get("rm_stock_ton"))
        safety = _n(b.get("safety_ton"))
        sicom = _n(b.get("sicom"))
        price = _n(b.get("op_price"))
        margin = (round(sicom - price, 4) if sicom is not None and price is not None
                  else _n(b.get("op_margin")))
        src = b.get("sumber_intake")
        kontigu = bool(prev and _berturutan(prev["key"], key))
        row = {
            "tahun": key[0], "bulan": key[1], "label": label,
            "rm_stock_ton": stock, "intake_ton": intake,
            "safety_ton": safety, "sicom": sicom, "op_price": price,
            "op_margin": margin, "sumber_intake": src,
            "stok_sebagian": bool(b.get("stok_sebagian")),
            "tanggal_stok": b.get("tanggal_stok"),
            "keandalan_intake": ("lebih rendah: referensi" if _referensi(src)
                                  else "normal" if src else "tidak diketahui"),
            "estimasi_total_margin_usd": round(intake * margin * 10, 2)
            if intake is not None and margin is not None else None,
            "days_of_cover": round(stock / (intake / 30), 2)
            if stock is not None and intake is not None and intake > 0 else None,
            "selisih_stok_safety_ton": round(stock - safety, 3)
            if stock is not None and safety is not None else None,
            "moM_tersedia": kontigu,
        }
        for nama, nilai in (("intake_ton", intake), ("sicom", sicom),
                            ("op_price", price), ("op_margin", margin)):
            chg = _perubahan(nilai, prev[nama] if kontigu else None)
            row[f"delta_{nama}"] = chg["delta"]
            row[f"delta_{nama}_pct"] = chg["persen"]
        per_bulan.append(row)
        prev = {"key": key, "intake_ton": intake, "sicom": sicom,
                "op_price": price, "op_margin": margin}

    intake_ada = [r for r in per_bulan if r["intake_ton"] is not None]
    stok_ada = [r for r in per_bulan if r["rm_stock_ton"] is not None]
    margin_ada = [r for r in per_bulan if r["op_margin"] is not None]
    estimasi = [r["estimasi_total_margin_usd"] for r in per_bulan
                if r["estimasi_total_margin_usd"] is not None]
    sumber_ref = [r for r in intake_ada if _referensi(r["sumber_intake"])]
    terakhir = per_bulan[-1]

    # 1. Kesimpulan: maksimal tiga kalimat, seluruh nilainya dari baris terpilih.
    kalimat = []
    gap_akhir = terakhir["selisih_stok_safety_ton"]
    if gap_akhir is not None:
        catatan_stok = ("; data stok bulan ini masih sebagian" if terakhir["stok_sebagian"] else "")
        kalimat.append(
            f"Pada {terakhir['label']}, stok {'di bawah' if gap_akhir < 0 else 'mencapai/di atas'} "
            f"safety sebesar {_fmt(abs(gap_akhir), 3)} ton "
            f"(stok {_fmt(terakhir['rm_stock_ton'], 3)} ton; safety "
            f"{_fmt(terakhir['safety_ton'], 3)} ton{catatan_stok}).")
    if terakhir["op_margin"] is not None:
        kalimat.append(
            f"OP Margin {terakhir['label']} {_fmt(terakhir['op_margin'], 2)} US¢/kg; "
            f"estimasi nilai margin atas intake periode {_fmt(sum(estimasi), 2)} US$. ")
    if sumber_ref:
        kalimat.append(
            f"Keandalan intake lebih rendah pada {len(sumber_ref)} bulan karena sumbernya referensi.")
    kesimpulan = " ".join(kalimat[:3]).strip()
    if not kesimpulan:
        kesimpulan = "Data harga/stok/intake belum lengkap untuk menarik kesimpulan utama."

    # 2. Temuan data: 5–7 fakta angka per periode.
    temuan: list[str] = []
    intake_total = sum(r["intake_ton"] for r in intake_ada)
    temuan.append(
        f"Periode {_bulan(None, _key(baris[0]))}–{_bulan(None, _key(baris[-1]))}: "
        f"{len(baris)} bulan; total intake terisi {_fmt(intake_total, 3)} ton; "
        f"estimasi total margin {_fmt(sum(estimasi), 2)} US$." )
    if stok_ada:
        low = min(stok_ada, key=lambda r: r["selisih_stok_safety_ton"]
                  if r["selisih_stok_safety_ton"] is not None else float("inf"))
        if low["selisih_stok_safety_ton"] is not None:
            temuan.append(
                f"Gap stok–safety terendah {low['label']}: "
                f"{_tanda(low['selisih_stok_safety_ton'], 3)} ton; stok "
                f"{_fmt(low['rm_stock_ton'], 3)} ton vs safety {_fmt(low['safety_ton'], 3)} ton.")
        if terakhir["days_of_cover"] is not None:
            temuan.append(
                f"Days of cover {terakhir['label']} = {_fmt(terakhir['days_of_cover'], 2)} hari, "
                f"mengikuti rumus stok ÷ (intake/30).")
    if intake_ada:
        tertinggi = max(intake_ada, key=lambda r: r["intake_ton"])
        terendah = min(intake_ada, key=lambda r: r["intake_ton"])
        temuan.append(
            f"Intake tertinggi {tertinggi['label']} {_fmt(tertinggi['intake_ton'], 3)} ton; "
            f"terendah {terendah['label']} {_fmt(terendah['intake_ton'], 3)} ton.")
    if terakhir["delta_intake_ton"] is not None:
        temuan.append(
            f"MoM intake {terakhir['label']} {_tanda(terakhir['delta_intake_ton'], 3)} ton "
            f"({_tanda(terakhir['delta_intake_ton_pct'], 2)}%).")
    if margin_ada:
        low_m = min(margin_ada, key=lambda r: r["op_margin"])
        high_m = max(margin_ada, key=lambda r: r["op_margin"])
        temuan.append(
            f"OP Margin terendah {low_m['label']} {_fmt(low_m['op_margin'], 3)} US¢/kg; "
            f"tertinggi {high_m['label']} {_fmt(high_m['op_margin'], 3)} US¢/kg.")
    if terakhir["sicom"] is not None and terakhir["op_price"] is not None:
        temuan.append(
            f"Harga {terakhir['label']}: SICOM {_fmt(terakhir['sicom'], 3)} dan OP Price "
            f"{_fmt(terakhir['op_price'], 3)} US¢/kg; margin = selisih keduanya "
            f"{_fmt(terakhir['op_margin'], 3)} US¢/kg.")
    if sumber_ref:
        labels = ", ".join(r["label"] for r in sumber_ref)
        temuan.append(
            f"{len(sumber_ref)} dari {len(intake_ada)} bulan intake bersumber referensi "
            f"({labels}); angka bulan tersebut berkeandalan lebih rendah.")
    temuan = temuan[:7]

    # 3. Anomali berdasarkan aturan eksplisit, bukan tebakan statistik tersembunyi.
    anomali: list[dict] = []
    for r in per_bulan:
        if r["selisih_stok_safety_ton"] is not None and r["selisih_stok_safety_ton"] < 0:
            anomali.append({
                "bulan": r["label"], "jenis": "Stok di bawah safety",
                "fakta": (f"Gap { _tanda(r['selisih_stok_safety_ton'], 3)} ton; "
                          f"stok {_fmt(r['rm_stock_ton'], 3)} ton, safety "
                          f"{_fmt(r['safety_ton'], 3)} ton."),
            })
        if (r["moM_tersedia"] and r["delta_intake_ton"] is not None
                and r["delta_op_margin"] is not None
                and r["delta_intake_ton"] > 0 and r["delta_op_margin"] < 0):
            anomali.append({
                "bulan": r["label"], "jenis": "Intake naik, margin turun",
                "fakta": (f"Intake MoM {_tanda(r['delta_intake_ton'], 3)} ton, "
                          f"sementara margin MoM {_tanda(r['delta_op_margin'], 3)} US¢/kg."),
            })
        if (r["moM_tersedia"] and r["delta_sicom"] is not None
                and r["delta_op_price"] is not None and r["delta_op_margin"] is not None
                and r["delta_sicom"] <= 0 and r["delta_op_price"] > 0
                and r["delta_op_margin"] < 0):
            anomali.append({
                "bulan": r["label"], "jenis": "OP Price naik saat SICOM tidak naik",
                "fakta": (f"SICOM MoM {_tanda(r['delta_sicom'], 3)}; OP Price MoM "
                          f"{_tanda(r['delta_op_price'], 3)}; margin MoM "
                          f"{_tanda(r['delta_op_margin'], 3)} US¢/kg."),
            })
        if _referensi(r["sumber_intake"]):
            anomali.append({
                "bulan": r["label"], "jenis": "Keandalan intake lebih rendah",
                "fakta": f"Sumber intake tercatat '{r['sumber_intake']}'; ditandai berkeandalan lebih rendah.",
            })
    if not anomali:
        anomali.append({"bulan": "Periode terpilih", "jenis": "Tidak ada anomali pada aturan yang diuji",
                        "fakta": "Tidak ditemukan stok di bawah safety, intake naik saat margin turun, atau intake referensi."})

    # 4. Lima Why: dua level fakta, dua hipotesis terukur, satu akar sementara.
    worst_gap = min((r for r in stok_ada if r["selisih_stok_safety_ton"] is not None),
                    key=lambda r: r["selisih_stok_safety_ton"], default=None)
    worst_margin = min(margin_ada, key=lambda r: r["op_margin"], default=None)
    issue = (f"stok di bawah safety pada {worst_gap['label']} sebesar "
             f"{_fmt(abs(worst_gap['selisih_stok_safety_ton']), 3)} ton"
             if worst_gap and worst_gap["selisih_stok_safety_ton"] < 0 else
             f"margin terendah pada {worst_margin['label']} sebesar "
             f"{_fmt(worst_margin['op_margin'], 3)} US¢/kg" if worst_margin else
             "belum ada indikator stok/margin yang lengkap")
    why = [
        {"level": 1, "pertanyaan": "Apa masalah utama?",
         "jawaban": f"FAKTA: {issue}.", "jenis": "FAKTA",
         "keyakinan": "tinggi", "data_dibutuhkan": "Tidak perlu; angka berasal dari tabel periode."},
    ]
    facts_same = []
    if worst_gap:
        facts_same.append(f"gap safety {_tanda(worst_gap['selisih_stok_safety_ton'], 3)} ton pada {worst_gap['label']}")
    if worst_margin:
        facts_same.append(f"margin {_fmt(worst_margin['op_margin'], 3)} US¢/kg pada {worst_margin['label']}")
    if terakhir["delta_intake_ton"] is not None:
        facts_same.append(f"MoM intake terakhir {_tanda(terakhir['delta_intake_ton'], 3)} ton")
    why.append({"level": 2, "pertanyaan": "Apa yang berubah bersamaan?",
                "jawaban": "FAKTA: " + ("; ".join(facts_same) if facts_same else
                                          "indikator MoM belum lengkap untuk membandingkan bulan."),
                "jenis": "FAKTA", "keyakinan": "tinggi",
                "data_dibutuhkan": "Deret bulanan yang lengkap untuk semua indikator."})
    if terakhir["delta_op_price"] is not None and terakhir["delta_intake_ton"] is not None:
        h3 = ("HIPOTESIS: perubahan OP Price dapat memengaruhi daya tarik penjualan ke pabrik; "
              "keterkaitan dengan perubahan intake belum membuktikan sebab-akibat.")
        h3data = "Penawaran harga pabrik sekitar, harga pengepul, dan transaksi/penolakan pemasok per bulan."
    else:
        h3 = ("HIPOTESIS: gugur daun pada Feb–Apr atau hujan dapat menurunkan sadapan/pasokan, "
              "tetapi data ini tidak memuat cuaca, musim, atau volume sadapan.")
        h3data = "Intake tiket per wilayah dan bulan lintas tahun, catatan hujan, dan produksi kebun/pemasok."
    why.append({"level": 3, "pertanyaan": "Mengapa perubahan itu mungkin terjadi?",
                "jawaban": h3, "jenis": "HIPOTESIS", "keyakinan": "rendah",
                "data_dibutuhkan": h3data})
    why.append({"level": 4, "pertanyaan": "Mengapa hipotesis belum dapat dipastikan?",
                "jawaban": ("HIPOTESIS: hubungan stok–intake–harga dapat dipengaruhi pemakaian, "
                            "penerimaan tertunda, penyesuaian stok, atau cakupan sumber intake; "
                            "kolom-kolom tersebut belum cukup memisahkan efeknya."),
                "jenis": "HIPOTESIS", "keyakinan": "rendah",
                "data_dibutuhkan": "Pemakaian/produksi bulanan, stok awal/akhir terverifikasi, koreksi stok, dan tiket lengkap."})
    why.append({"level": 5, "pertanyaan": "Akar masalah sementara",
                "jawaban": ("AKAR SEMENTARA: penyebab operasional spesifik belum dapat dibuktikan dari tabel ini. "
                            "Yang dapat dipastikan hanya pola angka; data pembanding harga pemasok, "
                            "pemakaian, cuaca, dan rekonsiliasi sumber intake diperlukan sebelum menetapkan akar sebab."),
                "jenis": "HIPOTESIS", "keyakinan": "rendah",
                "data_dibutuhkan": "Kumpulan data pembanding yang disebut pada level 3–4."})

    # 5. Rekomendasi memiliki target yang diturunkan dari angka tabel, bukan angka kebijakan karangan.
    rekomendasi: list[dict] = []
    if terakhir["safety_ton"] is not None:
        rekomendasi.append({
            "aksi": f"Pantau stok penutupan bulan; bila di bawah safety, eskalasi rencana penerimaan.",
            "target_angka": f"RM Stock ≥ {_fmt(terakhir['safety_ton'], 3)} ton (Safety Level pada {terakhir['label']}).",
            "evaluasi": "Penutupan bulan berikutnya.",
        })
    bukan_referensi = [r["intake_ton"] for r in intake_ada
                       if r["sumber_intake"] and not _referensi(r["sumber_intake"])]
    if bukan_referensi:
        target_intake = median(bukan_referensi)
        rekomendasi.append({
            "aksi": "Bandingkan rencana intake bulanan dengan baseline bulan yang sumbernya bukan referensi; telusuri selisih per pemasok.",
            "target_angka": f"Intake ≥ {_fmt(target_intake, 3)} ton/bulan (median {len(bukan_referensi)} bulan bersumber non-referensi pada periode ini; baseline analitis, bukan target resmi).", 
            "evaluasi": "Review pada laporan bulanan berikutnya.",
        })
    margins = [r["op_margin"] for r in margin_ada]
    if margins and terakhir["sicom"] is not None:
        margin_baseline = median(margins)
        price_cap = terakhir["sicom"] - margin_baseline
        rekomendasi.append({
            "aksi": "Tinjau OP Price terhadap SICOM sebelum penetapan harga beli.",
            "target_angka": (f"OP Price ≤ {_fmt(price_cap, 3)} US¢/kg pada SICOM "
                             f"{_fmt(terakhir['sicom'], 3)}; dihitung agar margin menyamai median periode "
                             f"{_fmt(margin_baseline, 3)} US¢/kg, bukan kebijakan resmi."),
            "evaluasi": "Setiap penetapan harga dan pada tutup bulan.",
        })
    if sumber_ref:
        rekomendasi.append({
            "aksi": "Ganti angka intake referensi dengan data tiket atau rekonsiliasi sumber primer sebelum RCA final.",
            "target_angka": "0 bulan intake bersumber referensi pada laporan berikutnya.",
            "evaluasi": "Saat unggah/rekonsiliasi bulanan berikutnya.",
        })
    if len(rekomendasi) < 3:
        rekomendasi.append({
            "aksi": "Lengkapi pencatatan intake, stok akhir, Safety Level, SICOM, dan OP Price setiap bulan.",
            "target_angka": f"{len(baris)} dari {len(baris)} bulan terpilih menjadi baseline; angka hilang saat ini tidak ditaksir.",
            "evaluasi": "Sebelum RCA periode berikutnya.",
        })
    rekomendasi = rekomendasi[:5]

    # 6. Keterbatasan yang melekat pada kolom yang benar-benar tersedia.
    keterbatasan = [
        "OP Margin = SICOM − OP Price; belum termasuk biaya olah dan logistik. Estimasi total margin bukan laba bersih.",
        "Days of cover memakai rumus yang diminta: RM Stock ÷ (Intake/30); pendekatan ini menganggap 30 hari dan memakai intake sebagai proksi kebutuhan.",
        "Perubahan bersamaan adalah korelasi, bukan bukti sebab-akibat. Data pesaing, harga pengepul, cuaca, produksi, dan pemakaian aktual tidak ada di tabel.",
        "Bulan bersumber referensi ditandai berkeandalan lebih rendah; MoM tidak dihitung bila bulan pembanding tidak berurutan atau nilainya kosong. RM Stock bulan berjalan dapat masih sebagian.",
    ]
    return {
        "ada_data": True,
        "periode_awal": per_bulan[0]["label"], "periode_akhir": per_bulan[-1]["label"],
        "kesimpulan": kesimpulan,
        "temuan_data": temuan,
        "anomali": anomali,
        "root_cause": why,
        "rekomendasi": rekomendasi,
        "keterbatasan": keterbatasan,
        "per_bulan": per_bulan,
        "catatan_margin": "OP Margin = SICOM − OP Price, belum termasuk biaya olah dan logistik.",
        "estimasi_total_margin_usd": round(sum(estimasi), 2),
        "jumlah_bulan_referensi": len(sumber_ref),
    }
