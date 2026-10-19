import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Kartu, ambilJson, fmtAngka, fmtTanggal, kelasInput, kelasLabel } from "../bersama";

function Geser({ label, nilai, setNilai, min, max, step, satuan }: {
  label: string; nilai: string; setNilai: (v: string) => void;
  min: number; max: number; step: number; satuan: string;
}) {
  return (
    <div>
      <label className={kelasLabel}>{label} ({satuan})</label>
      <div className="flex gap-3 items-center">
        <input type="range" className="flex-1 accent-violet-500" min={min} max={max} step={step}
               value={nilai === "" ? min : Number(nilai)}
               onChange={(e) => setNilai(e.target.value)} />
        <input type="text" inputMode="decimal" className={`${kelasInput} w-28`}
               value={nilai} placeholder="otomatis"
               onChange={(e) => setNilai(e.target.value)} />
      </div>
    </div>
  );
}

export default function Simulasi() {
  const [sicom, setSicom] = useState("");
  const [kurs, setKurs] = useState("");
  const [stok, setStok] = useState("");

  const params = new URLSearchParams();
  const angka = (s: string) => Number(s.replace(/\./g, "").replace(",", "."));
  if (sicom !== "") params.set("sicom", String(angka(sicom)));
  if (kurs !== "") params.set("kurs", String(angka(kurs)));
  if (stok !== "") params.set("stok_ton", String(angka(stok)));
  const url = `/api/simulasi${params.size ? "?" + params.toString() : ""}`;

  const q = useQuery({ queryKey: ["simulasi", url], queryFn: () => ambilJson(url) });
  const r = q.data;

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="simulasi" judul="Simulasi SICOM / kurs / stok"
             keterangan="Geser nilainya dan lihat dampaknya. Kosongkan untuk memakai nilai aktual terakhir. TIDAK ada yang disimpan."
             anak={
        <>
          <div className="grid gap-4 sm:grid-cols-3 mb-4">
            <Geser label="SICOM" satuan="US¢/kg" nilai={sicom} setNilai={setSicom}
                   min={100} max={350} step={0.1} />
            <Geser label="Kurs" satuan="IDR/USD" nilai={kurs} setNilai={setKurs}
                   min={12000} max={22000} step={10} />
            <Geser label="Stok" satuan="ton" nilai={stok} setNilai={setStok}
                   min={0} max={8000} step={10} />
          </div>

          {q.error && (
            <p className="rounded-md bg-red-500/10 border border-red-400/30 px-3 py-2 text-sm text-red-300">
              {(q.error as Error).message}
            </p>
          )}
          {r && r.status === "ATURAN BELUM DIISI" && (
            <p className="rounded-md bg-red-500/10 border border-red-400/30 px-3 py-3 text-sm font-semibold text-red-300">
              ATURAN BELUM DIISI — isi aturan stok → harga dahulu di tab Aturan Harga.
            </p>
          )}
          {r && r.status === "DATA KURANG" && (
            <p className="rounded-md bg-amber-400/10 border border-amber-400/30 px-3 py-3 text-sm text-amber-300">
              {r.pesan}
            </p>
          )}
          {r && r.status === "OK" && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                {[
                  ["Nilai dipakai", `SICOM ${fmtAngka(r.masukan.sicom_usc, 1)} · kurs ${fmtAngka(r.masukan.kurs, 0)} · stok ${fmtAngka(r.masukan.stok_ton, 0)} t`],
                  ["Days / rasio", `${fmtAngka(r.days, 2)} hari · ${fmtAngka(r.rasio_stok * 100, 1)}%`],
                  ["Target efektif", `${fmtAngka(r.target_bulan_usc, 2)} ${r.penyesuaian_usc >= 0 ? "+" : "−"} ${fmtAngka(Math.abs(r.penyesuaian_usc), 2)} = ${fmtAngka(r.target_efektif_usc, 2)}`],
                  ["Harga beli maks", `${fmtAngka(r.harga_beli_maks_usc)} US¢ = Rp ${fmtAngka(r.harga_beli_maks_rp_kg, 0)}/kg`],
                ].map(([label, nilai]) => (
                  <div key={label as string} className="rounded-lg border border-violet-500/20 bg-white/5 p-3">
                    <p className="text-xs text-slate-400">{label}</p>
                    <p className="font-semibold text-slate-100 text-sm">{nilai}</p>
                  </div>
                ))}
              </div>
              {r.harga_aktual && (
                <p className="text-sm text-slate-300">
                  Bila harga beli tetap seperti {fmtTanggal(r.harga_aktual.tanggal)}{" "}
                  (Rp {fmtAngka(r.harga_aktual.harga_rp_per_kg, 0)}/kg ={" "}
                  {fmtAngka(r.harga_aktual.harga_usc_dengan_kurs_simulasi)} US¢ dengan kurs
                  simulasi), margin menjadi{" "}
                  <b className={r.harga_aktual.margin_jika_harga_sama >= 0
                    ? "text-emerald-400" : "text-red-400"}>
                    {fmtAngka(r.harga_aktual.margin_jika_harga_sama)} US¢/kg
                  </b>.
                </p>
              )}
              {r.aturan_contoh && (
                <p className="mt-2 rounded-md bg-red-500/10 border border-red-400/30 px-3 py-2 text-xs text-red-300">
                  Aturan yang dipakai masih CONTOH — hasil simulasi bukan kebijakan resmi.
                </p>
              )}
            </>
          )}
          <p className="mt-3 text-xs text-slate-500">{r?.catatan ?? "Simulasi — tidak ada yang disimpan."}</p>
        </>
      } />
    </div>
  );
}
