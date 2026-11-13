import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ambilJson, fmtAngka, kelasInput, kelasTombolAnalisa, kelasTombolKecil,
  pesanGalat, urlApi,
} from "../bersama";
import { useBahasa } from "../i18n";

type Laporan = any;
type Periode = any;

function fmtPersen(n: number | null | undefined): string {
  return n === null || n === undefined ? "–" : `${fmtAngka(n * 100, 1)}%`;
}

function tampilSel(nilai: any): string {
  if (nilai === null || nilai === undefined || nilai === "") return "—";
  if (typeof nilai === "number") {
    return Number.isInteger(nilai) ? fmtAngka(nilai, 0) : fmtAngka(nilai, 3);
  }
  return String(nilai);
}

function KotakKpi({ label, nilai, warna = "text-[#1D2434]" }: {
  label: string;
  nilai: string;
  warna?: string;
}) {
  const { t } = useBahasa();
  return (
    <div className="rounded-sm border border-[#E4E5E8] bg-white px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#64676C]">
        {t(label)}
      </p>
      <p className={`mt-1 font-mono text-xl font-semibold ${warna}`}>{nilai}</p>
    </div>
  );
}

function TabelUmum({ kolom, baris, kosong }: {
  kolom: string[];
  baris: any[][];
  kosong: string;
}) {
  const { t } = useBahasa();
  if (!baris.length) {
    return <p className="py-4 text-sm text-[#64676C]">{t(kosong)}</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1100px] border-collapse text-xs">
        <thead>
          <tr className="bg-[#F8F8F8] text-left text-[#64676C]">
            {kolom.map((k, i) => (
              <th key={i} className="border border-[#E4E5E8] px-2 py-1.5 font-semibold align-top">
                {t(k)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {baris.map((b, i) => (
            <tr key={i} className="odd:bg-white even:bg-[#FCFCFC]">
              {b.map((v, j) => (
                <td key={j} className="border border-[#E4E5E8] px-2 py-1 align-top">
                  {tampilSel(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function KepatuhanVendorSampling() {
  const { t } = useBahasa();
  const [bulan, setBulan] = useState<string>("");
  const [cari, setCari] = useState<string>("");

  const laporan = useQuery<Laporan>({
    queryKey: ["kepatuhan-vendor-sampling", bulan],
    queryFn: () => ambilJson(
      `/api/kepatuhan-vendor-sampling${bulan ? `?bulan=${bulan}` : ""}`),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!bulan && laporan.data?.kunci) setBulan(laporan.data.kunci);
  }, [bulan, laporan.data?.kunci]);

  const data: Laporan | undefined = laporan.data;
  const p: Periode | undefined = data?.periode;
  const daftar: any[] = data?.daftar_periode ?? [];
  const ring = p?.ringkasan ?? {};

  const logTampil = useMemo(() => {
    const semua: any[][] = p?.log ?? [];
    const q = cari.trim().toLocaleLowerCase("id-ID");
    if (!q) return semua;
    return semua.filter((baris) => baris.some(
      (v) => String(v ?? "").toLocaleLowerCase("id-ID").includes(q)));
  }, [p?.log, cari]);

  const summaryTampil = useMemo(() => {
    const semua: any[] = p?.summary ?? [];
    const q = cari.trim().toLocaleLowerCase("id-ID");
    if (!q) return semua;
    return semua.filter((b) => [b.vendor, b.keterangan, b.kata_kunci]
      .some((v) => String(v ?? "").toLocaleLowerCase("id-ID").includes(q)));
  }, [p?.summary, cari]);

  const barisSummary = summaryTampil.map((b) => [
    b.no, b.vendor, b.tepat, b.terlambat, b.tanpa_data, b.total,
    typeof b.persen === "number" ? fmtPersen(b.persen) : b.persen,
    b.keterangan, b.kata_kunci,
  ]);
  if (!cari.trim() && p?.total) {
    const x = p.total;
    barisSummary.push([
      x.no, x.vendor, x.tepat, x.terlambat, x.tanpa_data, x.total,
      typeof x.persen === "number" ? fmtPersen(x.persen) : x.persen,
      x.keterangan, x.kata_kunci,
    ]);
  }

  if (laporan.isLoading) {
    return <p className="text-sm text-[#64676C]">⏳ {t("Memuat…")}</p>;
  }
  if (laporan.error) {
    return (
      <div className="rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-4 py-3">
        <p className="text-sm font-semibold text-[#B91C1C]">{t("Gagal memuat data")}</p>
        <p className="mt-1 text-xs text-[#64676C]">{pesanGalat(laporan.error)}</p>
        <button className={`${kelasTombolKecil} mt-3`}
                onClick={() => laporan.refetch()}>↻ {t("Coba lagi")}</button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Sumber & kontrol */}
      <section className="kartu-aksen rounded-sm border border-[#E4E5E8] bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-[#1D2434]">
              {t("Sumber laporan")}
            </h2>
            <p className="mt-1 text-sm text-[#64676C]">
              <b>{data?.sumber?.nama_file}</b> · {data?.sumber?.jumlah_lembar} {t("lembar")}
              {" · "}{fmtAngka((data?.sumber?.ukuran ?? 0) / 1024, 1)} KB
            </p>
            <p className="mt-0.5 text-xs text-[#9AA0A6]">
              {t("Diubah")}: {String(data?.sumber?.diubah ?? "").replace("T", " ").replace("+00:00", " UTC")}
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="block">
              <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#64676C]">
                {t("Periode")}
              </span>
              <select className={`${kelasInput} w-48`} value={bulan}
                      onChange={(e) => setBulan(e.target.value)}>
                {daftar.map((x) => (
                  <option key={x.kunci} value={x.kunci}>{t(x.label)}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.08em] text-[#64676C]">
                {t("Cari vendor / catatan")}
              </span>
              <input className={`${kelasInput} w-64`} value={cari}
                     placeholder={t("Ketik nama vendor atau catatan")}
                     onChange={(e) => setCari(e.target.value)} />
            </label>
            <button className={kelasTombolAnalisa}
                    disabled={laporan.isFetching}
                    onClick={() => laporan.refetch()}>
              {laporan.isFetching ? `⏳ ${t("Memuat…")}` : `↻ ${t("Refresh")}`}
            </button>
            <a className={kelasTombolKecil}
               href={urlApi(`/api/kepatuhan-vendor-sampling?bulan=${bulan || data?.kunci}&format=xlsx`)}>
              ↓ {t("Ekspor Excel")}
            </a>
          </div>
        </div>
        <p className="mt-3 text-xs text-[#64676C]">
          {t("Nilai ditampilkan apa adanya dari workbook.")} {p?.aturan}
        </p>
      </section>

      {/* Angka kunci */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <KotakKpi label="Total kunjungan" nilai={fmtAngka(ring.total_kunjungan, 0)} />
        <KotakKpi label="Tepat waktu" nilai={fmtAngka(ring.tepat, 0)} warna="text-[#15803D]" />
        <KotakKpi label="Terlambat" nilai={fmtAngka(ring.terlambat, 0)} warna="text-[#B91C1C]" />
        <KotakKpi label="Tanpa data waktu" nilai={fmtAngka(ring.tanpa_data, 0)} warna="text-[#B45309]" />
        <KotakKpi label="% Tepat waktu" nilai={fmtPersen(ring.persen_tepat)} warna="text-[#15803D]" />
      </section>

      {/* Catatan aturan */}
      <section className="rounded-sm border border-[#FDE68A] bg-[#FFFBEB] px-4 py-3">
        <h3 className="text-sm font-semibold text-[#B45309]">
          {t("Aturan dan catatan")}
        </h3>
        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs leading-snug text-[#64676C]">
          {(data?.catatan_aturan ?? []).map((x: string, i: number) => <li key={i}>{t(x)}</li>)}
        </ul>
        <p className="mt-2 text-xs text-[#64676C]">
          {p?.judul} · {p?.periode_teks} · {p?.sheet_log} / {p?.sheet_summary}
        </p>
      </section>

      {/* Perbandingan bulan */}
      <section className="kartu-aksen rounded-sm border border-[#E4E5E8] bg-white p-5">
        <h2 className="mb-3 text-lg font-semibold text-[#1D2434]">
          {t("Perbandingan bulan")}
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px] border-collapse text-xs">
            <thead>
              <tr className="bg-[#F8F8F8] text-left text-[#64676C]">
                {[t("Periode"), t("Total kunjungan"), t("Tepat waktu"), t("Terlambat"),
                  t("Tanpa data waktu"), t("% Tepat waktu")].map((h, i) => (
                  <th key={i} className="border border-[#E4E5E8] px-2 py-1.5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {daftar.map((x) => (
                <tr key={x.kunci} className={x.kunci === p?.kunci ? "bg-[#FFF5F5]" : "odd:bg-white even:bg-[#FCFCFC]"}>
                  <td className="border border-[#E4E5E8] px-2 py-1 font-semibold">{t(x.label)}</td>
                  <td className="border border-[#E4E5E8] px-2 py-1 font-mono">{fmtAngka(x.ringkasan.total_kunjungan, 0)}</td>
                  <td className="border border-[#E4E5E8] px-2 py-1 font-mono">{fmtAngka(x.ringkasan.tepat, 0)}</td>
                  <td className="border border-[#E4E5E8] px-2 py-1 font-mono">{fmtAngka(x.ringkasan.terlambat, 0)}</td>
                  <td className="border border-[#E4E5E8] px-2 py-1 font-mono">{fmtAngka(x.ringkasan.tanpa_data, 0)}</td>
                  <td className="border border-[#E4E5E8] px-2 py-1 font-mono">{fmtPersen(x.ringkasan.persen_tepat)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Summary */}
      <section className="kartu-aksen rounded-sm border border-[#E4E5E8] bg-white p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-[#1D2434]">
            {t("Ringkasan per vendor")}
          </h2>
          <span className="text-xs text-[#64676C]">
            {summaryTampil.length} / {p?.summary?.length ?? 0} {t("baris ringkasan")}
          </span>
        </div>
        <TabelUmum kolom={p?.kolom_summary ?? []} baris={barisSummary}
                   kosong="Tidak ada baris yang cocok." />
      </section>

      {/* Log */}
      <section className="kartu-aksen rounded-sm border border-[#E4E5E8] bg-white p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-[#1D2434]">
            {t("Log monitoring")}
          </h2>
          <span className="text-xs text-[#64676C]">
            {logTampil.length} / {p?.log?.length ?? 0} {t("baris log")}
          </span>
        </div>
        <TabelUmum kolom={p?.kolom_log ?? []} baris={logTampil}
                   kosong="Tidak ada baris yang cocok." />
      </section>
    </div>
  );
}
