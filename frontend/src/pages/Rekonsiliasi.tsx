import { useQuery } from "@tanstack/react-query";
import { Kartu, ambilJson, fmtAngka, fmtTanggal } from "../bersama";

export default function Rekonsiliasi() {
  const q = useQuery({ queryKey: ["rekonsiliasi"], queryFn: () => ambilJson("/api/rekonsiliasi") });
  const takCocok = q.data?.harian.filter((h: any) => !h.cocok) ?? [];

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="rekonsiliasi" judul="Selisih yang sudah diketahui"
             keterangan="Tiket vs angka lama (Excel). Tiket = sumber resmi tonase."
             urlEkspor="/api/rekonsiliasi"
             anak={
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[#64676C] border-b">
                <th className="py-1">Periode</th>
                <th className="text-right">Tiket (ton)</th>
                <th className="text-right">Excel lama (ton)</th>
                <th className="text-right">Selisih (ton)</th>
                <th className="pl-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.diketahui.map((d: any) => (
                <tr key={d.periode} className="border-b border-[#EDEFF2]">
                  <td className="py-1.5 font-medium">{d.periode}</td>
                  <td className="text-right font-mono">{fmtAngka(d.tiket_ton, 3)}</td>
                  <td className="text-right font-mono">{fmtAngka(d.excel_ton, 3)}</td>
                  <td className="text-right font-mono font-semibold text-[#B45309]">
                    {fmtAngka(d.selisih_ton, 3)}
                  </td>
                  <td className="pl-3 text-xs text-[#64676C]">{d.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {q.data?.catatan.map((c: string, i: number) => (
            <p key={i} className="mt-2 rounded-sm bg-[#F8F8F8] border border-[#E4E5E8] px-3 py-2 text-xs text-[#1D2434]">
              {c}
            </p>
          ))}
        </>
      } />

      <Kartu idMetrik="rekonsiliasi" judul="Pemeriksaan harian: tiket vs pembelian"
             keterangan="Jumlah Dry tiket per tanggal dibandingkan Quantity pembelian (hanya tanggal yang punya data tiket)."
             anak={
        q.data?.harian.length === 0 ? (
          <p className="text-sm text-[#64676C]">
            Belum ada data tiket historis untuk dibandingkan — unggah ekspor
            "Master Data" terlebih dahulu.
          </p>
        ) : (
          <>
            <p className="mb-2 text-sm text-[#1D2434]">
              {q.data?.harian.length} tanggal diperiksa ·{" "}
              <b className={takCocok.length ? "text-[#B45309]" : "text-[#15803D]"}>
                {takCocok.length} tidak cocok
              </b> (toleransi 1 kg)
            </p>
            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[#64676C] border-b">
                    <th className="py-1">Tanggal</th>
                    <th className="text-right">Dry tiket (kg)</th>
                    <th className="text-right">Qty pembelian (kg)</th>
                    <th className="text-right">Selisih (kg)</th>
                  </tr>
                </thead>
                <tbody>
                  {q.data?.harian.map((h: any) => (
                    <tr key={h.tanggal}
                        className={`border-b border-[#EDEFF2] ${h.cocok ? "" : "bg-[#FFFBEB]"}`}>
                      <td className="py-1">{fmtTanggal(h.tanggal)}</td>
                      <td className="text-right font-mono">{fmtAngka(h.dry_tiket_kg, 0)}</td>
                      <td className="text-right font-mono">{fmtAngka(h.qty_pembelian_kg, 0)}</td>
                      <td className="text-right font-mono">{fmtAngka(h.selisih_kg, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )
      } />
    </div>
  );
}
