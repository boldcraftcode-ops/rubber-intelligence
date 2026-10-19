import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, NAMA_BULAN, Pesan, ambilJson, fmtAngka,
  kelasInput, kelasTombolKecil, kirimJson,
} from "../bersama";

const pengisi = () => localStorage.getItem("op-margin.pengisi") || "?";

function BarisEdit({ tahunTarget, r, sesudahSimpan }: {
  tahunTarget: number; r: any; sesudahSimpan: () => void;
}) {
  const [edit, setEdit] = useState(false);
  const [penyesuaian, setPenyesuaian] = useState(String(r.penyesuaian_manual));
  const [effort, setEffort] = useState(String(r.effort));
  const [alasan, setAlasan] = useState(r.alasan ?? "");
  const [galat, setGalat] = useState<string | null>(null);

  const simpan = useMutation({
    mutationFn: () => kirimJson("/api/rencana", {
      tahun_target: tahunTarget, bulan: r.bulan,
      penyesuaian_manual_usc: Number(penyesuaian.replace(",", ".")),
      effort_usc: Number(effort.replace(",", ".")),
      alasan: alasan || null, pengisi: pengisi(),
    }),
    onSuccess: () => { setEdit(false); setGalat(null); sesudahSimpan(); },
    onError: (e: Error) => setGalat(e.message),
  });

  return (
    <>
      <tr className={`border-b border-white/5 ${r.perkiraan ? "bg-amber-400/10" : ""}`}>
        <td className="py-1 font-medium">
          {NAMA_BULAN[r.bulan]}
          {r.perkiraan && (
            <span className="ml-1 rounded bg-amber-400/20 text-amber-400 px-1 py-0.5 text-[10px]">
              perkiraan
            </span>
          )}
        </td>
        {Object.entries(r.margin_per_tahun).map(([t, v]) => (
          <td key={t} className="text-right font-mono text-slate-400">{fmtAngka(v as number)}</td>
        ))}
        <td className="text-right font-mono font-semibold">{fmtAngka(r.rata_rata_dasar)}</td>
        <td className="text-right font-mono">
          {edit ? (
            <input className={`${kelasInput} w-20 text-right`} value={penyesuaian}
                   onChange={(e) => setPenyesuaian(e.target.value)} />
          ) : fmtAngka(r.penyesuaian_manual, 2)}
        </td>
        <td className="text-right font-mono">{fmtAngka(r.sebelum_effort)}</td>
        <td className="text-right font-mono">
          {edit ? (
            <input className={`${kelasInput} w-20 text-right`} value={effort}
                   onChange={(e) => setEffort(e.target.value)} />
          ) : fmtAngka(r.effort, 2)}
        </td>
        <td className="text-right font-mono font-bold text-violet-200">{fmtAngka(r.net_margin)}</td>
        <td className="pl-3 text-slate-400">
          {edit ? (
            <input className={`${kelasInput} w-full`} value={alasan} placeholder="alasan"
                   onChange={(e) => setAlasan(e.target.value)} />
          ) : (r.alasan ?? "-")}
        </td>
        <td className="pl-2">
          {edit ? (
            <span className="flex gap-1">
              <button className={kelasTombolKecil} disabled={simpan.isPending}
                      onClick={() => simpan.mutate()}>simpan</button>
              <button className={kelasTombolKecil} onClick={() => setEdit(false)}>batal</button>
            </span>
          ) : (
            <button className={kelasTombolKecil} onClick={() => setEdit(true)}>ubah</button>
          )}
        </td>
      </tr>
      {galat && (
        <tr><td colSpan={12}><Pesan jenis="error" teks={galat} /></td></tr>
      )}
    </>
  );
}

export default function Perencanaan() {
  const qc = useQueryClient();
  const [tahunTarget, setTahunTarget] = useState(2027);
  const [dasar, setDasar] = useState<number[]>([]);

  const paramDasar = dasar.length ? `?tahun_dasar=${dasar.join(",")}` : "";
  const q = useQuery({
    queryKey: ["rencana", tahunTarget, paramDasar],
    queryFn: () => ambilJson(`/api/rencana/${tahunTarget}${paramDasar}`),
  });

  const tahunTersedia = [2020, 2021, 2022, 2023, 2024, 2025, 2026];
  const dipakai: number[] = q.data?.tahun_dasar ?? [];

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="perencanaan" judul={`Perencanaan OP Margin ${tahunTarget}`}
             keterangan="Pengganti sheet Y27. Nilai dasar tertaut OTOMATIS ke angka aktual (bukan salinan tempelan)."
             anak={
        <>
          <div className="flex flex-wrap items-center gap-3 mb-3 text-sm">
            <label className="font-medium text-slate-300">Tahun target:</label>
            <select className={kelasInput + " max-w-28"} value={tahunTarget}
                    onChange={(e) => { setTahunTarget(Number(e.target.value)); setDasar([]); }}>
              {[2026, 2027, 2028].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <label className="font-medium text-slate-300">Tahun dasar:</label>
            {tahunTersedia.map((t) => (
              <label key={t} className="flex items-center gap-1">
                <input type="checkbox" className="accent-violet-500"
                       checked={dipakai.includes(t)}
                       onChange={(e) => {
                         const baru = e.target.checked
                           ? [...dipakai, t].sort()
                           : dipakai.filter((x) => x !== t);
                         setDasar(baru);
                       }} />
                {t}
              </label>
            ))}
            <span className="text-xs text-slate-500">(default: 4 tahun terakhir)</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-400 border-b">
                  <th className="py-1">Bulan</th>
                  {dipakai.map((t: number) => <th key={t} className="text-right">{t}</th>)}
                  <th className="text-right">Rata-rata dasar</th>
                  <th className="text-right">Penyesuaian</th>
                  <th className="text-right">Sebelum effort</th>
                  <th className="text-right">Effort</th>
                  <th className="text-right">Net margin</th>
                  <th className="pl-3">Alasan</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {q.data?.bulan.map((r: any) => (
                  <BarisEdit key={r.bulan} tahunTarget={tahunTarget} r={r}
                             sesudahSimpan={() => {
                               qc.invalidateQueries({ queryKey: ["rencana"] });
                               qc.invalidateQueries({ queryKey: ["audit-aturan"] });
                             }} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Bulan bertanda "perkiraan" = sebagian tahun dasar belum punya data aktual.
            Penyesuaian & Effort wajib disertai alasan; dasarnya masih [TERBUKA] —
            nilai awal dimuat apa adanya dari template. Semua perubahan tercatat di audit log.
          </p>
        </>
      } />
    </div>
  );
}
