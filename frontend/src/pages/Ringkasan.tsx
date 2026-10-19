import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Kartu, NAMA_BULAN, ambilJson, fmtAngka, fmtTanggal, kelasTombolKecil } from "../bersama";

const WARNA = ["#60a5fa", "#fbbf24", "#34d399", "#f87171", "#c084fc",
               "#2dd4bf", "#f472b6"];

/* ---------- telusur: bulan -> hari -> baris & unggahan ---------- */
function Telusur({ tahun, bulan, tutup }: { tahun: number; bulan: number; tutup: () => void }) {
  const [tanggal, setTanggal] = useState<string | null>(null);
  const bln = useQuery({
    queryKey: ["telusur-bulan", tahun, bulan],
    queryFn: () => ambilJson(`/api/telusur/bulan?tahun=${tahun}&bulan=${bulan}`),
  });
  const hr = useQuery({
    queryKey: ["telusur-tanggal", tanggal],
    queryFn: () => ambilJson(`/api/telusur/tanggal?tanggal=${tanggal}`),
    enabled: !!tanggal,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
         onClick={tutup}>
      <div className="max-h-[85vh] w-full max-w-4xl overflow-y-auto rounded-xl bg-[#1a1844] border border-violet-500/30 p-6 shadow-2xl shadow-violet-950/50"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-lg font-semibold text-slate-100">
              Telusur asal angka — {NAMA_BULAN[bulan]} {tahun}
            </h3>
            <p className="text-sm text-slate-400">
              OP Margin bulan = <b>{fmtAngka(bln.data?.op_margin)}</b> US¢/kg.{" "}
              {bln.data?.rumus}
            </p>
          </div>
          <button className={kelasTombolKecil} onClick={tutup}>Tutup</button>
        </div>

        <h4 className="mt-4 mb-1 text-sm font-semibold text-slate-300">
          1. Hari pembelian penyusun bulan ini (klik tanggal untuk lanjut)
        </h4>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-slate-400 border-b">
                <th className="py-1">Tanggal</th><th className="text-right">Qty kg</th>
                <th className="text-right">Amount Rp</th><th className="text-right">Rp/kg</th>
                <th className="text-right">Kurs</th><th className="text-right">SICOM</th>
                <th className="text-right">Margin</th>
              </tr>
            </thead>
            <tbody>
              {bln.data?.hari.map((h: any) => (
                <tr key={h.tanggal}
                    className={`border-b border-white/5 cursor-pointer hover:bg-violet-500/10 ${
                      tanggal === h.tanggal ? "bg-violet-500/25" : ""}`}
                    onClick={() => setTanggal(h.tanggal)}>
                  <td className="py-1 text-violet-300 underline">{fmtTanggal(h.tanggal)}</td>
                  <td className="text-right font-mono">{fmtAngka(h.qty_kg, 0)}</td>
                  <td className="text-right font-mono">{fmtAngka(h.amount_rp, 0)}</td>
                  <td className="text-right font-mono">{fmtAngka(h.harga_rp_per_kg, 2)}</td>
                  <td className="text-right font-mono">{fmtAngka(h.kurs, 0)}</td>
                  <td className="text-right font-mono">{fmtAngka(h.sicom, 2)}</td>
                  <td className="text-right font-mono">{fmtAngka(h.margin)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {tanggal && (
          <>
            <h4 className="mt-4 mb-1 text-sm font-semibold text-slate-300">
              2. Baris pembelian & tiket pada {fmtTanggal(tanggal)} + unggahan asal
            </h4>
            {hr.data?.pembelian.map((p: any, i: number) => (
              <div key={i} className="mb-2 rounded-md border border-violet-500/20 p-2 text-xs">
                <b>Pembelian</b>: {p.item_code}
                {p.kode_vendor ? ` / ${p.kode_vendor}` : ""}{p.ticket_no ? ` / ${p.ticket_no}` : ""} —{" "}
                qty {fmtAngka(p.qty_kering_kg, 0)} kg, Amount Rp {fmtAngka(p.amount_rp, 0)}
                <div className="text-slate-400">
                  Asal: unggahan #{p.unggahan?.id} · {p.unggahan?.nama_file} · oleh{" "}
                  {p.unggahan?.pengunggah} · {p.unggahan?.waktu?.replace("T", " ")} UTC
                </div>
              </div>
            ))}
            {hr.data?.sicom && (
              <div className="mb-2 rounded-md border border-violet-500/20 p-2 text-xs">
                <b>SICOM</b>: {fmtAngka(hr.data.sicom.usc_per_kg, 2)} US¢/kg ·{" "}
                {hr.data.sicom.sumber ?? "-"}
                {hr.data.sicom.unggahan &&
                  ` · unggahan #${hr.data.sicom.unggahan.id} oleh ${hr.data.sicom.unggahan.pengunggah}`}
              </div>
            )}
            {hr.data?.tiket.length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-400 border-b">
                    <th className="py-1">Tiket (baris)</th><th>Vendor</th><th>Grade</th>
                    <th className="text-right">Wet kg</th><th className="text-right">DRC %</th>
                    <th className="text-right">Dry kg</th><th>Unggahan asal</th>
                  </tr>
                </thead>
                <tbody>
                  {hr.data.tiket.map((t: any, i: number) => (
                    <tr key={i} className="border-b border-white/5">
                      <td className="py-1">{t.ticket_no} ({t.line_seq})</td>
                      <td>{t.kode_vendor}</td><td>{t.item_code}</td>
                      <td className="text-right font-mono">{fmtAngka(t.wet_kg, 0)}</td>
                      <td className="text-right font-mono">{fmtAngka(t.drc_pct, 1)}</td>
                      <td className="text-right font-mono">{fmtAngka(t.dry_kg, 0)}</td>
                      <td className="text-slate-400">
                        #{t.unggahan?.id} · {t.unggahan?.pengunggah}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-xs text-slate-500">
                Tidak ada baris tiket pada tanggal ini (data tiket historis belum diunggah).
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ---------- elemen OP Margin: RM Stock-Intake vs Pricing (seperti Excel) ---------- */
function KartuElemen() {
  const [dari, setDari] = useState("");
  const [sampai, setSampai] = useState("");
  const params = new URLSearchParams();
  if (dari) params.set("dari", dari);
  if (sampai) params.set("sampai", sampai);
  const url = `/api/ringkasan-elemen${params.size ? "?" + params.toString() : ""}`;

  const q = useQuery({
    queryKey: ["ringkasan-elemen", url],
    queryFn: () => ambilJson(url),
  });

  return (
    <Kartu idMetrik="elemen_op_margin" judul="RM Stock – Intake vs Pricing"
           keterangan="Elemen pemengaruh OP Margin per bulan, disamakan dengan Excel: batang = ton (sumbu kiri), garis = US¢/kg (sumbu kanan)."
           urlEkspor={url}
           anak={
      <>
        <div className="flex flex-wrap items-end gap-3 mb-3 text-xs">
          <div>
            <label className="block text-slate-400 mb-1">Dari bulan</label>
            <input type="month" className="rounded-md border border-violet-400/30 bg-[#0b0a26]/80 px-2 py-1.5 text-slate-100"
                   value={dari} onChange={(e) => setDari(e.target.value)} />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Sampai bulan</label>
            <input type="month" className="rounded-md border border-violet-400/30 bg-[#0b0a26]/80 px-2 py-1.5 text-slate-100"
                   value={sampai} onChange={(e) => setSampai(e.target.value)} />
          </div>
          {(dari || sampai) && (
            <button className="rounded-md border border-violet-400/30 bg-white/5 px-2.5 py-1.5 text-slate-300 hover:bg-violet-500/20"
                    onClick={() => { setDari(""); setSampai(""); }}>
              tampilkan semua periode
            </button>
          )}
          <span className="text-slate-500">
            {q.data ? `${q.data.baris.length} bulan ditampilkan` : ""}
          </span>
        </div>
        <div className="h-96">
          <ResponsiveContainer>
            <ComposedChart data={q.data?.baris ?? []}
                           margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" fontSize={10} minTickGap={18} />
              <YAxis yAxisId="ton" fontSize={10}
                     label={{ value: "ton", angle: -90, position: "insideLeft",
                              fontSize: 11, fill: "#a5b4fc" }} />
              <YAxis yAxisId="usc" orientation="right" fontSize={10}
                     domain={["auto", "auto"]}
                     label={{ value: "US¢/kg", angle: 90, position: "insideRight",
                              fontSize: 11, fill: "#a5b4fc" }} />
              <Tooltip formatter={(v: any, nama: any) => [fmtAngka(v as number, 2), nama]} />
              <Legend />
              <Bar yAxisId="ton" dataKey="intake_ton" name="Intake"
                   fill="#818cf8" opacity={0.85} />
              <Bar yAxisId="ton" dataKey="rm_stock_ton" name="RM Stock"
                   fill="#2dd4bf" opacity={0.85} />
              <Line yAxisId="ton" dataKey="safety_ton" name="Safety Level Stock"
                    stroke="#fbbf24" strokeDasharray="6 3" dot={false}
                    type="stepAfter" strokeWidth={1.5} />
              <Line yAxisId="usc" dataKey="sicom" name="SICOM"
                    stroke="#f8fafc" dot={false} strokeWidth={2} connectNulls />
              <Line yAxisId="usc" dataKey="op_price" name="OP Price"
                    stroke="#f472b6" dot={false} strokeWidth={2} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-3 max-h-56 overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-slate-400 border-b">
                <th className="py-1">Date</th>
                <th className="text-right">RM Stock</th>
                <th className="text-right">Intake</th>
                <th className="text-right">Safety</th>
                <th className="text-right">SICOM</th>
                <th className="text-right">OP Price</th>
                <th className="pl-2">Sumber intake</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.baris.map((b: any) => (
                <tr key={b.label} className={`border-b border-white/5 ${
                    b.stok_sebagian ? "bg-amber-400/10" : ""}`}>
                  <td className="py-1">{b.label}{b.stok_sebagian ? " *" : ""}</td>
                  <td className="text-right font-mono">{fmtAngka(b.rm_stock_ton, 3)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.intake_ton, 3)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.safety_ton, 1)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.sicom, 4)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.op_price, 4)}</td>
                  <td className="pl-2 text-slate-500">{b.sumber_intake ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {q.data?.catatan.map((c: string, i: number) => (
          <p key={i} className="mt-2 rounded-md bg-amber-400/10 border border-amber-400/30 px-3 py-2 text-xs text-amber-300">
            {c}
          </p>
        ))}
      </>
    } />
  );
}

/* ---------- grafik margin: tren vs target & banding antar tahun ---------- */
function KartuGrafikMargin() {
  const [mode, setMode] = useState<"tren" | "banding">("tren");
  const bulanan = useQuery({
    queryKey: ["margin-bulanan-grafik"],
    queryFn: () => ambilJson("/api/kartu/margin-bulanan"),
  });
  const antar = useQuery({
    queryKey: ["grafik-margin"],
    queryFn: () => ambilJson("/api/grafik/margin-antar-tahun"),
  });

  const tahunSemua: number[] = antar.data?.map((d: any) => d.tahun) ?? [];
  const [pilih, setPilih] = useState<number[] | null>(null);
  const tahunDipilih = pilih ?? tahunSemua.slice(-2); // bawaan: 2 tahun terakhir

  const dataTren = (bulanan.data?.baris ?? []).map((b: any) => ({
    label: `${NAMA_BULAN[b.bulan]}-${String(b.tahun).slice(2)}`,
    margin: b.op_margin,
    target: b.target,
    capai: b.target !== null && b.op_margin !== null && b.op_margin >= b.target,
  }));
  const adaTarget = dataTren.filter((d: any) => d.target !== null);
  const capai = adaTarget.filter((d: any) => d.capai).length;

  const dataBanding = Array.from({ length: 12 }, (_, i) => {
    const titik: any = { bulan: NAMA_BULAN[i + 1] };
    antar.data?.forEach((th: any) => {
      if (tahunDipilih.includes(th.tahun)) titik[th.tahun] = th.data[i].margin;
    });
    return titik;
  });

  return (
    <Kartu idMetrik="margin_bulanan" judul="OP Margin bulanan vs target"
           keterangan="Tujuan grafik: menjawab “apakah margin tiap bulan mencapai target, dan bagaimana trennya?”"
           urlEkspor="/api/kartu/margin-bulanan"
           anak={
      <>
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {([["tren", "Tren & capaian target"], ["banding", "Banding antar tahun"]] as const)
            .map(([id, label]) => (
            <button key={id}
              className={`rounded-md px-3 py-1.5 text-xs font-medium ${mode === id
                ? "bg-violet-600 text-white" : "bg-white/10 text-slate-300 hover:bg-white/20"}`}
              onClick={() => setMode(id)}>
              {label}
            </button>
          ))}
          {mode === "tren" && adaTarget.length > 0 && (
            <span className="ml-auto text-xs text-slate-400">
              <b className="text-emerald-400">{capai}</b> dari {adaTarget.length} bulan
              mencapai target ({fmtAngka((capai / adaTarget.length) * 100, 0)}%)
            </span>
          )}
        </div>

        {mode === "tren" ? (
          <>
            <div className="h-80">
              <ResponsiveContainer>
                <ComposedChart data={dataTren}
                               margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" fontSize={10} minTickGap={26} />
                  <YAxis fontSize={11}
                         label={{ value: "US¢/kg", angle: -90, position: "insideLeft",
                                  fontSize: 11, fill: "#a5b4fc" }} />
                  <Tooltip content={({ payload, label }) => {
                    const p: any = payload?.[0]?.payload;
                    if (!p) return null;
                    return (
                      <div className="rounded-md bg-[#15143a] border border-violet-500/30 p-2 text-xs shadow">
                        <b>{label}</b><br />
                        OP Margin: <b>{fmtAngka(p.margin)}</b> US¢/kg<br />
                        Target: {fmtAngka(p.target, 1)}<br />
                        {p.target !== null && (p.capai
                          ? <span className="text-emerald-400">✓ mencapai target (+{fmtAngka(p.margin - p.target, 2)})</span>
                          : <span className="text-red-400">✗ di bawah target ({fmtAngka(p.margin - p.target, 2)})</span>)}
                      </div>
                    );
                  }} />
                  <ReferenceLine y={0} stroke="#64748b" />
                  <Bar dataKey="margin" name="OP Margin" maxBarSize={14}>
                    {dataTren.map((d: any, i: number) => (
                      <Cell key={i} fill={d.target === null ? "#818cf8"
                        : d.capai ? "#34d399" : "#fb7185"} />
                    ))}
                  </Bar>
                  <Line dataKey="target" name="Target" stroke="#fbbf24"
                        strokeDasharray="6 3" dot={false} type="stepAfter"
                        strokeWidth={1.8} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Cara baca: satu batang = satu bulan (urut waktu 2020 → sekarang).
              <span className="text-emerald-400"> ■ hijau</span> = margin mencapai
              target · <span className="text-red-400">■ merah</span> = di bawah
              target · <span className="text-amber-400">- - kuning</span> = garis
              target. Arahkan kursor ke batang untuk angka persisnya.
            </p>
          </>
        ) : (
          <>
            <div className="flex flex-wrap gap-2 mb-2 text-xs">
              <span className="text-slate-400">Pilih tahun yang dibandingkan:</span>
              {tahunSemua.map((th) => (
                <label key={th} className="flex items-center gap-1 text-slate-300">
                  <input type="checkbox" className="accent-violet-500"
                         checked={tahunDipilih.includes(th)}
                         onChange={(e) => setPilih(e.target.checked
                           ? [...tahunDipilih, th].sort()
                           : tahunDipilih.filter((x) => x !== th))} />
                  {th}
                </label>
              ))}
            </div>
            <div className="h-80">
              <ResponsiveContainer>
                <LineChart data={dataBanding}
                           margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="bulan" fontSize={12} />
                  <YAxis fontSize={11}
                         label={{ value: "US¢/kg", angle: -90, position: "insideLeft",
                                  fontSize: 11, fill: "#a5b4fc" }} />
                  <Tooltip formatter={(v: any) => fmtAngka(v as number)} />
                  <Legend />
                  {antar.data?.filter((th: any) => tahunDipilih.includes(th.tahun))
                    .map((th: any, i: number) => (
                    <Line key={th.tahun} dataKey={th.tahun} type="monotone"
                          stroke={WARNA[tahunSemua.indexOf(th.tahun) % WARNA.length]}
                          dot={{ r: 2.5 }} connectNulls
                          strokeWidth={th.tahun === Math.max(...tahunDipilih) ? 2.5 : 1.5} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Cara baca: membandingkan pola bulanan beberapa tahun (mis. apakah
              margin biasanya turun di pertengahan tahun). Centang maksimal 2–3
              tahun supaya tetap mudah dibaca; garis paling tebal = tahun terbaru
              yang dipilih.
            </p>
          </>
        )}
      </>
    } />
  );
}

/* ---------- halaman ---------- */
export default function Ringkasan() {
  const tahunQ = useQuery({ queryKey: ["tahun"], queryFn: () => ambilJson("/api/tahun") });
  const [tahun, setTahun] = useState<number | null>(null);
  const t = tahun ?? (tahunQ.data ? tahunQ.data[tahunQ.data.length - 1] : null);

  const ringkas = useQuery({
    queryKey: ["ringkasan", t],
    queryFn: () => ambilJson(`/api/ringkasan/${t}`),
    enabled: t !== null,
  });
  const [telusur, setTelusur] = useState<number | null>(null);

  const label = [
    ["sicom", "SICOM", 4], ["op_price", "OP Price", 4], ["op_margin", "OP Margin", 4],
    ["ton", "Ton (kering)", 3], ["target", "Target", 1],
    ["pencapaian", "Pencapaian", 1], ["vs_target", "vs Target", 4],
  ] as const;

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="ringkasan" judul={`Ringkasan OP Margin ${t ?? ""}`}
             keterangan="US¢/kg, basis berat kering — meniru Excel lama. Klik angka OP Margin untuk menelusuri asal angkanya."
             urlEkspor={t ? `/api/ringkasan/${t}` : undefined}
             anak={
        <>
          <div className="mb-3 flex gap-1 flex-wrap">
            {tahunQ.data?.map((th: number) => (
              <button key={th}
                className={`rounded-md px-3 py-1 text-sm ${th === t
                  ? "bg-violet-600 text-white" : "bg-white/10 text-slate-300 hover:bg-white/20"}`}
                onClick={() => setTahun(th)}>
                {th}
              </button>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-400 border-b">
                  <th className="py-1 pr-2"> </th>
                  {ringkas.data?.bulan.map((b: any) => (
                    <th key={b.bulan} className="text-right px-1">{NAMA_BULAN[b.bulan]}</th>
                  ))}
                  <th className="text-right px-1 font-semibold">Avg YTD</th>
                  <th className="text-right px-1">Tertimbang</th>
                </tr>
              </thead>
              <tbody>
                {label.map(([kunci, nama, des]) => (
                  <tr key={kunci} className="border-b border-white/5">
                    <td className="py-1 pr-2 font-medium text-slate-300 whitespace-nowrap">{nama}</td>
                    {ringkas.data?.bulan.map((b: any) => (
                      <td key={b.bulan}
                          className={`text-right px-1 font-mono ${
                            kunci === "op_margin" ? "text-violet-300 cursor-pointer underline" : ""} ${
                            b.catatan_koreksi && kunci === "op_margin" ? "bg-amber-400/10" : ""}`}
                          title={kunci === "op_margin" ? (b.catatan_koreksi ?? "klik untuk telusur") : undefined}
                          onClick={() => kunci === "op_margin" && setTelusur(b.bulan)}>
                        {kunci === "pencapaian"
                          ? (b.pencapaian !== null ? fmtAngka(b.pencapaian * 100, 1) + "%" : "–")
                          : fmtAngka(b[kunci], des)}
                      </td>
                    ))}
                    <td className="text-right px-1 font-mono font-semibold">
                      {kunci === "op_margin" ? fmtAngka(ringkas.data?.avg_ytd_sederhana) : ""}
                    </td>
                    <td className="text-right px-1 font-mono text-slate-400">
                      {kunci === "op_margin" ? fmtAngka(ringkas.data?.avg_ytd_tertimbang) : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {ringkas.data?.catatan.map((c: string, i: number) => (
            <p key={i} className="mt-2 rounded-md bg-amber-400/10 border border-amber-400/30 px-3 py-2 text-xs text-amber-300">
              Catatan koreksi: {c}
            </p>
          ))}
          <p className="mt-2 text-xs text-slate-500">
            Avg YTD = rata-rata sederhana bulan berdata (resmi, seperti Excel);
            kolom "Tertimbang" = rata-rata tertimbang tonase (informasi).
          </p>
        </>
      } />

      <KartuGrafikMargin />

      <KartuElemen />

      {telusur !== null && t !== null && (
        <Telusur tahun={t} bulan={telusur} tutup={() => setTelusur(null)} />
      )}
    </div>
  );
}
