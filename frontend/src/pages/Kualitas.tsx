import { useQuery } from "@tanstack/react-query";
import { Kartu, ambilJson, fmtAngka, fmtTanggal } from "../bersama";

export default function Kualitas() {
  const q = useQuery({ queryKey: ["kualitas"], queryFn: () => ambilJson("/api/kualitas") });

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="reject" judul="Kesegaran data"
             keterangan="Tanggal terakhir setiap sumber data. Kurs hanya diisi saat berubah."
             anak={
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {q.data?.terlambat.map((t: any) => (
            <div key={t.sumber}
                 className={`rounded-lg border p-3 ${t.terlambat
                   ? "border-amber-400/40 bg-amber-400/10" : "border-violet-500/20 bg-white/5"}`}>
              <p className="text-xs text-slate-400">{t.sumber}</p>
              <p className="font-semibold text-slate-100">
                {t.tanggal_terakhir ? fmtTanggal(t.tanggal_terakhir) : "–"}
              </p>
              <p className="text-xs text-slate-400">
                {t.umur_hari !== null ? `${t.umur_hari} hari lalu` : "belum ada"}
                {t.terlambat && " ⚠"}
              </p>
            </div>
          ))}
        </div>
      } />

      <Kartu idMetrik="margin_harian" judul="Hari pembelian tanpa SICOM persis"
             keterangan="Perhitungan tetap memakai harga terakhir (aturan hari libur), tetapi tanggal ini perlu dicek."
             anak={
        q.data?.hari_pembelian_tanpa_sicom.length === 0 ? (
          <p className="text-sm text-emerald-400">
            Semua hari pembelian punya baris SICOM pada tanggalnya. ✓
          </p>
        ) : (
          <p className="text-sm text-slate-300">
            {q.data?.hari_pembelian_tanpa_sicom.map((t: string) => fmtTanggal(t)).join(", ")}
          </p>
        )
      } />

      <Kartu idMetrik="margin_harian" judul="Lonjakan harga beli harian"
             keterangan="Hari dengan harga beli menyimpang lebih dari 10% dari median bulannya."
             anak={
        q.data?.lonjakan_harga.length === 0 ? (
          <p className="text-sm text-emerald-400">Tidak ada lonjakan terdeteksi. ✓</p>
        ) : (
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-400 border-b">
                  <th className="py-1">Tanggal</th>
                  <th className="text-right">Harga Rp/kg</th>
                  <th className="text-right">Median bulan</th>
                  <th className="text-right">Deviasi</th>
                </tr>
              </thead>
              <tbody>
                {q.data?.lonjakan_harga.map((l: any) => (
                  <tr key={l.tanggal} className="border-b border-white/5 bg-amber-400/10">
                    <td className="py-1">{fmtTanggal(l.tanggal)}</td>
                    <td className="text-right font-mono">{fmtAngka(l.harga_rp_per_kg, 2)}</td>
                    <td className="text-right font-mono">{fmtAngka(l.median_bulan_rp, 2)}</td>
                    <td className="text-right font-mono">{fmtAngka(l.deviasi_pct, 1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      } />

      <Kartu idMetrik="reject" judul="Rekap peringatan impor"
             keterangan="Semua peringatan dari proses impor & validasi (vendor tak dikenal, Dry tak cocok, wilayah beda, dll.)."
             anak={
        q.data?.peringatan.length === 0 ? (
          <p className="text-sm text-emerald-400">Tidak ada peringatan. ✓</p>
        ) : (
          <div className="grid gap-3">
            {q.data?.peringatan.map((p: any) => (
              <div key={p.kode} className="rounded-lg border border-violet-500/20 p-3">
                <p className="text-sm font-semibold text-slate-200">
                  {p.kode} <span className="font-normal text-slate-500">× {p.jumlah}</span>
                </p>
                <ul className="mt-1 list-disc pl-5 text-xs text-slate-400">
                  {p.contoh.map((c: string, i: number) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            ))}
          </div>
        )
      } />
    </div>
  );
}
