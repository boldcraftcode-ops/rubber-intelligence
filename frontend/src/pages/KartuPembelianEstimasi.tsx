import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ambilJson, fmtAngka, fmtTanggal, kelasInput, kelasTombolKecil } from "../bersama";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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
  const [detailTerbuka, setDetailTerbuka] = useState(false);
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
  const chartHarian = (p?.harian ?? []).map((h) => ({
    tanggal: fmtTanggal(h.tanggal),
    berat_ton: h.lengkap && h.qty_kering_kg != null ? h.qty_kering_kg / 1000 : null,
    nilai_juta: h.lengkap && h.estimasi_rp != null ? h.estimasi_rp / 1_000_000 : null,
  }));

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
    {q.isError && <div role="alert" className="mt-3 rounded-sm border border-[#FECACA] bg-[#FEF2F2] p-3 text-sm text-[#B42318]">
      <p className="font-semibold">{t("Ringkasan pembelian gagal dimuat.")}</p>
      <p className="mt-1">{t("Detail penyebab")}:  {q.error instanceof Error ? q.error.message : t("Kesalahan tidak diketahui.")}</p>
    </div>}
    {q.isLoading ? <p className="mt-4 text-sm text-[#64676C]">{t("Memuat…")}</p> : p && <>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3"><p className="text-xs text-[#64676C]">{t("Total berat kering")}</p><b className="font-mono text-lg">{fmtAngka(p.qty_kering_kg / 1000, 2)} ton</b><p className="text-xs text-[#64676C]">{t("vs periode sebelumnya")}: {perubahan("qty_kering_kg")}</p></div>
        <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3"><p className="text-xs text-[#64676C]">{t("Estimasi nilai pembelian")}</p><b className="font-mono text-lg">Rp {fmtAngka(p.estimasi_rp, 0)}</b><p className="text-xs text-[#64676C]">{t("vs periode sebelumnya")}: {perubahan("estimasi_rp")}</p></div>
        <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3"><p className="text-xs text-[#64676C]">{t("Harga rata-rata tertimbang")}</p><b className="font-mono text-lg">{p.harga_rata_rp_per_kg == null ? "–" : `Rp ${fmtAngka(p.harga_rata_rp_per_kg, 0)}/kg`}</b><p className="text-xs text-[#64676C]">{t("Hari harga lengkap")}: {p.hari_lengkap}/{p.total_hari} ({fmtAngka(lengkapPersen, 0)}%)</p></div>
      </div>
      {chartHarian.length ? <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-sm border border-[#E4E5E8] p-3">
          <h3 className="mb-2 text-sm font-semibold text-[#1D2434]">{t("Berat intake kering per hari (ton)")}</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%"><BarChart data={chartHarian} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="tanggal" interval="preserveStartEnd" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => fmtAngka(Number(v), 0)} />
              <Tooltip formatter={(v) => [`${fmtAngka(Number(v), 2)} ton`, t("Berat kering")]} />
              <Bar dataKey="berat_ton" name={t("Berat kering")} fill="#1D2434" radius={[2, 2, 0, 0]} />
            </BarChart></ResponsiveContainer>
          </div>
        </div>
        <div className="rounded-sm border border-[#E4E5E8] p-3">
          <h3 className="mb-2 text-sm font-semibold text-[#1D2434]">{t("Estimasi nilai pembelian per hari (Rp juta)")}</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%"><BarChart data={chartHarian} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="tanggal" interval="preserveStartEnd" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => fmtAngka(Number(v), 0)} />
              <Tooltip formatter={(v) => [`Rp ${fmtAngka(Number(v), 2)} juta`, t("Estimasi nilai")]} />
              <Bar dataKey="nilai_juta" name={t("Estimasi nilai")} fill="#FF1313" radius={[2, 2, 0, 0]} />
            </BarChart></ResponsiveContainer>
          </div>
        </div>
      </div> : <p className="mt-4 rounded-sm bg-[#F8F8F8] p-4 text-center text-sm text-[#64676C]">{t("Tidak ada intake pada rentang ini.")}</p>}
      <p className="mt-2 text-[11px] text-[#64676C]">{t("Hari dengan harga grade yang belum lengkap dikecualikan dari total periode.")}</p>
      {p.harian.length > 0 && <button type="button" className={`${kelasTombolKecil} mt-2`} aria-expanded={detailTerbuka} onClick={() => setDetailTerbuka((v) => !v)}>
        {detailTerbuka ? t("Tutup detail") : t("Cek detail")}
      </button>}
      {detailTerbuka && <div className="mt-3 max-h-[32rem] overflow-auto rounded-sm border border-[#E4E5E8]">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-[#F8F8F8]"><tr className="border-b text-left text-[#64676C]"><th className="py-2">{t("Tanggal / grade")}</th><th className="text-right">{t("Berat kering")}</th><th className="text-right">{t("Harga Rp/kg")}</th><th className="text-right">{t("Estimasi nilai")}</th><th>{t("Kelengkapan harga")}</th></tr></thead>
          <tbody>{p.harian.map((h) => <Fragment key={h.tanggal}>
            {h.rincian.map((r) => <tr key={`${h.tanggal}-${r.grade}`} className="border-b border-[#EDEFF2]"><td className="py-2">{fmtTanggal(h.tanggal)} · {r.grade}</td><td className="text-right font-mono">{fmtAngka(r.qty_kering_kg / 1000, 3)} ton</td><td className="text-right font-mono">{r.harga_rp_per_kg == null ? "–" : fmtAngka(r.harga_rp_per_kg, 0)}</td><td className="text-right font-mono">{r.estimasi_rp == null ? "–" : `Rp ${fmtAngka(r.estimasi_rp, 0)}`}</td><td>{h.lengkap ? <span className="text-[#15803D]">{t("Lengkap")}</span> : <span className="text-[#B54708]">{t("Belum lengkap")}: {h.grade_tanpa_harga.join(", ")}</span>}</td></tr>)}
          </Fragment>)}</tbody>
        </table>
      </div>}
    </>}
  </section>;
}
