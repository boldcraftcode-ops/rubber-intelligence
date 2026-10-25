import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { Kartu, NAMA_BULAN, Panel5W1H, ambilJson, fmtAngka, kelasInput, kelasTombolAnalisa, kelasTombolKecil } from "../bersama";

/* Palet seri grafik bulanan. Navy & merah lebih dulu (identitas), lalu warna
   pembeda yang tetap kontras di layar proyektor pabrik. */
const WARNA_SERI = ["#1D2434", "#FF1313", "#3B82F6", "#64676C", "#0F766E",
                    "#EAB308", "#F97316", "#7C3AED", "#0891B2", "#BE123C"];

const TAHUN_SEMUA: (number | "")[] = ["", 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027];

function PilihPeriode({ tahun, setTahun, bulan, setBulan }: any) {
  return (
    <div className="flex gap-2 mb-3">
      <select className={kelasInput + " max-w-32"} value={tahun}
              onChange={(e) => setTahun(e.target.value ? Number(e.target.value) : "")}>
        {TAHUN_SEMUA.map((t) => (
          <option key={t} value={t}>{t === "" ? "Semua tahun" : t}</option>
        ))}
      </select>
      {setBulan && (
        <select className={kelasInput + " max-w-36"} value={bulan}
                onChange={(e) => setBulan(e.target.value ? Number(e.target.value) : "")}>
          <option value="">Semua bulan</option>
          {NAMA_BULAN.slice(1).map((n, i) => (
            <option key={n} value={i + 1}>{n}</option>
          ))}
        </select>
      )}
    </div>
  );
}

/* ---------- rincian bulanan: grafik + tabel bulan x dimensi ----------
   Dipisah sebagai komponen supaya bisa dirender/diuji sendiri tanpa harus
   memilih filter lebih dulu. */
export function RincianBulanan({ data, dimensi, drill }: {
  data: any;
  dimensi: string;
  drill: (b: any) => void;
}) {
  if (!data || data.per !== "bulan") return null;
  const bulan: { ym: string; label: string }[] = data.bulan ?? [];
  const seri: any[] = data.baris ?? [];
  const grafik = bulan.map((b, i) => {
    const titik: Record<string, any> = { nama: b.label };
    seri.forEach((s: any) => { titik[s.label] = s.kg_per_bulan[i] ?? 0; });
    return titik;
  });

  if (!bulan.length || !seri.length) {
    return (
      <p className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-3 py-4 text-sm text-[#64676C]">
        Tidak ada data tiket untuk filter ini
        {bulan.length > 0 ? ` (${bulan[0].label}–${bulan[bulan.length - 1].label})` : ""}
        . Grafik akan terisi setelah ekspor "Master Data" tiket diunggah di tab
        Unggah Data.
      </p>
    );
  }

  return (
    <>
      <div style={{ height: Math.max(220, 40 + seri.length * 6 + 160) }}>
        <ResponsiveContainer>
          <BarChart data={grafik} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="nama" fontSize={10} />
            <YAxis fontSize={10} tickFormatter={(v) => fmtAngka(v as number, 0)} />
            <Tooltip formatter={(v: any, nama: any) =>
              [fmtAngka(v as number, 0) + " kg", nama]} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {seri.map((s: any, i: number) => (
              <Bar key={s.kunci} dataKey={s.label} stackId="kg"
                   fill={WARNA_SERI[i % WARNA_SERI.length]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* tabel = angka yang mengisi grafik, per bulan */}
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-xs" data-uji="tabel-bulanan">
          <thead>
            <tr className="border-b text-left text-[#64676C]">
              <th className="sticky left-0 z-10 bg-white py-1 pr-3">{dimensi}</th>
              {bulan.map((b) => (
                <th key={b.ym} className="px-2 py-1 text-right whitespace-nowrap">
                  {b.label}
                </th>
              ))}
              <th className="px-2 py-1 text-right font-semibold whitespace-nowrap">Total kg</th>
              <th className="px-2 py-1 text-right whitespace-nowrap">Porsi</th>
            </tr>
          </thead>
          <tbody>
            {seri.map((b: any, i: number) => (
              <tr key={b.kunci}
                  className={`border-b border-[#EDEFF2] ${data.drill_berikutnya
                    ? "cursor-pointer hover:bg-[#FFF1F1]" : ""}`}
                  onClick={() => drill(b)}>
                <td className="sticky left-0 z-10 bg-white py-1 pr-3">
                  <span className="mr-1.5 inline-block h-2 w-2 rounded-sm align-middle"
                        style={{ background: WARNA_SERI[i % WARNA_SERI.length] }} />
                  {b.label}
                </td>
                {b.kg_per_bulan.map((kg: number, j: number) => (
                  <td key={j} className={`px-2 py-1 text-right font-mono ${
                    kg === 0 ? "text-[#C9CCD1]" : ""}`}>
                    {fmtAngka(kg, 0)}
                  </td>
                ))}
                <td className="px-2 py-1 text-right font-mono font-semibold">
                  {fmtAngka(b.kg_total, 0)}
                </td>
                <td className="px-2 py-1 text-right font-mono">
                  {b.porsi !== null ? fmtAngka(b.porsi * 100, 1) + "%" : "–"}
                </td>
              </tr>
            ))}
            <tr className="bg-[#F8F8F8] font-semibold">
              <td className="sticky left-0 z-10 bg-[#F8F8F8] py-1 pr-3">Total per bulan</td>
              {data.total_per_bulan.map((kg: number, j: number) => (
                <td key={j} className="px-2 py-1 text-right font-mono">
                  {fmtAngka(kg, 0)}
                </td>
              ))}
              <td className="px-2 py-1 text-right font-mono">{fmtAngka(data.total_kg, 0)}</td>
              <td className="px-2 py-1 text-right font-mono">100%</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-xs text-[#64676C]">
        {data.jumlah_bulan} bulan × {seri.length} baris
        {data.jumlah_dimensi > seri.length
          ? ` (dari ${data.jumlah_dimensi} ${dimensi}, sisanya digabung)` : ""}
        {" "}· total {fmtAngka(data.total_kg, 0)} kg — biasa{" "}
        {fmtAngka(data.total_kg_biasa, 0)} kg · EUDR{" "}
        <span className="text-[#15803D]">
          {fmtAngka(data.total_kg_eudr, 0)} kg
          ({data.total_kg ? fmtAngka(data.total_kg_eudr / data.total_kg * 100, 1) : 0}%)
        </span>
        {" "}· sel kosong = tidak ada penerimaan bulan itu
      </p>
    </>
  );
}

/* ---------- penerimaan per dimensi, biasa vs EUDR (kg) ---------- */
function KartuPenerimaan() {
  const [dimensi, setDimensi] = useState("vendor");
  const [jejak, setJejak] = useState<{ dim: string; nilai: string }[]>([]);
  const [dari, setDari] = useState("");      // YYYY-MM
  const [sampai, setSampai] = useState("");
  const [modeEudr, setModeEudr] = useState<"semua" | "eudr" | "biasa">("semua");
  const [vendorFilter, setVendorFilter] = useState("");
  /* "bulan" = rincian bulan x dimensi; "total" = satu baris per dimensi.
     Otomatis "bulan" bila periode filter lebih dari satu bulan. */
  const [tampilan, setTampilan] = useState<"otomatis" | "bulan" | "total">("otomatis");
  const [topN, setTopN] = useState(8);

  const akhirBulan = (ym: string) => {
    const [y, m] = ym.split("-").map(Number);
    return `${ym}-${String(new Date(y, m, 0).getDate()).padStart(2, "0")}`;
  };
  /* Berapa bulan yang dicakup filter (dari..sampai). 0 = tanpa filter
     (memakai data apa adanya), 1 = satu bulan, >1 = perlu rincian bulanan. */
  const jumlahBulan = (() => {
    if (!dari || !sampai) return 0;
    const [y1, m1] = dari.split("-").map(Number);
    const [y2, m2] = sampai.split("-").map(Number);
    if (!y1 || !y2) return 0;
    const n = (y2 - y1) * 12 + (m2 - m1) + 1;
    return n > 0 ? n : 0;
  })();
  const bolehBulan = jumlahBulan > 1;
  const modeBulan = bolehBulan && tampilan !== "total";

  const params = new URLSearchParams({ dimensi });
  if (modeBulan) {
    params.set("per", "bulan");
    params.set("top", String(topN));
  }
  if (dari) params.set("dari", `${dari}-01`);
  if (sampai) params.set("sampai", akhirBulan(sampai));
  if (modeEudr !== "semua") params.set("eudr", modeEudr === "eudr" ? "true" : "false");
  if (vendorFilter && dimensi !== "vendor") params.set("vendor", vendorFilter);
  jejak.forEach((j) => params.set(j.dim, j.nilai));
  const url = `/api/kartu/penerimaan?${params.toString()}`;

  const q = useQuery({ queryKey: ["penerimaan", url], queryFn: () => ambilJson(url) });
  // daftar vendor untuk dropdown (sesuai mode EUDR terpilih)
  const vendorQ = useQuery({
    queryKey: ["penerimaan-vendor", modeEudr],
    queryFn: () => ambilJson(`/api/kartu/penerimaan?dimensi=vendor${
      modeEudr !== "semua" ? `&eudr=${modeEudr === "eudr"}` : ""}`),
  });

  const drill = (b: any) => {
    if (!q.data?.drill_berikutnya) return;
    setJejak([...jejak, { dim: dimensi, nilai: b.kunci }]);
    setDimensi(q.data.drill_berikutnya);
  };
  const mulaiUlang = (d: string) => { setJejak([]); setDimensi(d); };

  const dataGrafik = (q.data?.baris ?? []).slice(0, 10).map((b: any) => ({
    nama: b.label.length > 24 ? b.label.slice(0, 24) + "…" : b.label,
    "Grade biasa (kg)": b.kg_biasa,
    "Grade EUDR (kg)": b.kg_eudr,
  }));


  return (
    <Kartu idMetrik="penerimaan" judul="Penerimaan karet (kg) — biasa vs EUDR"
           keterangan="Grafik penerimaan per vendor / provinsi / kabupaten / kecamatan / desa, dipisah grade biasa dan grade EUDR (TTSR). Klik baris wilayah untuk turun level."
           urlEkspor={url}
           anak={
      <>
        <div className="flex gap-1 flex-wrap mb-2">
          {["vendor", "provinsi", "kabupaten", "kecamatan", "desa"].map((d) => (
            <button key={d}
              className={`rounded-sm px-2.5 py-1 text-xs ${d === dimensi && jejak.length === 0
                ? "bg-[#FF1313] text-white" : "bg-[#F1F2F4] text-[#1D2434] hover:bg-[#E8E9EC]"}`}
              onClick={() => mulaiUlang(d)}>
              {d}
            </button>
          ))}
          <span className="mx-2 border-l border-[#E4E5E8]" />
          {([["semua", "Semua grade"], ["eudr", "Hanya EUDR"], ["biasa", "Hanya biasa"]] as const)
            .map(([id, label]) => (
            <button key={id}
              className={`rounded-sm px-2.5 py-1 text-xs ${modeEudr === id
                ? "bg-emerald-600 text-white" : "bg-[#F1F2F4] text-[#1D2434] hover:bg-[#E8E9EC]"}`}
              onClick={() => setModeEudr(id)}>
              {label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-end gap-3 mb-3 text-xs">
          <div>
            <label className="block text-[#64676C] mb-1">Dari bulan</label>
            <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-[#1D2434]"
                   value={dari} onChange={(e) => setDari(e.target.value)} />
          </div>
          <div>
            <label className="block text-[#64676C] mb-1">Sampai bulan</label>
            <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-[#1D2434]"
                   value={sampai} onChange={(e) => setSampai(e.target.value)} />
          </div>
          {dimensi !== "vendor" && (
            <div>
              <label className="block text-[#64676C] mb-1">
                Vendor {modeEudr === "eudr" ? "(pemasok EUDR)" : ""}
              </label>
              <select className={kelasInput + " max-w-56"} value={vendorFilter}
                      onChange={(e) => setVendorFilter(e.target.value)}>
                <option value="">Semua vendor</option>
                {vendorQ.data?.baris.map((v: any) => (
                  <option key={v.kunci} value={v.kunci}>{v.label}</option>
                ))}
              </select>
            </div>
          )}
          {(dari || sampai || vendorFilter) && (
            <button className={kelasTombolKecil}
                    onClick={() => { setDari(""); setSampai(""); setVendorFilter(""); }}>
              hapus filter
            </button>
          )}
        </div>

        {/* ===== pilihan bentuk tampilan: rincian bulanan vs total periode ===== */}
        {bolehBulan && (
          <div className="mb-3 flex flex-wrap items-center gap-2 rounded-sm border
                          border-[#E4E5E8] bg-[#F8F8F8] px-3 py-2 text-xs">
            <span className="font-semibold text-[#1D2434]">
              Periode {jumlahBulan} bulan
            </span>
            <span className="text-[#64676C]">— tampilkan:</span>
            <div className="inline-flex overflow-hidden rounded-sm border border-[#D5D7DB]">
              {([["bulan", "Rincian per bulan"], ["total", "Total periode"]] as const)
                .map(([id, label]) => (
                <button key={id}
                  className={`px-2.5 py-1 font-medium ${(tampilan === id ||
                    (tampilan === "otomatis" && id === "bulan"))
                    ? "bg-[#1D2434] text-white" : "bg-white text-[#1D2434] hover:bg-[#E8E9EC]"}`}
                  onClick={() => setTampilan(id)}>
                  {label}
                </button>
              ))}
            </div>
            {modeBulan && (
              <label className="ml-2 flex items-center gap-1.5 text-[#64676C]">
                Tampilkan
                <select className="rounded-sm border border-[#D5D7DB] bg-white px-1.5 py-1"
                        value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
                  {[5, 8, 12, 20].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
                {dimensi} terbesar
              </label>
            )}
          </div>
        )}

        {jejak.length > 0 && (
          <p className="mb-2 text-xs text-[#64676C]">
            Jejak: {jejak.map((j) => `${j.dim} = ${j.nilai}`).join(" → ")} →{" "}
            <b>{dimensi}</b>{" "}
            <button className={kelasTombolKecil} onClick={() => mulaiUlang("provinsi")}>
              mulai ulang
            </button>
          </p>
        )}

        {/* ================= mode BULAN: grafik + tabel bulan x dimensi ===== */}
        {modeBulan && <RincianBulanan data={q.data} dimensi={dimensi} drill={drill} />}

        {/* ================= mode TOTAL: satu baris per dimensi ============== */}
        {!modeBulan && (
          <>
            {dataGrafik.length > 0 ? (
              <div style={{ height: Math.max(180, dataGrafik.length * 36 + 60) }}>
                <ResponsiveContainer>
                  <BarChart data={dataGrafik} layout="vertical"
                            margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" fontSize={10}
                           tickFormatter={(v) => fmtAngka(v as number, 0)} />
                    <YAxis type="category" dataKey="nama" width={170} fontSize={10} />
                    <Tooltip formatter={(v: any, nama: any) => [fmtAngka(v as number, 0) + " kg", nama]} />
                    <Legend />
                    <Bar dataKey="Grade biasa (kg)" stackId="kg" fill="#1D2434" />
                    <Bar dataKey="Grade EUDR (kg)" stackId="kg" fill="#FF1313" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="rounded-sm bg-[#F8F8F8] border border-[#E4E5E8] px-3 py-4 text-sm text-[#64676C]">
                Tidak ada data tiket untuk filter ini. Grafik akan terisi setelah
                ekspor "Master Data" tiket diunggah di tab Unggah Data.
              </p>
            )}

            {q.data && q.data.baris.length > 0 && (
              <>
                <div className="mt-3 max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-[#64676C] border-b">
                        <th className="py-1">{dimensi}</th>
                        <th className="text-right">Kg biasa</th>
                        <th className="text-right">Kg EUDR</th>
                        <th className="text-right">Kg total</th>
                        <th className="text-right">Porsi</th>
                        <th className="text-right">Tiket</th>
                      </tr>
                    </thead>
                    <tbody>
                      {q.data.baris.map((b: any) => (
                        <tr key={b.kunci}
                            className={`border-b border-[#EDEFF2] ${q.data.drill_berikutnya
                              ? "cursor-pointer hover:bg-[#FFF1F1]" : ""}`}
                            onClick={() => drill(b)}>
                          <td className="py-1">{b.label}</td>
                          <td className="text-right font-mono">{fmtAngka(b.kg_biasa, 0)}</td>
                          <td className="text-right font-mono text-[#15803D]">{fmtAngka(b.kg_eudr, 0)}</td>
                          <td className="text-right font-mono font-semibold">{fmtAngka(b.kg_total, 0)}</td>
                          <td className="text-right font-mono">
                            {b.porsi !== null ? fmtAngka(b.porsi * 100, 1) + "%" : "–"}
                          </td>
                          <td className="text-right font-mono">{b.jumlah_tiket}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-xs text-[#64676C]">
                  Total {fmtAngka(q.data.total_kg, 0)} kg — biasa{" "}
                  {fmtAngka(q.data.total_kg_biasa, 0)} kg · EUDR{" "}
                  <span className="text-[#15803D]">{fmtAngka(q.data.total_kg_eudr, 0)} kg
                  ({q.data.total_kg ? fmtAngka(q.data.total_kg_eudr / q.data.total_kg * 100, 1) : 0}%)</span>
                  {" "}· sumber: {q.data.sumber}
                </p>
              </>
            )}
          </>
        )}
      </>
    } />
  );
}

/* ---------- tonase drill-down berantai ---------- */
function KartuTonase() {
  const [dimensi, setDimensi] = useState("provinsi");
  const [jejak, setJejak] = useState<{ dim: string; nilai: string }[]>([]);
  const [tahun, setTahun] = useState<number | "">("");
  const [bulan, setBulan] = useState<number | "">("");

  const params = new URLSearchParams({ dimensi });
  if (tahun) params.set("tahun", String(tahun));
  if (bulan) params.set("bulan", String(bulan));
  jejak.forEach((j) => params.set(j.dim, j.nilai));
  const url = `/api/kartu/tonase?${params.toString()}`;

  const q = useQuery({ queryKey: ["tonase", url], queryFn: () => ambilJson(url) });

  const drill = (baris: any) => {
    if (!q.data?.drill_berikutnya) return;
    setJejak([...jejak, { dim: dimensi, nilai: baris.kunci }]);
    setDimensi(q.data.drill_berikutnya);
  };

  const mulaiUlang = (dim: string) => { setJejak([]); setDimensi(dim); };

  return (
    <Kartu idMetrik="tonase" judul="Tonase (drill-down)"
           keterangan="Ton kering dari tiket. Klik baris wilayah untuk turun: provinsi → kabupaten → kecamatan → desa."
           urlEkspor={url}
           anak={
      <>
        <div className="flex gap-1 flex-wrap mb-2">
          {["vendor", "grade", "provinsi", "kabupaten", "kecamatan", "desa"].map((d) => (
            <button key={d}
              className={`rounded-sm px-2.5 py-1 text-xs ${d === dimensi && jejak.length === 0
                ? "bg-[#FF1313] text-white" : "bg-[#F1F2F4] text-[#1D2434] hover:bg-[#E8E9EC]"}`}
              onClick={() => mulaiUlang(d)}>
              {d}
            </button>
          ))}
        </div>
        <PilihPeriode tahun={tahun} setTahun={setTahun} bulan={bulan} setBulan={setBulan} />
        {jejak.length > 0 && (
          <p className="mb-2 text-xs text-[#64676C]">
            Jejak: {jejak.map((j) => `${j.dim} = ${j.nilai}`).join(" → ")} →{" "}
            <b>{dimensi}</b>{" "}
            <button className={kelasTombolKecil} onClick={() => mulaiUlang("provinsi")}>
              mulai ulang
            </button>
          </p>
        )}
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[#64676C] border-b">
              <th className="py-1">{dimensi}</th><th className="text-right">Ton kering</th>
              <th className="text-right">Porsi</th><th className="text-right">Tiket</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.baris.map((b: any) => (
              <tr key={b.kunci}
                  className={`border-b border-[#EDEFF2] ${q.data.drill_berikutnya
                    ? "cursor-pointer hover:bg-[#FFF1F1]" : ""}`}
                  onClick={() => drill(b)}>
                <td className="py-1">{b.label}</td>
                <td className="text-right font-mono">{fmtAngka(b.ton, 3)}</td>
                <td className="text-right font-mono">
                  {b.porsi !== null ? fmtAngka(b.porsi * 100, 1) + "%" : "–"}
                </td>
                <td className="text-right font-mono">{b.jumlah_tiket}</td>
              </tr>
            ))}
            {q.data?.baris.length === 0 && (
              <tr><td colSpan={4} className="py-2 text-[#64676C]">
                Tidak ada data tiket untuk filter ini.</td></tr>
            )}
          </tbody>
        </table>
        {q.data && (
          <p className="mt-2 text-xs text-[#64676C]">
            Total: <b>{fmtAngka(q.data.total_ton, 3)}</b> ton kering · sumber {q.data.sumber}
          </p>
        )}
      </>
    } />
  );
}

/* ---------- konsentrasi vendor ---------- */
function KartuKonsentrasi() {
  const [top, setTop] = useState(5);
  const [tahun, setTahun] = useState<number | "">("");
  const url = `/api/kartu/konsentrasi-vendor?top=${top}${tahun ? `&tahun=${tahun}` : ""}`;
  const q = useQuery({ queryKey: ["konsentrasi", url], queryFn: () => ambilJson(url) });

  return (
    <Kartu idMetrik="konsentrasi_vendor" judul="Konsentrasi vendor" urlEkspor={url}
           anak={
      <>
        <div className="flex gap-2 mb-3">
          {[5, 10].map((n) => (
            <button key={n}
              className={`rounded-sm px-3 py-1 text-xs ${top === n
                ? "bg-[#FF1313] text-white" : "bg-[#F1F2F4] text-[#1D2434]"}`}
              onClick={() => setTop(n)}>Top {n}</button>
          ))}
          <PilihPeriode tahun={tahun} setTahun={setTahun} />
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[#64676C] border-b">
              <th className="py-1">Vendor</th><th className="text-right">Ton</th>
              <th className="text-right">Porsi</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.baris.map((b: any) => (
              <tr key={b.kunci} className="border-b border-[#EDEFF2]">
                <td className="py-1">{b.kunci} — {b.label}</td>
                <td className="text-right font-mono">{fmtAngka(b.ton, 3)}</td>
                <td className="text-right font-mono">{fmtAngka((b.porsi ?? 0) * 100, 1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        {q.data && (
          <p className="mt-2 text-xs text-[#64676C]">
            Porsi top {top}: <b>{fmtAngka(q.data.porsi_top * 100, 1)}%</b> dari{" "}
            {fmtAngka(q.data.total_ton, 3)} ton.
          </p>
        )}
      </>
    } />
  );
}

/* ---------- bauran grade & EUDR ---------- */
function KartuGrade() {
  const [tahun, setTahun] = useState<number | "">("");
  const url = `/api/kartu/bauran-grade${tahun ? `?tahun=${tahun}` : ""}`;
  const q = useQuery({ queryKey: ["grade", url], queryFn: () => ambilJson(url) });

  return (
    <Kartu idMetrik="bauran_grade" judul="Bauran grade & porsi EUDR" urlEkspor={url}
           anak={
      <>
        <PilihPeriode tahun={tahun} setTahun={setTahun} />
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[#64676C] border-b">
              <th className="py-1">Grade</th><th>EUDR</th>
              <th className="text-right">Ton</th><th className="text-right">Porsi</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.baris.map((b: any) => (
              <tr key={b.kunci} className="border-b border-[#EDEFF2]">
                <td className="py-1">{b.kunci}</td>
                <td>{b.eudr
                  ? <span className="rounded bg-[#DCFCE7] text-[#15803D] px-1.5 py-0.5">EUDR</span>
                  : "–"}</td>
                <td className="text-right font-mono">{fmtAngka(b.ton, 3)}</td>
                <td className="text-right font-mono">{fmtAngka((b.porsi ?? 0) * 100, 1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        {q.data && (
          <p className="mt-2 text-xs text-[#64676C]">
            Porsi EUDR (TTSR): <b>{fmtAngka(q.data.porsi_eudr * 100, 1)}%</b>
          </p>
        )}
      </>
    } />
  );
}

/* ---------- reject% ---------- */
function KartuReject() {
  const [tahun, setTahun] = useState<number | "">("");
  const url = `/api/kartu/reject${tahun ? `?tahun=${tahun}` : ""}`;
  const q = useQuery({ queryKey: ["reject", url], queryFn: () => ambilJson(url) });

  return (
    <Kartu idMetrik="reject" judul="KPI Reject %" urlEkspor={url}
           anak={
      <>
        <PilihPeriode tahun={tahun} setTahun={setTahun} />
        {q.data?.kpi.reject_pct !== null && q.data?.kpi && (
          <p className="mb-2 text-sm">
            Keseluruhan: <b>{fmtAngka(q.data.kpi.reject_pct, 2)}%</b>{" "}
            ({fmtAngka(q.data.kpi.reject_kg / 1000, 1)} ton reject dari{" "}
            {fmtAngka(q.data.kpi.wet_kg / 1000, 1)} ton wet) · tiket nol: {q.data.kpi.tiket_nol}
          </p>
        )}
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[#64676C] border-b">
              <th className="py-1">Bulan</th><th className="text-right">Wet ton</th>
              <th className="text-right">Reject ton</th><th className="text-right">Reject %</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.baris.map((b: any) => (
              <tr key={`${b.tahun}-${b.bulan}`} className="border-b border-[#EDEFF2]">
                <td className="py-1">{NAMA_BULAN[b.bulan]} {b.tahun}</td>
                <td className="text-right font-mono">{fmtAngka(b.wet_ton, 3)}</td>
                <td className="text-right font-mono">{fmtAngka(b.reject_ton, 3)}</td>
                <td className="text-right font-mono">{fmtAngka(b.reject_pct, 2)}%</td>
              </tr>
            ))}
            {q.data?.baris.length === 0 && (
              <tr><td colSpan={4} className="py-2 text-[#64676C]">
                Belum ada data tiket untuk periode ini.</td></tr>
            )}
          </tbody>
        </table>
        {q.data && (
          <p className="mt-2 rounded-sm bg-[#FFFBEB] border border-[#FDE68A] px-3 py-2 text-xs text-[#B45309]">
            {q.data.kpi.asumsi}
          </p>
        )}
      </>
    } />
  );
}

/* ---------- margin harian ---------- */
function KartuMarginHarian() {
  const [tahun, setTahun] = useState<number>(2026);
  const [bulan, setBulan] = useState<number>(1);
  const url = `/api/kartu/margin-harian?tahun=${tahun}&bulan=${bulan}`;
  const q = useQuery({ queryKey: ["margin-harian", url], queryFn: () => ambilJson(url) });

  return (
    <Kartu idMetrik="margin_harian" judul="Margin harian" urlEkspor={url}
           anak={
      <>
        <div className="flex gap-2 mb-3">
          <select className={kelasInput + " max-w-32"} value={tahun}
                  onChange={(e) => setTahun(Number(e.target.value))}>
            {[2020, 2021, 2022, 2023, 2024, 2025, 2026].map((t) => (
              <option key={t} value={t}>{t}</option>))}
          </select>
          <select className={kelasInput + " max-w-36"} value={bulan}
                  onChange={(e) => setBulan(Number(e.target.value))}>
            {NAMA_BULAN.slice(1).map((n, i) => (
              <option key={n} value={i + 1}>{n}</option>))}
          </select>
        </div>
        <div className="max-h-72 overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[#64676C] border-b">
                <th className="py-1">Tanggal</th><th className="text-right">Qty kg</th>
                <th className="text-right">Rp/kg</th><th className="text-right">US¢/kg</th>
                <th className="text-right">SICOM</th><th className="text-right">Margin</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.baris.map((b: any) => (
                <tr key={b.tanggal} className="border-b border-[#EDEFF2]">
                  <td className="py-1">{b.tanggal.slice(8, 10)}/{b.tanggal.slice(5, 7)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.qty_kg, 0)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.harga_rp_per_kg, 2)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.harga_usc)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.sicom, 2)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.margin)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>
    } />
  );
}

/* ---------- margin per grade / vendor ---------- */
function KartuMarginPer() {
  const [dimensi, setDimensi] = useState<"grade" | "vendor">("grade");
  const [tahun, setTahun] = useState<number>(2026);
  const url = `/api/kartu/margin-per?dimensi=${dimensi}&tahun=${tahun}`;
  const q = useQuery({ queryKey: ["margin-per", url], queryFn: () => ambilJson(url) });

  return (
    <Kartu idMetrik="margin_per" judul="Margin per grade / vendor"
           urlEkspor={q.data?.status === "ok" ? url : undefined}
           anak={
      <>
        <div className="flex gap-2 mb-3">
          {(["grade", "vendor"] as const).map((d) => (
            <button key={d}
              className={`rounded-sm px-3 py-1 text-xs ${dimensi === d
                ? "bg-[#FF1313] text-white" : "bg-[#F1F2F4] text-[#1D2434]"}`}
              onClick={() => setDimensi(d)}>per {d}</button>
          ))}
          <select className={kelasInput + " max-w-32"} value={tahun}
                  onChange={(e) => setTahun(Number(e.target.value))}>
            {[2020, 2021, 2022, 2023, 2024, 2025, 2026].map((t) => (
              <option key={t} value={t}>{t}</option>))}
          </select>
        </div>
        {q.data?.status === "data harga belum tersedia" ? (
          <p className="rounded-sm bg-[#F8F8F8] border border-[#E4E5E8] px-3 py-4 text-sm text-[#1D2434]">
            <b>Data harga belum tersedia.</b> {q.data.pesan}
          </p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[#64676C] border-b">
                <th className="py-1">{dimensi}</th><th className="text-right">Ton</th>
                <th className="text-right">SICOM</th><th className="text-right">OP Price</th>
                <th className="text-right">OP Margin</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.baris.map((b: any) => (
                <tr key={b.kunci} className="border-b border-[#EDEFF2]">
                  <td className="py-1">{b.kunci}</td>
                  <td className="text-right font-mono">{fmtAngka(b.ton, 3)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.sicom)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.op_price)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.op_margin)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </>
    } />
  );
}

export default function Analisis() {
  const [bukaAnalisa, setBukaAnalisa] = useState(false);
  const [dariA, setDariA] = useState("");
  const [sampaiA, setSampaiA] = useState("");
  const paramsA = new URLSearchParams();
  if (dariA) paramsA.set("dari", dariA);
  if (sampaiA) paramsA.set("sampai", sampaiA);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="lg:col-span-2 rounded-sm bg-white border border-[#E4E5E8] shadow-sm px-5 py-3 flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <h2 className="text-base font-semibold text-[#1D2434]">Analisa halaman ini (5W1H)</h2>
          <p className="text-xs text-[#64676C]">
            Merangkum seluruh data di halaman ini: penerimaan, konsentrasi vendor,
            bauran grade & EUDR, reject%, dan margin — pada periode terpilih.
          </p>
        </div>
        <div>
          <label className="block text-xs text-[#64676C] mb-1">Dari bulan</label>
          <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-xs text-[#1D2434]"
                 value={dariA} onChange={(e) => setDariA(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-[#64676C] mb-1">Sampai bulan</label>
          <input type="month" className="rounded-sm border border-[#E4E5E8] bg-white px-2 py-1.5 text-xs text-[#1D2434]"
                 value={sampaiA} onChange={(e) => setSampaiA(e.target.value)} />
        </div>
        <button className={kelasTombolAnalisa} onClick={() => setBukaAnalisa(true)}>
          ✨ Analisa semua data
        </button>
      </div>
      {bukaAnalisa && (
        <Panel5W1H judul="Analisa halaman Analisis — 5W1H"
                   url={`/api/analisis/analisa${paramsA.size ? "?" + paramsA.toString() : ""}`}
                   tutup={() => setBukaAnalisa(false)} />
      )}
      <div className="lg:col-span-2"><KartuPenerimaan /></div>
      <KartuTonase />
      <KartuKonsentrasi />
      <KartuGrade />
      <KartuReject />
      <KartuMarginHarian />
      <KartuMarginPer />
      <p className="lg:col-span-2 text-xs text-[#64676C]">
        Kartu tonase/grade/reject memakai data tiket; data tiket historis penuh belum
        diunggah (template hanya berisi contoh), jadi angka akan terisi setelah ekspor
        "Master Data" diunggah. Filter terbatas pada dimensi berdaftar-putih — tidak ada
        SQL dari layar.
      </p>
    </div>
  );
}
