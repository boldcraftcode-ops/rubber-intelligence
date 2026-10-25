import { Fragment, ReactNode, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, LabelList, Legend, Line,
  LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Kartu, NAMA_BULAN, Panel5W1H, ambilJson, fmtAngka, fmtTanggal, kelasTombolAnalisa, kelasTombolKecil, pesanGalat, urlApi } from "../bersama";
import { useBahasa } from "../i18n";

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

/* ---------- elemen OP Margin: RM Stock-Intake vs Pricing (seperti Excel) ---------- */
function KartuElemen() {
  const { t } = useBahasa();
  const [dari, setDari] = useState("");
  const [sampai, setSampai] = useState("");
  const [panel, setPanel] = useState<null | "5w1h" | "bridge" | "doc">(null);
  const params = new URLSearchParams();
  if (dari) params.set("dari", dari);
  if (sampai) params.set("sampai", sampai);
  const qs = params.size ? "?" + params.toString() : "";
  const url = `/api/ringkasan-elemen${qs}`;
  const urlAnalisa = `/api/ringkasan-elemen/analisa${qs}`;

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

  const q = useQuery({
    queryKey: ["ringkasan-elemen", url],
    queryFn: () => ambilJson(url),
  });

  return (
    <Kartu idMetrik="elemen_op_margin" judul={t("RM Stock – Intake vs Pricing")}
           keterangan={t("Elemen pemengaruh OP Margin per bulan, disamakan dengan Excel: batang = ton (sumbu kiri), garis = US¢/kg (sumbu kanan).")}
           urlEkspor={url}
           qsJelaskan={qs}
           anak={
      <>
        <div className="flex flex-wrap items-end gap-3 mb-3 text-xs">
          <div>
            <label className="block text-[#64676C] mb-1">{t("Dari bulan")}</label>
            <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-[#1D2434]"
                   value={dari} onChange={(e) => setDari(e.target.value)} />
          </div>
          <div>
            <label className="block text-[#64676C] mb-1">{t("Sampai bulan")}</label>
            <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-[#1D2434]"
                   value={sampai} onChange={(e) => setSampai(e.target.value)} />
          </div>
          {(dari || sampai) && (
            <button className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-2.5 py-1.5 text-[#1D2434] hover:bg-[#FFF1F1]"
                    onClick={() => { setDari(""); setSampai(""); }}>
              {t("tampilkan semua periode")}
            </button>
          )}
          <span className="text-[#64676C]">
            {q.data ? `${q.data.baris.length} ${t("bulan ditampilkan")}` : ""}
          </span>
          <div className="ml-auto flex flex-wrap gap-2">
            <button className={kelasTombolAnalisa} onClick={() => setPanel("5w1h")}>
              ✨ 5W1H
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
                     url={urlAnalisa + qsPeriode} tutup={() => setPanel(null)} />
        )}
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
          <ResponsiveContainer>
            <ComposedChart data={q.data?.baris ?? []}
                           margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" fontSize={10} minTickGap={18} />
              <YAxis yAxisId="ton" fontSize={10}
                     label={{ value: "ton", angle: -90, position: "insideLeft",
                              fontSize: 11, fill: "#1D2434" }} />
              <YAxis yAxisId="usc" orientation="right" fontSize={10}
                     domain={["auto", "auto"]}
                     label={{ value: "US¢/kg", angle: 90, position: "insideRight",
                              fontSize: 11, fill: "#1D2434" }} />
              <Tooltip formatter={(v: any, nama: any) => [fmtAngka(v as number, 2), nama]} />
              <Legend />
              <Bar yAxisId="ton" dataKey="intake_ton" name="Intake"
                   fill="#FF1313" opacity={0.9} />
              <Bar yAxisId="ton" dataKey="rm_stock_ton" name="RM Stock"
                   fill="#1D2434" opacity={0.85} />
              <Line yAxisId="ton" dataKey="safety_ton" name="Safety Level Stock"
                    stroke="#B45309" strokeDasharray="6 3" dot={false}
                    type="stepAfter" strokeWidth={1.5} />
              <Line yAxisId="usc" dataKey="sicom" name="SICOM"
                    stroke="#1D2434" dot={false} strokeWidth={2} connectNulls />
              <Line yAxisId="usc" dataKey="op_price" name="OP Price"
                    stroke="#FF1313" dot={false} strokeWidth={2} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-3 max-h-56 overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[#64676C] border-b">
                <th className="py-1">{t("Date")}</th>
                <th className="text-right">RM Stock</th>
                <th className="text-right">Intake</th>
                <th className="text-right">{t("Safety")}</th>
                <th className="text-right">SICOM</th>
                <th className="text-right">OP Price</th>
                <th className="text-right">OP Margin</th>
                <th className="pl-2">{t("Sumber intake")}</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.baris.map((b: any) => (
                <tr key={b.label} className={`border-b border-[#EDEFF2] ${
                    b.stok_sebagian ? "bg-[#FFFBEB]" : ""}`}>
                  <td className="py-1">{b.label}{b.stok_sebagian ? " *" : ""}</td>
                  <td className="text-right font-mono">{fmtAngka(b.rm_stock_ton, 3)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.intake_ton, 3)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.safety_ton, 1)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.sicom, 4)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.op_price, 4)}</td>
                  <td className={`text-right font-mono font-semibold ${
                    b.op_margin === null ? "" : b.op_margin >= 0
                      ? "text-[#15803D]" : "text-[#DC2626]"}`}>
                    {fmtAngka(b.op_margin, 4)}
                  </td>
                  <td className="pl-2 text-[#64676C]">{b.sumber_intake ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {q.data?.catatan.map((c: string, i: number) => (
          <p key={i} className="mt-2 rounded-sm bg-[#FFFBEB] border border-[#FDE68A] px-3 py-2 text-xs text-[#B45309]">
            {c}
          </p>
        ))}
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

  const bulanan = useQuery({
    queryKey: ["margin-bulanan-grafik", qs],
    queryFn: () => ambilJson(`/api/kartu/margin-bulanan${qs}`),
  });
  const antar = useQuery({
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
          <div>
            <label className="block text-[#64676C] mb-1">{t("Dari bulan")}</label>
            <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-[#1D2434]"
                   value={dari} onChange={(e) => setDari(e.target.value)} />
          </div>
          <div>
            <label className="block text-[#64676C] mb-1">{t("Sampai bulan")}</label>
            <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-[#1D2434]"
                   value={sampai} onChange={(e) => setSampai(e.target.value)} />
          </div>
          {(dari || sampai) && (
            <button className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-2.5 py-1.5 text-[#1D2434] hover:bg-[#FFF1F1]"
                    onClick={() => { setDari(""); setSampai(""); }}>
              {t("tampilkan semua periode")}
            </button>
          )}
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
              <ResponsiveContainer>
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
                    const lain = pakaiRp
                      ? (p.kurs ? `≈ ${fmtAngka(p.marginUsc, 2)} US¢/kg` : null)
                      : (p.kurs ? `≈ ${fmtAngka(p.marginUsc * p.kurs / 100, 0)} Rp/kg` : null);
                    return (
                      <div className="rounded-sm bg-white border border-[#E4E5E8] p-2 text-xs shadow">
                        <b>{label}</b><br />
                        {t("Margin")}: <b>{fmtNilai(p.margin ?? 0)}</b> {satuan}
                        {lain && <span className="text-[#64676C]"> ({lain})</span>}<br />
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
              </ResponsiveContainer>
            </div>

            {/* Panel selisih terhadap target: satu pandangan melihat bulan minus */}
            <div className="mt-2">
              <div className="text-[11px] text-[#64676C] mb-0.5">
                {t("Selisih terhadap target (ke atas = di atas target, ke bawah = kurang)")}
              </div>
              <div className="h-24">
                <ResponsiveContainer>
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
                </ResponsiveContainer>
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
              <ResponsiveContainer>
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
              </ResponsiveContainer>
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
function KepalaPanel({ judul, periode, url, tutup }: {
  judul: string; periode?: string; url: string; tutup: () => void;
}) {
  const { t } = useBahasa();
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <h3 className="text-lg font-semibold text-[#1D2434]">{judul}</h3>
        {periode && <p className="text-sm text-[#64676C]">{t("Periode")}: {periode}</p>}
      </div>
      <div className="flex gap-2 shrink-0">
        <a className={kelasTombolKecil}
           href={urlApi(`${url}${url.includes("?") ? "&" : "?"}format=xlsx`)}>
          {t("Ekspor Excel")}
        </a>
        <button className={kelasTombolKecil} onClick={tutup}>{t("Tutup")}</button>
      </div>
    </div>
  );
}

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
          <div>
            <label className="block text-[#64676C] mb-1">{t("Periode awal")}</label>
            <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-[#1D2434]"
                   value={awal} onChange={(e) => ubah(e.target.value, akhir)} />
          </div>
          <div>
            <label className="block text-[#64676C] mb-1">{t("Periode akhir")}</label>
            <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-[#1D2434]"
                   value={akhir} onChange={(e) => ubah(awal, e.target.value)} />
          </div>
          <p className="text-[#64676C]">{t("Bawaan: mengikuti filter kartu grafik.")}</p>
        </div>

        <p className="mt-2 text-sm text-[#1D2434] font-mono">
          ΔM = ΔSICOM − ΔOP Price
        </p>
        <p className="text-xs text-[#64676C]">
          {t("SICOM = harga acuan pasar (di luar kendali), OP Price = harga beli kita (keputusan). SICOM turun menekan margin; OP Price turun justru menolong.")}
        </p>

        {q.isLoading && <p className="mt-4 text-sm text-[#64676C]">{t("Memuat…")}</p>}
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
              <ResponsiveContainer width="100%" height="100%">
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
              </ResponsiveContainer>
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
          <div>
            <label className="block text-[#64676C] mb-1">{t("Dari bulan")}</label>
            <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-[#1D2434]"
                   value={awal} onChange={(e) => ubah(e.target.value, akhir)} />
          </div>
          <div>
            <label className="block text-[#64676C] mb-1">{t("Sampai bulan")}</label>
            <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-[#1D2434]"
                   value={akhir} onChange={(e) => ubah(awal, e.target.value)} />
          </div>
        </div>

        <p className="mt-2 text-sm text-[#1D2434] font-mono">
          Pemakaian = Stok awal + Intake − Stok akhir; DoC = Stok akhir ÷ (Pemakaian ÷ hari)
        </p>
        <p className="text-xs text-[#64676C]">
          {t("Pemakaian tidak ada di data, jadi dihitung dari neraca stok. DoC lebih adil daripada tonase karena menyesuaikan pemakaian.")}
        </p>

        {q.isLoading && <p className="mt-4 text-sm text-[#64676C]">{t("Memuat…")}</p>}
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
              <ResponsiveContainer width="100%" height="100%">
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
              </ResponsiveContainer>
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

function BlokAngka({ label, angka, satuan, bawah, arah, nada }: {
  label: string;
  angka: string;
  satuan?: string;
  bawah: ReactNode;
  arah?: "naik" | "turun" | null;
  nada?: "navy" | "merah";
}) {
  return (
    <div className="border-l border-[#EDEFF2] px-4 py-3 first:border-l-0 first:pl-0">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#64676C]">
        {label}
      </p>
      <p className={`mt-1 flex items-baseline gap-1 font-mono text-2xl font-bold ${
        nada === "merah" ? "text-[#FF1313]" : "text-[#1D2434]"}`}>
        {angka}
        {satuan && <span className="text-xs font-normal text-[#64676C]">{satuan}</span>}
      </p>
      <p className="mt-0.5 flex items-start gap-1 text-[11px] leading-snug text-[#64676C]">
        {arah && (
          <span aria-hidden className="mt-[1px] shrink-0">
            {arah === "naik" ? "▲" : "▼"}
          </span>
        )}
        <span>{bawah}</span>
      </p>
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

  const doc = useQuery({
    queryKey: ["doc-strip"],
    queryFn: () => ambilJson("/api/days-of-cover"),
  });
  const qsBridge = kini && lalu && thn !== null
    ? `?dari=${ymDariBulan(thn, lalu.bulan)}&sampai=${ymDariBulan(thn, kini.bulan)}`
    : "";
  const bridge = useQuery({
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
  const diAtasTarget = (kini.vs_target ?? 0) >= 0;
  const selisih = kini.op_margin != null && lalu?.op_margin != null
    ? kini.op_margin - lalu.op_margin : null;
  const diBawahSafety = docKini?.status === "di bawah safety";

  return (
    <section className="rounded-sm border border-[#E4E5E8] bg-white shadow-[0_1px_3px_rgba(29,36,52,0.08)]">
      <div className="grid gap-0 px-5 py-1 sm:grid-cols-2 xl:grid-cols-5">
        <BlokAngka
          label={`${t("OP Margin")} · ${label}`}
          angka={fmtAngka(kini.op_margin, 2)}
          satuan="US¢/kg"
          arah={diAtasTarget ? "naik" : "turun"}
          nada={diAtasTarget ? "navy" : "merah"}
          bawah={kini.target != null
            ? `${diAtasTarget ? t("di atas") : t("di bawah")} ${t("target")} ` +
              `${fmtAngka(Math.abs(kini.vs_target ?? 0), 2)} (${t("target")} ` +
              `${fmtAngka(kini.target, 1)})`
            : t("target belum diisi")}
        />
        <BlokAngka
          label={`${t("Perubahan vs")} ${lalu ? `${NAMA_BULAN[lalu.bulan]}-${String(thn ?? "").slice(2)}` : "–"}`}
          angka={tandaAngka(selisih)}
          satuan="US¢/kg"
          arah={selisih === null ? null : selisih >= 0 ? "naik" : "turun"}
          nada={selisih !== null && selisih < 0 ? "merah" : "navy"}
          bawah={dSicom !== null || dOp !== null
            ? `${t("SICOM")} ${tandaAngka(dSicom)} · ${t("OP Price")} ${tandaAngka(dOp)}`
            : t("rincian penyebab belum tersedia")}
        />
        <BlokAngka
          label={`${t("SICOM")} · ${label}`}
          angka={fmtAngka(kini.sicom, 2)}
          satuan="US¢/kg"
          bawah={t("harga acuan pasar, di luar kendali")}
        />
        <BlokAngka
          label={`Days of Cover · ${docKini?.bulan ?? "–"}`}
          angka={docKini?.doc_hari != null ? fmtAngka(docKini.doc_hari, 1) : "–"}
          satuan={t("hari")}
          nada={diBawahSafety ? "merah" : "navy"}
          bawah={docKini?.safety_hari != null
            ? `${t(docKini.status ?? "–")} · ${t("safety")} ${fmtAngka(docKini.safety_hari, 1)} ${t("hari")}`
            : t("belum bisa dihitung")}
        />
        <BlokAngka
          label={`${t("Intake")} · ${label}`}
          angka={fmtAngka(kini.ton, 0)}
          satuan={t("ton kering")}
          bawah={`${kini.hari_pembelian ?? "–"} ${t("hari pembelian")}`}
        />
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
  const alarm = useQuery({ queryKey: ["alarm-strip"], queryFn: () => ambilJson("/api/alarm") });
  const kualitas = useQuery({ queryKey: ["kualitas-strip"], queryFn: () => ambilJson("/api/kualitas") });
  const rekom = useQuery({ queryKey: ["rekomendasi-strip"], queryFn: () => ambilJson("/api/rekomendasi") });

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
  const tahunQ = useQuery({ queryKey: ["tahun"], queryFn: () => ambilJson("/api/tahun") });
  const [tahun, setTahun] = useState<number | null>(null);
  const thn = tahun ?? (tahunQ.data ? tahunQ.data[tahunQ.data.length - 1] : null);

  const ringkas = useQuery({
    queryKey: ["ringkasan", thn],
    queryFn: () => ambilJson(`/api/ringkasan/${thn}`),
    enabled: thn !== null,
  });
  const [telusur, setTelusur] = useState<number | null>(null);

  const label = [
    ["sicom", "SICOM", 4], ["op_price", "OP Price", 4], ["op_margin", "OP Margin", 4],
    ["ton", "Ton (kering)", 3], ["target", "Target", 1],
    ["pencapaian", "Pencapaian", 1], ["vs_target", "vs Target", 4],
  ] as const;

  return (
    <div className="grid gap-6">
      <StripAngkaKunci thn={thn} data={ringkas.data} ke={ke} />

      <PanelPerhatian ke={ke} />

      <Kartu idMetrik="ringkasan" judul={`${t("OP Margin bulanan")} — ${thn ?? ""}`}
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
                onClick={() => setTahun(th)}>
                {th}
              </button>
            ))}
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
                  <th className="text-right px-1">{t("Tertimbang")}</th>
                </tr>
              </thead>
              <tbody>
                {label.map(([kunci, nama, des]) => (
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
                          ? (b.pencapaian !== null ? fmtAngka(b.pencapaian * 100, 1) + "%" : "–")
                          : fmtAngka(b[kunci], des)}
                      </td>
                    ))}
                    <td className="text-right px-1 font-mono font-semibold">
                      {kunci === "op_margin" ? fmtAngka(ringkas.data?.avg_ytd_sederhana) : ""}
                    </td>
                    <td className="text-right px-1 font-mono text-[#64676C]">
                      {kunci === "op_margin" ? fmtAngka(ringkas.data?.avg_ytd_tertimbang) : ""}
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
            {t('Avg YTD = rata-rata sederhana bulan berdata (resmi, seperti Excel); kolom "Tertimbang" = rata-rata tertimbang tonase (informasi).')}
          </p>
        </>
      } />

      <KartuGrafikMargin />

      <KartuElemen />

      {telusur !== null && thn !== null && (
        <Telusur tahun={thn} bulan={telusur} tutup={() => setTelusur(null)} />
      )}
    </div>
  );
}
