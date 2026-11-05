import { useMemo, useState } from "react";
import { Kartu, PilihRentangBulan, TombolRefreshKartu, ambilJson, fmtAngka, useQueryKartu } from "../bersama";

const akhirBulan = (ym: string) => {
  const [tahun, bulan] = ym.split("-").map(Number);
  return `${ym}-${String(new Date(tahun, bulan, 0).getDate()).padStart(2, "0")}`;
};

type Feature = {
  type: "Feature";
  properties: { PROVINSI: string };
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: any };
};
type FeatureCollection = { type: "FeatureCollection"; features: Feature[] };
type ProvinceRow = { kunci: string; label: string; kg_total: number; jumlah_tiket: number };
type ProductionRow = { provinsi: string; ton: number | null; catatan?: string };
type IntakeYearRow = { provinsi: string; rata_rata_kg_per_tahun: number; tahun_tercakup: number[]; jumlah_tahun: number };
type PotentialResponse = {
  tahun_produksi: number;
  produksi_sentra: ProductionRow[];
  rata_rata_intake_tahunan: IntakeYearRow[];
  seri_lampung: { status: string; tahun: number | null; produksi_ton_slab: number | null; jumlah_kabupaten_kota: number | null; diperiksa_pada: string; url: string; pesan?: string };
  sumber: { nama: string; url: string; cakupan: string }[];
};

type ModePeta = "intake" | "potensi";

const LEBAR = 920;
const TINGGI = 430;
const WARNA_BERURUT = ["#DBEAFE", "#93C5FD", "#3B82F6", "#1D4ED8", "#172554"];
const WARNA_KOSONG = "#E5E7EB";
const pesanError = (error: unknown) => error instanceof Error ? error.message : "Gagal memuat peta atau data intake.";

function posisi(value: any, output: number[][] = []): number[][] {
  if (!Array.isArray(value)) return output;
  if (typeof value[0] === "number" && typeof value[1] === "number") {
    output.push(value as number[]);
    return output;
  }
  value.forEach((child) => posisi(child, output));
  return output;
}

function namaBaku(value: string | null | undefined): string {
  return (value ?? "").trim().replace(/\s+/g, " ").toLocaleUpperCase("id-ID");
}

function buatPath(geometri: Feature["geometry"], project: (p: number[]) => [number, number]) {
  const polygons = geometri.type === "Polygon" ? [geometri.coordinates] : geometri.coordinates;
  return polygons.map((polygon: any[]) => polygon.map((ring: number[][]) =>
    ring.map((p, i) => {
      const [x, y] = project(p);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ") + " Z",
  ).join(" ")).join(" ");
}

export default function PetaIntake() {
  const [dari, setDari] = useState("");
  const [sampai, setSampai] = useState("");
  const [mode, setMode] = useState<ModePeta>("intake");
  const params = new URLSearchParams({ dimensi: "provinsi" });
  if (dari) params.set("dari", `${dari}-01`);
  if (sampai) params.set("sampai", akhirBulan(sampai));
  const url = `/api/kartu/penerimaan?${params.toString()}`;

  const intake = useQueryKartu({
    queryKey: ["peta-intake-provinsi", url],
    queryFn: () => ambilJson(url),
  });
  const potensi = useQueryKartu<PotentialResponse>({
    queryKey: ["peta-potensi-karet"],
    queryFn: () => ambilJson("/api/kartu/potensi-karet"),
    staleTime: 60 * 60 * 1000,
  });
  const geo = useQueryKartu<FeatureCollection>({
    queryKey: ["peta-batas-provinsi-indonesia"],
    queryFn: async () => {
      const response = await fetch("/data/indonesia-provinsi.geojson");
      if (!response.ok) throw new Error("Batas peta provinsi gagal dimuat.");
      return response.json();
    },
    staleTime: Infinity,
  });

  const nilai = useMemo(() => {
    const rows: ProvinceRow[] = intake.data?.baris ?? [];
    const byName = new Map(rows.map((row) => [namaBaku(row.label), row]));
    const names = new Set((geo.data?.features ?? []).map((feature) => namaBaku(feature.properties.PROVINSI)));
    const mapped = (geo.data?.features ?? []).map((feature) => ({
      feature,
      row: byName.get(namaBaku(feature.properties.PROVINSI)) ?? null,
    }));
    const mappedNames = new Set(mapped.filter((item) => item.row).map((item) => namaBaku(item.feature.properties.PROVINSI)));
    const unmapped = rows.filter((row) => !names.has(namaBaku(row.label)) || !mappedNames.has(namaBaku(row.label)));
    const positive = mapped.flatMap((item) => item.row && item.row.kg_total > 0 ? [item.row.kg_total] : [])
      .sort((a, b) => a - b);
    return { mapped, unmapped, positive };
  }, [intake.data, geo.data]);

  const produksiByName = useMemo(() => new Map(
    (potensi.data?.produksi_sentra ?? []).map((row) => [namaBaku(row.provinsi), row]),
  ), [potensi.data]);
  const intakeTahunByName = useMemo(() => new Map(
    (potensi.data?.rata_rata_intake_tahunan ?? []).map((row) => [namaBaku(row.provinsi), row]),
  ), [potensi.data]);
  const produksiPositif = (potensi.data?.produksi_sentra ?? [])
    .flatMap((row) => row.ton !== null && row.ton > 0 ? [row.ton] : [])
    .sort((a, b) => a - b);

  const projectPath = useMemo(() => {
    const features = geo.data?.features ?? [];
    const points = features.flatMap((feature) => posisi(feature.geometry.coordinates));
    if (!points.length) return null;
    const minLon = Math.min(...points.map((p) => p[0]));
    const maxLon = Math.max(...points.map((p) => p[0]));
    const minLat = Math.min(...points.map((p) => p[1]));
    const maxLat = Math.max(...points.map((p) => p[1]));
    const padding = 18;
    const scale = Math.min((LEBAR - padding * 2) / (maxLon - minLon), (TINGGI - padding * 2) / (maxLat - minLat));
    const offsetX = (LEBAR - (maxLon - minLon) * scale) / 2;
    const offsetY = (TINGGI - (maxLat - minLat) * scale) / 2;
    const project = (p: number[]): [number, number] => [
      offsetX + (p[0] - minLon) * scale,
      offsetY + (maxLat - p[1]) * scale,
    ];
    return new Map(features.map((feature) => [feature.properties.PROVINSI, buatPath(feature.geometry, project)]));
  }, [geo.data]);

  const colorOf = (kg: number | null) => {
    if (kg === null) return WARNA_KOSONG;
    if (kg <= 0 || !nilai.positive.length) return WARNA_BERURUT[0];
    const rank = nilai.positive.filter((value) => value <= kg).length / nilai.positive.length;
    const bucket = Math.min(WARNA_BERURUT.length - 1, Math.ceil(rank * WARNA_BERURUT.length) - 1);
    return WARNA_BERURUT[Math.max(0, bucket)];
  };
  const colorProduksi = (ton: number | null) => {
    if (ton === null) return WARNA_KOSONG;
    if (ton <= 0 || !produksiPositif.length) return WARNA_BERURUT[0];
    const rank = produksiPositif.filter((value) => value <= ton).length / produksiPositif.length;
    const bucket = Math.min(WARNA_BERURUT.length - 1, Math.ceil(rank * WARNA_BERURUT.length) - 1);
    return WARNA_BERURUT[Math.max(0, bucket)];
  };
  const period = dari || sampai
    ? `${dari || "awal data"} – ${sampai || "terbaru"}`
    : "Seluruh periode data";
  const rows: ProvinceRow[] = intake.data?.baris ?? [];
  const totalTerpetakan = nilai.mapped.reduce((sum, item) => sum + (item.row?.kg_total ?? 0), 0);
  const topRows = [...rows].sort((a, b) => b.kg_total - a.kg_total).slice(0, 8);

  return (
    <Kartu idMetrik="peta_intake_provinsi" judul="Sebaran Intake per Provinsi Indonesia"
      keterangan="Peta sebaran intake karet berdasarkan provinsi yang tercatat pada tiket; warna semakin gelap menunjukkan intake Dry yang semakin besar."
      urlEkspor={url}
      anak={
        <>
          <div className="mb-4 flex flex-wrap items-end gap-3 text-xs">
            <div className="flex rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-0.5" role="group" aria-label="Lapisan peta">
              <button type="button" onClick={() => setMode("intake")}
                className={`rounded-sm px-3 py-1.5 ${mode === "intake" ? "bg-white font-semibold text-[#1D2434] shadow-sm" : "text-[#64676C]"}`}>
                Intake tercatat
              </button>
              <button type="button" onClick={() => setMode("potensi")}
                className={`rounded-sm px-3 py-1.5 ${mode === "potensi" ? "bg-white font-semibold text-[#1D2434] shadow-sm" : "text-[#64676C]"}`}>
                Sentra produksi
              </button>
            </div>
            {mode === "intake" ? (
              <>
                <PilihRentangBulan dari={dari} sampai={sampai}
                                   setDari={setDari} setSampai={setSampai}
                                   labelKosong="Hapus periode"
                                   aksi={<TombolRefreshKartu />} />
                <span className="ml-auto text-[#64676C]">Periode intake: <b>{period}</b></span>
              </>
            ) : (
              <>
                <span className="ml-auto text-[#64676C]">Produksi karet kering: <b>{potensi.data?.tahun_produksi ?? "—"}</b></span>
                <TombolRefreshKartu />
              </>
            )}
          </div>

          {(geo.isLoading || (mode === "intake" && intake.isLoading) || (mode === "potensi" && potensi.isLoading)) &&
            <p className="py-8 text-sm text-[#64676C]">Memuat peta dan data…</p>}
          {((mode === "intake" && intake.error) || (mode === "potensi" && potensi.error) || geo.error) && (
            <p className="rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-sm text-[#B91C1C]">
              {pesanError(mode === "intake" ? intake.error ?? geo.error : potensi.error ?? geo.error)}
            </p>
          )}
          {geo.data && ((mode === "intake" && intake.data) || (mode === "potensi" && potensi.data)) && (
            <>
              <div className="mb-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-[#475467]">
                {mode === "intake" ? (
                  <>
                    <span>Total intake periode: <b className="font-mono text-[#1D2434]">{fmtAngka(intake.data.total_kg, 0)} kg</b></span>
                    <span>Terpetakan: <b className="font-mono text-[#1D2434]">{fmtAngka(totalTerpetakan, 0)} kg</b></span>
                  </>
                ) : <span>Wilayah sentra resmi: <b className="font-mono text-[#1D2434]">{potensi.data?.produksi_sentra.length ?? 0} provinsi</b></span>}
                <span>{geo.data.features.length} batas provinsi</span>
              </div>
              <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(250px,1fr)]">
                <div className="min-w-0 overflow-x-auto rounded-sm border border-[#E4E5E8] bg-[#F8FAFC] p-2">
                  <svg viewBox={`0 0 ${LEBAR} ${TINGGI}`} role="img" aria-label={mode === "intake" ? `Peta intake Indonesia untuk periode ${period}` : `Peta sentra produksi karet kering tahun ${potensi.data?.tahun_produksi ?? ""}`} className="h-auto min-h-[250px] w-full min-w-[620px]">
                    {nilai.mapped.map(({ feature, row }) => {
                      const production = produksiByName.get(namaBaku(feature.properties.PROVINSI));
                      const productionTon = production?.ton ?? null;
                      const value = mode === "intake" ? row?.kg_total ?? null : productionTon;
                      const fill = mode === "intake" ? colorOf(value) : colorProduksi(value);
                      const text = value === null
                        ? (mode === "intake" ? "belum ada data intake" : "bukan provinsi sentra / belum ada data produksi")
                        : mode === "intake" ? `${fmtAngka(value, 0)} kg Dry` : `${fmtAngka(value, 0)} ton karet kering`;
                      return (
                        <path key={feature.properties.PROVINSI}
                          d={projectPath?.get(feature.properties.PROVINSI) ?? ""}
                          fill={fill} stroke="#FFFFFF" strokeWidth="0.75" strokeLinejoin="round"
                          aria-label={`${feature.properties.PROVINSI}: ${text}`}>
                          <title>{feature.properties.PROVINSI}: {text}{production?.catatan ? ` (${production.catatan})` : ""}</title>
                        </path>
                      );
                    })}
                  </svg>
                  <div className="flex flex-wrap items-center gap-2 px-2 pb-1 text-[11px] text-[#64676C]">
                    <span>{mode === "intake" ? "Intake lebih rendah" : "Produksi lebih rendah"}</span>
                    {WARNA_BERURUT.map((color) => <span key={color} className="h-3 w-5 rounded-sm border border-white" style={{ backgroundColor: color }} />)}
                    <span>{mode === "intake" ? "Intake lebih tinggi" : "Produksi lebih tinggi"}</span>
                    <span className="ml-3 inline-flex items-center gap-1"><span className="h-3 w-5 rounded-sm" style={{ backgroundColor: WARNA_KOSONG }} />{mode === "intake" ? "Belum ada data" : "Bukan sentra / data tidak tersedia"}</span>
                  </div>
                  <p className="px-2 pb-1 text-[10px] text-[#7B818A]">Skala warna relatif terhadap provinsi dengan data pada lapisan terpilih. Arahkan kursor ke provinsi untuk melihat nilainya.</p>
                </div>
                <aside className="min-w-0">
                  {mode === "intake" ? (
                    <>
                      <h3 className="mb-2 text-sm font-semibold text-[#1D2434]">Provinsi dengan intake terbesar</h3>
                      {topRows.length ? (
                        <ol className="space-y-1">
                          {topRows.map((row, index) => (
                            <li key={row.kunci} className="flex items-center justify-between gap-2 border-b border-[#EDEFF2] py-1.5 text-xs">
                              <span className="min-w-0 truncate"><span className="mr-2 text-[#9AA0A6]">{index + 1}.</span>{row.label}</span>
                              <span className="shrink-0 font-mono font-semibold">{fmtAngka(row.kg_total, 0)} kg</span>
                            </li>
                          ))}
                        </ol>
                      ) : <p className="text-xs text-[#64676C]">Belum ada intake dengan provinsi tercatat pada periode ini.</p>}
                    </>
                  ) : (
                    <>
                      <h3 className="mb-2 text-sm font-semibold text-[#1D2434]">Sentra produksi karet kering 2024</h3>
                      <ol className="space-y-1">
                        {[...(potensi.data?.produksi_sentra ?? [])].sort((a, b) => (b.ton ?? -1) - (a.ton ?? -1)).map((row, index) => {
                          const receipt = intakeTahunByName.get(namaBaku(row.provinsi));
                          return (
                            <li key={row.provinsi} className="border-b border-[#EDEFF2] py-1.5 text-xs">
                              <div className="flex items-center justify-between gap-2">
                                <span className="min-w-0 truncate"><span className="mr-2 text-[#9AA0A6]">{index + 1}.</span>{row.provinsi}</span>
                                <span className="shrink-0 font-mono font-semibold">{row.ton === null ? "—" : `${fmtAngka(row.ton, 0)} ton`}</span>
                              </div>
                              <div className="ml-5 mt-0.5 text-[10px] text-[#64676C]">
                                Rata-rata intake internal: {receipt ? `${fmtAngka(receipt.rata_rata_kg_per_tahun, 0)} kg Dry/tahun (${receipt.jumlah_tahun} th)` : "belum tersedia"}
                              </div>
                            </li>
                          );
                        })}
                      </ol>
                    </>
                  )}
                  {mode === "intake" && nilai.unmapped.length > 0 && (
                    <div className="mt-3 rounded-sm border border-[#FDE68A] bg-[#FFFBEB] p-2 text-[11px] text-[#92400E]">
                      <b>Belum terpetakan ke batas peta:</b>
                      <ul className="mt-1 list-disc pl-4">
                        {nilai.unmapped.map((row) => <li key={row.kunci}>{row.label} — {fmtAngka(row.kg_total, 0)} kg</li>)}
                      </ul>
                      <p className="mt-1">Nama tidak dicocokkan dengan tebakan atau kode buatan.</p>
                    </div>
                  )}
                </aside>
              </div>
              {mode === "intake" ? (
                <p className="mt-3 text-[11px] text-[#64676C]">
                  Nilai memakai Dry dari tiket dan agregasi periode dihitung server. Peta hanya memakai kolom provinsi yang tercatat eksplisit pada tiket; nilai yang kosong atau tidak cocok ditampilkan sebagai belum terpetakan, bukan diambil dari Asal Getah atau data collector.
                </p>
              ) : (
                <div className="mt-3 space-y-3 text-[11px] text-[#64676C]">
                  <p>
                    Produksi provinsi adalah volume produksi karet kering tahun 2024 dari seri resmi Ditjenbun yang dipublikasikan Pusdatin Kementan. Rata-rata intake dihitung terpisah dari Dry tiket di database aplikasi, dengan rata-rata atas tahun-tahun yang memiliki data; ini menunjukkan penerimaan internal, bukan total penjualan pasar.
                  </p>
                  {potensi.data?.seri_lampung && (
                    <div className="rounded-sm border border-[#BFDBFE] bg-[#EFF6FF] p-2.5 text-[#1E3A8A]">
                      <b>Feed online tambahan — Satu Data Lampung:</b>{" "}
                      {potensi.data.seri_lampung.status === "tersedia"
                        ? `tahun ${potensi.data.seri_lampung.tahun}, ${fmtAngka(potensi.data.seri_lampung.produksi_ton_slab ?? 0, 0)} ton slab dari ${potensi.data.seri_lampung.jumlah_kabupaten_kota} kabupaten/kota.`
                        : "sedang tidak dapat diakses; seri ini tidak digunakan untuk mengganti angka karet kering."}{" "}
                      <a href={potensi.data.seri_lampung.url} target="_blank" rel="noreferrer" className="underline">Buka dataset/API</a>
                      <span className="ml-1">(diperiksa {new Date(potensi.data.seri_lampung.diperiksa_pada).toLocaleString("id-ID")}).</span>
                      <div className="mt-1">Ton slab tidak dicampur dengan ton karet kering karena wujud/definisi produksinya berbeda.</div>
                    </div>
                  )}
                  <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F9FB] p-2.5">
                    <b className="text-[#344054]">Sumber online & definisi:</b>
                    <ul className="mt-1 list-disc space-y-1 pl-4">
                      {(potensi.data?.sumber ?? []).map((source) => (
                        <li key={source.nama}><a href={source.url} target="_blank" rel="noreferrer" className="font-medium text-[#175CD3] underline">{source.nama}</a> — {source.cakupan}</li>
                      ))}
                    </ul>
                    <p className="mt-2">Data penjualan provinsi tidak tersedia pada sumber resmi yang terverifikasi. Karena itu angka produksi dan intake tidak dilabeli sebagai penjualan. Publikasi nasional diperbarui berkala; feed Lampung diperiksa saat API diminta dan di-cache server selama enam jam.</p>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      }
    />
  );
}
