import { Fragment, ReactNode, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, LabelList, Legend, Line,
  LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Kartu, KartuMuatSaatDiminta, KepalaPanel, NAMA_BULAN, Panel5W1H,
  PilihRentangBulan, TombolRefreshKartu, ambilJson, fmtAngka, fmtTanggal,
  kelasTombolAnalisa, kelasTombolKecil, pesanGalat, urlApi, useQueryKartu,
  KerangkaMuatKartu, KerangkaMuatTabel, PengukurAmbang, useCountUp } from "../bersama";
import { useBahasa } from "../i18n";

import { AlatGrafik } from "../GrafikTools";

/* Palet korporat (navy / merah / abu) untuk seri grafik. */
const WARNA = ["#1D2434", "#FF1313", "#64676C", "#3B82F6", "#EAB308",
               "#F97316", "#0F766E"];

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
      <div className="max-h-[85vh] w-full max-w-4xl overflow-y-auto rounded-sm bg-white border border-[#E4E5E8] p-6 shadow-xl shadow-[#1D2434]/10"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-lg font-semibold text-[#1D2434]">
              Telusur asal angka — {NAMA_BULAN[bulan]} {tahun}
            </h3>
            <p className="text-sm text-[#64676C]">
              OP Margin bulan = <b>{fmtAngka(bln.data?.op_margin)}</b> US¢/kg.{" "}
              {bln.data?.rumus}
            </p>
          </div>
          <button className={kelasTombolKecil} onClick={tutup}>Tutup</button>
        </div>

        <h4 className="mt-4 mb-1 text-sm font-semibold text-[#1D2434]">
          1. Hari pembelian penyusun bulan ini (klik tanggal untuk lanjut)
        </h4>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[#64676C] border-b">
                <th className="py-1">Tanggal</th><th className="text-right">Qty kg</th>
                <th className="text-right">Amount Rp</th><th className="text-right">Rp/kg</th>
                <th className="text-right">Kurs</th><th className="text-right">SICOM</th>
                <th className="text-right">Margin</th>
              </tr>
            </thead>
            <tbody>
              {bln.data?.hari.map((h: any) => (
                <tr key={h.tanggal}
                    className={`border-b border-[#EDEFF2] cursor-pointer hover:bg-[#FFF1F1] ${
                      tanggal === h.tanggal ? "bg-[#FFE4E4]" : ""}`}
                    onClick={() => setTanggal(h.tanggal)}>
                  <td className="py-1 text-[#FF1313] underline">{fmtTanggal(h.tanggal)}</td>
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
            <h4 className="mt-4 mb-1 text-sm font-semibold text-[#1D2434]">
              2. Baris pembelian & tiket pada {fmtTanggal(tanggal)} + unggahan asal
            </h4>
            {hr.data?.pembelian.map((p: any, i: number) => (
              <div key={i} className="mb-2 rounded-sm border border-[#E4E5E8] p-2 text-xs">
                <b>Pembelian</b>: {p.item_code}
                {p.kode_vendor ? ` / ${p.kode_vendor}` : ""}{p.ticket_no ? ` / ${p.ticket_no}` : ""} —{" "}
                qty {fmtAngka(p.qty_kering_kg, 0)} kg, Amount Rp {fmtAngka(p.amount_rp, 0)}
                <div className="text-[#64676C]">
                  Asal: unggahan #{p.unggahan?.id} · {p.unggahan?.nama_file} · oleh{" "}
                  {p.unggahan?.pengunggah} · {p.unggahan?.waktu?.replace("T", " ")} UTC
                </div>
              </div>
            ))}
            {hr.data?.sicom && (
              <div className="mb-2 rounded-sm border border-[#E4E5E8] p-2 text-xs">
                <b>SICOM</b>: {fmtAngka(hr.data.sicom.usc_per_kg, 2)} US¢/kg ·{" "}
                {hr.data.sicom.sumber ?? "-"}
                {hr.data.sicom.unggahan &&
                  ` · unggahan #${hr.data.sicom.unggahan.id} oleh ${hr.data.sicom.unggahan.pengunggah}`}
              </div>
            )}
            {hr.data?.tiket.length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[#64676C] border-b">
                    <th className="py-1">Tiket (baris)</th><th>Vendor</th><th>Grade</th>
                    <th className="text-right">Wet kg</th><th className="text-right">DRC %</th>
                    <th className="text-right">Dry kg</th><th>Unggahan asal</th>
                  </tr>
                </thead>
                <tbody>
                  {hr.data.tiket.map((t: any, i: number) => (
                    <tr key={i} className="border-b border-[#EDEFF2]">
                      <td className="py-1">{t.ticket_no} ({t.line_seq})</td>
                      <td>{t.kode_vendor}</td><td>{t.item_code}</td>
                      <td className="text-right font-mono">{fmtAngka(t.wet_kg, 0)}</td>
                      <td className="text-right font-mono">{fmtAngka(t.drc_pct, 1)}</td>
                      <td className="text-right font-mono">{fmtAngka(t.dry_kg, 0)}</td>
                      <td className="text-[#64676C]">
                        #{t.unggahan?.id} · {t.unggahan?.pengunggah}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-xs text-[#64676C]">
                Tidak ada baris tiket pada tanggal ini (data tiket historis belum diunggah).
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ---------- panel RCA 5 Why: angka dihitung server dari periode kartu ---------- */
function PanelRCA({ url, tutup }: { url: string; tutup: () => void }) {
  const q = useQuery({ queryKey: ["rca-rm-stock-intake-pricing", url], queryFn: () => ambilJson(url) });
  const fmt = (v: number | null | undefined, d = 2) => v == null ? "—" : fmtAngka(v, d);
  const delta = (v: number | null | undefined, d = 2) =>
    v == null ? "—" : `${v > 0 ? "+" : ""}${fmtAngka(v, d)}`;
  const bagian = (judul: string, isi: ReactNode) => (
    <section className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
      <h4 className="mb-2 text-sm font-semibold text-[#FF1313]">{judul}</h4>{isi}
    </section>
  );
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3" onClick={tutup}>
      <div className="max-h-[92vh] w-full max-w-6xl overflow-y-auto rounded-sm border border-[#E4E5E8] bg-white p-5 shadow-xl"
           onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-[#1D2434]">Analisa Akar Masalah — RM Stock, Intake vs Pricing</h3>
            <p className="text-sm text-[#64676C]">Berbasis angka pada periode yang tampil. FAKTA dipisahkan dari HIPOTESIS.</p>
          </div>
          <button className={kelasTombolKecil} onClick={tutup}>Tutup</button>
        </div>
        {q.isLoading && <p className="py-6 text-sm text-[#64676C]">Menghitung analisa dari data periode…</p>}
        {q.error && <p className="rounded-sm border border-[#FECACA] bg-[#FEF2F2] p-3 text-sm text-[#1D2434]">{pesanGalat(q.error)}</p>}
        {q.data && !q.data.ada_data && <p className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3 text-sm text-[#1D2434]">{q.data.kesimpulan}</p>}
        {q.data?.ada_data && (
          <div className="grid gap-3">
            {bagian("1. Kesimpulan", <p className="text-sm leading-relaxed text-[#1D2434]">{q.data.kesimpulan}</p>)}
            {bagian("2. Temuan data (FAKTA)", <ul className="grid list-disc gap-1 pl-5 text-sm leading-relaxed text-[#1D2434]">
              {q.data.temuan_data.map((x: string, i: number) => <li key={i}>{x}</li>)}
            </ul>)}
            {bagian("3. Anomali", <ul className="grid gap-2">
              {q.data.anomali.map((x: any, i: number) => (
                <li key={i} className="border-l-2 border-[#FF1313] pl-3 text-sm text-[#1D2434]">
                  <b>{x.bulan} · {x.jenis}:</b> {x.fakta}
                </li>
              ))}
            </ul>)}
            {bagian("4. Root cause — 5 Why", <ol className="grid gap-2">
              {q.data.root_cause.map((x: any) => (
                <li key={x.level} className="rounded-sm border border-[#E4E5E8] bg-white p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-[#1D2434]">Why {x.level}/5 — {x.pertanyaan}</span>
                    <span className={`rounded-sm px-2 py-0.5 text-[11px] font-semibold ${x.jenis === "FAKTA" ? "bg-[#E9EDF3] text-[#1D2434]" : "bg-[#FFF1F1] text-[#1D2434]"}`}>{x.jenis}</span>
                    {x.jenis === "HIPOTESIS" && <span className="text-xs text-[#64676C]">Keyakinan: {x.keyakinan}</span>}
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-[#1D2434]">{x.jawaban}</p>
                  {x.jenis === "HIPOTESIS" && <p className="mt-1 text-xs text-[#64676C]"><b>Data pembanding:</b> {x.data_dibutuhkan}</p>}
                </li>
              ))}
            </ol>)}
            {bagian("5. Rekomendasi", <ol className="grid list-decimal gap-2 pl-5">
              {q.data.rekomendasi.map((x: any, i: number) => (
                <li key={i} className="text-sm leading-relaxed text-[#1D2434]"><b>{x.aksi}</b><br />Target: {x.target_angka}<br /><span className="text-[#64676C]">Waktu evaluasi: {x.evaluasi}</span></li>
              ))}
            </ol>)}
            {bagian("6. Keterbatasan & data tambahan", <ul className="grid list-disc gap-1 pl-5 text-sm leading-relaxed text-[#1D2434]">
              {q.data.keterbatasan.map((x: string, i: number) => <li key={i}>{x}</li>)}
              <li>Untuk menguji akar sebab: tambahkan data harga pesaing/pengepul, pemakaian dan produksi bulanan, cuaca, stok terverifikasi, serta tiket per pemasok/wilayah.</li>
            </ul>)}
            {bagian("Perhitungan bulanan (MoM)", <>
              <p className="mb-2 text-xs text-[#64676C]">Δ MoM ditampilkan hanya untuk bulan kalender berurutan. Estimasi nilai margin = intake ton × margin US¢/kg × 10; bukan laba bersih.</p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1500px] border-collapse text-xs">
                  <thead><tr className="border-b border-[#E4E5E8] text-left text-[#64676C]">
                    {["Bulan", "Intake ton", "Δ Intake ton", "SICOM", "Δ SICOM", "OP Price", "Δ OP Price", "Margin", "Δ Margin", "Estimasi margin US$", "RM Stock ton", "Status stok", "Gap safety ton", "Cover hari", "Sumber intake"].map(h => <th key={h} className="px-2 py-2">{h}</th>)}
                  </tr></thead>
                  <tbody>{q.data.per_bulan.map((r: any) => (
                    <tr key={`${r.tahun}-${r.bulan}`} className="border-b border-[#E4E5E8] text-[#1D2434]">
                      <td className="px-2 py-2 font-semibold">{r.label}</td>
                      <td className="px-2 text-right">{fmt(r.intake_ton, 3)}</td><td className="px-2 text-right">{r.moM_tersedia ? delta(r.delta_intake_ton, 3) : "—"}{r.moM_tersedia && r.delta_intake_ton_pct != null ? ` (${delta(r.delta_intake_ton_pct)}%)` : ""}</td>
                      <td className="px-2 text-right">{fmt(r.sicom, 3)}</td><td className="px-2 text-right">{r.moM_tersedia ? delta(r.delta_sicom, 3) : "—"}</td>
                      <td className="px-2 text-right">{fmt(r.op_price, 3)}</td><td className="px-2 text-right">{r.moM_tersedia ? delta(r.delta_op_price, 3) : "—"}</td>
                      <td className="px-2 text-right">{fmt(r.op_margin, 3)}</td><td className="px-2 text-right">{r.moM_tersedia ? delta(r.delta_op_margin, 3) : "—"}</td>
                      <td className="px-2 text-right">{fmt(r.estimasi_total_margin_usd, 2)}</td><td className="px-2 text-right">{fmt(r.rm_stock_ton, 3)}</td><td className="px-2">{r.rm_stock_ton == null ? "—" : r.stok_sebagian ? "Sebagian" : "Akhir bulan"}</td>
                      <td className="px-2 text-right">{fmt(r.selisih_stok_safety_ton, 3)}</td><td className="px-2 text-right">{fmt(r.days_of_cover, 2)}</td>
                      <td className="px-2">{r.sumber_intake || "—"}{r.keandalan_intake.startsWith("lebih rendah") ? " · keandalan lebih rendah" : ""}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </>)}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- satuan berat kartu RM Stock ---------- */
type SatuanBerat = "mt" | "kg";

/* Sumber angka di API adalah MT (*_ton). kg = MT x 1.000; konversi dilakukan
   di layar supaya grafik/tabel tidak bergantung pada versi API yang lama. */
const keBerat = (ton: number | null | undefined, satuan: SatuanBerat) =>
  ton == null ? null : ton * (satuan === "kg" ? 1000 : 1);

/* Sel tonase: angka utama memakai satuan terpilih, satuan pasangannya ditulis
   kecil di bawahnya — jadi MT dan kg selalu terbaca tanpa menambah kolom. */
function SelBerat({ ton, satuan }: { ton: number | null | undefined; satuan: SatuanBerat }) {
  const lainnya: SatuanBerat = satuan === "kg" ? "mt" : "kg";
  return (
    <td className="whitespace-nowrap border-r border-[#EDEFF2] px-3 py-2 text-right font-mono tabular-nums last:border-r-0">
      <span>{fmtAngka(keBerat(ton, satuan), satuan === "kg" ? 0 : 3)}</span>
      <span className="block text-[10px] font-normal text-[#9AA0A6]">
        {fmtAngka(keBerat(ton, lainnya), lainnya === "kg" ? 0 : 3)} {lainnya === "kg" ? "kg" : "MT"}
      </span>
    </td>
  );
}

/* ---------- elemen OP Margin: RM Stock-Intake vs Pricing (seperti Excel) ---------- */
function KartuElemen() {
  const { t } = useBahasa();
  const [dari, setDari] = useState("");
  const [sampai, setSampai] = useState("");
  const [tampilkanCatatan, setTampilkanCatatan] = useState(false);
  const [panel, setPanel] = useState<null | "5w1h" | "bridge" | "doc" | "rca">(null);
  const [satuan, setSatuan] = useState<SatuanBerat>("mt");
  const labelSatuan = satuan === "kg" ? "kg" : "MT";
  const params = new URLSearchParams();
  if (dari) params.set("dari", dari);
  if (sampai) params.set("sampai", sampai);
  const qs = params.size ? "?" + params.toString() : "";
  const url = `/api/ringkasan-elemen${qs}`;

  // Periode analisa: bawaan = filter kartu (bulan/tahun yang tampil di grafik),
  // tapi bisa diubah langsung di panel (periode awal & akhir).
  const [periA, setPeriA] = useState("");
  const [periB, setPeriB] = useState("");
  const awalAnalisa = periA || dari;
  const akhirAnalisa = periB || sampai;
  const qsPeriode = (() => {
    const p = new URLSearchParams();
    if (awalAnalisa) p.set("dari", awalAnalisa);
    if (akhirAnalisa) p.set("sampai", akhirAnalisa);
    return p.size ? "?" + p.toString() : "";
  })();
  const ubahPeriode = (a: string, b: string) => { setPeriA(a); setPeriB(b); };
  const urlBridge = `/api/margin-bridge${qsPeriode}`;
  const urlDoc = `/api/days-of-cover${qsPeriode}`;
  const urlRca = `/api/ringkasan-elemen/rca${qsPeriode}`;

  const q = useQueryKartu({
    queryKey: ["ringkasan-elemen", url],
    queryFn: () => ambilJson(url),
  });
  const dataGrafik = (q.data?.baris ?? []).map((b: any) => ({
    ...b,
    rm_stock: keBerat(b.rm_stock_ton, satuan),
    intake: keBerat(b.intake_ton, satuan),
    safety: keBerat(b.safety_ton, satuan),
  }));

  return (
    <Kartu idMetrik="elemen_op_margin" judul={t("RM Stock – Intake vs Pricing")}
           keterangan={t("Elemen pemengaruh OP Margin per bulan, disamakan dengan Excel: batang = tonase (pilih MT atau kg), garis = US¢/kg (sumbu kanan).")}
           urlEkspor={url}
           qsJelaskan={qs}
           anak={
      <>
        <div className="flex flex-wrap items-end gap-3 mb-3 text-xs">
          <PilihRentangBulan dari={dari} sampai={sampai}
                             setDari={setDari} setSampai={setSampai}
                             labelKosong={t("tampilkan semua periode")}
                             aksi={<TombolRefreshKartu />} />
          <span className="text-[#64676C]">
            {q.data ? `${q.data.baris.length} ${t("bulan ditampilkan")}` : ""}
          </span>
          <div className="pb-0.5">
            <label className="mb-1 block text-[#64676C]">{t("Satuan berat")}</label>
            <div className="flex overflow-hidden rounded-sm border border-[#E4E5E8]">
              {(["mt", "kg"] as const).map((s) => (
                <button key={s} type="button" aria-pressed={satuan === s}
                  onClick={() => setSatuan(s)}
                  className={`px-2.5 py-1.5 text-xs font-semibold ${satuan === s
                    ? "bg-[#FF1313] text-white"
                    : "bg-[#F8F8F8] text-[#1D2434] hover:bg-[#F1F2F4]"}`}>
                  {s === "mt" ? "MT" : "kg"}
                </button>
              ))}
            </div>
          </div>
          <div className="ml-auto flex flex-wrap gap-2">
            <button className={kelasTombolAnalisa} onClick={() => setPanel("5w1h")}>
              ✨ 5W1H
            </button>
            <button className={kelasTombolAnalisa} onClick={() => setPanel("rca")}>
              🔎 RCA · 5 Why
            </button>
            <button className={kelasTombolAnalisa} onClick={() => setPanel("bridge")}>
              🌉 {t("Margin Bridge")}
            </button>
            <button className={kelasTombolAnalisa} onClick={() => setPanel("doc")}>
              📦 {t("Days of Cover")}
            </button>
          </div>
        </div>
        <p className="-mt-1 mb-2 text-xs text-[#64676C]">
          {t("Tombol analisa memakai periode yang dipilih di atas — bulan/tahun yang dianalisa sama dengan grafik.")}
        </p>
        {panel === "5w1h" && (
          <Panel5W1H judul={`${t("Analisa grafik")} — 5W1H`}
                     url={`/api/ringkasan-elemen/analisa${qsPeriode}`}
                     tutup={() => setPanel(null)} />
        )}
        {panel === "rca" && <PanelRCA url={urlRca} tutup={() => setPanel(null)} />}
        {panel === "bridge" && (
          <PanelMarginBridge url={urlBridge} tutup={() => setPanel(null)}
                             awal={awalAnalisa} akhir={akhirAnalisa}
                             ubah={ubahPeriode} />
        )}
        {panel === "doc" && (
          <PanelDaysOfCover url={urlDoc} tutup={() => setPanel(null)}
                            awal={awalAnalisa} akhir={akhirAnalisa}
                            ubah={ubahPeriode} />
        )}
        <div className="h-96">
          <AlatGrafik id="ringkasan-01" animasiKunci={`${qs}|${satuan}`}><ResponsiveContainer>
            <ComposedChart data={dataGrafik}
                           margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" fontSize={10} minTickGap={18} />
              <YAxis yAxisId="ton" fontSize={10}
                     label={{ value: labelSatuan, angle: -90, position: "insideLeft",
                              fontSize: 11, fill: "#1D2434" }} />
              <YAxis yAxisId="usc" orientation="right" fontSize={10}
                     domain={["auto", "auto"]}
                     label={{ value: "US¢/kg", angle: 90, position: "insideRight",
                              fontSize: 11, fill: "#1D2434" }} />
              <Tooltip formatter={(v: any, nama: any) => {
                const seriBerat = ["Intake", "RM Stock", "Safety Level Stock"]
                  .includes(String(nama));
                if (!seriBerat || v === null || v === undefined)
                  return [fmtAngka(v as number, 4), nama];
                const utama = `${fmtAngka(v as number, satuan === "kg" ? 0 : 2)} ${labelSatuan}`;
                const pasangan = satuan === "kg"
                  ? `${fmtAngka((v as number) / 1000, 3)} MT`
                  : `${fmtAngka((v as number) * 1000, 0)} kg`;
                return [`${utama} (${pasangan})`, nama];
              }} />
              <Legend />
              <Bar yAxisId="ton" dataKey="intake" name="Intake"
                   fill="#FF1313" opacity={0.9} />
              <Bar yAxisId="ton" dataKey="rm_stock" name="RM Stock"
                   fill="#1D2434" opacity={0.85} />
              <Line yAxisId="ton" dataKey="safety" name="Safety Level Stock"
                    stroke="#B45309" strokeDasharray="6 3" dot={false}
                    type="stepAfter" strokeWidth={1.5} />
              <Line yAxisId="usc" dataKey="sicom" name="SICOM"
                    stroke="#1D2434" dot={false} strokeWidth={2} connectNulls />
              <Line yAxisId="usc" dataKey="op_price" name="OP Price"
                    stroke="#FF1313" dot={false} strokeWidth={2} connectNulls />
            </ComposedChart>
          </ResponsiveContainer></AlatGrafik>
        </div>
        <div className="mt-3 max-h-72 overflow-auto rounded-sm border border-[#E4E5E8]">
          <table className="w-full min-w-[980px] text-xs">
            <thead className="sticky top-0 z-10">
              <tr className="border-b border-[#E4E5E8] bg-[#F8F8F8] text-[10px] uppercase tracking-wide text-[#64676C]">
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">{t("Date")}</th>
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">{t("RM Stock")} ({labelSatuan})</th>
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">{t("Intake")} ({labelSatuan})</th>
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">{t("Safety")} ({labelSatuan})</th>
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">SICOM (US¢/kg)</th>
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">OP Price (US¢/kg)</th>
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">OP Margin (US¢/kg)</th>
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">{t("Sumber intake")}</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.baris.map((b: any) => (
                <tr key={b.label} className={`border-b border-[#EDEFF2] hover:bg-[#FFFAEB] ${
                    b.stok_sebagian ? "bg-[#FFFBEB]" : "even:bg-[#FAFAFA]"}`}>
                  <td className="whitespace-nowrap border-r border-[#EDEFF2] px-3 py-2 text-[#1D2434] last:border-r-0">
                    {b.label}{b.stok_sebagian ? " *" : ""}
                  </td>
                  <SelBerat ton={b.rm_stock_ton} satuan={satuan} />
                  <SelBerat ton={b.intake_ton} satuan={satuan} />
                  <SelBerat ton={b.safety_ton} satuan={satuan} />
                  <td className="whitespace-nowrap border-r border-[#EDEFF2] px-3 py-2 text-right font-mono tabular-nums last:border-r-0">{fmtAngka(b.sicom, 4)}</td>
                  <td className="whitespace-nowrap border-r border-[#EDEFF2] px-3 py-2 text-right font-mono tabular-nums last:border-r-0">{fmtAngka(b.op_price, 4)}</td>
                  <td className={`whitespace-nowrap border-r border-[#EDEFF2] px-3 py-2 text-right font-mono font-semibold tabular-nums last:border-r-0 ${
                    b.op_margin === null ? "" : b.op_margin >= 0
                      ? "text-[#15803D]" : "text-[#DC2626]"}`}>
                    {fmtAngka(b.op_margin, 4)}
                  </td>
                  <td className="px-3 py-2 text-[#64676C]">{b.sumber_intake ?? "-"}</td>
                </tr>
              ))}
              {q.data?.baris.length === 0 && (
                <tr><td colSpan={8} className="px-3 py-6 text-center text-[#9AA0A6]">
                  {t("Belum ada data untuk periode ini.")}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-[#64676C]">
          {t("1 MT = 1.000 kg. Angka kecil di bawah tonase menampilkan satuan pasangannya; SICOM, OP Price, dan OP Margin tetap US¢/kg.")}
        </p>
        {!!q.data?.catatan?.length && <div className="mt-2">
          <button type="button" aria-expanded={tampilkanCatatan}
            className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-3 py-1.5 text-xs font-medium text-[#475467] hover:bg-[#F1F2F4]"
            onClick={() => setTampilkanCatatan((shown) => !shown)}>
            {tampilkanCatatan ? "Sembunyikan keterangan" : `Tampilkan keterangan (${q.data.catatan.length})`}
          </button>
          {tampilkanCatatan && q.data.catatan.map((c: string, i: number) => (
            <p key={i} className="mt-2 rounded-sm bg-[#FFFBEB] border border-[#FDE68A] px-3 py-2 text-xs text-[#B45309]">
              {c}
            </p>
          ))}
        </div>}
      </>
    } />
  );
}

/* ---------- grafik margin: tren vs target & banding antar tahun ---------- */
// Palet aman buta warna (bukan hijau-merah): biru = di atas target,
// kuning = hanya tipis di atas target, oranye = di bawah target.
const WARNA_STATUS: Record<string, { isi: string; ikon: string; teks: string }> = {
  "di atas target": { isi: "#3b82f6", ikon: "✓", teks: "text-[#0369A1]" },
  tipis: { isi: "#eab308", ikon: "≈", teks: "text-[#A16207]" },
  "di bawah target": { isi: "#f97316", ikon: "!", teks: "text-[#C2410C]" },
  "tanpa target": { isi: "#9AA0A6", ikon: "–", teks: "text-[#64676C]" },
};
const warnaIkon = (status: string) => (WARNA_STATUS[status] ?? WARNA_STATUS["tanpa target"]).isi;

const labelBulanTahun = (tahun: number, bulan: number) =>
  `${NAMA_BULAN[bulan]}-${String(tahun).slice(2)}`;

/* Segmen target pendek per batang (bukan garis tangga) — tidak bisa disalahbaca
   sebagai target bulan lain seperti garis tangga. */
function SegmenTarget({ cx, cy, lebar }: any) {
  if (cx == null || cy == null) return null;
  const w = (lebar ?? 16) / 2;
  return (
    <line x1={cx - w} x2={cx + w} y1={cy} y2={cy}
          stroke="#1D2434" strokeWidth={3} strokeLinecap="round" />
  );
}

/* Kesimpulan otomatis sebagai judul kartu (bukan nama grafik). */
function kesimpulanMargin(rows: any[], satuan: string, fmt: (n: number) => string) {
  const berstatus = rows.filter((r) => r.status !== "tanpa target");
  if (!berstatus.length) return null;
  const akhir = berstatus[berstatus.length - 1];
  const selisih = Math.abs(akhir.delta);
  const arah = akhir.delta >= 0 ? "di atas" : "di bawah";

  // berapa bulan berturut-turut status akhir ini?
  let rentet = 0;
  for (let i = berstatus.length - 1; i >= 0; i--) {
    if (berstatus[i].status === akhir.status) rentet++;
    else break;
  }
  const capai = berstatus.filter((r) => r.delta >= 0).length;

  if (akhir.status === "di bawah target" && rentet >= 2) {
    return `Margin di bawah target ${rentet} bulan berturut-turut sejak ${berstatus[berstatus.length - rentet].label}`;
  }
  if (akhir.status === "tipis") {
    return `Margin ${akhir.label} hanya ${fmt(selisih)} ${satuan} di atas target — praktis pas`;
  }
  if (akhir.status === "di bawah target") {
    return `Margin ${akhir.label} ${arah} target ${fmt(selisih)} ${satuan}`;
  }
  return `Margin ${akhir.label} di atas target ${fmt(selisih)} ${satuan} ` +
         `(${capai} dari ${berstatus.length} bulan mencapai target)`;
}

function KartuGrafikMargin() {
  const { t } = useBahasa();
  const [mode, setMode] = useState<"tren" | "banding">("tren");
  const [unit, setUnit] = useState<"usc" | "rp">("usc");
  // Periode yang ditampilkan (YYYY-MM). Kosong = semua periode.
  const [dari, setDari] = useState("");
  const [sampai, setSampai] = useState("");
  const params = new URLSearchParams();
  if (dari) params.set("dari", dari);
  if (sampai) params.set("sampai", sampai);
  const qs = params.size ? "?" + params.toString() : "";

  const bulanan = useQueryKartu({
    queryKey: ["margin-bulanan-grafik", qs],
    queryFn: () => ambilJson(`/api/kartu/margin-bulanan${qs}`),
  });
  const antar = useQueryKartu({
    queryKey: ["grafik-margin", qs],
    queryFn: () => ambilJson(`/api/grafik/margin-antar-tahun${qs}`),
  });

  const tahunSemua: number[] = antar.data?.map((d: any) => d.tahun) ?? [];
  const [pilih, setPilih] = useState<number[] | null>(null);
  const tahunDipilih = pilih ?? tahunSemua.slice(-2); // bawaan: 2 tahun terakhir

  const adaKurs = (bulanan.data?.baris ?? []).some((b: any) => b.kurs);
  const pakaiRp = unit === "rp" && adaKurs;
  // 1 US¢/kg = kurs/100 Rp/kg
  const keSatuan = (usc: number | null, kurs: number | null) =>
    usc === null || usc === undefined ? null
      : pakaiRp ? (kurs ? (usc * kurs) / 100 : null) : usc;
  const satuan = pakaiRp ? "Rp/kg" : "US¢/kg";
  const fmtNilai = (n: number) => fmtAngka(n, pakaiRp ? 0 : 2);

  const dataTren = (bulanan.data?.baris ?? []).map((b: any) => {
    const m = keSatuan(b.op_margin, b.kurs);
    const tgt = keSatuan(b.target, b.kurs);
    const delta = m !== null && tgt !== null ? m - tgt : null;
    return {
      label: labelBulanTahun(b.tahun, b.bulan),
      margin: m, target: tgt, delta,
      marginUsc: b.op_margin, targetUsc: b.target, kurs: b.kurs,
      sicom: b.sicom,
      status: b.status_target ?? "tanpa target",
      capai: delta !== null && delta >= 0,
    };
  });
  const adaTarget = dataTren.filter((d: any) => d.target !== null);
  const capai = adaTarget.filter((d: any) => d.capai).length;
  const tipis = adaTarget.filter((d: any) => d.status === "tipis").length;

  // jumlah batang menentukan kerapatan label & lebar segmen target
  const n = dataTren.length;
  const lebarSegmen = n > 36 ? 6 : n > 20 ? 10 : n > 12 ? 14 : 18;
  const tampilLabel = n <= 40;
  // ambang "tipis" = 1 US¢/kg; dalam Rp/kg dikonversi dengan kurs terakhir
  const kursTerakhir = [...dataTren].reverse().find((d: any) => d.kurs)?.kurs ?? null;
  const ambangTipis = pakaiRp && kursTerakhir ? kursTerakhir / 100 : 1;

  // Anotasi ringkas: titik-titik yang layak dijelaskan (maks 3)
  const anotasi: { label: string; teks: string }[] = [];
  const berdata = dataTren.filter((d: any) => d.sicom !== null);
  if (n > 1 && n <= 40) {
    const jatuh = [...berdata].sort((a, b) => (a.sicom - b.sicom))[0];
    const iJatuh = berdata.indexOf(jatuh);
    if (iJatuh > 0 && n > 1) {
      anotasi.push({ label: jatuh.label, teks: t("SICOM turun tajam") });
    }
    // perubahan target antar bulan
    for (let i = 1; i < dataTren.length; i++) {
      const kini = dataTren[i], lalu = dataTren[i - 1];
      if (kini.target != null && lalu.target != null && kini.target !== lalu.target) {
        anotasi.push({
          label: kini.label,
          teks: `${t("target")} ${kini.target > lalu.target ? "↑" : "↓"} ${fmtNilai(kini.target)}`,
        });
        break;
      }
    }
    // penurunan margin terbesar
    const turun = dataTren.filter((d: any) => d.delta !== null)
      .sort((a: any, b: any) => a.delta - b.delta)[0];
    if (turun && turun.delta < 0 && !anotasi.some((a) => a.label === turun.label)) {
      anotasi.push({ label: turun.label, teks: t("selisih terburuk") });
    }
  }
  const anotasiTampil = anotasi.slice(0, 3);

  const judulKesimpulan = mode === "tren" ? kesimpulanMargin(dataTren, satuan, fmtNilai) : null;
  const periodeTeks = bulanan.data?.dari
    ? `${bulanan.data.dari} → ${bulanan.data.sampai}`
    : "";

  const dataBanding = Array.from({ length: 12 }, (_, i) => {
    const titik: any = { bulan: NAMA_BULAN[i + 1] };
    antar.data?.forEach((th: any) => {
      if (tahunDipilih.includes(th.tahun)) titik[th.tahun] = th.data[i].margin;
    });
    return titik;
  });

  return (
    <Kartu idMetrik="margin_bulanan"
           judul={judulKesimpulan ? t(judulKesimpulan) : t("OP Margin bulanan vs target")}
           keterangan={t("OP Margin tiap bulan dibandingkan target bulan itu sendiri (segmen putih pada tiap batang). Satuan: sen dolar AS per kg (US¢/kg) — bukan dolar.")}
           urlEkspor={`/api/kartu/margin-bulanan${qs}`}
           qsJelaskan={qs}
           anak={
      <>
        <div className="flex flex-wrap items-end gap-3 mb-3 text-xs">
          <PilihRentangBulan dari={dari} sampai={sampai}
                             setDari={setDari} setSampai={setSampai}
                             labelKosong={t("tampilkan semua periode")}
                             aksi={<TombolRefreshKartu />} />
          <div>
            <label className="block text-[#64676C] mb-1">{t("Satuan")}</label>
            <div className="flex rounded-sm overflow-hidden border border-[#E4E5E8]">
              {([["usc", "US¢/kg"], ["rp", "Rp/kg"]] as const).map(([id, label]) => (
                <button key={id} disabled={id === "rp" && !adaKurs}
                  className={`px-2.5 py-1.5 ${unit === id ? "bg-[#FF1313] text-white"
                    : "bg-[#F8F8F8] text-[#1D2434] hover:bg-[#F1F2F4]"} disabled:opacity-40`}
                  title={id === "rp" && !adaKurs ? t("Kurs bulanan belum tersedia") : undefined}
                  onClick={() => setUnit(id)}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <span className="text-[#64676C] pb-1.5">
            {bulanan.data
              ? `${bulanan.data.jumlah_bulan} ${t("bulan ditampilkan")}` +
                (periodeTeks ? ` (${periodeTeks})` : "")
              : ""}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 mb-3">
          {([["tren", t("Tren & capaian target")], ["banding", t("Banding antar tahun")]] as const)
            .map(([id, label]) => (
            <button key={id}
              className={`rounded-sm px-3 py-1.5 text-xs font-medium ${mode === id
                ? "bg-[#FF1313] text-white" : "bg-[#F1F2F4] text-[#1D2434] hover:bg-[#E8E9EC]"}`}
              onClick={() => setMode(id)}>
              {label}
            </button>
          ))}
          {mode === "tren" && adaTarget.length > 0 && (
            <span className="ml-auto text-xs text-[#64676C]">
              <b className="text-[#0369A1]">{capai}</b> {t("dari")} {adaTarget.length}{" "}
              {t("bulan mencapai target")} ({fmtAngka((capai / adaTarget.length) * 100, 0)}%)
              {tipis > 0 && <span className="text-[#A16207]"> · {tipis} {t("tipis")}</span>}
            </span>
          )}
        </div>

        {mode === "tren" ? (
          <>
            <div className="h-80">
              <AlatGrafik id="ringkasan-02" animasiKunci={`${qs}|${unit}|${mode}`}><ResponsiveContainer>
                <ComposedChart data={dataTren}
                               margin={{ top: 22, right: 10, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDEFF2" />
                  <XAxis dataKey="label" fontSize={10} minTickGap={26}
                         tick={{ fill: "#64676C" }} />
                  <YAxis fontSize={11} tick={{ fill: "#64676C" }}
                         label={{ value: satuan, angle: -90, position: "insideLeft",
                                  fontSize: 11, fill: "#1D2434" }} />
                  <Tooltip content={({ payload, label }) => {
                    const p: any = payload?.[0]?.payload;
                    if (!p) return null;
                    const st = WARNA_STATUS[p.status] ?? WARNA_STATUS["tanpa target"];
                    return (
                      <div className="rounded-sm bg-white border border-[#E4E5E8] p-2 text-xs shadow">
                        <b>{label}</b><br />
                        {t("Margin")}: <b>{fmtNilai(p.margin ?? 0)}</b> {satuan}<br />
                        {t("Target")}: {p.target === null ? "–" : `${fmtNilai(p.target)} ${satuan}`}<br />
                        {t("Selisih")}: <b className={st.teks}>
                          {p.delta === null ? "–" : `${p.delta >= 0 ? "+" : "−"}${fmtNilai(Math.abs(p.delta))}`}
                        </b><br />
                        <span className={st.teks}>{st.ikon} {t(p.status)}</span>
                        {p.kurs && (
                          <div className="text-[#64676C] mt-0.5">
                            {t("Kurs")}: {fmtAngka(p.kurs, 0)} Rp/USD
                          </div>
                        )}
                      </div>
                    );
                  }} />
                  <ReferenceLine y={0} stroke="#9AA0A6" />
                  {anotasiTampil.map((a) => (
                    <ReferenceLine key={a.label} x={a.label} stroke="#FF1313"
                                   strokeDasharray="2 3"
                                   label={{ value: a.teks, position: "insideTop",
                                            fill: "#FF1313", fontSize: 9 }} />
                  ))}
                  <Bar dataKey="margin" name="OP Margin" maxBarSize={16} isAnimationActive={false}>
                    {dataTren.map((d: any, i: number) => (
                      <Cell key={i} fill={warnaIkon(d.status)} />
                    ))}
                    {tampilLabel && (
                      <LabelList dataKey="margin" content={(p: any) => {
                        const d = p?.payload;
                        if (!d || d.margin === null) return null;
                        const st = WARNA_STATUS[d.status] ?? WARNA_STATUS["tanpa target"];
                        const naik = (d.margin ?? 0) >= 0;
                        const y = naik ? p.y - 5 : p.y + p.height + 11;
                        const teks = d.delta === null
                          ? fmtNilai(d.margin)
                          : `${fmtNilai(d.margin)} (${d.delta >= 0 ? "+" : "−"}${fmtNilai(Math.abs(d.delta))})`;
                        return (
                          <text x={p.x + p.width / 2} y={y} textAnchor="middle"
                                fontSize={n > 20 ? 8 : 9} fontWeight={600} fill="#FFFFFF">
                            {st.ikon} {teks}
                          </text>
                        );
                      }} />
                    )}
                  </Bar>
                  <Line dataKey="target" name="Target" stroke="transparent" strokeWidth={0}
                        dot={<SegmenTarget lebar={lebarSegmen} />} activeDot={false}
                        isAnimationActive={false} legendType="none" />
                </ComposedChart>
              </ResponsiveContainer></AlatGrafik>
            </div>

            {/* Panel selisih terhadap target: satu pandangan melihat bulan minus */}
            <div className="mt-2">
              <div className="text-[11px] text-[#64676C] mb-0.5">
                {t("Selisih terhadap target (ke atas = di atas target, ke bawah = kurang)")}
              </div>
              <div className="h-24">
                <AlatGrafik id="ringkasan-03" animasiKunci={`${qs}|${unit}|${mode}`}><ResponsiveContainer>
                  <BarChart data={dataTren} margin={{ top: 4, right: 10, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" />
                    <XAxis dataKey="label" hide />
                    <YAxis fontSize={9} tick={{ fill: "#64676C" }} width={38} />
                    <Tooltip content={({ payload, label }) => {
                      const p: any = payload?.[0]?.payload;
                      if (!p) return null;
                      const st = WARNA_STATUS[p.status] ?? WARNA_STATUS["tanpa target"];
                      return (
                        <div className="rounded-sm bg-white border border-[#E4E5E8] p-2 text-xs shadow">
                          <b>{label}</b><br />
                          {t("Selisih")}: {p.delta === null ? "–"
                            : `${p.delta >= 0 ? "+" : "−"}${fmtNilai(Math.abs(p.delta))}`} {satuan}<br />
                          <span className={st.teks}>{st.ikon} {t(p.status)}</span>
                        </div>
                      );
                    }} />
                    <ReferenceLine y={0} stroke="#9AA0A6" />
                    <Bar dataKey="delta" isAnimationActive={false} maxBarSize={16}>
                      {dataTren.map((d: any, i: number) => (
                        <Cell key={i} fill={warnaIkon(d.status)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer></AlatGrafik>
              </div>
            </div>

            <div className="mt-2 grid gap-1 text-xs text-[#64676C]">
              <p>
                {t("Cara baca: satu batang = satu bulan")}
                {periodeTeks ? `, ${t("periode aktif")} ${periodeTeks}` : ""}
                {bulanan.data ? ` (${bulanan.data.jumlah_bulan} ${t("bulan")})` : ""}.
                {" "}
                <span className="text-[#0369A1]">■ ✓ {t("di atas target")}</span> ·{" "}
                <span className="text-[#A16207]">■ ≈ {t("tipis")} (&lt; {fmtAngka(ambangTipis, pakaiRp ? 0 : 1)} {satuan} {t("di atas target")})</span> ·{" "}
                <span className="text-[#C2410C]">■ ! {t("di bawah target")}</span> ·{" "}
                <span className="text-[#1D2434]">▬ {t("segmen target bulan itu")}</span>
              </p>
              <p className="text-[#64676C]">
                {t("Warna tidak sendirian — setiap batang diberi ikon dan angka, jadi tetap terbaca oleh penglihatan buta warna.")}
              </p>
            </div>
          </>
        ) : (
          <>
            <div className="flex flex-wrap gap-2 mb-2 text-xs">
              <span className="text-[#64676C]">{t("Pilih tahun yang dibandingkan:")}</span>
              {tahunSemua.map((th) => (
                <label key={th} className="flex items-center gap-1 text-[#1D2434]">
                  <input type="checkbox" className="accent-[#FF1313]"
                         checked={tahunDipilih.includes(th)}
                         onChange={(e) => setPilih(e.target.checked
                           ? [...tahunDipilih, th].sort()
                           : tahunDipilih.filter((x) => x !== th))} />
                  {th}
                </label>
              ))}
            </div>
            <div className="h-80">
              <AlatGrafik id="ringkasan-04" animasiKunci={`${qs}|${tahunDipilih.join(",")}`}><ResponsiveContainer>
                <LineChart data={dataBanding}
                           margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDEFF2" />
                  <XAxis dataKey="bulan" fontSize={12} tick={{ fill: "#64676C" }} />
                  <YAxis fontSize={11} tick={{ fill: "#64676C" }}
                         label={{ value: "US¢/kg", angle: -90, position: "insideLeft",
                                  fontSize: 11, fill: "#1D2434" }} />
                  <Tooltip formatter={(v: any) => `${fmtAngka(v as number)} US¢/kg`} />
                  <Legend />
                  {antar.data?.filter((th: any) => tahunDipilih.includes(th.tahun))
                    .map((th: any) => (
                    <Line key={th.tahun} dataKey={th.tahun} type="monotone"
                          stroke={WARNA[tahunSemua.indexOf(th.tahun) % WARNA.length]}
                          dot={{ r: 2.5 }} connectNulls
                          strokeWidth={th.tahun === Math.max(...tahunDipilih) ? 2.5 : 1.5} />
                  ))}
                </LineChart>
              </ResponsiveContainer></AlatGrafik>
            </div>
            <p className="mt-2 text-xs text-[#64676C]">
              {t("Cara baca: membandingkan pola bulanan beberapa tahun (mis. apakah margin biasanya turun di pertengahan tahun). Centang maksimal 2–3 tahun supaya tetap mudah dibaca; garis paling tebal = tahun terbaru yang dipilih.")}
              {periodeTeks && ` ${t("Periode aktif")}: ${periodeTeks}.`}
            </p>
          </>
        )}
      </>
    } />
  );
}

/* ---------- panel analisa kartu RM Stock – Intake vs Pricing ----------
   Ketiganya memakai periode (dari/sampai) yang sedang dipilih di kartu itu,
   jadi bulan/tahun yang dianalisa selalu sama dengan yang ada di grafik. */
function TipBridge({ active, payload }: any) {
  const { t } = useBahasa();
  if (!active || !payload?.length) return null;
  const isi = payload.find((p: any) => p.dataKey === "nilai") ?? payload[0];
  const d = isi?.payload;
  if (!d) return null;
  return (
    <div className="rounded-sm border border-[#FF1313]/40 bg-white px-3 py-2 text-xs shadow-xl">
      <div className="font-semibold text-[#1D2434] mb-1">{d.label}</div>
      <div className={d.delta >= 0 ? "text-[#15803D]" : "text-[#BE123C]"}>
        {d.delta >= 0 ? "+" : ""}{fmtAngka(d.delta, 2)} US¢/kg
      </div>
      {d.langkah && (
        <>
          <div className="text-[#64676C] mt-0.5">
            {fmtAngka(d.sebelum, 2)} → {fmtAngka(d.sesudah, 2)}
          </div>
          {typeof d.mentah === "number" && (
            <div className="text-[#64676C] mt-0.5">
              {t("perubahan")}: {d.mentah >= 0 ? "+" : ""}{fmtAngka(d.mentah, 2)}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function PanelMarginBridge({ url, tutup, awal, akhir, ubah }: {
  url: string; tutup: () => void;
  awal: string; akhir: string;
  ubah: (a: string, b: string) => void;
}) {
  const { t } = useBahasa();
  const [rincian, setRincian] = useState(false);
  const q = useQuery({ queryKey: ["margin-bridge", url],
                       queryFn: () => ambilJson(url), retry: false });
  const d = q.data;

  const labelPeriode = (p: any) => (p ? `${NAMA_BULAN[p.bulan]} ${p.tahun}` : "");

  const titik: any[] = [];
  if (d) {
    titik.push({ label: `${t("Margin awal")} ${labelPeriode(d.periode_a)}`,
                 dasar: Math.min(0, d.awal), nilai: Math.abs(d.awal),
                 delta: d.awal, total: true });
    let kum = d.awal;
    for (const l of d.langkah) {
      const sebelum = kum;
      kum += l.nilai;
      titik.push({ label: l.label, dasar: Math.min(sebelum, kum),
                   nilai: Math.abs(l.nilai), delta: l.nilai,
                   mentah: l.perubahan_mentah, jenis: l.jenis,
                   sebelum, sesudah: kum, langkah: true });
    }
    titik.push({ label: `${t("Margin akhir")} ${labelPeriode(d.periode_b)}`,
                 dasar: Math.min(0, kum), nilai: Math.abs(kum),
                 delta: kum, total: true });
  }
  // Penurunan dibuat MERAH TEGAS (bukan merah muda) supaya langsung terbaca.
  const MERAH = "#dc2626";
  const warna = (x: any) => (x.total ? "#8b5cf6" : x.delta >= 0 ? "#22c55e" : MERAH);
  const garis = (x: any) => (x.total ? "#6d28d9" : x.delta >= 0 ? "#15803d" : "#7f1d1d");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
         onClick={tutup}>
      <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-sm bg-white border border-[#E4E5E8] p-6 shadow-xl shadow-[#1D2434]/10"
           onClick={(e) => e.stopPropagation()}>
        <KepalaPanel judul={t("Margin Bridge — analisa grafik")}
                     periode={d ? `${labelPeriode(d.periode_a)} → ${labelPeriode(d.periode_b)}` : undefined}
                     url={url} tutup={tutup} />

        <div className="mt-3 flex flex-wrap items-end gap-3 text-xs">
          <PilihRentangBulan dari={awal} sampai={akhir}
            setDari={(v) => ubah(v, akhir)} setSampai={(v) => ubah(awal, v)}
            labelKosong={t("seluruh data")} />
          <p className="text-[#64676C]">{t("Bawaan: mengikuti filter kartu grafik.")}</p>
        </div>

        <p className="mt-2 text-sm text-[#1D2434] font-mono">
          ΔM = ΔSICOM − ΔOP Price
        </p>
        <p className="text-xs text-[#64676C]">
          {t("SICOM = harga acuan pasar (di luar kendali), OP Price = harga beli kita (keputusan). SICOM turun menekan margin; OP Price turun justru menolong.")}
        </p>

        {q.isLoading && <KerangkaMuatKartu className="mt-4" />}
        {q.error && (
          <p className="mt-4 rounded-sm bg-[#FEF2F2] border border-[#FECACA] px-3 py-2 text-sm text-[#B91C1C]">
            {pesanGalat(q.error)}
          </p>
        )}

        {d && (
          <>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {[
                [t("OP Margin awal"), fmtAngka(d.awal, 2), "text-[#1D2434]"],
                [t("Perubahan margin"), `${d.delta_margin >= 0 ? "+" : ""}${fmtAngka(d.delta_margin, 2)}`,
                 d.delta_margin >= 0 ? "text-[#15803D]" : "text-[#BE123C]"],
                [t("OP Margin akhir"), fmtAngka(d.akhir, 2), "text-[#1D2434]"],
              ].map(([l, v, k]) => (
                <div key={l as string} className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                  <div className="text-[11px] text-[#64676C]">{l}</div>
                  <div className={`font-mono text-lg font-semibold ${k}`}>{v}</div>
                </div>
              ))}
            </div>

            <div className="h-72 mt-3">
              <AlatGrafik id="ringkasan-05" animasiKunci={url}><ResponsiveContainer width="100%" height="100%">
                <BarChart data={titik} margin={{ top: 10, right: 10, bottom: 5, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDEFF2" />
                  <XAxis dataKey="label" tick={{ fill: "#64676C", fontSize: 10 }}
                         interval={0} height={48} angle={-12} textAnchor="end" />
                  <YAxis tick={{ fill: "#64676C", fontSize: 11 }}
                         label={{ value: "US¢/kg", angle: -90, position: "insideLeft",
                                  fill: "#64676C", fontSize: 11 }} />
                  <Tooltip content={<TipBridge />} />
                  <Bar dataKey="dasar" stackId="a" fill="transparent" isAnimationActive={false} />
                  <Bar dataKey="nilai" stackId="a" isAnimationActive={false}
                       stroke="#FFFFFF" strokeWidth={0.8}>
                    {titik.map((x, i) => (
                      <Cell key={i} fill={warna(x)} stroke={garis(x)} strokeWidth={1.5} />
                    ))}
                    <LabelList dataKey="nilai" content={(p: any) => {
                      const d = p?.payload;
                      if (!d) return null;
                      const naik = (d.delta ?? 0) >= 0;
                      const teks = `${naik ? "+" : "−"}${fmtAngka(Math.abs(d.delta ?? 0), 2)}`;
                      const y = naik ? p.y - 6 : p.y + p.height + 12;
                      return (
                        <text x={p.x + p.width / 2} y={y} textAnchor="middle"
                              fontSize={10} fontWeight={700}
                              fill={d.total ? "#1D2434" : naik ? "#0F766E" : "#FF1313"}>
                          {teks}
                        </text>
                      );
                    }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer></AlatGrafik>
            </div>

            <div className="mt-3 rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
              <div className="flex flex-wrap items-center gap-2 mb-1.5">
                <span className="text-sm font-semibold text-[#1D2434]">
                  {t("Kenapa naik, kenapa turun")}
                </span>
                {d.kesimpulan && (
                  <span className={`rounded-sm px-2 py-0.5 text-[10px] font-medium ${
                    d.kesimpulan.includes("pasar")
                      ? "bg-[#F0F9FF] text-[#0369A1]"
                      : d.kesimpulan.includes("keputusan")
                        ? "bg-[#FEF3C7] text-[#B45309]"
                        : "bg-[#DCFCE7] text-[#15803D]"}`}>
                    {d.kesimpulan}
                  </span>
                )}
              </div>
              <ul className="grid gap-1">
                {(d.analisa ?? []).map((a: string, i: number) => (
                  <li key={i} className="text-xs text-[#1D2434] leading-relaxed flex gap-1.5">
                    <span className="text-[#FF1313] shrink-0">▸</span><span>{a}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-2 text-xs">
              {d.langkah.map((l: any) => {
                const negatif = l.nilai < 0;
                return (
                  <div key={`j-${l.kode}`}
                       className={`rounded-sm border p-3 ${negatif
                         ? "border-red-500/50 bg-[#FEF2F2]"
                         : "border-emerald-500/40 bg-[#F0FDF4]"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-[#1D2434]">
                        {negatif ? "▼ " : "▲ "}{l.label}
                      </span>
                      <span className={`font-mono font-bold ${negatif
                        ? "text-[#B91C1C]" : "text-[#15803D]"}`}>
                        {l.nilai >= 0 ? "+" : "−"}{fmtAngka(Math.abs(l.nilai), 2)}
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] leading-relaxed text-[#1D2434]">
                      {l.penjelasan}
                    </p>
                    <div className="mt-1 text-[10px] text-[#64676C]">
                      {l.jenis === "eksternal" ? t("pasar — di luar kendali")
                        : t("keputusan pembelian")}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2 text-xs">
              <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                <div className="font-semibold text-[#1D2434] mb-1">{t("Kontribusi")}</div>
                {d.langkah.map((l: any) => (
                  <div key={l.kode} className="flex justify-between py-0.5">
                    <span className="text-[#64676C]">
                      {l.label} <span className="text-[#64676C]">
                        ({l.jenis === "eksternal" ? t("pasar") : t("keputusan")})
                      </span>
                    </span>
                    <span className={`font-mono ${l.nilai >= 0 ? "text-[#15803D]" : "text-[#BE123C]"}`}>
                      {l.nilai >= 0 ? "+" : ""}{fmtAngka(l.nilai, 2)}
                    </span>
                  </div>
                ))}
                {d.passthrough && (
                  <p className="mt-2 text-[#64676C] leading-relaxed">
                    {t("OP Price hanya mengikuti")}{" "}
                    <b className="text-[#1D2434]">{fmtAngka(Math.abs(d.passthrough.rasio) * 100, 1)}%</b>{" "}
                    {t("dari perubahan SICOM; sisa")}{" "}
                    <b className="text-[#1D2434]">{fmtAngka(Math.abs(d.passthrough.porsi_ditanggung_margin) * 100, 1)}%</b>{" "}
                    {t("ditanggung margin.")}
                  </p>
                )}
              </div>
              <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                <button className="font-semibold text-[#1D2434] mb-1 hover:text-[#FF1313]"
                        onClick={() => setRincian(!rincian)}>
                  {rincian ? "▾" : "▸"} {t("Rincian Δ OP Price (harga Rp vs kurs)")}
                </button>
                {rincian && d.rincian_op_price ? (
                  <>
                    {[["harga_rp", t("Efek harga beli (Rp/kg)")], ["kurs", t("Efek kurs")]]
                      .map(([k, nama]) => (
                        <div key={k} className="flex justify-between py-0.5">
                          <span className="text-[#64676C]">{nama}</span>
                          <span className={`font-mono ${(d.rincian_op_price as any)[k] >= 0
                            ? "text-[#15803D]" : "text-[#BE123C]"}`}>
                            {(d.rincian_op_price as any)[k] >= 0 ? "+" : ""}
                            {fmtAngka((d.rincian_op_price as any)[k], 2)}
                          </span>
                        </div>
                      ))}
                    <div className="flex justify-between border-t border-[#E4E5E8] mt-1 pt-1">
                      <span className="text-[#1D2434]">{t("Total = −Δ OP Price")}</span>
                      <span className="font-mono text-[#1D2434]">
                        {fmtAngka(d.rincian_op_price.total, 2)}
                      </span>
                    </div>
                    <p className="mt-1 text-[#64676C]">
                      {t("Kurs efektif")}: {fmtAngka(d.rincian_op_price.kurs_a, 0)} →{" "}
                      {fmtAngka(d.rincian_op_price.kurs_b, 0)} Rp/USD
                    </p>
                  </>
                ) : (
                  <p className="text-[#64676C]">{t("Klik untuk memisahkan efek harga beli dan kurs.")}</p>
                )}
              </div>
            </div>

            <div className="mt-4">
              <div className="text-sm font-semibold text-[#1D2434] mb-1">
                {t("Bridge per bulan — mana yang dipicu pasar, mana yang keputusan")}
              </div>
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-[#64676C] border-b">
                      <th className="py-1 pr-2">{t("Bulan")}</th>
                      <th className="text-right px-1">Δ SICOM</th>
                      <th className="text-right px-1">Δ OP Price</th>
                      <th className="text-right px-1">Δ Margin</th>
                      <th className="text-right px-1">{t("Ikut SICOM")}</th>
                      <th className="pl-2">{t("Penyebab")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(d.per_bulan ?? []).map((b: any) => (
                      <Fragment key={b.bulan}>
                      <tr className="border-b-0">
                        <td className="pt-1.5 pr-2 text-[#1D2434]">{b.bulan}</td>
                        <td className={`text-right px-1 font-mono ${
                          b.kontribusi_sicom >= 0 ? "text-[#15803D]" : "text-[#BE123C]"}`}>
                          {b.delta_sicom >= 0 ? "+" : ""}{fmtAngka(b.delta_sicom, 2)}
                        </td>
                        <td className="text-right px-1 font-mono text-[#1D2434]">
                          {b.delta_op_price >= 0 ? "+" : ""}{fmtAngka(b.delta_op_price, 2)}
                        </td>
                        <td className={`text-right px-1 font-mono font-semibold ${
                          b.delta_margin >= 0 ? "text-[#15803D]" : "text-[#BE123C]"}`}>
                          {b.delta_margin >= 0 ? "+" : ""}{fmtAngka(b.delta_margin, 2)}
                        </td>
                        <td className="text-right px-1 font-mono text-[#64676C]">
                          {b.passthrough === null ? "–" : `${fmtAngka(b.passthrough * 100, 0)}%`}
                        </td>
                        <td className="pl-2">
                          <span className={`rounded px-1.5 py-0.5 text-[10px] ${
                            b.penyebab === "pasar"
                              ? "bg-[#F0F9FF] text-[#0369A1]" : "bg-[#FEF3C7] text-[#B45309]"}`}>
                            {b.penyebab === "pasar" ? t("dipicu pasar") : t("dipicu keputusan")}
                          </span>
                        </td>
                      </tr>
                      <tr className="border-b border-[#EDEFF2]">
                        <td colSpan={6} className="pb-1.5 pl-2 text-[10px] leading-relaxed text-[#64676C]">
                          ↳ {b.penjelasan}
                        </td>
                      </tr>
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <p className="mt-2 text-xs text-[#64676C]">
              {t("Selisih penutupan (awal + komponen − akhir):")}{" "}
              <span className="font-mono">{fmtAngka(d.penutupan_selisih, 8)}</span>{" "}
              {t("— bridge tertutup persis.")}
            </p>
            {d.catatan.map((c: string, i: number) => (
              <p key={i} className="mt-1 text-[11px] text-[#64676C]">{c}</p>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function PanelDaysOfCover({ url, tutup, awal, akhir, ubah }: {
  url: string; tutup: () => void;
  awal: string; akhir: string;
  ubah: (a: string, b: string) => void;
}) {
  const { t } = useBahasa();
  const q = useQuery({ queryKey: ["days-of-cover", url],
                       queryFn: () => ambilJson(url), retry: false });
  const d = q.data;
  const baris: any[] = d?.baris ?? [];
  const seri = baris.map((b) => ({
    ...b,
    label: b.bulan,
    doc: b.doc_hari,
    safety: b.safety_hari,
    dinamis: d ? d.hari_safety_acuan : null,
  }));
  const kini = d?.terkini;
  const warnaStatus = (s: string) => s === "aman"
    ? "text-[#15803D] border-[#BBF7D0] bg-[#F0FDF4]"
    : s === "di bawah safety"
      ? "text-[#BE123C] border-[#FECDD3] bg-[#FFF1F2]"
      : "text-[#1D2434] border-[#D5D7DB] bg-[#F8F8F8]";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
         onClick={tutup}>
      <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-sm bg-white border border-[#E4E5E8] p-6 shadow-xl shadow-[#1D2434]/10"
           onClick={(e) => e.stopPropagation()}>
        <KepalaPanel judul={t("Days of Cover — analisa grafik")}
                     periode={d ? `${d.dari} – ${d.sampai}` : undefined}
                     url={url} tutup={tutup} />

        <div className="mt-3 flex flex-wrap items-end gap-3 text-xs">
          <PilihRentangBulan dari={awal} sampai={akhir}
            setDari={(v) => ubah(v, akhir)} setSampai={(v) => ubah(awal, v)}
            labelKosong={t("seluruh data")} />
        </div>

        <p className="mt-2 text-sm text-[#1D2434] font-mono">
          Pemakaian = Stok awal + Intake − Stok akhir; DoC = Stok akhir ÷ (Pemakaian ÷ hari)
        </p>
        <p className="text-xs text-[#64676C]">
          {t("Pemakaian tidak ada di data, jadi dihitung dari neraca stok. DoC lebih adil daripada tonase karena menyesuaikan pemakaian.")}
        </p>

        {q.isLoading && <KerangkaMuatKartu className="mt-4" />}
        {q.error && (
          <p className="mt-4 rounded-sm bg-[#FEF2F2] border border-[#FECACA] px-3 py-2 text-sm text-[#B91C1C]">
            {pesanGalat(q.error)}
          </p>
        )}

        {d && kini && (
          <>
            <div className="mt-3 flex flex-wrap items-end gap-6">
              <div>
                <div className="text-4xl font-bold font-mono text-[#FF1313]">
                  {fmtAngka(kini.doc_hari, 1)}{" "}
                  <span className="text-base text-[#64676C]">{t("hari")}</span>
                </div>
                <div className="text-xs text-[#64676C] mt-1">
                  {kini.bulan} · {t("stok akhir")} {fmtAngka(kini.stok_akhir_ton, 0)} ton ·{" "}
                  {t("pemakaian")} {fmtAngka(kini.pemakaian_harian_ton, 0)} ton/{t("hari")}
                </div>
              </div>
              <span className={`rounded-sm border px-3 py-1 text-xs font-medium ${warnaStatus(kini.status)}`}>
                {t(kini.status)} · {t("safety")} {fmtAngka(kini.safety_hari, 1)} {t("hari")}
              </span>
              <div className="text-xs text-[#64676C]">
                <div>
                  {t("Rerata pemakaian:")}{" "}
                  <b className="text-[#1D2434] font-mono">{fmtAngka(d.rerata_pemakaian_bulan_ton, 0)}</b>{" "}
                  ton/{t("bulan")} ({fmtAngka(d.rerata_pemakaian_harian_ton, 0)} ton/{t("hari")})
                </div>
                <div>
                  {t("Safety dinamis (21,5 hari):")} <b className="text-[#1D2434] font-mono">
                    {fmtAngka(d.safety_dinamis_ton, 0)}</b> ton
                </div>
                <div>
                  {t("Terendah:")} <b className="text-[#BE123C] font-mono">{fmtAngka(d.terendah?.doc_hari, 1)}</b>{" "}
                  ({d.terendah?.bulan}) · {t("Tertinggi:")}{" "}
                  <b className="text-[#15803D] font-mono">{fmtAngka(d.tertinggi?.doc_hari, 1)}</b>{" "}
                  ({d.tertinggi?.bulan}) · {t("bulan di bawah safety:")}{" "}
                  <b className="text-[#1D2434] font-mono">{d.jumlah_bulan_di_bawah_safety}</b>/{d.jumlah_bulan}
                </div>
              </div>
            </div>

            <div className="h-64 mt-4">
              <AlatGrafik id="ringkasan-06" animasiKunci={url}><ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={seri} margin={{ top: 10, right: 10, bottom: 5, left: -15 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDEFF2" />
                  <XAxis dataKey="label" tick={{ fill: "#64676C", fontSize: 10 }} minTickGap={12} />
                  <YAxis tick={{ fill: "#64676C", fontSize: 11 }}
                         label={{ value: t("hari"), angle: -90, position: "insideLeft",
                                  fill: "#64676C", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid #E4E5E8",
                                           borderRadius: 8, fontSize: 12,
                                           color: "#1D2434" }}
                           formatter={(v: any, _n: any, p: any) =>
                             [fmtAngka(v, 1), p?.dataKey === "doc" ? t("Days of cover")
                               : t("Safety (hari)")]} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="doc" name={t("Days of cover")} isAnimationActive={false}>
                    {seri.map((x: any, i: number) => (
                      <Cell key={i} fill={(x.doc ?? 0) >= (x.safety ?? 0) ? "#1D2434" : "#FF1313"} />
                    ))}
                  </Bar>
                  <Line type="stepAfter" dataKey="safety" name={t("Safety (hari)")}
                        stroke="#B45309" strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
                </ComposedChart>
              </ResponsiveContainer></AlatGrafik>
            </div>

            <div className="mt-4 max-h-72 overflow-y-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[#64676C] border-b">
                    <th className="py-1 pr-2">{t("Bulan")}</th>
                    <th className="text-right px-1">{t("Stok awal")}</th>
                    <th className="text-right px-1">Intake</th>
                    <th className="text-right px-1">{t("Stok akhir")}</th>
                    <th className="text-right px-1">{t("Pemakaian")}</th>
                    <th className="text-right px-1">ton/{t("hari")}</th>
                    <th className="text-right px-1">DoC</th>
                    <th className="text-right px-1">{t("Safety (hari)")}</th>
                    <th className="pl-2">{t("Status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {baris.map((b) => (
                    <tr key={b.bulan} className={`border-b border-[#EDEFF2] ${
                      b.perlu_cek ? "bg-amber-400/5" : ""}`}>
                      <td className="py-1 pr-2 text-[#1D2434]" title={b.alasan_cek.join("; ")}>
                        {b.bulan}{b.perlu_cek ? " ⚠" : ""}
                      </td>
                      <td className="text-right px-1 font-mono text-[#64676C]">{fmtAngka(b.stok_awal_ton, 0)}</td>
                      <td className="text-right px-1 font-mono text-[#1D2434]">{fmtAngka(b.intake_ton, 0)}</td>
                      <td className="text-right px-1 font-mono text-[#1D2434]">{fmtAngka(b.stok_akhir_ton, 0)}</td>
                      <td className="text-right px-1 font-mono text-[#64676C]">{fmtAngka(b.pemakaian_ton, 0)}</td>
                      <td className="text-right px-1 font-mono text-[#64676C]">{fmtAngka(b.pemakaian_harian_ton, 0)}</td>
                      <td className={`text-right px-1 font-mono font-semibold ${
                        b.status === "aman" ? "text-[#15803D]" : "text-[#BE123C]"}`}>
                        {fmtAngka(b.doc_hari, 1)}
                      </td>
                      <td className="text-right px-1 font-mono text-[#B45309]">{fmtAngka(b.safety_hari, 1)}</td>
                      <td className="pl-2 text-[#64676C]">{t(b.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {d.bulan_tak_terhitung.length > 0 && (
              <div className="mt-2 rounded-sm bg-[#FFFBEB] border border-[#FDE68A] px-3 py-2 text-xs text-[#B45309]">
                <div className="font-semibold mb-0.5">{t("Bulan tidak bisa dihitung:")}</div>
                {d.bulan_tak_terhitung.map((x: any) => (
                  <div key={x.bulan}>• {x.bulan} — {x.alasan}</div>
                ))}
              </div>
            )}
            {d.catatan.map((c: string, i: number) => (
              <p key={i} className="mt-1 text-[11px] text-[#64676C]">{c}</p>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

/* ==========================================================================
   Halaman depan: angka kunci + "perlu perhatian".
   Tujuan: pembaca tahu posisi margin dan apa yang harus dilakukan hari ini
   tanpa membuka menu lain. Semua angka berasal dari endpoint yang sudah ada.
   ========================================================================== */

const tandaAngka = (n: number | null | undefined, des = 2) =>
  n === null || n === undefined ? "–" : (n > 0 ? "+" : "") + fmtAngka(n, des);

const potong = (s: string, n = 110) =>
  s.length > n ? `${s.slice(0, n).trimEnd()}…` : s;

function BlokAngka({ label, angka, nilai, desimal = 2, satuan, bawah, arah, nada, anakTambahan }: {
  label: string;
  angka?: string;
  nilai?: number | null;
  desimal?: number;
  satuan?: string;
  bawah: ReactNode;
  arah?: "naik" | "turun" | null;
  nada?: "baik" | "buruk" | "netral";
  anakTambahan?: ReactNode;
}) {
  const hitung = useCountUp(nilai);
  const angkaTampil = nilai !== undefined
    ? hitung.nilai === null ? "–" : fmtAngka(hitung.nilai, desimal)
    : angka ?? "–";
  const warna = nada === "buruk" ? "text-[#FF1313]" : "text-[#1D2434]";
  const warnaNilai = hitung.kilat
    ? hitung.arah === "naik" ? "text-[#15803D]" : "text-[#FF1313]"
    : warna;
  const warnaKotak = nada === "baik" ? "border-l-[#16A34A] bg-[#F0FDF4]"
    : nada === "buruk" ? "border-l-[#DC2626] bg-[#FEF2F2]" : "border-l-[#EDEFF2] bg-white";
  return (
    <div className={`border-l px-4 py-3 first:border-l-0 first:pl-0 ${warnaKotak}`}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#64676C]">
        {label}
      </p>
      <p className={`mt-1 flex items-baseline gap-1 font-mono text-2xl font-bold tabular-nums ${warnaNilai}`}>
        {angkaTampil}
        {satuan && <span className="text-xs font-normal text-[#64676C]">{satuan}</span>}
        {hitung.kilat && hitung.arah && (
          <span aria-hidden="true" className={`kilat-angka ${hitung.arah === "naik" ? "text-[#15803D]" : "text-[#FF1313]"}`}>
            {hitung.arah === "naik" ? "▲" : "▼"}
          </span>
        )}
      </p>
      <p className={`mt-0.5 flex items-start gap-1 text-[11px] leading-snug ${
        nada === "baik" ? "text-[#15803D]" : nada === "buruk" ? "text-[#DC2626]" : "text-[#64676C]"}`}>
        {nada && nada !== "netral" && <span aria-hidden className="mt-[1px] shrink-0">●</span>}
        {arah && (
          <span aria-hidden className="mt-[1px] shrink-0">
            {arah === "naik" ? "▲" : "▼"}
          </span>
        )}
        <span>{bawah}</span>
      </p>
      {anakTambahan}
    </div>
  );
}

const ymDariBulan = (thn: number, bln: number) =>
  `${thn}-${String(bln).padStart(2, "0")}`;

function StripAngkaKunci({ thn, data, ke }: {
  thn: number | null;
  data: any;
  ke?: (tab: string) => void;
}) {
  const { t } = useBahasa();
  const berdata: any[] = (data?.bulan ?? []).filter(
    (b: any) => b.op_margin !== null && b.op_margin !== undefined);
  const kini = berdata.length ? berdata[berdata.length - 1] : null;
  const lalu = berdata.length > 1 ? berdata[berdata.length - 2] : null;

  const doc = useQueryKartu({
    queryKey: ["doc-strip"],
    queryFn: () => ambilJson("/api/days-of-cover"),
  });
  const qsBridge = kini && lalu && thn !== null
    ? `?dari=${ymDariBulan(thn, lalu.bulan)}&sampai=${ymDariBulan(thn, kini.bulan)}`
    : "";
  const bridge = useQueryKartu({
    queryKey: ["bridge-strip", qsBridge],
    queryFn: () => ambilJson(`/api/margin-bridge${qsBridge}`),
  });

  const langkahSicom = bridge.data?.langkah?.find((l: any) => l.kode === "sicom");
  const langkahOp = bridge.data?.langkah?.find((l: any) => l.kode === "op_price");
  const dSicom = langkahSicom?.perubahan_mentah ?? null;
  const dOp = langkahOp?.perubahan_mentah ?? null;
  const docKini = doc.data?.terkini ?? null;

  if (!kini) return null;

  const label = `${NAMA_BULAN[kini.bulan]}-${String(thn ?? "").slice(2)}`;
  const selisih = kini.op_margin != null && lalu?.op_margin != null
    ? kini.op_margin - lalu.op_margin : null;
  const intakeChange = kini.ton != null && lalu?.ton != null ? kini.ton - lalu.ton : null;
  const statusTarget = kini.target == null ? "netral" : (kini.vs_target ?? 0) >= 0 ? "baik" : "buruk";
  const statusMargin = selisih === null || selisih === 0 ? "netral" : selisih > 0 ? "baik" : "buruk";
  const statusSicom = dSicom === null || dSicom === 0 ? "netral" : dSicom > 0 ? "baik" : "buruk";
  const statusDoc = docKini?.status === "aman" ? "baik"
    : docKini?.status === "di bawah safety" ? "buruk" : "netral";
  const statusIntake = intakeChange === null || intakeChange === 0 ? "netral"
    : intakeChange > 0 ? "baik" : "buruk";

  return (
    <section className="rounded-sm border border-[#E4E5E8] bg-white shadow-[0_1px_3px_rgba(29,36,52,0.08)]">
      <div className="overflow-x-auto">
        <div className="grid min-w-[1100px] grid-cols-5 gap-0 px-5 py-1">
        <BlokAngka
          label={`${t("OP Margin")} · ${label}`}
          nilai={kini.op_margin}
          desimal={2}
          satuan="US¢/kg"
          arah={statusTarget === "netral" ? null : statusTarget === "baik" ? "naik" : "turun"}
          nada={statusTarget}
          bawah={kini.target != null
            ? `${statusTarget === "baik" ? "Kabar baik" : "Kabar buruk"}: margin ${statusTarget === "baik" ? "di atas" : "di bawah"} target ${fmtAngka(Math.abs(kini.vs_target ?? 0), 2)} US¢/kg (target ${fmtAngka(kini.target, 2)}).`
            : "Belum ada target; status kinerja belum dapat dinilai."}
        />
        <BlokAngka
          label={`${t("Perubahan vs")} ${lalu ? `${NAMA_BULAN[lalu.bulan]}-${String(thn ?? "").slice(2)}` : "–"}`}
          angka={tandaAngka(selisih)}
          satuan="US¢/kg"
          arah={statusMargin === "netral" ? null : statusMargin === "baik" ? "naik" : "turun"}
          nada={statusMargin}
          bawah={selisih === null ? "Belum ada bulan berdata sebelumnya sebagai pembanding."
            : selisih > 0 ? `Kabar baik: margin naik ${fmtAngka(selisih, 2)} US¢/kg vs bulan berdata sebelumnya.`
            : selisih < 0 ? `Kabar buruk: margin turun ${fmtAngka(Math.abs(selisih), 2)} US¢/kg vs bulan berdata sebelumnya.`
            : "Margin stabil dibanding bulan berdata sebelumnya."}
        />
        <BlokAngka
          label={`${t("SICOM")} · ${label}`}
          nilai={kini.sicom}
          desimal={2}
          satuan="US¢/kg"
          arah={statusSicom === "netral" ? null : statusSicom === "baik" ? "naik" : "turun"}
          nada={statusSicom}
          bawah={dSicom === null ? "Belum ada perubahan historis untuk dibandingkan."
            : dSicom > 0 ? `Kabar baik: SICOM naik ${fmtAngka(dSicom, 2)}; mendukung margin bila OP Price tidak naik sebanding.`
            : dSicom < 0 ? `Kabar buruk: SICOM turun ${fmtAngka(Math.abs(dSicom), 2)}; menekan margin bila OP Price tidak turun mengimbangi.`
            : "SICOM stabil dibanding bulan berdata sebelumnya."}
        />
        <BlokAngka
          label={`Days of Cover · ${docKini?.bulan ?? "–"}`}
          nilai={docKini?.doc_hari ?? null}
          desimal={1}
          satuan={t("hari")}
          arah={statusDoc === "netral" ? null : statusDoc === "baik" ? "naik" : "turun"}
          nada={statusDoc}
          bawah={docKini?.safety_hari != null
            ? `${statusDoc === "baik" ? "Kabar baik" : "Kabar buruk"}: cover ${fmtAngka(docKini.doc_hari, 1)} hari; safety ${fmtAngka(docKini.safety_hari, 1)} hari.`
            : "Belum ada safety atau data yang cukup untuk menilai cover."}
          anakTambahan={docKini?.doc_hari != null && docKini?.safety_hari != null
            ? <PengukurAmbang label="Rasio terhadap safety" nilai={docKini.doc_hari}
                ambang={docKini.safety_hari} nilaiTeks={`${fmtAngka(docKini.doc_hari, 1)} hari`}
                ambangTeks={`${fmtAngka(docKini.safety_hari, 1)} hari`} />
            : null}
        />
        <BlokAngka
          label={`${t("Intake")} · ${label}`}
          nilai={kini.ton}
          desimal={2}
          satuan={t("ton kering")}
          arah={statusIntake === "netral" ? null : statusIntake === "baik" ? "naik" : "turun"}
          nada={statusIntake}
          bawah={intakeChange === null ? `${kini.hari_pembelian ?? "–"} hari pembelian; belum ada pembanding.`
            : intakeChange > 0 ? `Kabar baik: volume intake naik ${fmtAngka(intakeChange, 2)} ton dari bulan berdata sebelumnya.`
            : intakeChange < 0 ? `Kabar buruk: volume intake turun ${fmtAngka(Math.abs(intakeChange), 2)} ton dari bulan berdata sebelumnya.`
            : "Volume intake sama dengan bulan berdata sebelumnya."}
        />
        </div>
      </div>
      <p className="border-t border-[#EDEFF2] px-5 py-2 text-[11px] text-[#9AA0A6]">
        {t("Pada blok perubahan, SICOM dan OP Price adalah perubahan harga bulan itu (US¢/kg): SICOM naik menolong margin, OP Price naik menekan margin. Rincian angkanya ada di Margin Bridge pada kartu di bawah.")}
        {ke && (
          <>{" "}
            <button className="font-semibold text-[#FF1313] underline"
                    onClick={() => ke("analisis")}>
              {t("Lihat analisa lengkap")}
            </button>
          </>
        )}
      </p>
    </section>
  );
}

type BarisPerhatian = {
  kunci: string;
  judul: string;
  isi: string;
  tab: string;
  tautan: string;
  nada: "merah" | "kuning" | "abu";
};

function PanelPerhatian({ ke }: { ke?: (tab: string) => void }) {
  const { t } = useBahasa();
  const alarm = useQueryKartu({ queryKey: ["alarm-strip"], queryFn: () => ambilJson("/api/alarm") });
  const kualitas = useQueryKartu({ queryKey: ["kualitas-strip"], queryFn: () => ambilJson("/api/kualitas") });
  const rekom = useQueryKartu({ queryKey: ["rekomendasi-strip"], queryFn: () => ambilJson("/api/rekomendasi") });

  const baris: BarisPerhatian[] = [];

  const r = rekom.data;
  if (r) {
    if (r.status === "OK" && r.harga_beli_maks_rp_kg != null) {
      baris.push({
        kunci: "rekom",
        judul: `${t("Harga beli maksimum hari ini")}: Rp ${fmtAngka(r.harga_beli_maks_rp_kg, 0)}/kg`,
        isi: `${fmtAngka(r.harga_beli_maks_usc, 2)} US¢/kg · ` +
             (r.alasan?.[0] ?? t("sesuai aturan stok → harga yang berlaku")),
        tab: "aturan", tautan: t("Aturan Harga"), nada: "abu",
      });
    } else {
      baris.push({
        kunci: "rekom",
        judul: t("Rekomendasi harga beli belum bisa dihitung"),
        isi: `${r.alasan?.[0] ?? t("data belum lengkap")} ` +
             (r.tanggal ? `(${fmtTanggal(r.tanggal)})` : ""),
        tab: "aturan", tautan: t("Aturan Harga"), nada: "kuning",
      });
    }
  }

  const telat = (kualitas.data?.terlambat ?? []).filter((x: any) => x.terlambat);
  if (telat.length) {
    baris.push({
      kunci: "telat",
      judul: t("Ada data yang belum diperbarui"),
      isi: telat.map((x: any) => `${x.sumber} ${x.umur_hari} ${t("hari")}`).join(" · "),
      tab: "input", tautan: t("Input Harian"), nada: "kuning",
    });
  }

  const daftarAlarm = alarm.data?.alarm ?? [];
  if (daftarAlarm.length) {
    baris.push({
      kunci: "alarm",
      judul: `${daftarAlarm.length} ${t("temuan alarm")}`,
      isi: potong(daftarAlarm[0].pesan),
      tab: "alarm", tautan: t("Alarm"), nada: "merah",
    });
  }

  if (!baris.length && (alarm.isLoading || kualitas.isLoading || rekom.isLoading)) {
    return <KerangkaMuatKartu />;
  }
  if (!baris.length) return null;
  const urutan = { merah: 0, kuning: 1, abu: 2 };
  baris.sort((a, b) => urutan[a.nada] - urutan[b.nada]);

  const kelasNada = {
    merah: "border-l-[#FF1313]",
    kuning: "border-l-[#EAB308]",
    abu: "border-l-[#1D2434]",
  };

  return (
    <section className="rounded-sm border border-[#E4E5E8] bg-white shadow-[0_1px_3px_rgba(29,36,52,0.08)]">
      <div className="flex items-baseline justify-between gap-3 border-b border-[#EDEFF2] px-5 pt-4 pb-2">
        <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-[#1D2434]">
          {t("Perlu perhatian hari ini")}
        </h2>
        <span className="text-[11px] text-[#9AA0A6]">
          {t("diurutkan dari yang paling mendesak")}
        </span>
      </div>
      <ul className="divide-y divide-[#EDEFF2]">
        {baris.map((b) => (
          <li key={b.kunci}
              className={`flex items-start gap-3 border-l-2 px-5 py-2.5 ${kelasNada[b.nada]}`}>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-[#1D2434]">{b.judul}</p>
              <p className="mt-0.5 text-xs leading-snug text-[#64676C]">{b.isi}</p>
            </div>
            {ke && (
              <button className="shrink-0 text-xs font-semibold text-[#FF1313] underline"
                      onClick={() => ke(b.tab)}>
                {b.tautan} →
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ---------- halaman ---------- */
export default function Ringkasan({ ke }: { ke?: (tab: string) => void }) {
  const { t } = useBahasa();
  const [ringkasanDiminta, setRingkasanDiminta] = useState(false);
  const tahunQ = useQuery({ queryKey: ["tahun"], queryFn: () => ambilJson("/api/tahun"), staleTime: Infinity });
  const [tahun, setTahun] = useState<number | null>(null);
  const thn = tahun ?? (tahunQ.data ? tahunQ.data[tahunQ.data.length - 1] : null);

  const ringkas = useQuery({
    queryKey: ["ringkasan", thn],
    queryFn: () => ambilJson(`/api/ringkasan/${thn}`),
    enabled: ringkasanDiminta && thn !== null,
    staleTime: Infinity,
  });
  // Kartu "Angka kunci" punya query sendiri yang AKTIF sejak halaman dibuka.
  // Query `ringkas` di bawah tetap dikunci oleh Refresh kartu "OP Margin bulanan".
  const ringkasOtomatis = useQuery({
    queryKey: ["ringkasan-angka-kunci", thn],
    queryFn: () => ambilJson(`/api/ringkasan/${thn}`),
    enabled: thn !== null,
    staleTime: Infinity,
  });
  const tahunKosongOtomatis = !tahunQ.isLoading &&
    Array.isArray(tahunQ.data) && tahunQ.data.length === 0;
  const galatOtomatis = ringkasOtomatis.error ?? tahunQ.error;
  const siapOtomatis = !!ringkasOtomatis.data || !!galatOtomatis || tahunKosongOtomatis;
  const tahunKosong = ringkasanDiminta && !tahunQ.isLoading &&
    Array.isArray(tahunQ.data) && tahunQ.data.length === 0;
  const siapRingkasan = !!ringkas.data || !!ringkas.error || !!tahunQ.error || tahunKosong;
  const galatRingkasan = ringkas.error ?? tahunQ.error;
  const [telusur, setTelusur] = useState<number | null>(null);

  const label = [
    ["sicom", "SICOM", 2], ["op_price", "OP Price", 2], ["op_margin", "OP Margin", 2],
    ["ton", "Ton (kering)", 2], ["target", "Target", 2],
    ["pencapaian", "Pencapaian", 2], ["vs_target", "vs Target", 2],
  ] as const;

  return (
    <div className="grid gap-6">
      <KartuMuatSaatDiminta
        otomatis
        judul="Angka kunci Margin Performance"
        keterangan="Indikator ringkas, margin, days of cover, dan perubahan harga."
        siap={siapOtomatis}
        anak={galatOtomatis
          ? <p className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3 text-sm text-[#64676C]">{pesanGalat(galatOtomatis)}</p>
          : tahunKosongOtomatis
            ? <p className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3 text-sm text-[#64676C]">Belum ada data margin untuk ditampilkan.</p>
            : ringkasOtomatis.isLoading
              ? <KerangkaMuatKartu />
              : <StripAngkaKunci thn={thn} data={ringkasOtomatis.data} ke={ke} />}
      />

      <KartuMuatSaatDiminta
        judul="Perlu perhatian hari ini"
        keterangan="Pemeriksaan alarm, kualitas data, dan rekomendasi harga dimuat saat diminta."
        anak={<PanelPerhatian ke={ke} />}
      />

      <KartuMuatSaatDiminta
        letakRefresh="filter"
        judul="OP Margin bulanan"
        keterangan="Tabel margin dan harga bulanan. Data baru dimuat setelah Anda meminta."
        siap={siapRingkasan}
        setelahDiminta={() => setRingkasanDiminta(true)}
        kunciRefreshTambahan={[["tahun"], ["ringkasan", thn]]}
        anak={galatRingkasan
          ? <><p className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3 text-sm text-[#64676C]">{pesanGalat(galatRingkasan)}</p><TombolRefreshKartu className="mt-2" /></>
          : tahunKosong
            ? <><p className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3 text-sm text-[#64676C]">Belum ada data margin untuk ditampilkan.</p><TombolRefreshKartu className="mt-2" /></>
            : <Kartu idMetrik="ringkasan" judul={`${t("OP Margin bulanan")} — ${thn ?? ""}`}
             keterangan={t("US¢/kg, basis berat kering — meniru Excel lama. Klik angka OP Margin untuk menelusuri asal angkanya.")}
             urlEkspor={thn ? `/api/ringkasan/${thn}` : undefined}
             qsJelaskan={thn ? `?tahun=${thn}` : ""}
             anak={
        <>
          <div className="mb-3 flex gap-1 flex-wrap">
            {tahunQ.data?.map((th: number) => (
              <button key={th}
                className={`rounded-sm px-3 py-1 text-sm ${th === thn
                  ? "bg-[#FF1313] text-white" : "bg-[#F1F2F4] text-[#1D2434] hover:bg-[#E8E9EC]"}`}
                onClick={() => { setTahun(th); setRingkasanDiminta(false); }}>
                {th}
              </button>
            ))}
            <TombolRefreshKartu className="ml-auto" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[#64676C] border-b">
                  <th className="py-1 pr-2"> </th>
                  {ringkas.data?.bulan.map((b: any) => (
                    <th key={b.bulan} className="text-right px-1">{NAMA_BULAN[b.bulan]}</th>
                  ))}
                  <th className="text-right px-1 font-semibold">{t("Avg YTD")}</th>
                  <th className="text-right px-1" title="Rata-rata OP Margin dengan bobot tonase kering; bulan dengan tonase lebih besar lebih berpengaruh.">{t("Tertimbang (Margin)")}</th>
                </tr>
              </thead>
              <tbody>
                {ringkas.isLoading && !ringkas.data
                  ? <KerangkaMuatTabel kolom={15} baris={7} />
                  : label.map(([kunci, nama]) => (
                  <tr key={kunci} className="border-b border-[#EDEFF2]">
                    <td className="py-1 pr-2 font-medium text-[#1D2434] whitespace-nowrap">{t(nama)}</td>
                    {ringkas.data?.bulan.map((b: any) => (
                      <td key={b.bulan}
                          className={`text-right px-1 font-mono ${
                            kunci === "op_margin" ? "text-[#FF1313] cursor-pointer underline" : ""} ${
                            b.catatan_koreksi && kunci === "op_margin" ? "bg-[#FFFBEB]" : ""}`}
                          title={kunci === "op_margin" ? (b.catatan_koreksi ?? "klik untuk telusur") : undefined}
                          onClick={() => kunci === "op_margin" && setTelusur(b.bulan)}>
                        {kunci === "pencapaian"
                          ? (b.pencapaian !== null ? fmtAngka(b.pencapaian * 100, 2) + "%" : "–")
                          : fmtAngka(b[kunci], 2)}
                      </td>
                    ))}
                    <td className="text-right px-1 font-mono font-semibold">
                      {kunci === "sicom" ? fmtAngka(ringkas.data?.avg_ytd_sicom_sederhana, 2)
                        : kunci === "op_price" ? fmtAngka(ringkas.data?.avg_ytd_op_price_sederhana, 2)
                        : kunci === "op_margin" ? fmtAngka(ringkas.data?.avg_ytd_sederhana, 2) : ""}
                    </td>
                    <td className="text-right px-1 font-mono text-[#64676C]">
                      {kunci === "op_margin" ? fmtAngka(ringkas.data?.avg_ytd_tertimbang, 2) : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {ringkas.data?.catatan.map((c: string, i: number) => (
            <p key={i} className="mt-2 rounded-sm bg-[#FFFBEB] border border-[#FDE68A] px-3 py-2 text-xs text-[#B45309]">
              {t("Catatan koreksi:")} {c}
            </p>
          ))}
          <p className="mt-2 text-xs text-[#64676C]">
            {t('Avg YTD = rata-rata sederhana dari bulan yang memiliki data, tersedia untuk SICOM, OP Price, dan OP Margin. Tertimbang (Margin) = Σ(OP Margin × ton kering) ÷ Σ(ton kering); bulan dengan tonase lebih besar memiliki pengaruh lebih besar.')}
          </p>
        </>
      } />} />

      <KartuMuatSaatDiminta
        letakRefresh="filter"
        judul="Margin bulanan vs target"
        keterangan="Grafik tren margin dan perbandingan antar tahun dimuat setelah Anda meminta."
        anak={<KartuGrafikMargin />}
      />

      <KartuMuatSaatDiminta
        letakRefresh="filter"
        judul="RM Stock – Intake vs Pricing"
        keterangan="Grafik stok, intake, dan harga dimuat setelah Anda meminta."
        anak={<KartuElemen />}
      />

      {telusur !== null && thn !== null && (
        <Telusur tahun={thn} bulan={telusur} tutup={() => setTelusur(null)} />
      )}
    </div>
  );
}
