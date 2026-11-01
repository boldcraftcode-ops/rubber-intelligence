import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Kartu, ambilJson, fmtAngka, kelasInput } from "../bersama";

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
  const params = new URLSearchParams({ dimensi: "provinsi" });
  if (dari) params.set("dari", `${dari}-01`);
  if (sampai) params.set("sampai", akhirBulan(sampai));
  const url = `/api/kartu/penerimaan?${params.toString()}`;

  const intake = useQuery({
    queryKey: ["peta-intake-provinsi", url],
    queryFn: () => ambilJson(url),
  });
  const geo = useQuery<FeatureCollection>({
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
            <div>
              <label className="mb-1 block text-[#64676C]">Dari bulan</label>
              <input type="month" className={kelasInput} value={dari} onChange={(event) => setDari(event.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-[#64676C]">Sampai bulan</label>
              <input type="month" className={kelasInput} value={sampai} onChange={(event) => setSampai(event.target.value)} />
            </div>
            {(dari || sampai) && (
              <button type="button" className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-2.5 py-1.5 text-[#1D2434] hover:bg-[#F1F2F4]"
                onClick={() => { setDari(""); setSampai(""); }}>
                Hapus periode
              </button>
            )}
            <span className="ml-auto text-[#64676C]">Periode: <b>{period}</b></span>
          </div>

          {(intake.isLoading || geo.isLoading) && <p className="py-8 text-sm text-[#64676C]">Memuat peta dan menghitung intake…</p>}
          {(intake.error || geo.error) && (
            <p className="rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-sm text-[#B91C1C]">
              {pesanError(intake.error ?? geo.error)}
            </p>
          )}
          {intake.data && geo.data && (
            <>
              <div className="mb-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-[#475467]">
                <span>Total intake periode: <b className="font-mono text-[#1D2434]">{fmtAngka(intake.data.total_kg, 0)} kg</b></span>
                <span>Terpetakan: <b className="font-mono text-[#1D2434]">{fmtAngka(totalTerpetakan, 0)} kg</b></span>
                <span>{geo.data.features.length} batas provinsi</span>
              </div>
              <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(250px,1fr)]">
                <div className="min-w-0 overflow-x-auto rounded-sm border border-[#E4E5E8] bg-[#F8FAFC] p-2">
                  <svg viewBox={`0 0 ${LEBAR} ${TINGGI}`} role="img" aria-label={`Peta intake Indonesia untuk periode ${period}`} className="h-auto min-h-[250px] w-full min-w-[620px]">
                    {nilai.mapped.map(({ feature, row }) => {
                      const kg = row?.kg_total ?? null;
                      return (
                        <path key={feature.properties.PROVINSI}
                          d={projectPath?.get(feature.properties.PROVINSI) ?? ""}
                          fill={colorOf(kg)} stroke="#FFFFFF" strokeWidth="0.75" strokeLinejoin="round"
                          aria-label={`${feature.properties.PROVINSI}: ${kg === null ? "belum ada data intake" : `${fmtAngka(kg, 0)} kg`}`}>
                          <title>{feature.properties.PROVINSI}: {kg === null ? "belum ada data intake" : `${fmtAngka(kg, 0)} kg`}</title>
                        </path>
                      );
                    })}
                  </svg>
                  <div className="flex flex-wrap items-center gap-2 px-2 pb-1 text-[11px] text-[#64676C]">
                    <span>Intake lebih rendah</span>
                    {WARNA_BERURUT.map((color) => <span key={color} className="h-3 w-5 rounded-sm border border-white" style={{ backgroundColor: color }} />)}
                    <span>Intake lebih tinggi</span>
                    <span className="ml-3 inline-flex items-center gap-1"><span className="h-3 w-5 rounded-sm" style={{ backgroundColor: WARNA_KOSONG }} />Belum ada data</span>
                  </div>
                  <p className="px-2 pb-1 text-[10px] text-[#7B818A]">Skala warna relatif terhadap provinsi berdata pada periode terpilih. Arahkan kursor ke provinsi untuk melihat nilai.</p>
                </div>
                <aside className="min-w-0">
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
                  {nilai.unmapped.length > 0 && (
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
              <p className="mt-3 text-[11px] text-[#64676C]">
                Nilai memakai Dry dari tiket dan agregasi periode dihitung server. Peta hanya memakai kolom provinsi yang tercatat eksplisit pada tiket; nilai yang kosong atau tidak cocok ditampilkan sebagai belum terpetakan, bukan diambil dari Asal Getah atau data collector.
              </p>
            </>
          )}
        </>
      }
    />
  );
}
