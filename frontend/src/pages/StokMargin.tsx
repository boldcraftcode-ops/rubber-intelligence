import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { Kartu, NAMA_BULAN, ambilJson, fmtAngka } from "../bersama";

export default function StokMargin() {
  const q = useQuery({
    queryKey: ["stok-margin"],
    queryFn: () => ambilJson("/api/analisis/stok-margin"),
  });

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="stok_margin" judul="Hubungan rasio stok dengan OP Margin per bulan"
             keterangan="INFORMASI, bukan aturan. Setiap titik = satu bulan."
             anak={
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            {[
              ["Bulan berdata", q.data?.jumlah_bulan],
              ["Korelasi (Pearson)", fmtAngka(q.data?.korelasi, 2)],
              [`Rata-rata margin saat stok < 50% safety (${q.data?.jumlah_bulan_stok_rendah ?? 0} bln)`,
               fmtAngka(q.data?.margin_stok_rendah, 2)],
              [`Rata-rata margin saat stok ≥ 80% safety (${q.data?.jumlah_bulan_stok_tinggi ?? 0} bln)`,
               fmtAngka(q.data?.margin_stok_tinggi, 2)],
            ].map(([label, nilai]) => (
              <div key={label as string} className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                <p className="text-xs text-[#64676C]">{label}</p>
                <p className="font-semibold text-[#1D2434]">{nilai ?? "–"}</p>
              </div>
            ))}
          </div>
          <div className="h-80">
            <ResponsiveContainer>
              <ScatterChart margin={{ top: 5, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="rasio_stok" name="Rasio stok/safety" fontSize={11}
                       label={{ value: "Rasio stok ÷ safety", position: "insideBottom", offset: -10, fontSize: 12 }}
                       tickFormatter={(v) => fmtAngka(v as number, 1)} />
                <YAxis dataKey="op_margin" name="OP Margin" fontSize={11}
                       label={{ value: "OP Margin US¢/kg", angle: -90, position: "insideLeft", fontSize: 12 }} />
                <Tooltip
                  formatter={(v: any, nama: any) => [fmtAngka(v as number, 3), nama]}
                  labelFormatter={() => ""}
                  content={({ payload }) => {
                    const p: any = payload?.[0]?.payload;
                    if (!p) return null;
                    return (
                      <div className="rounded-sm bg-white border border-[#E4E5E8] p-2 text-xs shadow">
                        <b>{NAMA_BULAN[p.bulan]} {p.tahun}</b><br />
                        rasio {fmtAngka(p.rasio_stok, 3)} · margin {fmtAngka(p.op_margin, 4)}<br />
                        {fmtAngka(p.ton, 0)} ton
                      </div>
                    );
                  }} />
                <Scatter data={q.data?.titik ?? []} fill="#FF1313" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          {q.data && (
            <p className="mt-3 rounded-sm bg-[#FFFBEB] border border-[#FDE68A] px-3 py-2 text-xs text-[#B45309]">
              {q.data.catatan}
            </p>
          )}
        </>
      } />
    </div>
  );
}
