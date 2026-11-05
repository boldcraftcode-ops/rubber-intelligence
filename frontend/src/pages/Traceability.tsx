import { type ReactNode, Fragment, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ambilJson, fmtAngka, kelasInput, kelasLabel, kelasTombol, urlApi } from "../bersama";

type Filter = { year: string; period: string; supplier: string; eudr: string; includeLatex: boolean };
type Wilayah = {
  name: string; level: string; code: string; dry_mt: number; traceable_mt: number;
  traceability_pct: number | null; ticket_lines: number; status_code: string;
  traceability_status: "traceable" | "partial" | "unmatched"; children: Wilayah[];
};
type TingkatGap = "Kabupaten/Kota" | "Kecamatan" | "Desa/Kelurahan";
type BarisGap = {
  name: string; path: string; dry_mt: number; traceable_mt: number;
  untraceable_mt: number; traceability_pct: number | null; ticket_lines: number;
  traceability_status: Wilayah["traceability_status"];
};

function daftarBelumTraceable(nodes: Wilayah[], tingkat: TingkatGap, parents: string[] = []): BarisGap[] {
  return nodes.flatMap((node) => {
    const path = [...parents, node.name];
    const belumTraceable = node.traceability_status !== "traceable" ||
      (node.traceability_pct !== null && node.traceability_pct < 100);
    if (node.level === tingkat) {
      return belumTraceable ? [{
        name: node.name,
        path: parents.join(" / ") || "—",
        dry_mt: node.dry_mt,
        traceable_mt: node.traceable_mt,
        untraceable_mt: Math.max(0, node.dry_mt - node.traceable_mt),
        traceability_pct: node.traceability_pct,
        ticket_lines: node.ticket_lines,
        traceability_status: node.traceability_status,
      }] : [];
    }
    return daftarBelumTraceable(node.children ?? [], tingkat, path);
  });
}

const PERIODE = [
  ["ALL", "Satu tahun"], ["H1", "Semester 1"], ["H2", "Semester 2"],
  ["Q1", "Kuartal 1"], ["Q2", "Kuartal 2"], ["Q3", "Kuartal 3"], ["Q4", "Kuartal 4"],
  ...Array.from({ length: 12 }, (_, i) => [`${i + 1}`.padStart(2, "0"), `Bulan ${`${i + 1}`.padStart(2, "0")}`]),
];

function paramsFilter(f: Filter) {
  const p = new URLSearchParams();
  if (f.year) p.set("tahun", f.year);
  p.set("periode", f.period);
  if (f.supplier) p.set("supplier", f.supplier);
  p.set("eudr", f.eudr);
  if (f.includeLatex) p.set("include_latex", "true");
  return p.toString();
}

function Kpi({ title, value, unit, note, onClick, active = false }: {
  title: string; value: number | null; unit: string; note?: string;
  onClick?: () => void; active?: boolean;
}) {
  const className = `min-w-0 rounded-sm border ${active ? "border-[#F79009] bg-[#FFFAEB]" : "border-[#E4E5E8] bg-white"} border-l-2 ${onClick ? "border-l-[#F79009] hover:bg-[#FFFAEB] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#175CD3]" : "border-l-[#FF1313]"} px-4 py-3 text-left`;
  const content = (
    <>
      <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#64676C]">{title}</p>
      <p className="mt-1 text-xl font-bold tabular-nums text-[#1D2434]">
        {value == null ? "—" : fmtAngka(value, unit === "%" ? 2 : unit === "MT" ? 3 : 0)}
        <span className="ml-1 text-xs font-medium text-[#64676C]">{unit}</span>
      </p>
      {note && <p className="mt-1 text-[10px] text-[#9AA0A6]">{note}</p>}
      {onClick && <p className="mt-1 text-[10px] font-semibold text-[#B54708]">Klik untuk melihat rincian belum traceable</p>}
    </>
  );
  return onClick ? (
    <button type="button" className={`${className} w-full cursor-pointer`} onClick={onClick} aria-haspopup="dialog" aria-expanded={active}>
      {content}
    </button>
  ) : <div className={className}>{content}</div>;
}

export default function Traceability() {
  const [filters, setFilters] = useState<Filter>({ year: "", period: "ALL", supplier: "", eudr: "all", includeLatex: false });
  const [tab, setTab] = useState<"regions" | "actors">("regions");
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const [selectedActor, setSelectedActor] = useState<string | null>(null);
  const [gapLevel, setGapLevel] = useState<TingkatGap | null>(null);
  const [editingOrigin, setEditingOrigin] = useState<any | null>(null);
  const [targetDistrict, setTargetDistrict] = useState("");
  const [targetSubdistrict, setTargetSubdistrict] = useState("");
  const queryClient = useQueryClient();
  const query = paramsFilter(filters);
  const q = useQuery({
    queryKey: ["traceability", query],
    queryFn: () => ambilJson(`/api/traceability?${query}`),
  });
  const actors = useQuery({
    queryKey: ["traceability-actors", query],
    queryFn: () => ambilJson(`/api/traceability/actors?${query}`),
    enabled: tab === "actors",
  });
  const actorDetail = useQuery({
    queryKey: ["traceability-actor-detail", selectedActor, query],
    queryFn: () => ambilJson(`/api/traceability/actors/${encodeURIComponent(selectedActor!)}?${query}`),
    enabled: Boolean(selectedActor),
  });
  const districtOptions = useQuery({
    queryKey: ["traceability-district-options", editingOrigin?.source_key?.kabupaten_norm],
    queryFn: () => {
      const p = new URLSearchParams({ kabupaten_norm: editingOrigin.source_key.kabupaten_norm });
      return ambilJson(`/api/traceability/locations/districts?${p}`);
    },
    enabled: Boolean(editingOrigin),
  });
  const subdistrictOptions = useQuery({
    queryKey: ["traceability-subdistrict-options", editingOrigin?.source_key, targetDistrict],
    queryFn: () => {
      const p = new URLSearchParams({
        kabupaten_norm: editingOrigin.source_key.kabupaten_norm,
        kecamatan_norm: targetDistrict || editingOrigin.source_key.kecamatan_norm,
      });
      return ambilJson(`/api/traceability/locations/subdistricts?${p}`);
    },
    enabled: Boolean(editingOrigin && targetDistrict),
  });
  const historicalRecommendations = useQuery({
    queryKey: ["traceability-origin-recommendations", selectedActor, editingOrigin?.source_key, query],
    queryFn: () => {
      const p = new URLSearchParams(query);
      p.set("source_kabupaten_norm", editingOrigin.source_key.kabupaten_norm);
      p.set("source_kecamatan_norm", editingOrigin.source_key.kecamatan_norm);
      return ambilJson(`/api/traceability/actors/${encodeURIComponent(selectedActor!)}/origin-recommendations?${p}`);
    },
    enabled: Boolean(editingOrigin && selectedActor),
  });
  const simpanKoreksi = useMutation({
    mutationFn: ({ origin, target }: { origin: any; target: string | null }) =>
      ambilJson(`/api/traceability/actors/${encodeURIComponent(selectedActor!)}/origin-correction?${query}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_kabupaten_norm: origin.source_key.kabupaten_norm,
          source_kecamatan_norm: origin.source_key.kecamatan_norm,
          source_desa_norm: origin.source_key.desa_norm,
          target_kecamatan_norm: targetDistrict || origin.source_key.kecamatan_norm,
          target_desa_norm: target,
        }),
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["traceability"] }),
        queryClient.invalidateQueries({ queryKey: ["traceability-actors"] }),
        queryClient.invalidateQueries({ queryKey: ["traceability-actor-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["traceability-origin-recommendations"] }),
      ]);
      setEditingOrigin(null);
    },
  });
  const imporMapping = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return ambilJson("/api/traceability/unmapped/import", { method: "POST", body: form });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["traceability"] }),
        queryClient.invalidateQueries({ queryKey: ["traceability-actors"] }),
        queryClient.invalidateQueries({ queryKey: ["traceability-actor-detail"] }),
      ]);
    },
  });
  const hapusPemetaan = (origin: any) => {
    if (window.confirm("Hapus pemetaan District/Sub-district ini? Data intake tetap tersimpan dan status kembali mengikuti pencocokan asli.")) {
      simpanKoreksi.mutate({ origin, target: null });
    }
  };
  useEffect(() => {
    if (!filters.year && q.data?.year) setFilters((f) => ({ ...f, year: String(q.data.year) }));
  }, [filters.year, q.data?.year]);

  const exportQuery = useMemo(() => `${query}${query ? "&" : ""}format=xlsx`, [query]);
  const unmappedQuery = query;
  const toggle = (key: string) => setOpen((previous) => {
    const next = new Set(previous);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  const renderNodes = (nodes: Wilayah[], depth = 0, prefix = ""): ReactNode[] => nodes.flatMap((node) => {
    const key = `${prefix}/${node.name}`;
    const hasChildren = node.children?.length > 0;
    const expanded = open.has(key);
    const row = (
      <tr key={key} className="border-b border-[#EDEFF2] hover:bg-[#FAFAFA]">
        <td className="py-2 pr-2">
          <div className="flex items-center gap-1.5" style={{ paddingLeft: `${depth * 18}px` }}>
            {hasChildren ? (
              <button aria-label={expanded ? "Tutup wilayah" : "Buka wilayah"}
                      className="w-5 h-5 text-[#64676C]" onClick={() => toggle(key)}>
                {expanded ? "▾" : "▸"}
              </button>
            ) : <span className="w-5" />}
            <span className={depth === 0 ? "font-semibold text-[#1D2434]" : "text-[#374151]"}>{node.name}</span>
            <span className="ml-1 text-[9px] uppercase tracking-wide text-[#9AA0A6]">{node.level}</span>
          </div>
        </td>
        <td className="px-2 font-mono text-[#9AA0A6]">{node.code || "—"}</td>
        <td className="px-2 text-right font-mono">{fmtAngka(node.dry_mt, 3)}</td>
        <td className="px-2 text-right font-mono">{fmtAngka(node.traceable_mt, 3)}</td>
        <td className="px-2 text-right font-mono">{node.traceability_pct == null ? "—" : `${fmtAngka(node.traceability_pct, 2)}%`}</td>
        <td className="px-2 text-right font-mono">{fmtAngka(node.ticket_lines, 0)}</td>
        <td className="px-2"><span className={`rounded-sm px-1.5 py-0.5 text-[10px] ${node.traceability_status === "traceable" ? "bg-[#ECFDF3] text-[#027A48]" : node.traceability_status === "partial" ? "bg-[#FFFAEB] text-[#B54708]" : "bg-[#FEF3F2] text-[#B42318]"}`}>{node.traceability_status === "traceable" ? "Traceable" : node.traceability_status === "partial" ? "Partial" : "Unmatched"}</span></td>
      </tr>
    );
    return hasChildren && expanded ? [row, ...renderNodes(node.children, depth + 1, key)] : [row];
  });

  const d = q.data;
  const k = d?.kpis ?? {};
  const wilayah = d?.wilayah ?? [];
  const regencyGaps = daftarBelumTraceable(wilayah, "Kabupaten/Kota");
  const districtGaps = daftarBelumTraceable(wilayah, "Kecamatan");
  const subdistrictGaps = daftarBelumTraceable(wilayah, "Desa/Kelurahan");
  const gapRows = gapLevel ? daftarBelumTraceable(wilayah, gapLevel) : [];
  const totalGapMt = gapRows.reduce((sum, row) => sum + row.untraceable_mt, 0);
  const gapNote = (traceableMt: number | null | undefined, gaps: BarisGap[]) => {
    const remaining = Math.max(0, (k.dry_mt ?? 0) - (traceableMt ?? 0));
    return `${fmtAngka(traceableMt ?? 0, 3)} MT traceable${gaps.length ? ` · ${fmtAngka(remaining, 3)} MT belum` : ""}`;
  };
  const actorRows = actors.data?.baris ?? [];
  const maxActorDry = actorRows.reduce((max: number, row: any) => Math.max(max, Number(row.period_turnover_mt) || 0), 0);
  const downloadUrl = (path: string, queryString: string) => urlApi(`${path}${queryString ? `?${queryString}` : ""}`);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-[#1D2434]">Traceability</h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[#64676C]">
            Volume Dry dari tiket tervalidasi dan dideduplikasi hanya bila seluruh baris sumber identik. Nama wilayah dicocokkan ke SCDF; Code sengaja kosong karena file referensi tidak menyediakan kode administrasi.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a className={kelasTombol} href={downloadUrl("/api/traceability", exportQuery)}>⬇ Ekspor Excel</a>
          <a className="inline-flex items-center rounded-sm border border-[#D1D5DB] bg-white px-3 py-2 text-xs font-semibold text-[#374151] hover:bg-[#F8F8F8]"
             href={downloadUrl("/api/traceability/unmapped", unmappedQuery)}>⬇ Unduh belum termapping</a>
          <label className={`inline-flex cursor-pointer items-center rounded-sm border border-[#D1D5DB] bg-white px-3 py-2 text-xs font-semibold text-[#374151] hover:bg-[#F8F8F8] ${imporMapping.isPending ? "pointer-events-none opacity-60" : ""}`}>
            <input className="sr-only" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              disabled={imporMapping.isPending}
              onChange={(e) => {
                const file = e.currentTarget.files?.[0];
                if (file) imporMapping.mutate(file);
                e.currentTarget.value = "";
              }} />
            {imporMapping.isPending ? "Mengunggah…" : "⬆ Unggah hasil mapping"}
          </label>
        </div>
      </div>
      <div aria-live="polite" className="text-xs">
        <p className="text-[#64676C]">Unduh file lewat tombol <b>Unduh belum termapping</b>, isi kolom <b>SCDF District</b> dan <b>SCDF Sub-district</b> bersama-sama, lalu unggah file .xlsx di sini. Jangan ubah kolom sumber; pasangan target divalidasi terhadap SCDF dalam Kabupaten/Kota sumber yang sama. Baris dengan alasan Asal Getah tidak valid atau tanpa lokasi sumber biarkan kosong dan perbaiki dari data intake. Pemetaan tersimpan dapat dihapus dari detail Supplier Actors.</p>
        {imporMapping.isSuccess && <p className="mt-1 rounded-sm border border-[#A6F4C5] bg-[#ECFDF3] px-3 py-2 text-[#027A48]">{imporMapping.data.pesan} {imporMapping.data.baris_mapping_diisi} baris Excel terisi; {imporMapping.data.lokasi_dipetakan} lokasi unik diproses, {imporMapping.data.baris_direvisi} koreksi direvisi ({imporMapping.data.koreksi_baru} baru, {imporMapping.data.koreksi_diperbarui} diperbarui, {imporMapping.data.koreksi_tidak_berubah} sudah sama).</p>}
        {imporMapping.error && <p className="mt-1 whitespace-pre-line rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-[#B42318]">{(imporMapping.error as Error).message}</p>}
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        <div>
          <label className={kelasLabel}>Tahun</label>
          <select className={kelasInput} value={filters.year} onChange={(e) => setFilters({ ...filters, year: e.target.value })}>
            {(d?.years ?? []).map((y: number) => <option key={y} value={y}>{y}</option>)}
            {!d?.years?.length && <option value="">—</option>}
          </select>
        </div>
        <div>
          <label className={kelasLabel}>Periode</label>
          <select className={kelasInput} value={filters.period} onChange={(e) => setFilters({ ...filters, period: e.target.value })}>
            {PERIODE.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </div>
        <div>
          <label className={kelasLabel}>Supplier</label>
          <select className={kelasInput} value={filters.supplier} onChange={(e) => setFilters({ ...filters, supplier: e.target.value })}>
            <option value="">Semua supplier</option>
            {(d?.suppliers ?? []).map((v: any) => <option key={v.kode} value={v.kode}>{v.nama} ({v.kode})</option>)}
          </select>
        </div>
        <div>
          <label className={kelasLabel}>EUDR</label>
          <select className={kelasInput} value={filters.eudr} onChange={(e) => setFilters({ ...filters, eudr: e.target.value })}>
            <option value="all">Semua item</option><option value="eudr">EUDR / TTSR</option><option value="non_eudr">Non-EUDR</option>
          </select>
        </div>
        <label className="flex items-center gap-2 self-end rounded-sm border border-[#E4E5E8] bg-white px-3 py-2.5 text-xs text-[#374151]">
          <input type="checkbox" checked={filters.includeLatex} onChange={(e) => setFilters({ ...filters, includeLatex: e.target.checked })} />
          Sertakan LATEX OP
        </label>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        <Kpi title="Dry volume" value={k.dry_mt} unit="MT" />
        <Kpi title="Traceable · Regency" value={k.trace_reg_pct} unit="%"
          note={gapNote(k.trace_reg_mt, regencyGaps)} onClick={regencyGaps.length ? () => setGapLevel("Kabupaten/Kota") : undefined}
          active={gapLevel === "Kabupaten/Kota"} />
        <Kpi title="Traceable · District" value={k.trace_kec_pct} unit="%"
          note={gapNote(k.trace_kec_mt, districtGaps)} onClick={districtGaps.length ? () => setGapLevel("Kecamatan") : undefined}
          active={gapLevel === "Kecamatan"} />
        <Kpi title="Traceable · Sub-district" value={k.trace_desa_pct} unit="%"
          note={gapNote(k.trace_desa_mt, subdistrictGaps)} onClick={subdistrictGaps.length ? () => setGapLevel("Desa/Kelurahan") : undefined}
          active={gapLevel === "Desa/Kelurahan"} />
        <Kpi title="Validated tickets" value={k.tickets} unit="tickets" note={`${fmtAngka(k.regencies ?? 0, 0)} regencies`} />
      </div>

      <div className="rounded-sm border border-[#E4E5E8] bg-white">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E4E5E8] px-4 py-3">
          <div className="flex gap-1">
            <button onClick={() => setTab("regions")} className={`rounded-sm px-3 py-1.5 text-xs font-semibold ${tab === "regions" ? "bg-[#1D2434] text-white" : "text-[#64676C] hover:bg-[#F8F8F8]"}`}>Regional Traceability</button>
            <button onClick={() => setTab("actors")} className={`rounded-sm px-3 py-1.5 text-xs font-semibold ${tab === "actors" ? "bg-[#1D2434] text-white" : "text-[#64676C] hover:bg-[#F8F8F8]"}`}>Supplier Actors</button>
          </div>
          {d?.settings && <div className="flex gap-3 text-[10px] text-[#64676C]"><span>Accounting: <b className="text-[#374151]">{d.settings.accounting}</b></span><span>Scope: <b className="text-[#374151]">{d.settings.scope}</b></span></div>}
        </div>

        {tab === "regions" ? (
          <div className="max-h-[580px] overflow-auto">
            <table className="w-full min-w-[850px] text-xs">
              <thead className="sticky top-0 z-10 bg-[#F8F8F8] text-left text-[10px] uppercase tracking-wide text-[#64676C]">
                <tr><th className="py-2 pl-4">Region / hierarchy</th><th className="px-2">Code</th><th className="px-2 text-right">Dry (MT)</th><th className="px-2 text-right">Traceable (MT)</th><th className="px-2 text-right">Traceability</th><th className="px-2 text-right">Ticket lines</th><th className="px-2">SCDF status</th></tr>
              </thead>
              <tbody>
                {(d?.wilayah ?? []).length ? renderNodes(d.wilayah) : <tr><td colSpan={7} className="px-4 py-8 text-center text-[#9AA0A6]">Tidak ada tiket tervalidasi untuk filter ini.</td></tr>}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="max-h-[580px] overflow-auto">
            {actors.error && <p className="m-4 rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">{(actors.error as Error).message}</p>}
            <table className="w-full min-w-[1180px] text-xs">
              <thead className="sticky top-0 z-10 bg-[#F8F8F8] text-left text-[10px] uppercase tracking-wide text-[#64676C]">
                <tr>
                  <th className="py-2 pl-4">ID</th><th className="px-2">Name</th><th className="px-2">Tier</th><th className="px-2">Collector</th>
                  <th className="px-2">Type</th><th className="px-2">Terminal</th><th className="px-2">Period turnover</th>
                  <th className="px-2">Sourcing types</th><th className="px-2">Country</th><th className="px-2">Regency</th>
                  <th className="px-2">District</th><th className="px-2">Source from</th><th className="px-2 pr-4">Sell to</th>
                </tr>
              </thead>
              <tbody>
                {actorRows.map((a: any) => {
                  const barWidth = maxActorDry > 0 ? Math.max(3, Number(a.period_turnover_mt) / maxActorDry * 100) : 0;
                  return <Fragment key={a.supplier_code}>
                  <tr className="border-b border-[#EDEFF2] hover:bg-[#FAFAFA]">
                    <td className="py-3 pl-4 font-mono text-[#64676C]">{a.supplier_code}</td>
                    <td className="px-2">
                      <button className="text-left font-semibold text-[#1D2434] underline decoration-dotted underline-offset-2 hover:text-[#B91C1C]" onClick={() => setSelectedActor(a.supplier_code)}>{a.supplier}</button>
                    </td>
                    <td className="px-2">{a.tier ? <span className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-1.5 py-0.5 font-mono text-[10px] text-[#1D2434]">{a.tier}</span> : "—"}</td>
                    <td className="px-2">{a.collector_code
                      ? <><span className="font-mono text-[#1D2434]">{a.collector_code}</span><span className="block text-[10px] text-[#64676C]">{a.collector_name || "—"}</span></>
                      : <span className="text-[#9AA0A6]">—</span>}</td>
                    <td className="px-2">{a.activity_type || "—"}</td>
                    <td className="px-2 text-[#9AA0A6]">{a.terminal_status || "—"}</td>
                    <td className="px-2"><div className="min-w-[115px]"><div className="flex justify-between gap-2 font-mono"><span>{fmtAngka(a.period_turnover_mt, 3)} MT</span><span className="text-[#9AA0A6]">{fmtAngka(a.tickets, 0)} tk</span></div><div className="mt-1 h-1.5 rounded bg-[#EDEFF2]"><div className="h-1.5 rounded bg-[#FF1313]" style={{ width: `${barWidth}%` }} /></div></div></td>
                    <td className="px-2">{a.sourcing_type || "Belum diklasifikasi"}{a.is_direct_producer && <span className="ml-1 text-[9px] text-[#9AA0A6]">*</span>}</td>
                    <td className="px-2">{a.country || "—"}</td><td className="px-2">{a.regency || "—"}</td><td className="px-2">{a.district || "—"}</td>
                    <td className="px-2">{a.source_from ? `${a.source_from} lokasi` : "—"}</td><td className="px-2 pr-4 text-[#9AA0A6]">Tidak tercatat</td>
                  </tr>
                  </Fragment>;
                })}
                {!actors.isLoading && !(actors.data?.baris?.length) && <tr><td colSpan={13} className="px-4 py-8 text-center text-[#9AA0A6]">Tidak ada aktor untuk filter ini.</td></tr>}
              </tbody>
            </table>
            <p className="px-4 py-2 text-[10px] leading-relaxed text-[#9AA0A6]">Tier T1 dipakai untuk vendor; T2 dipakai saat ada kolektor berafiliasi ke vendor itu yang desanya cocok dengan desa Asal Getah. Kolektor tidak dibuat baris terpisah: desa, kolektor, dan vendor dihitung sebagai satu supplier actor (satu rantai). Rantai ini inferensi dari data intake, bukan catatan transaksi jual-beli. Terminal dan tujuan penjualan tidak tercatat di intake/master. Klik nama supplier untuk melihat rincian Asal Getah. * Flag produsen langsung bersifat sementara.</p>
          </div>
        )}
      </div>
      {gapLevel && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-[#101828]/55 p-3 sm:p-6" onMouseDown={(e) => { if (e.target === e.currentTarget) setGapLevel(null); }}>
          <section role="dialog" aria-modal="true" aria-labelledby="traceability-gap-title" className="flex max-h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-sm border border-[#E4E5E8] bg-white shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-[#E4E5E8] px-5 py-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#B54708]">Traceability gap</p>
                <h3 id="traceability-gap-title" className="mt-1 text-lg font-bold text-[#1D2434]">Data belum traceable · {gapLevel}</h3>
                <p className="mt-1 text-xs text-[#64676C]">Menampilkan wilayah pada tingkat KPI ini yang masih memiliki volume Dry belum cocok dengan referensi SCDF.</p>
              </div>
              <button aria-label="Tutup rincian belum traceable" onClick={() => setGapLevel(null)} className="rounded-sm border border-[#E4E5E8] px-2.5 py-1 text-lg leading-none text-[#64676C] hover:bg-[#F8F8F8]">×</button>
            </div>
            <div className="overflow-auto p-5">
              {q.isLoading && <p className="py-8 text-center text-sm text-[#64676C]">Memuat wilayah…</p>}
              {!q.isLoading && (
                <>
                  <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[#475467]">
                    <span>Wilayah belum traceable: <b>{fmtAngka(gapRows.length, 0)}</b></span>
                    <span>Volume belum traceable: <b className="font-mono">{fmtAngka(totalGapMt, 3)} MT</b></span>
                    <span>Filter mengikuti tahun, periode, supplier, EUDR, dan LATEX OP di halaman.</span>
                  </div>
                  <div className="max-h-[55vh] overflow-auto rounded-sm border border-[#E4E5E8]">
                    <table className="w-full min-w-[850px] text-xs">
                      <thead className="sticky top-0 bg-[#F8F8F8] text-left text-[10px] uppercase tracking-wide text-[#64676C]">
                        <tr><th className="py-2 pl-3">Wilayah ({gapLevel})</th><th className="px-2">Parent wilayah</th><th className="px-2 text-right">Dry (MT)</th><th className="px-2 text-right">Traceable (MT)</th><th className="px-2 text-right">Belum traceable (MT)</th><th className="px-2 text-right">Traceability</th><th className="px-2 text-right pr-3">Ticket lines</th></tr>
                      </thead>
                      <tbody>
                        {gapRows.map((row, index) => (
                          <tr key={`${row.path}/${row.name}/${index}`} className="border-t border-[#EDEFF2]">
                            <td className="py-2 pl-3 font-semibold text-[#1D2434]">{row.name}</td>
                            <td className="px-2 text-[#64676C]">{row.path}</td>
                            <td className="px-2 text-right font-mono">{fmtAngka(row.dry_mt, 3)}</td>
                            <td className="px-2 text-right font-mono">{fmtAngka(row.traceable_mt, 3)}</td>
                            <td className="px-2 text-right font-mono font-semibold text-[#B54708]">{fmtAngka(row.untraceable_mt, 3)}</td>
                            <td className="px-2 text-right font-mono">{row.traceability_pct == null ? "—" : `${fmtAngka(row.traceability_pct, 2)}%`}</td>
                            <td className="px-2 pr-3 text-right font-mono">{fmtAngka(row.ticket_lines, 0)}</td>
                          </tr>
                        ))}
                        {!gapRows.length && <tr><td colSpan={7} className="py-8 text-center text-[#9AA0A6]">Tidak ada data belum traceable pada filter saat ini.</td></tr>}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-3 text-[10px] leading-relaxed text-[#64676C]">Wilayah ditampilkan sebagaimana tercatat/tercocokkan pada data Traceability. Rincian ini tidak menebak provinsi atau lokasi dari Asal Getah; perbaikan Sub-district dapat dilakukan pada tab Supplier Actors jika tersedia padanan SCDF.</p>
                </>
              )}
            </div>
          </section>
        </div>
      )}
      {selectedActor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/55 p-3 sm:p-6" onMouseDown={(e) => { if (e.target === e.currentTarget) setSelectedActor(null); }}>
          <section role="dialog" aria-modal="true" aria-labelledby="actor-detail-title" className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-sm border border-[#E4E5E8] bg-white shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-[#E4E5E8] px-5 py-4">
              <div><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#9AA0A6]">Supplier actor details</p><h3 id="actor-detail-title" className="mt-1 text-lg font-bold text-[#1D2434]">{actorDetail.data?.supplier || selectedActor}</h3><p className="mt-0.5 font-mono text-xs text-[#64676C]">{selectedActor}</p></div>
              <button aria-label="Tutup detail supplier" onClick={() => setSelectedActor(null)} className="rounded-sm border border-[#E4E5E8] px-2.5 py-1 text-lg leading-none text-[#64676C] hover:bg-[#F8F8F8]">×</button>
            </div>
            <div className="overflow-auto p-5">
              {actorDetail.isLoading && <p className="py-10 text-center text-sm text-[#64676C]">Memuat detail supplier…</p>}
              {actorDetail.error && <p className="rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">{(actorDetail.error as Error).message}</p>}
              {actorDetail.data && (() => {
                const detail = actorDetail.data;
                const origins = detail.origins ?? [];
                return <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                    <Kpi title="Filtered Dry turnover" value={detail.period_turnover_mt} unit="MT" />
                    <Kpi title="Intake tickets" value={detail.tickets} unit="tickets" />
                    <Kpi title="Supplier class" value={null} unit="" note={detail.classification || "Belum diklasifikasi di master"} />
                    <Kpi title="Top sourcing regency" value={null} unit="" note={detail.top_geography?.regency || "Tidak tersedia"} />
                  </div>
                  <div>
                    <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-[#374151]">Supplier details</h4>
                    <div className="grid grid-cols-2 gap-x-5 gap-y-3 rounded-sm border border-[#E4E5E8] p-4 text-xs sm:grid-cols-4">
                      <div><p className="text-[#9AA0A6]">Alt ID</p><p className="mt-1 font-medium text-[#1D2434]">{detail.alt_id || "Not recorded"}</p></div>
                      <div><p className="text-[#9AA0A6]">Product / category</p><p className="mt-1 font-medium text-[#1D2434]">{detail.product || "Not recorded"}</p></div>
                      <div><p className="text-[#9AA0A6]">Tier</p><p className="mt-1 font-mono text-[#1D2434]">{detail.tier || "Not recorded"}</p></div>
                      <div><p className="text-[#9AA0A6]">Terminal status</p><p className="mt-1 text-[#64676C]">Not recorded in intake/master</p></div>
                      <div><p className="text-[#9AA0A6]">Coordinates</p><p className="mt-1 text-[#64676C]">{detail.coordinates_note}</p></div>
                      <div><p className="text-[#9AA0A6]">Direct producer flag</p><p className="mt-1 text-[#1D2434]">{detail.is_direct_producer ? "Yes — provisional" : "No (default)"}</p></div>
                      <div><p className="text-[#9AA0A6]">Collector affiliation</p><p className="mt-1 text-[#1D2434]">{detail.is_collector ? "Yes" : "No"}</p></div>
                      <div><p className="text-[#9AA0A6]">Collector (T2)</p><p className="mt-1 font-mono text-[11px] text-[#1D2434]">{detail.collector_code || "Not registered"}</p>{detail.collector_name && <p className="mt-0.5 text-[10px] text-[#64676C]">{detail.collector_name}</p>}</div>
                      <div><p className="text-[#9AA0A6]">Sourcing type source</p><p className="mt-1 text-[#1D2434]">{detail.sourcing_type_source}</p></div>
                      <div><p className="text-[#9AA0A6]">Sell to</p><p className="mt-1 text-[#64676C]">Not recorded in intake</p></div>
                    </div>
                  </div>
                  <div>
                    <div className="mb-2 flex flex-wrap items-end justify-between gap-2"><div><h4 className="text-xs font-bold uppercase tracking-wide text-[#374151]">Sourcing locations from Asal Getah</h4><p className="mt-1 text-[10px] text-[#9AA0A6]">Dry volume and share are calculated from filtered intake rows. Klik Edit untuk memilih District dan Sub-district SCDF; koreksi tidak menimpa intake asli dan berlaku untuk semua tiket dengan kombinasi lokasi sumber yang sama.</p></div><span className="text-[10px] text-[#64676C]">{origins.length} location groups</span></div>
                    <div className="max-h-[320px] overflow-auto rounded-sm border border-[#E4E5E8]">
                      <table className="w-full min-w-[750px] text-xs">
                        <thead className="sticky top-0 bg-[#F8F8F8] text-left text-[10px] uppercase tracking-wide text-[#64676C]"><tr><th className="py-2 pl-3">Country</th><th className="px-2">Regency / city</th><th className="px-2">District</th><th className="px-2">Sub-district</th><th className="px-2 text-right">Dry (MT)</th><th className="px-2 text-right">Share</th><th className="px-2 text-right">Traceable dry (MT)</th><th className="px-2 pr-3">SCDF match</th></tr></thead>
                        <tbody>{origins.map((origin: any, index: number) => {
                          const originKey = JSON.stringify(origin.source_key);
                          const isEditing = editingOrigin && JSON.stringify(editingOrigin.source_key) === originKey;
                          return <tr key={`${originKey}-${index}`} className="border-t border-[#EDEFF2]">
                            <td className="py-2 pl-3">{origin.country || "Indonesia"}</td>
                            <td className="px-2">{origin.regency || "Unknown"}</td>
                            <td className="px-2"><span>{origin.district || "Unknown"}</span>{origin.manual_correction && <p className="text-[9px] text-[#9AA0A6]">Input: {origin.source_district || "Not recorded"}</p>}</td>
                            <td className="px-2">
                              {isEditing ? <div className="min-w-[250px] space-y-1">
                                <select className="w-full rounded-sm border border-[#D1D5DB] bg-white px-2 py-1 text-xs" value={targetDistrict} onChange={(e) => { setTargetDistrict(e.target.value); setTargetSubdistrict(""); }} disabled={districtOptions.isLoading}>
                                  <option value="">{districtOptions.isLoading ? "Memuat District SCDF…" : "Pilih District SCDF"}</option>
                                  {(districtOptions.data?.options ?? []).map((option: any) => <option key={option.value} value={option.value}>{option.label}</option>)}
                                </select>
                                {districtOptions.error && <p className="text-[10px] text-[#B42318]">Gagal memuat District SCDF: {(districtOptions.error as Error).message}</p>}
                                <select className="w-full rounded-sm border border-[#D1D5DB] bg-white px-2 py-1 text-xs" value={targetSubdistrict} onChange={(e) => setTargetSubdistrict(e.target.value)} disabled={!targetDistrict || subdistrictOptions.isLoading}>
                                  <option value="">{!targetDistrict ? "Pilih District terlebih dahulu" : subdistrictOptions.isLoading ? "Memuat Sub-district SCDF…" : "Pilih Sub-district SCDF"}</option>
                                  {(subdistrictOptions.data?.options ?? []).map((option: any) => <option key={option.value} value={option.value}>{option.label}</option>)}
                                </select>
                                <div className="rounded-sm border border-[#D1D5DB] bg-[#F8FAFC] p-2">
                                  <p className="text-[10px] font-semibold text-[#344054]">Rekomendasi dari intake tahun sebelumnya{historicalRecommendations.data?.history_through ? ` (s.d. ${historicalRecommendations.data.history_through})` : ""}</p>
                                  {historicalRecommendations.isLoading && <p className="mt-1 text-[10px] text-[#667085]">Menghitung pola historis…</p>}
                                  {(historicalRecommendations.data?.recommendations ?? []).slice(0, 3).map((recommendation: any) => <div key={recommendation.sub_district_norm} className="mt-1 flex items-center justify-between gap-2 text-[10px]"><span><b>{recommendation.sub_district}</b> · Keyakinan historis {fmtAngka(recommendation.confidence_pct, 1)}% · {recommendation.historical_tickets} tiket / {recommendation.historical_years} tahun</span><button className="shrink-0 rounded-sm border border-[#D1D5DB] bg-white px-1.5 py-0.5 font-semibold text-[#344054] hover:bg-[#F2F4F7]" onClick={() => setTargetSubdistrict(recommendation.sub_district_norm)}>Pakai</button></div>)}
                                  {historicalRecommendations.error && <p className="mt-1 text-[10px] text-[#B42318]">Gagal memuat rekomendasi historis: {(historicalRecommendations.error as Error).message}</p>}
                                  {!historicalRecommendations.isLoading && !historicalRecommendations.error && !(historicalRecommendations.data?.recommendations?.length) && <p className="mt-1 text-[10px] text-[#667085]">Belum ada lokasi cocok dari intake tahun sebelumnya untuk supplier, Regency, dan District ini.</p>}
                                  <p className="mt-1 text-[9px] leading-relaxed text-[#667085]">Persentase adalah porsi volume Dry historis pada supplier dan Regency/District yang sama, bukan probabilitas bahwa lokasi sekarang pasti benar. Mohon verifikasi sebelum menyimpan.</p>
                                </div>
                                {!subdistrictOptions.isLoading && !(subdistrictOptions.data?.options?.length) && <p className="text-[10px] text-[#B54708]">Tidak ada pilihan SCDF untuk Regency/District ini. Periksa parent location pada intake.</p>}
                                <div className="flex flex-wrap gap-1">
                                  <button className="rounded-sm bg-[#1D2434] px-2 py-1 text-[10px] font-semibold text-white disabled:opacity-50" disabled={!targetDistrict || !targetSubdistrict || simpanKoreksi.isPending} onClick={() => simpanKoreksi.mutate({ origin, target: targetSubdistrict })}>{simpanKoreksi.isPending ? "Menyimpan…" : "Simpan"}</button>
                                  {origin.manual_correction && <button className="rounded-sm border border-[#D1D5DB] px-2 py-1 text-[10px] text-[#B54708] disabled:opacity-50" disabled={simpanKoreksi.isPending} onClick={() => hapusPemetaan(origin)}>Hapus pemetaan</button>}
                                  <button className="rounded-sm px-2 py-1 text-[10px] text-[#64676C] hover:bg-[#F8F8F8]" onClick={() => setEditingOrigin(null)}>Batal</button>
                                </div>
                                <p className="text-[9px] text-[#9AA0A6]">Koreksi berlaku untuk semua tiket dengan kombinasi lokasi sumber ini.</p>
                              </div> : <div className="flex items-start justify-between gap-2">
                                <div><span>{origin.sub_district || "Unknown"}</span>{origin.manual_correction && <p className="text-[9px] text-[#9AA0A6]">Input: {origin.source_sub_district}</p>}</div>
                                <div className="flex shrink-0 flex-col items-end gap-1">
                                  <button className="text-[10px] font-semibold text-[#475467] underline decoration-dotted underline-offset-2 hover:text-[#B91C1C]" onClick={() => { setEditingOrigin(origin); setTargetDistrict(origin.target_district_norm || origin.source_key.kecamatan_norm || ""); setTargetSubdistrict(origin.target_subdistrict_norm || origin.source_key.desa_norm || ""); }}>Edit</button>
                                  {origin.manual_correction && <button className="text-[10px] font-semibold text-[#B42318] underline decoration-dotted underline-offset-2" disabled={simpanKoreksi.isPending} onClick={() => hapusPemetaan(origin)}>Hapus pemetaan</button>}
                                </div>
                              </div>}
                            </td>
                            <td className="px-2 text-right font-mono">{fmtAngka(origin.dry_mt, 3)}</td>
                            <td className="px-2 text-right font-mono">{fmtAngka(origin.share_pct, 2)}%</td>
                            <td className="px-2 text-right font-mono">{fmtAngka(origin.traceable_mt, 3)}</td>
                            <td className="px-2 pr-3"><span className={`rounded-sm px-1.5 py-0.5 text-[10px] ${origin.matched_to_id_aux ? "bg-[#ECFDF3] text-[#027A48]" : "bg-[#FFFAEB] text-[#B54708]"}`}>{origin.manual_correction ? "Manual match" : origin.matched_to_id_aux ? "Matched" : "Unmatched"}</span></td>
                          </tr>;
                        })}
                          {!origins.length && <tr><td colSpan={8} className="py-8 text-center text-[#9AA0A6]">Tidak ada rincian lokasi untuk filter ini.</td></tr>}
                        </tbody>
                      </table>
                    </div>
                    {simpanKoreksi.error && <p className="mt-2 rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">{(simpanKoreksi.error as Error).message}</p>}
                    <div className="mt-2 grid gap-2 text-[10px] leading-relaxed text-[#64676C] md:grid-cols-2"><p className="rounded-sm bg-[#F8F8F8] p-2">{detail.supply_chain_note}</p><p className="rounded-sm bg-[#F8F8F8] p-2">Top geography is the largest recorded origin. Province and administrative codes are not supplied by SCDF and are intentionally omitted; unmatched names are shown as received after normalization.</p></div>
                  </div>
                </div>;
              })()}
            </div>
          </section>
        </div>
      )}
      {q.error && <p className="rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">{(q.error as Error).message}</p>}
      <p className="text-[10px] leading-relaxed text-[#9AA0A6]">* Direct producer adalah flag sementara per supplier dan default-nya Tidak. Code geografi tidak ada di SCDF; kolom Code sengaja dikosongkan, terpisah dari pencocokan nama wilayah.</p>
    </section>
  );
}
