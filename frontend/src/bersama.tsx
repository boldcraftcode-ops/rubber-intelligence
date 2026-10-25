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
   Di development URL relatif (proxy satu-origin). Bila tampilan web dipisah
   dari API, VITE_API_URL berisi https://api.domain-anda; cookie sesi login
   ikut dikirim (credentials: include). */
const API_URL: string = (import.meta as any).env?.VITE_API_URL ?? "";

export const urlApi = (path: string) => `${API_URL}${path}`;

/* ---------- token sesi cadangan ----------
   Cookie HttpOnly (`op_sesi`) adalah cara utama. Namun bila aplikasi dibuka di
   dalam iframe (preview/embed) atau browser memblokir cookie lintas situs,
   cookie tidak pernah terkirim: login berhasil lalu permintaan berikutnya 401,
   sehingga pengguna kembali ke form login. Untuk itu API juga mengirim token
   pada saat login, disimpan di sini, dan dikirim lewat header Authorization. */
const KUNCI_TOKEN = "op-margin.token";

/* Salinan di MEMORI. Ini penting: di dalam iframe yang di-sandbox browser juga
   memblokir localStorage (melempar galat), sehingga token tidak bisa disimpan
   sama sekali dan setiap permintaan kembali 401. Salinan memori membuat sesi
   tetap hidup selama halaman belum dimuat ulang. */
let tokenMemori: string | null = null;

export const tokenSesi = (): string | null => {
  if (tokenMemori) return tokenMemori;
  try { return localStorage.getItem(KUNCI_TOKEN); } catch { return null; }
};

export const simpanToken = (token: string | null | undefined) => {
  tokenMemori = token || null;
  try {
    if (token) localStorage.setItem(KUNCI_TOKEN, token);
    else localStorage.removeItem(KUNCI_TOKEN);
  } catch { /* localStorage diblokir: salinan memori sudah menyimpan */ }
};

const kepalaSesi = (): Record<string, string> => {
  const t = tokenSesi();
  return t ? { Authorization: `Bearer ${t}` } : {};
};

export async function ambilJson(url: string) {
  const r = await fetch(urlApi(url), {
    credentials: "include",
    headers: kepalaSesi(),
  });
  if (r.status === 401) {
    simpanToken(null);   // token kedaluwarsa/tidak sah: jangan dipakai lagi
    let detail = "Belum login. Silakan masuk dengan username dan sandi Anda.";
    try { detail = (await r.json()).detail ?? detail; } catch { /* abaikan */ }
    throw galatApi(detail, 401);
  }
  if (!r.ok) {
    let detail = "Gagal memuat data.";
    try { detail = (await r.json()).detail ?? detail; } catch { /* abaikan */ }
    throw galatApi(detail, r.status);
  }
  return r.json();
}

/* ---------- galat API + pesan ramah ----------
   Kasus yang sering membingungkan: endpoint baru (Margin Bridge, Days of
   Cover, Jelaskan ke saya) menjawab 404 "Not Found" karena proses API yang
   berjalan masih KODE LAMA (jendela API lama belum ditutup). Pesannya
   diterjemahkan supaya tidak tampak seperti aplikasi rusak. */
export interface GalatApi extends Error { status: number; }

export const galatApi = (pesan: string, status: number): GalatApi => {
  const e = new Error(pesan) as GalatApi;
  e.status = status;
  return e;
};

export function pesanGalat(e: unknown): string {
  const err = e as GalatApi | undefined;
  const teks = err?.message ?? "Gagal memuat data.";
  if (err?.status === 404 && /^not found$/i.test(teks.trim())) {
    return ("Fitur ini tidak dikenali oleh API yang sedang berjalan — biasanya "
      + "karena jendela \"OP Margin - API\" dari sesi sebelumnya masih hidup "
      + "(memakai kode lama). Tutup jendela API lama, lalu jalankan "
      + "start-web.bat lagi, dan muat ulang halaman ini (Ctrl+F5).");
  }
  if (err?.status === 404) return teks;
  if (err?.status === 422) return `Permintaan tidak valid: ${teks}`;
  return teks;
}

export async function kirimJson(url: string, body: unknown) {
  const r = await fetch(urlApi(url), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...kepalaSesi() },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail ?? "Gagal menyimpan.");
  return data;
}

/* ---------- gaya (tema korporat: navy, merah, putih) ---------- */
export const NAVY = "#1D2434";
export const MERAH = "#FF1313";
export const ABU = "#64676C";

export const kelasInput =
  "w-full rounded-sm border border-[#D5D7DB] bg-white px-3 py-2 text-sm text-[#1D2434] " +
  "placeholder-[#9AA0A6] focus:outline-none focus:border-[#FF1313] focus:ring-2 " +
  "focus:ring-[#FF1313]/20 transition-colors";

export const kelasLabel =
  "block text-[11px] font-semibold uppercase tracking-wider text-[#64676C] mb-1.5";

export const kelasTombol =
  "rounded-sm bg-[#FF1313] px-4 py-2 text-sm font-semibold text-white " +
  "hover:bg-[#D90F0F] disabled:opacity-40 disabled:cursor-not-allowed " +
  "transition-colors shadow-sm shadow-[#1D2434]/10";

export const kelasTombolKecil =
  "rounded-sm border border-[#D5D7DB] bg-white px-2.5 py-1 text-xs font-semibold " +
  "text-[#1D2434] hover:border-[#FF1313] hover:text-[#FF1313] transition-colors";

export const kelasTombolNav =
  "rounded-sm border border-[#D5D7DB] bg-[#1D2434] px-2.5 py-1 text-xs font-semibold " +
  "text-white hover:bg-[#2A3345] transition-colors";

export function Pesan({ jenis, teks }: { jenis: "sukses" | "error"; teks: string }) {
  return (
    <p className={`mt-3 rounded-sm px-3 py-2 text-sm border ${
      jenis === "sukses"
        ? "bg-[#F0FDF4] text-[#15803D] border-[#BBF7D0]"
        : "bg-[#FEF2F2] text-[#B91C1C] border-[#FECACA]"}`}>
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
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-sm bg-white border border-[#E4E5E8] p-6 shadow-xl shadow-[#1D2434]/10"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-[#FF1313]">
              {t("Jelaskan ke saya")}
            </p>
            <h3 className="text-lg font-semibold text-[#1D2434]">{judul}</h3>
          </div>
          <button className={kelasTombolKecil} onClick={tutup}>{t("Tutup")}</button>
        </div>

        {q.isLoading && <p className="mt-4 text-sm text-[#64676C]">{t("Menyusun penjelasan…")}</p>}
        {q.error && (
          <p className="mt-4 rounded-sm bg-[#FEF2F2] border border-[#FECACA] px-3 py-2 text-sm text-[#B91C1C]">
            {pesanGalat(q.error)}
          </p>
        )}

        {d && (
          <>
            {/* Satu angka utama — tidak lebih */}
            {d.angka_utama && (
              <div className="mt-3 rounded-sm border border-[#FF1313]/40 bg-[#FFF1F1] p-4">
                <div className="text-3xl font-bold font-mono text-[#1D2434]">
                  {d.angka_utama.nilai}
                </div>
                <div className="text-xs text-[#1D2434] mt-0.5">{d.angka_utama.label}</div>
              </div>
            )}

            {!d.ada_data && (
              <p className="mt-3 rounded-sm bg-[#FFFBEB] border border-[#FDE68A] px-3 py-2 text-sm text-[#B45309]">
                {t("Datanya belum cukup untuk menjelaskan kartu ini.")}
              </p>
            )}

            <div className="mt-3 grid gap-3">
              {bagian.map(([nama, ikon, isi]) => (
                isi.length > 0 && (
                  <section key={nama} className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                    <h4 className="text-sm font-semibold text-[#FF1313] mb-1">{ikon} {nama}</h4>
                    <ul className="grid gap-1">
                      {isi.map((kalimat, i) => (
                        <li key={i} className="text-sm leading-relaxed text-[#1D2434] flex gap-1.5">
                          <span className="text-[#64676C] shrink-0">•</span><span>{kalimat}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )
              ))}
            </div>

            {d.analogi && (
              <p className="mt-3 rounded-sm bg-[#F0F9FF] border border-[#BAE6FD] px-3 py-2 text-sm text-[#0369A1]">
                💡 {d.analogi}
              </p>
            )}
            {d.cara_baca && (
              <p className="mt-2 text-xs text-[#64676C]">
                <b className="text-[#1D2434]">{t("Cara membaca grafik")}:</b> {d.cara_baca}
              </p>
            )}
            {(d.catatan ?? []).map((c: string, i: number) => (
              <p key={i} className="mt-1 text-xs text-[#64676C]">ℹ {c}</p>
            ))}

            {/* Lapisan kedua: hanya bila ditanyakan */}
            <button className={`${kelasTombolKecil} mt-4`} onClick={() => setDetail(!detail)}>
              {detail ? "▾" : "▸"} {t("Lihat detail angka & rumus")}
            </button>
            {detail && (
              <div className="mt-2 grid gap-3">
                {(d.detail ?? []).map((tabel: any, i: number) => (
                  <div key={i} className="overflow-x-auto rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                    <div className="text-xs font-semibold text-[#1D2434] mb-1">{tabel.judul}</div>
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left text-[#64676C] border-b">
                          {(tabel.kolom ?? []).map((k: string) => (
                            <th key={k} className="py-1 pr-3 whitespace-nowrap">{k}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(tabel.baris ?? []).map((b: any[], j: number) => (
                          <tr key={j} className="border-b border-[#EDEFF2]">
                            {b.map((sel, k) => (
                              <td key={k} className={`py-1 pr-3 ${k === 0 ? "text-[#1D2434]" : "font-mono text-[#64676C]"}`}>
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
                  <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                    <div className="text-xs font-semibold text-[#1D2434] mb-1">
                      {t("Cara dihitung (rujukan teknis)")}
                    </div>
                    <p className="text-xs text-[#64676C] whitespace-pre-line">{d.rumus}</p>
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
    <section className="kartu-aksen rounded-sm bg-white p-5 shadow-[0_1px_3px_rgba(29,36,52,0.08)]
                       border border-[#E4E5E8]">
      <div className="flex items-start justify-between gap-3 mb-1">
        <div>
          <h2 className="text-lg font-semibold text-[#1D2434]">{judul}</h2>
          {keterangan && <p className="text-sm text-[#64676C]">{keterangan}</p>}
        </div>
        <div className="flex gap-2 shrink-0">
          <button className={`${kelasTombolKecil} border-[#FF1313]`} onClick={() => setBuka(true)}>
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
      <div className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-sm bg-white border border-[#E4E5E8] p-6 shadow-xl shadow-[#1D2434]/10"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-[#1D2434]">{judul}</h3>
            {q.data?.periode && (
              <p className="text-sm text-[#64676C]">Periode: {q.data.periode}</p>
            )}
          </div>
          <button className={kelasTombolKecil} onClick={tutup}>Tutup</button>
        </div>

        {q.isLoading && <p className="mt-4 text-sm text-[#64676C]">Menganalisa data…</p>}
        {q.error && (
          <p className="mt-4 rounded-sm bg-[#FEF2F2] border border-[#FECACA] px-3 py-2 text-sm text-[#B91C1C]">
            {pesanGalat(q.error)}
          </p>
        )}
        {q.data?.ringkas && (
          <p className="mt-4 rounded-sm bg-[#FFFBEB] border border-[#FDE68A] px-3 py-2 text-sm text-[#B45309]">
            {q.data.ringkas}
          </p>
        )}
        {q.data && !q.data.ringkas && (
          <div className="mt-4 grid gap-4">
            {JUDUL_5W1H.map(([kunci, judulBagian, ikon]) => (
              q.data[kunci]?.length > 0 && (
                <section key={kunci} className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                  <h4 className="text-sm font-semibold text-[#FF1313] mb-1.5">
                    {ikon} {judulBagian}
                  </h4>
                  <ul className="list-disc pl-5 grid gap-1.5">
                    {q.data[kunci].map((kalimat: string, i: number) => (
                      <li key={i}
                          className={`text-sm leading-relaxed ${
                            kalimat.includes("HIPOTESIS")
                              ? "text-[#B45309]" : "text-[#1D2434]"}`}>
                        {kalimat}
                      </li>
                    ))}
                  </ul>
                </section>
              )
            ))}
            {q.data.catatan.map((c: string, i: number) => (
              <p key={i} className="rounded-sm bg-[#F8F8F8] border border-[#E4E5E8] px-3 py-2 text-xs text-[#64676C]">
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
  "rounded-sm bg-[#1D2434] px-3 py-1.5 text-xs font-semibold text-white " +
  "hover:bg-[#2A3345] transition-colors";
