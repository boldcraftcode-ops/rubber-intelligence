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
