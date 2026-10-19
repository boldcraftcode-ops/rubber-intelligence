import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { Kartu, ambilJson, fmtAngka, fmtTanggal } from "../bersama";

export default function Stok() {
  const q = useQuery({ queryKey: ["stok"], queryFn: () => ambilJson("/api/stok") });
  const t = q.data?.terakhir;
  const dataGrafik = q.data?.baris.map((b: any) => ({
    tanggal: b.tanggal, stok: b.stok_ton, safety: b.safety_ton,
  }));
  const diBawah = q.data?.baris.filter((b: any) => b.status === "di bawah safety") ?? [];

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="stok" judul="Stok hari terakhir"
             keterangan="Days = stok ÷ kapasitas olah; rasio = stok ÷ safety stock (parameter berversi tanggal berlaku)."
             anak={
        t ? (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {[
              ["Tanggal", fmtTanggal(t.tanggal)],
              ["Stok (ton)", fmtAngka(t.stok_ton, 1)],
              ["Days", fmtAngka(t.days, 3)],
              ["Rasio vs safety", t.rasio_stok !== null ? fmtAngka(t.rasio_stok * 100, 2) + "%" : "–"],
              ["Status", t.status],
            ].map(([label, nilai]) => (
              <div key={label as string}
                   className={`rounded-lg border p-3 ${label === "Status" && t.status === "di bawah safety"
                     ? "border-red-400/40 bg-red-500/10" : "border-violet-500/20 bg-white/5"}`}>
                <p className="text-xs text-slate-400">{label}</p>
                <p className="font-semibold text-slate-100">{nilai}</p>
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-slate-500">Belum ada data stok.</p>
      } />

      <Kartu idMetrik="stok" judul="Grafik stok vs safety stock"
             keterangan="Ton bahan baku per hari dibandingkan safety stock yang berlaku."
             anak={
        <div className="h-80">
          <ResponsiveContainer>
            <LineChart data={dataGrafik} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="tanggal" fontSize={11}
                     tickFormatter={(v) => v.slice(0, 7)} minTickGap={40} />
              <YAxis fontSize={11} />
              <Tooltip formatter={(v: any) => fmtAngka(v as number, 1) + " ton"}
                       labelFormatter={(l) => fmtTanggal(l as string)} />
              <Legend />
              <Line dataKey="stok" name="Stok (ton)" stroke="#818cf8" dot={false} />
              <Line dataKey="safety" name="Safety stock (ton)" stroke="#fb7185"
                    dot={false} strokeDasharray="6 3" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      } />

      <Kartu idMetrik="stok" judul="Hari dengan stok di bawah safety"
             keterangan="Rasio stok < 100% safety stock."
             anak={
        <>
          <p className="text-sm text-slate-300 mb-2">
            <b className={diBawah.length ? "text-red-400" : "text-emerald-400"}>
              {diBawah.length}
            </b>{" "}
            dari {q.data?.jumlah_hari ?? 0} hari berdata.
          </p>
          {diBawah.length > 0 && (
            <div className="max-h-60 overflow-y-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-400 border-b">
                    <th className="py-1">Tanggal</th><th className="text-right">Stok ton</th>
                    <th className="text-right">Safety ton</th><th className="text-right">Rasio</th>
                    <th className="text-right">Days</th>
                  </tr>
                </thead>
                <tbody>
                  {diBawah.slice(-60).reverse().map((b: any) => (
                    <tr key={b.tanggal} className="border-b border-white/5 bg-red-500/10">
                      <td className="py-1">{fmtTanggal(b.tanggal)}</td>
                      <td className="text-right font-mono">{fmtAngka(b.stok_ton, 1)}</td>
                      <td className="text-right font-mono">{fmtAngka(b.safety_ton, 1)}</td>
                      <td className="text-right font-mono">{fmtAngka(b.rasio_stok * 100, 1)}%</td>
                      <td className="text-right font-mono">{fmtAngka(b.days, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      } />
    </div>
  );
}
