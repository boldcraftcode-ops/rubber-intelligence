import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ambilJson, fmtAngka, kelasInput, kelasLabel, kelasTombol, urlApi } from "../bersama";

type Filter = { year: string; period: string; supplier: string; eudr: string; includeLatex: boolean };
type Wilayah = {
  name: string; level: string; code: string; dry_mt: number; traceable_mt: number;
  traceability_pct: number | null; ticket_lines: number; status_code: string; children: Wilayah[];
};

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

function Kpi({ title, value, unit, note }: { title: string; value: number | null; unit: string; note?: string }) {
  return (
    <div className="min-w-0 rounded-sm border border-[#E4E5E8] border-l-2 border-l-[#FF1313] bg-white px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#64676C]">{title}</p>
      <p className="mt-1 text-xl font-bold tabular-nums text-[#1D2434]">
        {value == null ? "—" : fmtAngka(value, unit === "%" ? 2 : unit === "MT" ? 3 : 0)}
        <span className="ml-1 text-xs font-medium text-[#64676C]">{unit}</span>
      </p>
      {note && <p className="mt-1 text-[10px] text-[#9AA0A6]">{note}</p>}
    </div>
  );
}

export default function Traceability() {
  const [filters, setFilters] = useState<Filter>({ year: "", period: "ALL", supplier: "", eudr: "all", includeLatex: false });
  const [tab, setTab] = useState<"regions" | "actors">("regions");
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const [selectedActor, setSelectedActor] = useState<string | null>(null);
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
        <td className="px-2"><span className="rounded-sm border border-[#FDE68A] bg-[#FFFBEB] px-1.5 py-0.5 text-[10px] text-[#92400E]">belum termapping</span></td>
      </tr>
    );
    return hasChildren && expanded ? [row, ...renderNodes(node.children, depth + 1, key)] : [row];
  });

  const d = q.data;
  const k = d?.kpis ?? {};
  const actorRows = actors.data?.baris ?? [];
  const maxActorDry = actorRows.reduce((max: number, row: any) => Math.max(max, Number(row.period_turnover_mt) || 0), 0);
  const downloadUrl = (path: string, queryString: string) => urlApi(`${path}${queryString ? `?${queryString}` : ""}`);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-[#1D2434]">Traceability</h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[#64676C]">
            Volume Dry dari tiket tervalidasi dan dideduplikasi hanya bila seluruh baris sumber identik. Nama wilayah dicocokkan ke ID_AUX; Code sengaja kosong karena file referensi tidak menyediakan kode administrasi.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a className={kelasTombol} href={downloadUrl("/api/traceability", exportQuery)}>⬇ Ekspor Excel</a>
          <a className="inline-flex items-center rounded-sm border border-[#D1D5DB] bg-white px-3 py-2 text-xs font-semibold text-[#374151] hover:bg-[#F8F8F8]"
             href={downloadUrl("/api/traceability/unmapped", unmappedQuery)}>⬇ Unduh belum termapping</a>
        </div>
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
        <Kpi title="Traceable · Regency" value={k.trace_reg_pct} unit="%" note={`${fmtAngka(k.trace_reg_mt ?? 0, 3)} MT`} />
        <Kpi title="Traceable · District" value={k.trace_kec_pct} unit="%" note={`${fmtAngka(k.trace_kec_mt ?? 0, 3)} MT`} />
        <Kpi title="Traceable · Sub-district" value={k.trace_desa_pct} unit="%" note={`${fmtAngka(k.trace_desa_mt ?? 0, 3)} MT`} />
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
                <tr><th className="py-2 pl-4">Region / hierarchy</th><th className="px-2">Code</th><th className="px-2 text-right">Dry (MT)</th><th className="px-2 text-right">Traceable (MT)</th><th className="px-2 text-right">Traceability</th><th className="px-2 text-right">Ticket lines</th><th className="px-2">Code mapping</th></tr>
              </thead>
              <tbody>
                {(d?.wilayah ?? []).length ? renderNodes(d.wilayah) : <tr><td colSpan={7} className="px-4 py-8 text-center text-[#9AA0A6]">Tidak ada tiket tervalidasi untuk filter ini.</td></tr>}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="max-h-[580px] overflow-auto">
            {actors.error && <p className="m-4 rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">{(actors.error as Error).message}</p>}
            <table className="w-full min-w-[1050px] text-xs">
              <thead className="sticky top-0 z-10 bg-[#F8F8F8] text-left text-[10px] uppercase tracking-wide text-[#64676C]">
                <tr>
                  <th className="py-2 pl-4">ID</th><th className="px-2">Name</th><th className="px-2">Tier</th>
                  <th className="px-2">Type</th><th className="px-2">Terminal</th><th className="px-2">Period turnover</th>
                  <th className="px-2">Sourcing types</th><th className="px-2">Country</th><th className="px-2">Regency</th>
                  <th className="px-2">District</th><th className="px-2">Source from</th><th className="px-2 pr-4">Sell to</th>
                </tr>
              </thead>
              <tbody>
                {actorRows.map((a: any) => {
                  const barWidth = maxActorDry > 0 ? Math.max(3, Number(a.period_turnover_mt) / maxActorDry * 100) : 0;
                  return <tr key={a.supplier_code} className="border-b border-[#EDEFF2] hover:bg-[#FAFAFA]">
                    <td className="py-3 pl-4 font-mono text-[#64676C]">{a.supplier_code}</td>
                    <td className="px-2"><button className="text-left font-semibold text-[#1D2434] underline decoration-dotted underline-offset-2 hover:text-[#B91C1C]" onClick={() => setSelectedActor(a.supplier_code)}>{a.supplier}</button></td>
                    <td className="px-2 text-[#9AA0A6]">{a.tier || "—"}</td>
                    <td className="px-2">{a.activity_type || "—"}</td>
                    <td className="px-2 text-[#9AA0A6]">{a.terminal_status || "—"}</td>
                    <td className="px-2"><div className="min-w-[115px]"><div className="flex justify-between gap-2 font-mono"><span>{fmtAngka(a.period_turnover_mt, 3)} MT</span><span className="text-[#9AA0A6]">{fmtAngka(a.tickets, 0)} tk</span></div><div className="mt-1 h-1.5 rounded bg-[#EDEFF2]"><div className="h-1.5 rounded bg-[#FF1313]" style={{ width: `${barWidth}%` }} /></div></div></td>
                    <td className="px-2">{a.sourcing_type || "Belum diklasifikasi"}{a.is_direct_producer && <span className="ml-1 text-[9px] text-[#9AA0A6]">*</span>}</td>
                    <td className="px-2">{a.country || "—"}</td><td className="px-2">{a.regency || "—"}</td><td className="px-2">{a.district || "—"}</td>
                    <td className="px-2">{a.source_from ? `${a.source_from} lokasi` : "—"}</td><td className="px-2 pr-4 text-[#9AA0A6]">Tidak tercatat</td>
                  </tr>;
                })}
                {!actors.isLoading && !(actors.data?.baris?.length) && <tr><td colSpan={12} className="px-4 py-8 text-center text-[#9AA0A6]">Tidak ada aktor untuk filter ini.</td></tr>}
              </tbody>
            </table>
            <p className="px-4 py-2 text-[10px] text-[#9AA0A6]">Tier, terminal, dan tujuan penjualan tidak tercatat di intake/master. Klik nama supplier untuk melihat rincian Asal Getah. * Flag produsen langsung bersifat sementara.</p>
          </div>
        )}
      </div>
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
                      <div><p className="text-[#9AA0A6]">Tier</p><p className="mt-1 text-[#64676C]">Not recorded in intake/master</p></div>
                      <div><p className="text-[#9AA0A6]">Terminal status</p><p className="mt-1 text-[#64676C]">Not recorded in intake/master</p></div>
                      <div><p className="text-[#9AA0A6]">Coordinates</p><p className="mt-1 text-[#64676C]">{detail.coordinates_note}</p></div>
                      <div><p className="text-[#9AA0A6]">Direct producer flag</p><p className="mt-1 text-[#1D2434]">{detail.is_direct_producer ? "Yes — provisional" : "No (default)"}</p></div>
                      <div><p className="text-[#9AA0A6]">Sourcing type source</p><p className="mt-1 text-[#1D2434]">{detail.sourcing_type_source}</p></div>
                      <div><p className="text-[#9AA0A6]">Sell to</p><p className="mt-1 text-[#64676C]">Not recorded in intake</p></div>
                    </div>
                  </div>
                  <div>
                    <div className="mb-2 flex flex-wrap items-end justify-between gap-2"><div><h4 className="text-xs font-bold uppercase tracking-wide text-[#374151]">Sourcing locations from Asal Getah</h4><p className="mt-1 text-[10px] text-[#9AA0A6]">Dry volume and share are calculated from filtered intake rows; geographic names are matched to official ID_AUX where available.</p></div><span className="text-[10px] text-[#64676C]">{origins.length} location groups</span></div>
                    <div className="max-h-[320px] overflow-auto rounded-sm border border-[#E4E5E8]">
                      <table className="w-full min-w-[750px] text-xs">
                        <thead className="sticky top-0 bg-[#F8F8F8] text-left text-[10px] uppercase tracking-wide text-[#64676C]"><tr><th className="py-2 pl-3">Country</th><th className="px-2">Regency / city</th><th className="px-2">District</th><th className="px-2">Sub-district</th><th className="px-2 text-right">Dry (MT)</th><th className="px-2 text-right">Share</th><th className="px-2 text-right">Traceable dry (MT)</th><th className="px-2 pr-3">ID_AUX match</th></tr></thead>
                        <tbody>{origins.map((origin: any, index: number) => <tr key={`${origin.regency}-${origin.district}-${origin.sub_district}-${index}`} className="border-t border-[#EDEFF2]"><td className="py-2 pl-3">{origin.country || "Indonesia"}</td><td className="px-2">{origin.regency || "Unknown"}</td><td className="px-2">{origin.district || "Unknown"}</td><td className="px-2">{origin.sub_district || "Unknown"}</td><td className="px-2 text-right font-mono">{fmtAngka(origin.dry_mt, 3)}</td><td className="px-2 text-right font-mono">{fmtAngka(origin.share_pct, 2)}%</td><td className="px-2 text-right font-mono">{fmtAngka(origin.traceable_mt, 3)}</td><td className="px-2 pr-3"><span className={`rounded-sm px-1.5 py-0.5 text-[10px] ${origin.matched_to_id_aux ? "bg-[#ECFDF3] text-[#027A48]" : "bg-[#FFFAEB] text-[#B54708]"}`}>{origin.matched_to_id_aux ? "Matched" : "Unmatched"}</span></td></tr>)}
                          {!origins.length && <tr><td colSpan={8} className="py-8 text-center text-[#9AA0A6]">Tidak ada rincian lokasi untuk filter ini.</td></tr>}
                        </tbody>
                      </table>
                    </div>
                    <div className="mt-2 grid gap-2 text-[10px] leading-relaxed text-[#64676C] md:grid-cols-2"><p className="rounded-sm bg-[#F8F8F8] p-2">{detail.supply_chain_note}</p><p className="rounded-sm bg-[#F8F8F8] p-2">Top geography is the largest recorded origin. Province and administrative codes are not supplied by ID_AUX and are intentionally omitted; unmatched names are shown as received after normalization.</p></div>
                  </div>
                </div>;
              })()}
            </div>
          </section>
        </div>
      )}
      {q.error && <p className="rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">{(q.error as Error).message}</p>}
      <p className="text-[10px] leading-relaxed text-[#9AA0A6]">* Direct producer adalah flag sementara per supplier dan default-nya Tidak. Code geografi tidak ada di ID_AUX; kolom Code sengaja dikosongkan, terpisah dari pencocokan nama wilayah.</p>
    </section>
  );
}
