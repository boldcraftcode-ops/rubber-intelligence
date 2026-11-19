import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ambilJson, fmtAngka, fmtTanggal, kelasInput } from "../bersama";
import { useBahasa } from "../i18n";

const hariISO = (tanggal: Date) => {
  const y = tanggal.getFullYear();
  const m = String(tanggal.getMonth() + 1).padStart(2, "0");
  const d = String(tanggal.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};
type BarisDetail = { grade: string; qty_kering_kg: number; harga_rp_per_kg: number | null; estimasi_rp: number | null };
type Harian = { tanggal: string; lengkap: boolean; qty_kering_kg: number | null; estimasi_rp: number | null; harga_rata_rp_per_kg: number | null; grade_tanpa_harga: string[]; rincian: BarisDetail[] };
type Periode = { total_hari: number; hari_lengkap: number; hari_belum_lengkap: number; qty_kering_kg: number; estimasi_rp: number; harga_rata_rp_per_kg: number | null; harian: Harian[] };
type Hasil = { periode: Periode; sebelumnya: Periode };

export default function KartuPembelianEstimasi() {
  const { t } = useBahasa();
  const sekarang = new Date();
  const awal = new Date(sekarang); awal.setDate(awal.getDate() - 6);
  const [dari, setDari] = useState(hariISO(awal));
  const [sampai, setSampai] = useState(hariISO(sekarang));
  const url = `/api/pembelian/ringkasan?dari=${dari}&sampai=${sampai}`;
  const q = useQuery<Hasil>({ queryKey: ["ringkasan-pembelian", dari, sampai], queryFn: () => ambilJson(url), enabled: !!dari && !!sampai && dari <= sampai });
  const p = q.data?.periode;
  const prev = q.data?.sebelumnya;
  const perubahan = (k: "qty_kering_kg" | "estimasi_rp") => {
    if (!p || !prev) return "–";
    const a = p[k], b = prev[k];
    if (!b) return a ? "+100%" : "0%";
    const pct = ((a - b) / b) * 100;
    return `${pct > 0 ? "+" : ""}${fmtAngka(pct, 1)}%`;
  };
  const lengkapPersen = p?.total_hari ? (p.hari_lengkap / p.total_hari) * 100 : 0;

  return <section className="rounded-sm border border-[#E4E5E8] bg-white p-5 shadow-sm">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-[#1D2434]">{t("Pembelian berbasis intake")}</h2>
        <p className="mt-1 text-xs text-[#64676C]">{t("Estimasi nilai dihitung dari berat kering × harga grade yang berlaku; bukan pembayaran aktual.")}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <label className="text-xs text-[#64676C]">{t("Dari")}<input className={`${kelasInput} mt-1`} type="date" value={dari} max={sampai} onChange={(e) => setDari(e.target.value)} /></label>
        <label className="text-xs text-[#64676C]">{t("Sampai")}<input className={`${kelasInput} mt-1`} type="date" value={sampai} min={dari} onChange={(e) => setSampai(e.target.value)} /></label>
      </div>
    </div>
    {q.isError && <p role="alert" className="mt-3 text-sm text-[#B42318]">{t("Ringkasan pembelian gagal dimuat.")}</p>}
    {q.isLoading ? <p className="mt-4 text-sm text-[#64676C]">{t("Memuat…")}</p> : p && <>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3"><p className="text-xs text-[#64676C]">{t("Total berat kering")}</p><b className="font-mono text-lg">{fmtAngka(p.qty_kering_kg / 1000, 2)} ton</b><p className="text-xs text-[#64676C]">{t("vs periode sebelumnya")}: {perubahan("qty_kering_kg")}</p></div>
        <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3"><p className="text-xs text-[#64676C]">{t("Estimasi nilai pembelian")}</p><b className="font-mono text-lg">Rp {fmtAngka(p.estimasi_rp, 0)}</b><p className="text-xs text-[#64676C]">{t("vs periode sebelumnya")}: {perubahan("estimasi_rp")}</p></div>
        <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3"><p className="text-xs text-[#64676C]">{t("Harga rata-rata tertimbang")}</p><b className="font-mono text-lg">{p.harga_rata_rp_per_kg == null ? "–" : `Rp ${fmtAngka(p.harga_rata_rp_per_kg, 0)}/kg`}</b><p className="text-xs text-[#64676C]">{t("Hari harga lengkap")}: {p.hari_lengkap}/{p.total_hari} ({fmtAngka(lengkapPersen, 0)}%)</p></div>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr className="border-b text-left text-[#64676C]"><th className="py-2">{t("Tanggal")}</th><th className="text-right">{t("Berat kering")}</th><th className="text-right">{t("Estimasi nilai")}</th><th className="text-right">{t("Harga tertimbang")}</th><th>{t("Kelengkapan harga")}</th></tr></thead>
          <tbody>{p.harian.map((h) => <tr key={h.tanggal} className="border-b border-[#EDEFF2] align-top">
            <td className="py-2">{fmtTanggal(h.tanggal)}{h.rincian.map((r) => <div key={r.grade} className="pl-2 pt-1 text-[10px] text-[#64676C]">{r.grade}: {fmtAngka(r.qty_kering_kg / 1000, 3)} ton × {r.harga_rp_per_kg == null ? "–" : `Rp ${fmtAngka(r.harga_rp_per_kg, 0)}/kg`}</div>)}</td>
            <td className="text-right font-mono">{h.qty_kering_kg == null ? "–" : `${fmtAngka(h.qty_kering_kg / 1000, 3)} ton`}</td>
            <td className="text-right font-mono">{h.estimasi_rp == null ? "–" : `Rp ${fmtAngka(h.estimasi_rp, 0)}`}{h.rincian.some((r) => r.estimasi_rp != null) && <div className="text-[10px] text-[#64676C]">{h.rincian.filter((r) => r.estimasi_rp != null).map((r) => `${r.grade}: Rp ${fmtAngka(r.estimasi_rp, 0)}`).join(" · ")}</div>}</td>
            <td className="text-right font-mono">{h.harga_rata_rp_per_kg == null ? "–" : `Rp ${fmtAngka(h.harga_rata_rp_per_kg, 0)}/kg`}</td>
            <td>{h.lengkap ? <span className="text-[#15803D]">{t("Lengkap")}</span> : <span className="text-[#B54708]">{t("Belum lengkap")}: {h.grade_tanpa_harga.join(", ")}</span>}</td>
          </tr>)}{p.harian.length === 0 && <tr><td colSpan={5} className="py-4 text-center text-[#64676C]">{t("Tidak ada intake pada rentang ini.")}</td></tr>}</tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-[#64676C]">{t("Hari dengan harga grade yang belum lengkap dikecualikan dari total periode.")}</p>
    </>}
  </section>;
}
