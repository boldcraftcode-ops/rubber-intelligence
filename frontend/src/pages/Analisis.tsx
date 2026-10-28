import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Kartu, KartuMuatSaatDiminta, NAMA_BULAN, Panel5W1H, PilihRentangBulan, akhirBulan,
  KepalaPanel, ambilJson, fmtAngka, fmtTanggal, hitungJumlahBulan, kelasInput,
  kelasTombolAnalisa, kelasTombolKecil, pesanGalat,
} from "../bersama";

/* Palet seri grafik bulanan. Navy & merah lebih dulu (identitas), lalu warna
   pembeda yang tetap kontras di layar proyektor pabrik. */
const WARNA_SERI = ["#1D2434", "#FF1313", "#3B82F6", "#64676C", "#0F766E",
                    "#EAB308", "#F97316", "#7C3AED", "#0891B2", "#BE123C"];

const TAHUN_SEMUA: (number | "")[] = ["", 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027];

/* Tabel bulan x dimensi — angka yang sama dengan grafik.
   Dipakai kartu Tonase & Margin per grade/vendor (kartu Penerimaan punya
   versi sendiri karena memisahkan grade biasa vs EUDR). */
export function TabelBulanan({ data, dimensi, nilaiKey, desimal, satuan,
                        footerNilai, drill }: {
  data: any;
  dimensi: string;
  nilaiKey: string;          // "ton_per_bulan" | "margin_per_bulan"
  desimal: number;
  satuan: string;
  footerNilai?: (number | null)[];   // total per bulan (mis. margin tertimbang)
  drill?: (b: any) => void;
}) {
  const bulan: { ym: string; label: string }[] = data?.bulan ?? [];
  const seri: any[] = data?.baris ?? [];
  if (!bulan.length || !seri.length) return null;

  const sel = (v: number | null | undefined) => v === null || v === undefined
    ? "–"
    : (v === 0 ? "0" : fmtAngka(v, desimal));

  return (
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
            <th className="px-2 py-1 text-right font-semibold whitespace-nowrap">Total</th>
            <th className="px-2 py-1 text-right whitespace-nowrap">Porsi</th>
          </tr>
        </thead>
        <tbody>
          {seri.map((b: any, i: number) => (
            <tr key={b.kunci}
                className={`border-b border-[#EDEFF2] ${drill && data.drill_berikutnya
                  ? "cursor-pointer hover:bg-[#FFF1F1]" : ""}`}
                onClick={() => drill?.(b)}>
              <td className="sticky left-0 z-10 bg-white py-1 pr-3">
                <span className="mr-1.5 inline-block h-2 w-2 rounded-sm align-middle"
                      style={{ background: WARNA_SERI[i % WARNA_SERI.length] }} />
                {b.label ?? b.kunci}
              </td>
              {(b[nilaiKey] ?? []).map((v: number | null, j: number) => (
                <td key={j} className={`px-2 py-1 text-right font-mono ${
                  v === 0 || v === null ? "text-[#C9CCD1]" : ""}`}>
                  {sel(v)}
                </td>
              ))}
              <td className="px-2 py-1 text-right font-mono font-semibold">
                {sel(b[nilaiKey === "ton_per_bulan" ? "ton" : "op_margin"])}
              </td>
              <td className="px-2 py-1 text-right font-mono">
                {b.porsi !== null && b.porsi !== undefined
                  ? fmtAngka(b.porsi * 100, 1) + "%" : "–"}
              </td>
            </tr>
          ))}
          {footerNilai && (
            <tr className="bg-[#F8F8F8] font-semibold">
              <td className="sticky left-0 z-10 bg-[#F8F8F8] py-1 pr-3">
                Total per bulan
              </td>
              {footerNilai.map((v, j) => (
                <td key={j} className="px-2 py-1 text-right font-mono">{sel(v)}</td>
              ))}
              <td className="px-2 py-1 text-right font-mono">–</td>
              <td className="px-2 py-1 text-right font-mono">100%</td>
            </tr>
          )}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-[#64676C]">
        {data.jumlah_bulan} bulan × {seri.length} baris
        {data.jumlah_dimensi > seri.length
          ? ` (dari ${data.jumlah_dimensi} ${dimensi}, sisanya digabung)` : ""}
        {" "}· satuan {satuan} · sel kosong = tidak ada data bulan itu
      </p>
    </div>
  );
}

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
/* ---------- analisis tren & musiman (disematkan di kartu Penerimaan) ---------- */

/* Angka pertumbuhan dengan arah yang TIDAK bergantung warna saja
   (ikon ▲/▼ + kata), sesuai aturan aksesibilitas. */
function AngkaPertumbuhan({ nilai }: { nilai: number | null | undefined }) {
  if (nilai === null || nilai === undefined) {
    return <span className="text-[#9AA0A6]">–</span>;
  }
  const naik = nilai > 0.005, turun = nilai < -0.005;
  const kelas = naik ? "text-[#15803D]" : turun ? "text-[#DC2626]" : "text-[#64676C]";
  return (
    <span className={kelas}>
      {naik ? "▲" : turun ? "▼" : "■"} {fmtAngka(Math.abs(nilai), 2)}%
    </span>
  );
}

export function AnalisisTren({ dari, sampai, modeEudr, bukaAwal = false }: {
  dari: string; sampai: string; modeEudr: "semua" | "eudr" | "biasa";
  /** Bawaannya tertutup: tombol dibuka seperti Margin Bridge. */
  bukaAwal?: boolean;
}) {
  const [buka, setBuka] = useState(bukaAwal);
  const params = new URLSearchParams();
  if (dari) params.set("dari", dari);
  if (sampai) params.set("sampai", sampai);
  if (modeEudr !== "semua") params.set("eudr", String(modeEudr === "eudr"));
  const url = `/api/kartu/penerimaan/tren${params.size ? `?${params.toString()}` : ""}`;
  const q = useQuery({
    queryKey: ["tren-penerimaan", url],
    queryFn: () => ambilJson(url),
    enabled: buka,
  });

  const data = q.data;
  const dekom = data?.dekomposisi;
  const validasi = data?.validasi;

  const grafik = (data?.bulan ?? []).map((b: any, i: number) => ({
    nama: b.label,
    "Total kg": data.total_kg[i],
    "MA3 (tren dasar)": data.ma3[i],
    "EUDR kg": data.eudr_kg[i],
  }));

  const grafikDekom = dekom?.tersedia
    ? (data.bulan ?? []).map((b: any, i: number) => ({
        nama: b.label,
        "Nilai aktual": data.total_kg[i],
        Tren: dekom.tren?.[i] ?? null,
        Musiman: dekom.musiman?.[i] ?? null,
      }))
    : [];

  /* Tombol + panel disamakan dengan tombol Margin Bridge di Margin Performance:
     tombol navy (kelasTombolAnalisa) -> panel modal dengan KepalaPanel
     (Ekspor Excel + Tutup), klik latar untuk menutup. */
  const labelPeriode = data && data.bulan.length > 0
    ? `${data.bulan[0].label} → ${data.bulan[data.bulan.length - 1].label}`
    : undefined;

  return (
    <>
      <button className={kelasTombolAnalisa} onClick={() => setBuka(true)}>
        📈 Analisis tren &amp; musiman
      </button>

      {buka && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
             onClick={() => setBuka(false)}>
          <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-sm bg-white border border-[#E4E5E8] p-6 shadow-xl shadow-[#1D2434]/10"
               onClick={(e) => e.stopPropagation()}>
            <KepalaPanel judul={"Analisis tren & musiman — penerimaan karet"}
                         periode={labelPeriode} url={url}
                         tutup={() => setBuka(false)} />
          {q.isLoading && <p className="text-xs text-[#64676C]">Menghitung…</p>}
          {q.error && (
            <p className="text-xs text-[#B91C1C]">{pesanGalat(q.error)}</p>
          )}

          {data && data.bulan.length === 0 && (
            <p className="text-xs text-[#64676C]">Belum ada data tiket untuk dianalisis.</p>
          )}

          {data && data.bulan.length > 0 && (
            <>
              {/* ---- peringatan validasi data ---- */}
              {validasi?.peringatan?.length > 0 && (
                <div className="mb-3 rounded-sm border border-[#FDE68A] bg-[#FFFBEB] px-3 py-2">
                  <p className="mb-1 text-xs font-semibold text-[#B45309]">
                    Periksa dulu sebelum angka ini dipakai untuk perkiraan:
                  </p>
                  <ul className="list-disc pl-4 text-xs text-[#92400E]">
                    {validasi.peringatan.map((p: string, i: number) => (
                      <li key={i} className="mb-0.5">{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* ---- grafik total + MA3 ---- */}
              <div className="mb-1 flex flex-wrap items-center gap-3 text-xs text-[#64676C]">
                <span>Total penerimaan vs rata-rata bergerak 3 bulan</span>
                {validasi && (
                  <span>
                    · data {validasi.dari_data} s.d. {validasi.sampai_data}
                    {validasi.bulan_terakhir_lengkap ? " (bulan terakhir lengkap)"
                      : " (bulan terakhir belum lengkap)"}
                  </span>
                )}
              </div>
              <div className="h-64">
                <ResponsiveContainer>
                  <LineChart data={grafik} margin={{ top: 5, right: 15, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="nama" fontSize={10} minTickGap={20} />
                    <YAxis fontSize={10} tickFormatter={(v) => fmtAngka(v as number, 0)} />
                    <Tooltip formatter={(v: any, n: any) => [
                      v === null ? "–" : fmtAngka(v as number, 0) + " kg", n]} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="Total kg" stroke="#1D2434"
                          strokeWidth={2} dot={{ r: 2 }} />
                    <Line type="monotone" dataKey="MA3 (tren dasar)" stroke="#FF1313"
                          strokeWidth={2} strokeDasharray="6 3" dot={false} />
                    <Line type="monotone" dataKey="EUDR kg" stroke="#15803D"
                          strokeWidth={1} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* ---- tabel MoM & YoY ---- */}
              <div className="mt-3 max-h-72 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-[#F8F8F8]">
                    <tr className="text-left text-[#64676C] border-b">
                      <th className="py-1">Bulan</th>
                      <th className="text-right">Total kg</th>
                      <th className="text-right">Biasa kg</th>
                      <th className="text-right">EUDR kg</th>
                      <th className="text-right">MA3 kg</th>
                      <th className="text-right">MoM</th>
                      <th className="text-right">YoY</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.bulan ?? []).map((b: any, i: number) => (
                      <tr key={b.ym} className="border-b border-[#EDEFF2]">
                        <td className="py-1 whitespace-nowrap">{b.label}</td>
                        <td className="text-right font-mono">{fmtAngka(data.total_kg[i], 0)}</td>
                        <td className="text-right font-mono">{fmtAngka(data.biasa_kg[i], 0)}</td>
                        <td className="text-right font-mono text-[#15803D]">{fmtAngka(data.eudr_kg[i], 0)}</td>
                        <td className="text-right font-mono">
                          {data.ma3[i] === null ? <span className="text-[#9AA0A6]">–</span>
                            : fmtAngka(data.ma3[i], 0)}
                        </td>
                        <td className="text-right font-mono"><AngkaPertumbuhan nilai={data.mom_pct[i]} /></td>
                        <td className="text-right font-mono"><AngkaPertumbuhan nilai={data.yoy_pct[i]} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-1 text-[11px] text-[#64676C]">
                {data.catatan_metode?.ma3} · {data.catatan_metode?.mom} ·{" "}
                {data.catatan_metode?.yoy}
              </p>

              {/* ---- dekomposisi tren-musiman ---- */}
              <div className="mt-4 border-t border-[#E4E5E8] pt-3">
                <h4 className="text-xs font-semibold text-[#1D2434]">
                  Dekomposisi tren-musiman {dekom?.tersedia ? "" : "(belum bisa dihitung)"}
                </h4>
                {dekom?.tersedia ? (
                  <>
                    <p className="mb-2 text-[11px] text-[#64676C]">
                      {dekom.metode} · {dekom.jumlah_bulan} bulan · kekuatan musiman{" "}
                      <b className={dekom.kekuatan_musiman_pct >= 15
                        ? "text-[#1D2434]" : "text-[#B45309]"}>
                        {fmtAngka(dekom.kekuatan_musiman_pct, 1)}%
                      </b>. {dekom.catatan}
                    </p>
                    <div className="h-56">
                      <ResponsiveContainer>
                        <LineChart data={grafikDekom}
                                   margin={{ top: 5, right: 15, bottom: 5, left: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="nama" fontSize={10} minTickGap={20} />
                          <YAxis fontSize={10} tickFormatter={(v) => fmtAngka(v as number, 0)} />
                          <Tooltip formatter={(v: any, n: any) => [
                            v === null ? "–" : fmtAngka(v as number, 0) + " kg", n]} />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          <Line type="monotone" dataKey="Nilai aktual" stroke="#64676C"
                                strokeWidth={1} dot={false} />
                          <Line type="monotone" dataKey="Tren" stroke="#1D2434"
                                strokeWidth={2} dot={false} />
                          <Line type="monotone" dataKey="Musiman" stroke="#FF1313"
                                strokeWidth={1.5} strokeDasharray="4 3" dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>

                    <p className="mt-3 mb-1 text-xs font-semibold text-[#1D2434]">
                      Indeks musiman per bulan kalender
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                      {(dekom.indeks_musiman ?? []).map((m: any) => (
                        <div key={m.bulan}
                             className={`rounded-sm border px-2 py-1 text-xs ${
                               m.kg < 0
                                 ? "border-[#FECACA] bg-[#FEF2F2]"
                                 : m.kg > 0
                                   ? "border-[#BBF7D0] bg-[#F0FDF4]"
                                   : "border-[#E4E5E8] bg-white"}`}>
                          <span className="font-semibold text-[#1D2434]">{m.label}</span>{" "}
                          <span className="font-mono">
                            {m.kg > 0 ? "+" : ""}{fmtAngka(m.kg, 0)} kg
                          </span>
                          {m.pct !== null && (
                            <span className="text-[#64676C]"> ({m.kg > 0 ? "+" : ""}{fmtAngka(m.pct, 1)}%)</span>
                          )}
                        </div>
                      ))}
                    </div>
                    <p className="mt-1 text-[11px] text-[#64676C]">
                      Angka negatif = penerimaan cenderung di bawah tren pada bulan itu
                      (mis. musim gugur daun Feb–Apr), positif = di atas tren.
                    </p>
                  </>
                ) : (
                  <p className="mt-1 rounded-sm border border-[#E4E5E8] bg-white px-3 py-2 text-xs text-[#64676C]">
                    {dekom?.pesan}
                    <br />
                    <span className="text-[11px]">
                      Yang sudah bisa dipakai sekarang: MA3, MoM, dan YoY. Angka
                      bulanan tetap bisa dibaca dari tabel di atas; dekomposisi
                      menyusul otomatis setelah data {dekom?.min_bulan ?? 24} bulan
                      terkumpul.
                    </span>
                  </p>
                )}
              </div>

              {/* ---- laporan penggabungan ejaan wilayah ---- */}
              {data.wilayah?.digabung?.length > 0 && (
                <details className="mt-3">
                  <summary className="cursor-pointer text-[11px] text-[#64676C]">
                    Nama wilayah yang digabung ({data.wilayah.digabung.length}) — ejaan
                    berbeda, provinsi sama
                  </summary>
                  <table className="mt-1 w-full text-[11px]">
                    <tbody>
                      {data.wilayah.digabung.map((g: any) => (
                        <tr key={g.kunci} className="border-b border-[#EDEFF2]">
                          <td className="py-0.5 pr-2 font-semibold text-[#1D2434]">{g.label}</td>
                          <td className="text-[#64676C]">
                            {g.varian.map((v: any) => `${v.ejaan} (${v.jumlah})`).join(" · ")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              )}
            </>
          )}
          </div>
        </div>
      )}
    </>
  );
}

/* ---------- analisis deskriptif & komposisi (share, Pareto/ABC, EUDR) ---------- */

const WARNA_KELAS: Record<string, string> = {
  A: "bg-[#1D2434] text-white",
  B: "bg-[#FF1313] text-white",
  C: "bg-[#F1F2F4] text-[#1D2434]",
};

export function AnalisisKomposisi({ dari, sampai, modeEudr, dimensi,
                                    bukaAwal = false }: {
  dari: string; sampai: string; modeEudr: "semua" | "eudr" | "biasa";
  dimensi: string;
  /** Bawaannya tertutup: tombol dibuka seperti Margin Bridge. */
  bukaAwal?: boolean;
}) {
  const [buka, setBuka] = useState(bukaAwal);
  const [dim, setDim] = useState(dimensi);
  /* dimensi kartu ikut berubah saat drill-down; samakan selama panel tertutup */
  useEffect(() => { setDim(dimensi); }, [dimensi]);

  const params = new URLSearchParams({ dimensi: dim });
  if (dari) params.set("dari", dari);
  if (sampai) params.set("sampai", sampai);
  if (modeEudr !== "semua") params.set("eudr", String(modeEudr === "eudr"));
  const url = `/api/kartu/penerimaan/komposisi?${params.toString()}`;
  const q = useQuery({
    queryKey: ["komposisi-penerimaan", url],
    queryFn: () => ambilJson(url),
    enabled: buka,
  });

  const d = q.data;
  const baris: any[] = d?.baris ?? [];
  const eudrBulan: any[] = d?.eudr?.per_bulan ?? [];
  const grafikEudr = eudrBulan.map((m: any) => ({
    nama: m.label,
    "Share EUDR (%)": m.eudr_pct,
  }));
  const grafikPorsi = baris.slice(0, 12).map((b: any) => ({
    nama: b.label.length > 22 ? b.label.slice(0, 22) + "…" : b.label,
    "Porsi (%)": b.porsi_pct,
  }));

  return (
    <>
      <button className={kelasTombolAnalisa} onClick={() => setBuka(true)}>
        📊 Analisis deskriptif &amp; komposisi
      </button>

      {buka && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
             onClick={() => setBuka(false)}>
          <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-sm bg-white border border-[#E4E5E8] p-6 shadow-xl shadow-[#1D2434]/10"
               onClick={(e) => e.stopPropagation()}>
            <KepalaPanel judul={"Analisis deskriptif & komposisi — penerimaan karet"}
                         periode={d && baris.length
                           ? `${fmtAngka(d.total_ton, 1)} ton · ${d.jumlah_tiket} tiket`
                           : undefined}
                         url={url} tutup={() => setBuka(false)} />

            {/* dimensi komposisi (bisa berbeda dari dimensi kartu) */}
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              <span className="text-[#64676C]">Komposisi menurut:</span>
              <div className="inline-flex overflow-hidden rounded-sm border border-[#D5D7DB]">
                {["provinsi", "vendor", "grade", "kabupaten"].map((dk) => (
                  <button key={dk}
                    className={`px-2.5 py-1 font-medium ${dim === dk
                      ? "bg-[#1D2434] text-white" : "bg-white text-[#1D2434] hover:bg-[#E8E9EC]"}`}
                    onClick={() => setDim(dk)}>
                    {dk}
                  </button>
                ))}
              </div>
            </div>

            {q.isLoading && <p className="mt-3 text-xs text-[#64676C]">Menghitung…</p>}
            {q.error && <p className="mt-3 text-xs text-[#B91C1C]">{pesanGalat(q.error)}</p>}

            {d && (
              <>
                {d.peringatan?.length > 0 && (
                  <div className="mt-3 rounded-sm border border-[#FDE68A] bg-[#FFFBEB] px-3 py-2">
                    <ul className="list-disc pl-4 text-xs text-[#92400E]">
                      {d.peringatan.map((t: string, i: number) => (
                        <li key={i} className="mb-0.5">{t}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {baris.length === 0 ? (
                  <p className="mt-3 text-sm text-[#64676C]">
                    Tidak ada data pada periode ini.
                  </p>
                ) : (
                  <>
                    {/* ---- KPI ringkas ---- */}
                    <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {[
                        ["Total", fmtAngka(d.total_kg, 0) + " kg",
                          fmtAngka(d.total_ton, 1) + " ton"],
                        ["Wilayah terbesar", d.konsentrasi.top1_label ?? "–",
                          `${fmtAngka(d.konsentrasi.top1_porsi_pct, 1)}% dari total`],
                        ["Mencapai 80%", `${d.pareto.jumlah_kategori_80} dari ${d.jumlah_kategori}`,
                          "kategori (Pareto)"],
                        ["Share EUDR", d.eudr.porsi_pct === null ? "–"
                          : fmtAngka(d.eudr.porsi_pct, 2) + "%",
                          `${fmtAngka(d.eudr.total_kg, 0)} kg dari total`],
                      ].map(([judul, nilai, bawah]) => (
                        <div key={judul as string}
                             className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-2.5">
                          <p className="text-[11px] text-[#64676C]">{judul}</p>
                          <p className="text-sm font-semibold text-[#1D2434]">{nilai}</p>
                          <p className="text-[11px] text-[#64676C]">{bawah}</p>
                        </div>
                      ))}
                    </div>

                    <p className="mt-2 rounded-sm border border-[#E4E5E8] bg-white px-3 py-2 text-xs text-[#64676C]">
                      <b className="text-[#1D2434]">Ketergantungan pasokan:</b>{" "}
                      {d.konsentrasi.top1_label} menyumbang{" "}
                      {fmtAngka(d.konsentrasi.top1_porsi_pct, 1)}%; tiga terbesar{" "}
                      {fmtAngka(d.konsentrasi.top3_porsi_pct, 1)}%. Indeks
                      konsentrasi (HHI) {fmtAngka(d.konsentrasi.hhi, 3)} —{" "}
                      {d.konsentrasi.label}.
                    </p>

                    {/* ---- grafik porsi ---- */}
                    {grafikPorsi.length > 1 && (
                      <div style={{ height: Math.max(160, grafikPorsi.length * 28 + 40) }}
                           className="mt-3">
                        <ResponsiveContainer>
                          <BarChart data={grafikPorsi} layout="vertical"
                                    margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis type="number" fontSize={10} unit="%"
                                   tickFormatter={(v) => fmtAngka(v as number, 0)} />
                            <YAxis type="category" dataKey="nama" width={150} fontSize={10} />
                            <Tooltip formatter={(v: any) => [fmtAngka(v as number, 2) + "%", "Porsi"]} />
                            <Bar dataKey="Porsi (%)" fill="#1D2434" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}

                    {/* ---- tabel share + Pareto/ABC ---- */}
                    <div className="mt-3 max-h-72 overflow-y-auto">
                      <table className="w-full text-xs">
                        <thead className="sticky top-0 bg-white">
                          <tr className="text-left text-[#64676C] border-b">
                            <th className="py-1">{dim}</th>
                            <th className="text-right">Kg</th>
                            <th className="text-right">Porsi</th>
                            <th className="text-right">Kumulatif</th>
                            <th className="text-center">Kelas</th>
                            <th className="text-right">EUDR %</th>
                            <th className="text-right">Tiket</th>
                          </tr>
                        </thead>
                        <tbody>
                          {baris.map((b: any) => (
                            <tr key={b.kunci} className="border-b border-[#EDEFF2]">
                              <td className="py-1">{b.label}</td>
                              <td className="text-right font-mono">{fmtAngka(b.kg, 0)}</td>
                              <td className="text-right font-mono">{fmtAngka(b.porsi_pct, 2)}%</td>
                              <td className="text-right font-mono">{fmtAngka(b.kumulatif_pct, 2)}%</td>
                              <td className="text-center">
                                <span className={`rounded-sm px-1.5 py-0.5 text-[10px] font-semibold ${WARNA_KELAS[b.kelas]}`}>
                                  {b.kelas}
                                </span>
                              </td>
                              <td className="text-right font-mono">
                                {b.eudr_pct === null ? "–" : fmtAngka(b.eudr_pct, 2) + "%"}
                              </td>
                              <td className="text-right font-mono">{b.jumlah_tiket}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="mt-1 text-[11px] text-[#64676C]">
                      <b>Kelas A</b> = kategori yang membuat kumulatif mencapai 80%
                      (fokus pengelolaan), <b>B</b> sampai 95%, <b>C</b> sisanya
                      (ekor panjang). {d.pareto.catatan}
                    </p>

                    {/* ---- EUDR vs biasa ---- */}
                    <div className="mt-4 border-t border-[#E4E5E8] pt-3">
                      <h4 className="text-xs font-semibold text-[#1D2434]">
                        Share EUDR vs biasa
                      </h4>
                      <p className="mt-1 text-xs text-[#64676C]">
                        EUDR <b className="text-[#15803D]">{fmtAngka(d.eudr.total_kg, 0)} kg
                        ({fmtAngka(d.eudr.porsi_pct, 2)}%)</b> · biasa{" "}
                        {fmtAngka(d.eudr.biasa_kg, 0)} kg ({fmtAngka(d.eudr.biasa_porsi_pct, 2)}%).
                      </p>
                      {eudrBulan.length > 1 && (
                        <div className="mt-2 h-48">
                          <ResponsiveContainer>
                            <LineChart data={grafikEudr}
                                       margin={{ top: 5, right: 15, bottom: 5, left: 0 }}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="nama" fontSize={10} minTickGap={20} />
                              <YAxis fontSize={10} unit="%" domain={[0, "auto"]} />
                              <Tooltip formatter={(v: any) => [fmtAngka(v as number, 2) + "%", "Share EUDR"]} />
                              <Line type="monotone" dataKey="Share EUDR (%)" stroke="#15803D"
                                    strokeWidth={2} dot={{ r: 2 }} />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      )}
                      <div className="mt-2 max-h-40 overflow-y-auto">
                        <table className="w-full text-xs">
                          <thead className="sticky top-0 bg-white">
                            <tr className="text-left text-[#64676C] border-b">
                              <th className="py-1">Bulan</th>
                              <th className="text-right">Total kg</th>
                              <th className="text-right">EUDR kg</th>
                              <th className="text-right">Share EUDR</th>
                              <th>Perubahan</th>
                            </tr>
                          </thead>
                          <tbody>
                            {eudrBulan.map((m: any, i: number) => {
                              const sebelum = i > 0 ? eudrBulan[i - 1].eudr_pct : null;
                              const delta = sebelum !== null && m.eudr_pct !== null
                                ? m.eudr_pct - sebelum : null;
                              return (
                                <tr key={m.ym} className="border-b border-[#EDEFF2]">
                                  <td className="py-1">{m.label}</td>
                                  <td className="text-right font-mono">{fmtAngka(m.total_kg, 0)}</td>
                                  <td className="text-right font-mono">{fmtAngka(m.eudr_kg, 0)}</td>
                                  <td className="text-right font-mono">{fmtAngka(m.eudr_pct, 2)}%</td>
                                  <td className={delta === null ? ""
                                    : delta > 0.005 ? "text-[#15803D]"
                                      : delta < -0.005 ? "text-[#DC2626]" : "text-[#64676C]"}>
                                    {delta === null ? "–"
                                      : `${delta > 0.005 ? "▲" : delta < -0.005 ? "▼" : "■"} ${fmtAngka(Math.abs(delta), 2)} poin`}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      <p className="mt-1 text-[11px] text-[#64676C]">
                        Dipantau per bulan untuk melihat apakah porsi EUDR naik
                        (target kepatuhan). Bulan dengan data tipis membuat
                        persentasenya mudah melonjak — bandingkan dengan kolom Total kg.
                      </p>
                    </div>

                    {d.wilayah?.digabung?.length > 0 && (
                      <p className="mt-3 text-[11px] text-[#92400E]">
                        Ejaan wilayah digabung (beda huruf besar/kecil):{" "}
                        {d.wilayah.digabung.map((g: any) => g.label).join(", ")}.
                      </p>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

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
          {/* Tombol analisa rata kanan di baris filter — bentuk yang sama
              dengan tombol Margin Bridge / Days of Cover di Margin Performance. */}
          <div className="ml-auto flex flex-wrap gap-2">
            <AnalisisTren dari={dari} sampai={sampai} modeEudr={modeEudr} />
            <AnalisisKomposisi dari={dari} sampai={sampai} modeEudr={modeEudr}
                               dimensi={dimensi} />
          </div>
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
                {q.data.wilayah?.digabung?.length > 0 && (
                  <p className="mt-1 rounded-sm border border-[#FDE68A] bg-[#FFFBEB] px-2 py-1 text-[11px] text-[#92400E]">
                    Ejaan {dimensi} digabung:{" "}
                    {q.data.wilayah.digabung.map((g: any) => g.label).join(", ")} — beda
                    huruf besar/kecil, wilayahnya sama. Sumber datanya sebaiknya ikut
                    dibakukan.
                  </p>
                )}
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
  const [dari, setDari] = useState("");
  const [sampai, setSampai] = useState("");
  const [topN, setTopN] = useState(8);

  const jumlahBulan = hitungJumlahBulan(dari, sampai);
  const modeBulan = jumlahBulan > 1;

  const params = new URLSearchParams({ dimensi });
  if (modeBulan) {
    params.set("per", "bulan");
    params.set("top", String(topN));
  }
  if (dari) params.set("dari", `${dari}-01`);
  if (sampai) params.set("sampai", akhirBulan(sampai));
  jejak.forEach((j) => params.set(j.dim, j.nilai));
  const url = `/api/kartu/tonase?${params.toString()}`;

  const q = useQuery({ queryKey: ["tonase", url], queryFn: () => ambilJson(url) });

  const drill = (baris: any) => {
    if (baris?.kunci === "__lainnya__" || !q.data?.drill_berikutnya) return;
    setJejak([...jejak, { dim: dimensi, nilai: baris.kunci }]);
    setDimensi(q.data.drill_berikutnya);
  };

  const mulaiUlang = (dim: string) => { setJejak([]); setDimensi(dim); };

  /* grafik bulanan: satu batang per bulan, ditumpuk per dimensi (ton) */
  const bulan: { ym: string; label: string }[] = q.data?.per === "bulan"
    ? (q.data.bulan ?? []) : [];
  const seriBulan: any[] = q.data?.per === "bulan" ? (q.data.baris ?? []) : [];
  const grafik = bulan.map((b, i) => {
    const titik: Record<string, any> = { nama: b.label };
    seriBulan.forEach((r: any) => {
      titik[r.label ?? r.kunci] = r.ton_per_bulan[i] ?? 0;
    });
    return titik;
  });

  return (
    <Kartu idMetrik="tonase" judul="Tonase (drill-down)"
           keterangan="Ton kering dari tiket. Bila periode lebih dari satu bulan, tampil rincian per bulan sesuai dimensi. Klik baris wilayah untuk turun: provinsi → kabupaten → kecamatan → desa."
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
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <PilihRentangBulan dari={dari} sampai={sampai}
                             setDari={setDari} setSampai={setSampai} />
          {modeBulan && (
            <label className="flex items-center gap-1.5 text-xs text-[#64676C]">
              Tampilkan
              <select className="rounded-sm border border-[#D5D7DB] bg-white px-1.5 py-1"
                      value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
                {[5, 8, 12, 20].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
              {dimensi} terbesar
            </label>
          )}
        </div>
        {jejak.length > 0 && (
          <p className="mb-2 text-xs text-[#64676C]">
            Jejak: {jejak.map((j) => `${j.dim} = ${j.nilai}`).join(" → ")} →{" "}
            <b>{dimensi}</b>{" "}
            <button className={kelasTombolKecil} onClick={() => mulaiUlang("provinsi")}>
              mulai ulang
            </button>
          </p>
        )}

        {modeBulan ? (
          bulan.length > 0 && seriBulan.length > 0 ? (
            <>
              <div style={{ height: Math.max(220, 40 + seriBulan.length * 6 + 160) }}>
                <ResponsiveContainer>
                  <BarChart data={grafik} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="nama" fontSize={10} />
                    <YAxis fontSize={10} tickFormatter={(v) => fmtAngka(v as number, 1)} />
                    <Tooltip formatter={(v: any, nama: any) =>
                      [fmtAngka(v as number, 1) + " ton", nama]} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {seriBulan.map((r: any, i: number) => (
                      <Bar key={r.kunci} dataKey={r.label ?? r.kunci} stackId="ton"
                           fill={WARNA_SERI[i % WARNA_SERI.length]} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <TabelBulanan data={q.data} dimensi={dimensi} nilaiKey="ton_per_bulan"
                            desimal={3} satuan="ton kering"
                            footerNilai={q.data.total_per_bulan} drill={drill} />
            </>
          ) : (
            <p className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-3 py-4 text-sm text-[#64676C]">
              Tidak ada data tiket untuk filter ini.
            </p>
          )
        ) : (
          <>
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

/* ---------- daftar intake terakhir ---------- */
/* Umur data dalam kata: 0 = hari ini, 1 = kemarin, sisanya "N hari lalu". */
const umurDalamKata = (hari: number) =>
  hari <= 0 ? "hari ini" : hari === 1 ? "kemarin" : `${hari} hari lalu`;

export function KartuIntakeTerakhir() {
  const [limit, setLimit] = useState(20);
  const url = `/api/kartu/intake-terakhir?limit=${limit}`;
  const q = useQuery({ queryKey: ["intake-terakhir", url], queryFn: () => ambilJson(url) });
  const t = q.data?.terakhir;

  return (
    <Kartu idMetrik="penerimaan" judul="Daftar intake terakhir"
           urlEkspor={url}
           keterangan={"Satu baris = satu tiket (satu kendaraan datang). Urut dari yang paling baru, supaya kelihatan kapan intake terakhir masuk."}
           anak={
      <>
        {t ? (
          <div className="mb-3 rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
              <div>
                <p className="text-xs text-[#64676C]">Intake terakhir masuk</p>
                <p className="text-lg font-semibold text-[#1D2434]">
                  {fmtTanggal(t.tanggal)}
                  <span className={`ml-2 rounded-sm px-2 py-0.5 text-xs font-semibold ${
                    t.umur_hari > 7
                      ? "bg-[#FEF2F2] text-[#B91C1C] border border-[#FECACA]"
                      : "bg-[#ECFDF5] text-[#166534] border border-[#A7F3D0]"}`}>
                    {umurDalamKata(t.umur_hari)}
                  </span>
                </p>
              </div>
              <div>
                <p className="text-xs text-[#64676C]">Tiket</p>
                <p className="text-sm font-mono text-[#1D2434]">{t.ticket_no}</p>
              </div>
              <div>
                <p className="text-xs text-[#64676C]">Vendor</p>
                <p className="text-sm text-[#1D2434]">{t.label_vendor}</p>
              </div>
              <div>
                <p className="text-xs text-[#64676C]">Grade · ton kering</p>
                <p className="text-sm text-[#1D2434]">
                  {t.grade ?? "–"} · {fmtAngka(t.dry_ton, 3)} t
                </p>
              </div>
              <div>
                <p className="text-xs text-[#64676C]">Sehari itu</p>
                <p className="text-sm text-[#1D2434]">
                  {t.jumlah_tiket_hari_itu} tiket · {fmtAngka(t.dry_ton_hari_itu, 3)} t
                </p>
              </div>
            </div>
            {t.umur_hari > 7 && (
              <p className="mt-2 text-xs text-[#B45309]">
                Data intake terakhir sudah {t.umur_hari} hari. Bila seharusnya sudah ada
                tiket baru, unggah ekspor “Master Data” terbaru di menu Unggah Data.
              </p>
            )}
          </div>
        ) : (
          <p className="mb-3 text-sm text-[#64676C]">
            Belum ada tiket intake sama sekali. Unggah ekspor “Master Data” di menu Unggah Data.
          </p>
        )}

        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-[#64676C]">
          <label className="flex items-center gap-1.5">
            Tampilkan
            <select className={kelasInput + " max-w-24"} value={limit}
                    onChange={(e) => setLimit(Number(e.target.value))}>
              {[10, 20, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            tiket terakhir
          </label>
          {q.data && (
            <span>
              · {q.data.baris.length} dari {q.data.jumlah_tiket_total} tiket
              {q.data.tanggal_pertama ? ` (data sejak ${fmtTanggal(q.data.tanggal_pertama)})` : ""}
            </span>
          )}
        </div>

        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-white">
              <tr className="text-left text-[#64676C] border-b">
                <th className="py-1">Tanggal</th>
                <th>No tiket</th>
                <th>Vendor</th>
                <th>Grade</th>
                <th className="text-right">Wet ton</th>
                <th className="text-right">Dry ton</th>
                <th className="text-right">Reject ton</th>
                <th>Wilayah</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.baris.map((b: any) => (
                <tr key={`${b.tanggal}-${b.ticket_no}`} className="border-b border-[#EDEFF2]">
                  <td className="py-1 whitespace-nowrap">{fmtTanggal(b.tanggal)}</td>
                  <td className="font-mono">{b.ticket_no}</td>
                  <td>{b.label_vendor}</td>
                  <td>{b.grade ?? "–"}</td>
                  <td className="text-right font-mono">{fmtAngka(b.wet_ton, 3)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.dry_ton, 3)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.reject_ton, 3)}</td>
                  <td>{[b.kabupaten, b.provinsi].filter(Boolean).join(", ") || "–"}</td>
                </tr>
              ))}
              {q.data?.baris.length === 0 && (
                <tr><td colSpan={8} className="py-2 text-[#64676C]">Belum ada tiket intake.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </>
    } />
  );
}

/* ---------- reject% (tabel dibatasi 12 bulan terakhir) ---------- */
export function KartuReject() {
  const [tahun, setTahun] = useState<number | "">("");
  const [jmlBulan, setJmlBulan] = useState(12);   // 0 = semua bulan
  const params = new URLSearchParams();
  if (tahun) params.set("tahun", String(tahun));
  params.set("bulan", String(jmlBulan));
  const url = `/api/kartu/reject?${params.toString()}`;
  const q = useQuery({ queryKey: ["reject", url], queryFn: () => ambilJson(url) });

  const kp = q.data?.kpi?.kpi_periode;
  const labelPeriode = jmlBulan === 0 ? "seluruh periode"
    : `${jmlBulan} bulan terakhir yang berdata`;

  return (
    <Kartu idMetrik="reject" judul="KPI Reject %" urlEkspor={url}
           keterangan={`Reject ÷ wet per bulan, ditampilkan ${labelPeriode}.`}
           anak={
      <>
        <div className="flex flex-wrap items-end gap-2">
          <PilihPeriode tahun={tahun} setTahun={setTahun} />
          <label className="mb-3 flex items-center gap-1.5 text-xs text-[#64676C]">
            Tampilkan
            <select className={kelasInput + " max-w-44"}
                    value={jmlBulan} onChange={(e) => setJmlBulan(Number(e.target.value))}>
              {[[6, "6 bulan terakhir"], [12, "12 bulan terakhir"],
                [24, "24 bulan terakhir"], [0, "Semua bulan"]].map(([v, t]) => (
                <option key={v} value={v}>{t}</option>
              ))}
            </select>
          </label>
        </div>
        {kp && kp.reject_pct !== null && (
          <p className="mb-2 text-sm">
            {jmlBulan === 0 ? "Seluruh periode" : `Rata-rata ${labelPeriode}`}:{" "}
            <b>{fmtAngka(kp.reject_pct, 2)}%</b>{" "}
            ({fmtAngka(kp.reject_kg / 1000, 2)} ton reject dari{" "}
            {fmtAngka(kp.wet_kg / 1000, 1)} ton wet) · tiket nol: {q.data.kpi.tiket_nol}
          </p>
        )}
        {q.data?.terpotong && (
          <p className="mb-2 text-xs text-[#64676C]">
            Menampilkan {q.data.jumlah_bulan_tampil} bulan terakhir dari{" "}
            {q.data.jumlah_bulan_total} bulan yang ada data
            {tahun ? ` (tahun ${tahun})` : ""}. Pilih “Semua bulan” untuk melihat semuanya.
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
  const [dari, setDari] = useState("");
  const [sampai, setSampai] = useState("");
  const [topN, setTopN] = useState(8);

  const jumlahBulan = hitungJumlahBulan(dari, sampai);
  const modeBulan = jumlahBulan > 1;

  const params = new URLSearchParams({ dimensi });
  if (modeBulan) {
    params.set("per", "bulan");
    params.set("top", String(topN));
  }
  if (dari) params.set("dari", `${dari}-01`);
  if (sampai) params.set("sampai", akhirBulan(sampai));
  const url = `/api/kartu/margin-per?${params.toString()}`;

  const q = useQuery({ queryKey: ["margin-per", url], queryFn: () => ambilJson(url) });

  /* Margin adalah TINGKAT (US¢/kg) — batang dikelompokkan, tidak ditumpuk. */
  const bulan: { ym: string; label: string }[] = q.data?.per === "bulan"
    ? (q.data.bulan ?? []) : [];
  const seriBulan: any[] = q.data?.per === "bulan" ? (q.data.baris ?? []) : [];
  const grafik = bulan.map((b, i) => {
    const titik: Record<string, any> = { nama: b.label };
    seriBulan.forEach((r: any) => {
      titik[r.label ?? r.kunci] = r.margin_per_bulan[i];
    });
    return titik;
  });

  return (
    <Kartu idMetrik="margin_per" judul="Margin per grade / vendor"
           keterangan="Margin US¢/kg tertimbang tonase kering. Bila periode lebih dari satu bulan, tampil rincian per bulan; total per bulan memakai timbangan tonase, bukan penjumlahan margin."
           urlEkspor={q.data?.status === "ok" ? url : undefined}
           anak={
      <>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          {(["grade", "vendor"] as const).map((d) => (
            <button key={d}
              className={`rounded-sm px-3 py-1 text-xs ${dimensi === d
                ? "bg-[#FF1313] text-white" : "bg-[#F1F2F4] text-[#1D2434]"}`}
              onClick={() => setDimensi(d)}>per {d}</button>
          ))}
          <PilihRentangBulan dari={dari} sampai={sampai}
                             setDari={setDari} setSampai={setSampai} />
          {modeBulan && (
            <label className="flex items-center gap-1.5 text-xs text-[#64676C]">
              Tampilkan
              <select className="rounded-sm border border-[#D5D7DB] bg-white px-1.5 py-1"
                      value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
                {[5, 8, 12, 20].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
              {dimensi} terbesar
            </label>
          )}
        </div>

        {q.data?.status === "data harga belum tersedia" ? (
          <p className="rounded-sm bg-[#F8F8F8] border border-[#E4E5E8] px-3 py-4 text-sm text-[#1D2434]">
            <b>Data harga belum tersedia.</b> {q.data.pesan}
          </p>
        ) : modeBulan ? (
          bulan.length > 0 && seriBulan.length > 0 ? (
            <>
              <div style={{ height: Math.max(220, 40 + seriBulan.length * 8 + 150) }}>
                <ResponsiveContainer>
                  <BarChart data={grafik} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="nama" fontSize={10} />
                    <YAxis fontSize={10} tickFormatter={(v) => fmtAngka(v as number, 1)} />
                    <Tooltip formatter={(v: any, nama: any) =>
                      [v === null || v === undefined ? "–" : fmtAngka(v as number, 2) + " US¢/kg", nama]} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {seriBulan.map((r: any, i: number) => (
                      <Bar key={r.kunci} dataKey={r.label ?? r.kunci}
                           fill={WARNA_SERI[i % WARNA_SERI.length]} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <TabelBulanan data={q.data} dimensi={dimensi} nilaiKey="margin_per_bulan"
                            desimal={2} satuan="US¢/kg"
                            footerNilai={q.data.total_per_bulan?.op_margin} />
              <p className="mt-2 text-xs text-[#64676C]">
                Ton per bulan:{" "}
                {(q.data.total_per_bulan?.ton ?? []).map((t: number, i: number) => (
                  <span key={i} className="mr-2 font-mono">
                    {bulan[i]?.label} {fmtAngka(t, 1)} t
                  </span>
                ))}
              </p>
            </>
          ) : (
            <p className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-3 py-4 text-sm text-[#64676C]">
              Tidak ada data harga rinci untuk filter ini.
            </p>
          )
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
        <Panel5W1H judul="Analisa halaman Intake Analisis — 5W1H"
                   url={`/api/analisis/analisa${paramsA.size ? "?" + paramsA.toString() : ""}`}
                   tutup={() => setBukaAnalisa(false)} />
      )}
      <div className="lg:col-span-2"><KartuMuatSaatDiminta
        judul="Penerimaan karet (kg) — biasa vs EUDR"
        keterangan="Memuat grafik dan rincian penerimaan hanya setelah Anda meminta."
        anak={<KartuPenerimaan />}
      /></div>
      <KartuMuatSaatDiminta judul="Tonase (drill-down)" keterangan="Memuat rincian tonase hanya setelah Anda meminta." anak={<KartuTonase />} />
      <KartuMuatSaatDiminta judul="Konsentrasi vendor" keterangan="Memuat konsentrasi pemasok hanya setelah Anda meminta." anak={<KartuKonsentrasi />} />
      <KartuMuatSaatDiminta judul="Bauran grade & porsi EUDR" keterangan="Memuat komposisi grade hanya setelah Anda meminta." anak={<KartuGrade />} />
      <KartuMuatSaatDiminta judul="KPI Reject %" keterangan="Memuat indikator reject hanya setelah Anda meminta." anak={<KartuReject />} />
      <KartuMuatSaatDiminta judul="Margin harian" keterangan="Memuat margin harian hanya setelah Anda meminta." anak={<KartuMarginHarian />} />
      <KartuMuatSaatDiminta judul="Margin per grade / vendor" keterangan="Memuat perincian margin hanya setelah Anda meminta." anak={<KartuMarginPer />} />
      <div className="lg:col-span-2"><KartuMuatSaatDiminta
        judul="Daftar intake terakhir"
        keterangan="Memuat daftar tiket terakhir hanya setelah Anda meminta."
        anak={<KartuIntakeTerakhir />}
      /></div>
      <p className="lg:col-span-2 text-xs text-[#64676C]">
        Kartu tonase/grade/reject memakai data tiket; data tiket historis penuh belum
        diunggah (template hanya berisi contoh), jadi angka akan terisi setelah ekspor
        "Master Data" diunggah. Filter terbatas pada dimensi berdaftar-putih — tidak ada
        SQL dari layar.
      </p>
    </div>
  );
}
