import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Kartu, PilihRentangBulan, akhirBulan, ambilJson,
  awalTahunBerjalan, bulanBerjalan, fmtAngka, fmtTanggal, kelasTombolKecil,
  labelRentangBulan,
} from "../bersama";

/* Periode bawaan menu Stok: 1 Januari tahun berjalan s.d. bulan berjalan.
   Contoh: dibuka Oktober 2026 -> "2026-01" s.d. "2026-10". */
const periodeBawaan = () => ({
  dari: awalTahunBerjalan(),
  sampai: bulanBerjalan(),
});

export default function Stok() {
  const [bawaan] = useState(periodeBawaan);
  const [dari, setDari] = useState(bawaan.dari);
  const [sampai, setSampai] = useState(bawaan.sampai);

  /* Bulan awal setelah bulan akhir: jangan kirim permintaan yang pasti kosong. */
  const urutanSalah = Boolean(dari && sampai && dari > sampai);

  const params = new URLSearchParams();
  if (dari) params.set("dari", `${dari}-01`);
  if (sampai) params.set("sampai", akhirBulan(sampai));
  const url = `/api/stok${params.toString() ? `?${params.toString()}` : ""}`;

  const q = useQuery({
    queryKey: ["stok", url],
    queryFn: () => ambilJson(url),
    enabled: !urutanSalah,
  });

  const t = q.data?.terakhir;
  const dataGrafik = q.data?.baris.map((b: any) => ({
    tanggal: b.tanggal, stok: b.stok_ton, safety: b.safety_ton,
  }));
  const diBawah = q.data?.baris.filter((b: any) => b.status === "di bawah safety") ?? [];
  const jumlahHari = q.data?.jumlah_hari ?? 0;
  const rentang = labelRentangBulan(dari, sampai);
  const tanpaBatas = !dari && !sampai;

  const keteranganPeriode = tanpaBatas
    ? "seluruh data yang tersedia"
    : `periode ${rentang}`;

  const bar = (
    <div className="rounded-sm border border-[#E4E5E8] bg-white p-3">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <p className="mb-1 text-xs font-semibold text-[#1D2434]">Periode tampilan</p>
          <PilihRentangBulan dari={dari} sampai={sampai}
                             setDari={setDari} setSampai={setSampai}
                             labelKosong="seluruh data" />
        </div>
        <button className={kelasTombolKecil}
                onClick={() => { setDari(bawaan.dari); setSampai(bawaan.sampai); }}>
          tahun ini
        </button>
        <p className="text-xs text-[#64676C]">
          {urutanSalah
            ? "Bulan awal harus sebelum (atau sama dengan) bulan akhir."
            : <>Menampilkan <b className="text-[#1D2434]">{rentang}</b>
                {!tanpaBatas && <> · {jumlahHari.toLocaleString("id-ID")} hari berdata</>}
              </>}
        </p>
      </div>
      <p className="mt-2 text-[11px] text-[#64676C]">
        Bawaan saat halaman dibuka: awal tahun berjalan sampai bulan ini.
        Klik <b>seluruh data</b> untuk melihat semua tanggal tanpa batas periode.
      </p>
    </div>
  );

  return (
    <div className="grid gap-6">
      {bar}

      <Kartu idMetrik="stok" judul="Stok hari terakhir"
             keterangan={`Keadaan stok pada tanggal terakhir dalam ${keteranganPeriode}. Days = stok ÷ kapasitas olah; rasio = stok ÷ safety stock (parameter berversi tanggal berlaku).`}
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
                   className={`rounded-sm border p-3 ${label === "Status" && t.status === "di bawah safety"
                     ? "border-[#FECACA] bg-[#FEF2F2]" : "border-[#E4E5E8] bg-[#F8F8F8]"}`}>
                <p className="text-xs text-[#64676C]">{label}</p>
                <p className="font-semibold text-[#1D2434]">{nilai}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[#64676C]">
            {urutanSalah ? "Periode belum sah." : `Belum ada data stok pada ${keteranganPeriode}.`}
          </p>
        )
      } />

      <Kartu idMetrik="stok" judul="Grafik stok vs safety stock"
             keterangan={`Ton bahan baku per hari dibandingkan safety stock yang berlaku — ${keteranganPeriode}.`}
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
              <Line dataKey="stok" name="Stok (ton)" stroke="#1D2434" dot={false} />
              <Line dataKey="safety" name="Safety stock (ton)" stroke="#FF1313"
                    dot={false} strokeDasharray="6 3" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      } />

      <Kartu idMetrik="stok" judul="Hari dengan stok di bawah safety"
             keterangan={`Rasio stok < 100% safety stock, dihitung dalam ${keteranganPeriode}.`}
             anak={
        <>
          <p className="text-sm text-[#1D2434] mb-2">
            <b className={diBawah.length ? "text-[#DC2626]" : "text-[#15803D]"}>
              {diBawah.length}
            </b>{" "}
            dari {jumlahHari} hari berdata{tanpaBatas ? "" : ` (${rentang})`}.
          </p>
          {diBawah.length > 0 && (
            <div className="max-h-60 overflow-y-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[#64676C] border-b">
                    <th className="py-1">Tanggal</th><th className="text-right">Stok ton</th>
                    <th className="text-right">Safety ton</th><th className="text-right">Rasio</th>
                    <th className="text-right">Days</th>
                  </tr>
                </thead>
                <tbody>
                  {diBawah.slice(-60).reverse().map((b: any) => (
                    <tr key={b.tanggal} className="border-b border-[#EDEFF2] bg-[#FEF2F2]">
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
