/* Dwibahasa ID/EN. Teks di kode ditulis dalam Bahasa Indonesia;
   t() menerjemahkan ke Inggris lewat kamus di bawah. Kata yang belum
   ada di kamus tampil apa adanya (jatuh kembali ke Indonesia). */
import { ReactNode, createContext, useContext, useState } from "react";

export type Bahasa = "id" | "en";

const KAMUS: Record<string, string> = {
  // ---- menu samping
  "Ringkasan": "Summary",
  "Analisis": "Analytics",
  "Stok": "Stock",
  "Stok vs Margin": "Stock vs Margin",
  "Aturan Harga": "Pricing Rules",
  "Simulasi": "Simulation",
  "Perencanaan": "Planning",
  "Alarm": "Alerts",
  "Rekonsiliasi": "Reconciliation",
  "Kualitas Data": "Data Quality",
  "Grade & Harga": "Grades & Prices",
  "Unggah Data": "Upload Data",
  "Input Harian": "Daily Input",
  "Database": "Database",
  "Pengguna": "Users",
  "Ganti sandi": "Change password",
  "Keluar": "Sign out",
  "Rubber Raw Material Big Data": "Rubber Raw Material Big Data",
  "Nama Anda (untuk catatan)": "Your name (for audit trail)",
  "nama pengisi": "your name",
  "✦ tema: Milky Way": "✦ theme: Milky Way",
  // ---- kartu umum
  "Cara dihitung": "How it's calculated",
  "Ekspor Excel": "Export to Excel",
  "Tutup": "Close",
  // ---- halaman ringkasan
  "Ringkasan OP Margin": "OP Margin Summary",
  "US¢/kg, basis berat kering — meniru Excel lama. Klik angka OP Margin untuk menelusuri asal angkanya.":
    "US¢/kg, dry-weight basis — mirrors the legacy Excel. Click any OP Margin figure to trace its origin.",
  "SICOM": "SICOM",
  "OP Price": "OP Price",
  "OP Margin": "OP Margin",
  "Ton (kering)": "Tonnes (dry)",
  "Target": "Target",
  "Pencapaian": "Achievement",
  "vs Target": "vs Target",
  "Avg YTD": "Avg YTD",
  "Tertimbang": "Weighted",
  "Catatan koreksi:": "Correction note:",
  "Avg YTD = rata-rata sederhana bulan berdata (resmi, seperti Excel); kolom \"Tertimbang\" = rata-rata tertimbang tonase (informasi).":
    "Avg YTD = simple average of months with data (official, as in Excel); the \"Weighted\" column is the tonnage-weighted average (informational).",
  // grafik margin
  "OP Margin bulanan vs target": "Monthly OP Margin vs target",
  "Tujuan grafik: menjawab “apakah margin tiap bulan mencapai target, dan bagaimana trennya?”":
    "Purpose: answers “did each month's margin meet the target, and what is the trend?”",
  "Tren & capaian target": "Trend & target achievement",
  "Banding antar tahun": "Compare years",
  "dari": "of",
  "bulan mencapai target": "months met the target",
  "Pilih tahun yang dibandingkan:": "Select years to compare:",
  // kartu elemen
  "RM Stock – Intake vs Pricing": "RM Stock – Intake vs Pricing",
  "Elemen pemengaruh OP Margin per bulan, disamakan dengan Excel: batang = ton (sumbu kiri), garis = US¢/kg (sumbu kanan).":
    "Monthly OP Margin drivers, matched to the Excel sheet: bars = tonnes (left axis), lines = US¢/kg (right axis).",
  "Dari bulan": "From month",
  "Sampai bulan": "To month",
  "tampilkan semua periode": "show all periods",
  "bulan ditampilkan": "months shown",
  "Sumber intake": "Intake source",
  "Date": "Date",
  "RM Stock": "RM Stock",
  "Intake": "Intake",
  "Safety": "Safety",
  // telusur
  "Telusur asal angka": "Trace this figure",
  "Hari pembelian penyusun bulan ini (klik tanggal untuk lanjut)":
    "Purchase days composing this month (click a date to continue)",
  "Baris pembelian & tiket pada": "Purchase & ticket rows on",
  "unggahan asal": "source upload",
  // ---- panel analisa kartu RM Stock – Intake vs Pricing
  "Margin Bridge": "Margin Bridge",
  "Days of Cover": "Days of Cover",
  "Margin Bridge — analisa grafik": "Margin Bridge — chart analysis",
  "Days of Cover — analisa grafik": "Days of Cover — chart analysis",
  "Periode": "Period",
  "Tombol analisa memakai periode yang dipilih di atas — bulan/tahun yang dianalisa sama dengan grafik.":
    "The analysis buttons use the period selected above — the analysed month/year matches the chart.",
  "Analisa grafik": "Chart analysis",
  // ---- margin bridge
  // ---- margin bridge (ΔM = ΔSICOM − ΔOP Price)
  "Periode awal": "Opening period",
  "Periode akhir": "Closing period",
  "Bawaan: mengikuti filter kartu grafik.": "Default: follows the chart card's filter.",
  "SICOM = harga acuan pasar (di luar kendali), OP Price = harga beli kita (keputusan). SICOM turun menekan margin; OP Price turun justru menolong.":
    "SICOM = market reference price (outside our control), OP Price = our purchase price (a decision). Falling SICOM squeezes margin; falling OP Price actually helps.",
  "OP Margin awal": "Opening OP Margin",
  "Perubahan margin": "Margin change",
  "OP Margin akhir": "Closing OP Margin",
  "Kontribusi": "Contributions",
  "pasar": "market",
  "keputusan": "decision",
  "OP Price hanya mengikuti": "OP Price only follows",
  "dari perubahan SICOM; sisa": "of the SICOM move; the remaining",
  "ditanggung margin.": "is absorbed by margin.",
  "Rincian Δ OP Price (harga Rp vs kurs)": "Δ OP Price breakdown (Rp price vs FX)",
  "Efek harga beli (Rp/kg)": "Purchase price effect (Rp/kg)",
  "Efek kurs": "FX effect",
  "Total = −Δ OP Price": "Total = −Δ OP Price",
  "Klik untuk memisahkan efek harga beli dan kurs.": "Click to split the purchase-price and FX effects.",
  "Bridge per bulan — mana yang dipicu pasar, mana yang keputusan":
    "Monthly bridge — which moves are market-driven, which are decisions",
  "Bulan": "Month",
  "Ikut SICOM": "Follows SICOM",
  "Penyebab": "Driver",
  "dipicu pasar": "market-driven",
  "dipicu keputusan": "decision-driven",
  "— bridge tertutup persis.": "— the bridge closes exactly.",
  "perubahan": "change",
  // ---- days of cover (pemakaian implisit)
  "Pemakaian tidak ada di data, jadi dihitung dari neraca stok. DoC lebih adil daripada tonase karena menyesuaikan pemakaian.":
    "Consumption is not in the data, so it is derived from the stock balance. DoC is fairer than tonnage because it adjusts to consumption.",
  "stok akhir": "closing stock",
  "pemakaian": "consumption",
  "bulan": "month",
  "safety": "safety",
  "Rerata pemakaian:": "Average consumption:",
  "Safety dinamis (21,5 hari):": "Dynamic safety (21.5 days):",
  "bulan di bawah safety:": "months below safety:",
  "Stok awal": "Opening stock",
  "Stok akhir": "Closing stock",
  "Pemakaian": "Consumption",
  "Status": "Status",
  "Bulan tidak bisa dihitung:": "Months that cannot be computed:",
  "Menjembatani OP Margin periode awal ke periode akhir grafik: kontribusi Δ SICOM, Δ harga beli (Rp/kg), dan Δ kurs — jumlahnya tertutup persis.":
    "Bridges OP Margin from the chart's opening period to its closing period: contributions from Δ SICOM, Δ purchase price (Rp/kg) and Δ FX — the sum closes exactly.",
  "Margin awal": "Opening margin",
  "Margin akhir": "Closing margin",
  "Memuat…": "Loading…",
  "Harga beli (Rp/kg)": "Purchase price (Rp/kg)",
  "Kurs efektif": "Effective FX rate",
  "Qty kering (ton)": "Dry qty (tonnes)",
  "Hari pembelian": "Purchase days",
  "Selisih penutupan (awal + komponen − akhir):": "Closing gap (opening + components − closing):",
  "— praktis nol, jadi bridge tertutup persis.": "— practically zero, so the bridge closes exactly.",
  "Hijau = menambah margin, merah = mengurangi margin. Arahkan kursor ke batang untuk nilai persisnya.":
    "Green = adds margin, red = reduces margin. Hover a bar for the exact value.",
  // ---- days of cover
  "Berapa hari olah tersisa dari stok bila laju olah tetap: stok ÷ kapasitas olah. Garis kuning = safety stock pada hari yang sama.":
    "How many processing days remain in stock at the current rate: stock ÷ processing capacity. Yellow line = safety stock on the same day.",
  "hari": "days",
  "per": "as of",
  "stok": "stock",
  "kapasitas": "capacity",
  "dari safety": "of safety",
  "Rerata 30 hari terakhir:": "Average of last 30 days:",
  "Terendah:": "Lowest:",
  "Tertinggi:": "Highest:",
  "Hari di bawah safety:": "Days below safety:",
  "Days of cover": "Days of cover",
  "Safety (hari)": "Safety (days)",
  "di bawah safety": "below safety",
  "aman": "safe",
  "tanpa safety": "no safety stock",
};

let bahasaAktif: Bahasa =
  (typeof localStorage !== "undefined" &&
    (localStorage.getItem("op-margin.bahasa") as Bahasa)) || "id";

/** Dipakai fungsi non-komponen (mis. format angka). */
export const bahasaSekarang = (): Bahasa => bahasaAktif;

const Ctx = createContext<{
  lang: Bahasa;
  setLang: (l: Bahasa) => void;
  t: (s: string) => string;
}>({ lang: "id", setLang: () => {}, t: (s) => s });

export function ProviderBahasa({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Bahasa>(bahasaAktif);
  const setLang = (l: Bahasa) => {
    bahasaAktif = l;
    localStorage.setItem("op-margin.bahasa", l);
    setLangState(l);
  };
  const t = (s: string) => (lang === "id" ? s : KAMUS[s] ?? s);
  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}

export const useBahasa = () => useContext(Ctx);
