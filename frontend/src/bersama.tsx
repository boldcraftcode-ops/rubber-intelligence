import { ReactNode, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { bahasaSekarang, useBahasa } from "./i18n";

/* ---------- format angka mengikuti bahasa aktif ---------- */
export const fmtAngka = (n: number | null | undefined, desimal = 4) =>
  n === null || n === undefined
    ? "–"
    : new Intl.NumberFormat(bahasaSekarang() === "id" ? "id-ID" : "en-US", {
        minimumFractionDigits: desimal,
        maximumFractionDigits: desimal,
      }).format(n);

export const fmtTanggal = (iso: string) => {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
};

export const NAMA_BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
  "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

export const hariIni = () => new Date().toISOString().slice(0, 10);

/* ---------- API ----------
   Di development URL relatif (proxy satu-origin). Di produksi (Cloudflare
   Pages) VITE_API_URL berisi https://api.domain-anda; cookie login Access
   ikut dikirim (credentials: include). */
const API_URL: string = (import.meta as any).env?.VITE_API_URL ?? "";

export const urlApi = (path: string) => `${API_URL}${path}`;

export async function ambilJson(url: string) {
  const r = await fetch(urlApi(url), { credentials: "include" });
  if (r.status === 401) {
    let detail = "Belum login. Muat ulang halaman untuk masuk lewat Cloudflare Access.";
    try { detail = (await r.json()).detail ?? detail; } catch { /* abaikan */ }
    throw new Error(detail);
  }
  if (!r.ok) {
    let detail = "Gagal memuat data.";
    try { detail = (await r.json()).detail ?? detail; } catch { /* abaikan */ }
    throw new Error(detail);
  }
  return r.json();
}

export async function kirimJson(url: string, body: unknown) {
  const r = await fetch(urlApi(url), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail ?? "Gagal menyimpan.");
  return data;
}

/* ---------- gaya ---------- */
export const kelasInput =
  "w-full rounded-md border border-violet-400/30 bg-[#0b0a26]/80 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500";
export const kelasLabel = "block text-sm font-medium text-slate-200 mb-1";
export const kelasTombol =
  "rounded-md bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-50 shadow-lg shadow-violet-950/60";
export const kelasTombolKecil =
  "rounded-md border border-violet-400/30 bg-white/5 px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-violet-500/20";

export function Pesan({ jenis, teks }: { jenis: "sukses" | "error"; teks: string }) {
  return (
    <p className={`mt-3 rounded-md px-3 py-2 text-sm border ${
      jenis === "sukses"
        ? "bg-emerald-500/10 text-emerald-300 border-emerald-400/30"
        : "bg-red-500/10 text-red-300 border-red-400/30"}`}>
      {teks}
    </p>
  );
}

/* ---------- modal "Jelaskan ke saya" ----------
   Prinsip: jawaban dulu, bukti kemudian (What -> So what -> Now what).
   Satu angka utama, bahasa sehari-hari, maksud tindakan di akhir.
   Lapisan kedua (angka pendukung + rumus) hanya dibuka bila ditanyakan. */
function ModalJelaskan({ idMetrik, judul, qs, tutup }: {
  idMetrik: string; judul: string; qs?: string; tutup: () => void;
}) {
  const { t } = useBahasa();
  const [detail, setDetail] = useState(false);
  const q = useQuery({
    queryKey: ["jelaskan", idMetrik, qs ?? ""],
    queryFn: () => ambilJson(`/api/jelaskan/${idMetrik}${qs ?? ""}`),
    retry: false,
  });
  const d = q.data;

  const bagian: [string, string, string[]][] = d ? [
    [t("Apa yang terjadi"), "📌", d.what ?? []],
    [t("Kenapa begitu"), "🔎", d.so_what ?? []],
    [t("Apa yang perlu dilakukan"), "🧭", d.now_what ?? []],
  ] : [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
         onClick={tutup}>
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-[#1a1844] border border-violet-500/30 p-6 shadow-2xl shadow-violet-950/50"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-violet-300">
              {t("Jelaskan ke saya")}
            </p>
            <h3 className="text-lg font-semibold text-slate-100">{judul}</h3>
          </div>
          <button className={kelasTombolKecil} onClick={tutup}>{t("Tutup")}</button>
        </div>

        {q.isLoading && <p className="mt-4 text-sm text-slate-400">{t("Menyusun penjelasan…")}</p>}
        {q.error && (
          <p className="mt-4 rounded-md bg-red-500/10 border border-red-400/30 px-3 py-2 text-sm text-red-300">
            {(q.error as Error).message}
          </p>
        )}

        {d && (
          <>
            {/* Satu angka utama — tidak lebih */}
            {d.angka_utama && (
              <div className="mt-3 rounded-lg border border-violet-400/40 bg-violet-500/10 p-4">
                <div className="text-3xl font-bold font-mono text-violet-200">
                  {d.angka_utama.nilai}
                </div>
                <div className="text-xs text-slate-300 mt-0.5">{d.angka_utama.label}</div>
              </div>
            )}

            {!d.ada_data && (
              <p className="mt-3 rounded-md bg-amber-400/10 border border-amber-400/30 px-3 py-2 text-sm text-amber-300">
                {t("Datanya belum cukup untuk menjelaskan kartu ini.")}
              </p>
            )}

            <div className="mt-3 grid gap-3">
              {bagian.map(([nama, ikon, isi]) => (
                isi.length > 0 && (
                  <section key={nama} className="rounded-lg border border-violet-500/20 bg-white/5 p-3">
                    <h4 className="text-sm font-semibold text-violet-300 mb-1">{ikon} {nama}</h4>
                    <ul className="grid gap-1">
                      {isi.map((kalimat, i) => (
                        <li key={i} className="text-sm leading-relaxed text-slate-200 flex gap-1.5">
                          <span className="text-slate-500 shrink-0">•</span><span>{kalimat}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )
              ))}
            </div>

            {d.analogi && (
              <p className="mt-3 rounded-md bg-sky-500/10 border border-sky-400/30 px-3 py-2 text-sm text-sky-200">
                💡 {d.analogi}
              </p>
            )}
            {d.cara_baca && (
              <p className="mt-2 text-xs text-slate-400">
                <b className="text-slate-300">{t("Cara membaca grafik")}:</b> {d.cara_baca}
              </p>
            )}
            {(d.catatan ?? []).map((c: string, i: number) => (
              <p key={i} className="mt-1 text-xs text-slate-500">ℹ {c}</p>
            ))}

            {/* Lapisan kedua: hanya bila ditanyakan */}
            <button className={`${kelasTombolKecil} mt-4`} onClick={() => setDetail(!detail)}>
              {detail ? "▾" : "▸"} {t("Lihat detail angka & rumus")}
            </button>
            {detail && (
              <div className="mt-2 grid gap-3">
                {(d.detail ?? []).map((tabel: any, i: number) => (
                  <div key={i} className="overflow-x-auto rounded-lg border border-violet-500/20 bg-white/5 p-3">
                    <div className="text-xs font-semibold text-slate-200 mb-1">{tabel.judul}</div>
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left text-slate-400 border-b">
                          {(tabel.kolom ?? []).map((k: string) => (
                            <th key={k} className="py-1 pr-3 whitespace-nowrap">{k}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(tabel.baris ?? []).map((b: any[], j: number) => (
                          <tr key={j} className="border-b border-white/5">
                            {b.map((sel, k) => (
                              <td key={k} className={`py-1 pr-3 ${k === 0 ? "text-slate-300" : "font-mono text-slate-400"}`}>
                                {sel}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
                {d.rumus && (
                  <div className="rounded-lg border border-violet-500/20 bg-white/5 p-3">
                    <div className="text-xs font-semibold text-slate-200 mb-1">
                      {t("Cara dihitung (rujukan teknis)")}
                    </div>
                    <p className="text-xs text-slate-400 whitespace-pre-line">{d.rumus}</p>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ---------- kartu dengan "Jelaskan ke saya" + ekspor Excel ---------- */
export function Kartu({ idMetrik, judul, keterangan, urlEkspor, qsJelaskan, anak }: {
  idMetrik: string;
  judul: string;
  keterangan?: string;
  urlEkspor?: string;
  /** Query string periode kartu (mis. "?dari=2026-01&sampai=2026-10") supaya
   *  penjelasan memakai periode yang sama dengan yang sedang dilihat. */
  qsJelaskan?: string;
  anak: ReactNode;
}) {
  const [buka, setBuka] = useState(false);
  const { t } = useBahasa();

  return (
    <section className="rounded-xl bg-[#15143a]/90 p-5 shadow-lg shadow-black/30 border border-violet-500/20">
      <div className="flex items-start justify-between gap-3 mb-1">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{judul}</h2>
          {keterangan && <p className="text-sm text-slate-400">{keterangan}</p>}
        </div>
        <div className="flex gap-2 shrink-0">
          <button className={`${kelasTombolKecil} border-violet-400/60`} onClick={() => setBuka(true)}>
            ✨ {t("Jelaskan ke saya")}
          </button>
          {urlEkspor && (
            <a className={kelasTombolKecil}
               href={urlApi(`${urlEkspor}${urlEkspor.includes("?") ? "&" : "?"}format=xlsx`)}>
              {t("Ekspor Excel")}
            </a>
          )}
        </div>
      </div>
      <div className="mt-3">{anak}</div>
      {buka && <ModalJelaskan idMetrik={idMetrik} judul={judul} qs={qsJelaskan}
                              tutup={() => setBuka(false)} />}
    </section>
  );
}


/* ---------- panel analisa 5W1H (dipakai Ringkasan & Analisis) ---------- */
const JUDUL_5W1H: [string, string, string][] = [
  ["what", "What — apa yang terjadi", "📌"],
  ["when", "When — kapan titik pentingnya", "🕒"],
  ["where", "Where — di mana", "🗺"],
  ["who", "Who — siapa", "👥"],
  ["why", "Why — mengapa (fakta + hipotesis)", "🔎"],
  ["how", "How — bagaimana menyikapi", "🧭"],
];

export function Panel5W1H({ url, judul, tutup }: {
  url: string; judul: string; tutup: () => void;
}) {
  const q = useQuery({ queryKey: ["analisa-5w1h", url], queryFn: () => ambilJson(url) });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
         onClick={tutup}>
      <div className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-[#1a1844] border border-violet-500/30 p-6 shadow-2xl shadow-violet-950/50"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-100">{judul}</h3>
            {q.data?.periode && (
              <p className="text-sm text-slate-400">Periode: {q.data.periode}</p>
            )}
          </div>
          <button className={kelasTombolKecil} onClick={tutup}>Tutup</button>
        </div>

        {q.isLoading && <p className="mt-4 text-sm text-slate-400">Menganalisa data…</p>}
        {q.error && (
          <p className="mt-4 rounded-md bg-red-500/10 border border-red-400/30 px-3 py-2 text-sm text-red-300">
            {(q.error as Error).message}
          </p>
        )}
        {q.data?.ringkas && (
          <p className="mt-4 rounded-md bg-amber-400/10 border border-amber-400/30 px-3 py-2 text-sm text-amber-300">
            {q.data.ringkas}
          </p>
        )}
        {q.data && !q.data.ringkas && (
          <div className="mt-4 grid gap-4">
            {JUDUL_5W1H.map(([kunci, judulBagian, ikon]) => (
              q.data[kunci]?.length > 0 && (
                <section key={kunci} className="rounded-lg border border-violet-500/20 bg-white/5 p-3">
                  <h4 className="text-sm font-semibold text-violet-300 mb-1.5">
                    {ikon} {judulBagian}
                  </h4>
                  <ul className="list-disc pl-5 grid gap-1.5">
                    {q.data[kunci].map((kalimat: string, i: number) => (
                      <li key={i}
                          className={`text-sm leading-relaxed ${
                            kalimat.includes("HIPOTESIS")
                              ? "text-amber-300" : "text-slate-200"}`}>
                        {kalimat}
                      </li>
                    ))}
                  </ul>
                </section>
              )
            ))}
            {q.data.catatan.map((c: string, i: number) => (
              <p key={i} className="rounded-md bg-white/5 border border-violet-500/20 px-3 py-2 text-xs text-slate-400">
                {c}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export const kelasTombolAnalisa =
  "rounded-md bg-gradient-to-r from-violet-600 to-fuchsia-600 px-3 py-1.5 text-xs font-semibold text-white hover:from-violet-500 hover:to-fuchsia-500 shadow-lg shadow-violet-950/50";
