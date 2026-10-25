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
                 className={`rounded-sm border p-3 ${t.terlambat
                   ? "border-[#FDE68A] bg-[#FFFBEB]" : "border-[#E4E5E8] bg-[#F8F8F8]"}`}>
              <p className="text-xs text-[#64676C]">{t.sumber}</p>
              <p className="font-semibold text-[#1D2434]">
                {t.tanggal_terakhir ? fmtTanggal(t.tanggal_terakhir) : "–"}
              </p>
              <p className="text-xs text-[#64676C]">
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
          <p className="text-sm text-[#15803D]">
            Semua hari pembelian punya baris SICOM pada tanggalnya. ✓
          </p>
        ) : (
          <p className="text-sm text-[#1D2434]">
            {q.data?.hari_pembelian_tanpa_sicom.map((t: string) => fmtTanggal(t)).join(", ")}
          </p>
        )
      } />

      <Kartu idMetrik="margin_harian" judul="Lonjakan harga beli harian"
             keterangan="Hari dengan harga beli menyimpang lebih dari 10% dari median bulannya."
             anak={
        q.data?.lonjakan_harga.length === 0 ? (
          <p className="text-sm text-[#15803D]">Tidak ada lonjakan terdeteksi. ✓</p>
        ) : (
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[#64676C] border-b">
                  <th className="py-1">Tanggal</th>
                  <th className="text-right">Harga Rp/kg</th>
                  <th className="text-right">Median bulan</th>
                  <th className="text-right">Deviasi</th>
                </tr>
              </thead>
              <tbody>
                {q.data?.lonjakan_harga.map((l: any) => (
                  <tr key={l.tanggal} className="border-b border-[#EDEFF2] bg-[#FFFBEB]">
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
          <p className="text-sm text-[#15803D]">Tidak ada peringatan. ✓</p>
        ) : (
          <div className="grid gap-3">
            {q.data?.peringatan.map((p: any) => (
              <div key={p.kode} className="rounded-sm border border-[#E4E5E8] p-3">
                <p className="text-sm font-semibold text-[#1D2434]">
                  {p.kode} <span className="font-normal text-[#64676C]">× {p.jumlah}</span>
                </p>
                <ul className="mt-1 list-disc pl-5 text-xs text-[#64676C]">
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
