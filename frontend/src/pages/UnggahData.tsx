import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Kartu, Pesan, fmtAngka, kelasTombol, kelasTombolKecil, urlApi,
} from "../bersama";

/* Layar Unggah Data — tiga langkah supaya tidak ada data "nyasar" ke database:

   1. Pilih file                -> file dikirim, divalidasi, TIDAK disimpan
   2. Pratinjau                 -> lihat berapa baris siap & baris bermasalah,
                                   unduh daftar mismatch (Excel) bila perlu
   3. Konfirmasi simpan         -> baru sekarang data masuk database

   Selama proses berjalan ditampilkan progress bar + tulisan tahap yang sedang
   dikerjakan, supaya tidak ada layar "diam" yang membingungkan. */

const pengisi = () => localStorage.getItem("op-margin.pengisi") || "?";

const NAMA_TABEL: Record<string, string> = {
  tiket_baris: "Baris tiket",
  tiket: "Baris tiket",
  pembelian: "Pembelian",
  sicom: "SICOM",
  kurs: "Kurs",
  stok: "Stok",
  harga_grade: "Harga per grade",
  parameter_pabrik: "Parameter pabrik",
  target_margin: "Target margin",
  perencanaan: "Perencanaan",
  vendor: "Vendor",
  grade: "Grade",
  aturan_stok_harga: "Aturan stok→harga",
};

type Tahap = "pilih" | "pratinjau" | "selesai";
type Proses = { persen: number; teks: string } | null;
type Mismatch = {
  sheet: string;
  baris: number | null;
  kode: string;
  alasan: string;
};

/* ---------------------------------------------------------------- progress */

export function BilahProgres({ proses }: { proses: NonNullable<Proses> }) {
  return (
    <div className="mt-4" role="status" aria-live="polite">
      <div className="flex items-baseline justify-between gap-3 mb-1.5">
        <p className="text-xs font-semibold text-[#1D2434]">{proses.teks}</p>
        <p className="text-xs tabular-nums text-[#64676C]">{Math.round(proses.persen)}%</p>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-sm bg-[#EDEFF2]">
        <div
          className="h-full bg-[#FF1313] transition-[width] duration-300 ease-out"
          style={{ width: `${Math.max(3, Math.min(100, proses.persen))}%` }}
        />
      </div>
      <p className="mt-1.5 text-[11px] text-[#64676C]">
        Biarkan halaman ini terbuka sampai proses selesai.
      </p>
    </div>
  );
}

/* --------------------------------------------------------------- komponen */

export function DaftarAngka({ jumlah }: { jumlah: Record<string, number> }) {
  const isi = Object.entries(jumlah ?? {}).filter(([, v]) => Number(v) > 0);
  if (isi.length === 0) return null;
  return (
    <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
      {isi.map(([k, v]) => (
        <div key={k} className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-2.5">
          <p className="text-xs text-[#64676C]">{NAMA_TABEL[k] ?? k}</p>
          <p className="font-semibold text-[#1D2434]">{fmtAngka(Number(v), 0)} baris</p>
        </div>
      ))}
    </div>
  );
}

export function TabelMismatch({ daftar, jumlah }: { daftar: Mismatch[]; jumlah: number }) {
  return (
    <div className="mt-3 rounded-sm border border-[#FECACA] overflow-hidden">
      <div className="max-h-72 overflow-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-[#FEF2F2] text-[#B91C1C]">
            <tr>
              <th className="px-2 py-1.5 text-left font-semibold">Sheet</th>
              <th className="px-2 py-1.5 text-right font-semibold">Baris</th>
              <th className="px-2 py-1.5 text-left font-semibold">Kode</th>
              <th className="px-2 py-1.5 text-left font-semibold">Yang harus diperbaiki</th>
            </tr>
          </thead>
          <tbody>
            {daftar.map((m, i) => (
              <tr key={i} className="border-t border-[#FECACA] align-top">
                <td className="px-2 py-1.5 font-medium text-[#1D2434]">{m.sheet}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-[#64676C]">
                  {m.baris ?? "-"}
                </td>
                <td className="px-2 py-1.5 text-[#64676C]">{m.kode}</td>
                <td className="px-2 py-1.5 text-[#1D2434]">{m.alasan}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {jumlah > daftar.length && (
        <p className="border-t border-[#FECACA] bg-[#FEF2F2] px-2 py-1.5 text-[11px] text-[#B91C1C]">
          Menampilkan {daftar.length} dari {jumlah} baris bermasalah — unduh Excel
          untuk daftar lengkapnya.
        </p>
      )}
    </div>
  );
}

export function UnduhMismatch({ token, jumlah }: { token: string; jumlah: number }) {
  return (
    <a className={`${kelasTombolKecil} inline-block`}
       href={urlApi(`/api/unggah/pratinjau/${token}/mismatch.xlsx`)}>
      ⬇ Unduh Excel data mismatch ({fmtAngka(jumlah, 0)} baris)
    </a>
  );
}

/* ------------------------------------------------------------------ halaman */

export default function UnggahData() {
  const qc = useQueryClient();
  const [tahap, setTahap] = useState<Tahap>("pilih");
  const [pratinjau, setPratinjau] = useState<any | null>(null);
  const [selesai, setSelesai] = useState<any | null>(null);
  const [galat, setGalat] = useState<string | null>(null);
  const [proses, setProses] = useState<Proses>(null);
  const [seret, setSeret] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const jam = useRef<number | null>(null);

  const hentikanJam = () => {
    if (jam.current !== null) {
      window.clearInterval(jam.current);
      jam.current = null;
    }
  };
  useEffect(() => hentikanJam, []);

  /** Naikkan bilah perlahan antara dua persen (untuk tahap yang tidak punya
      angka kemajuan nyata, mis. validasi & penyimpanan). */
  const naikPerlahan = (dari: number, sampai: number, teks: string) => {
    hentikanJam();
    setProses({ persen: dari, teks });
    jam.current = window.setInterval(() => {
      setProses((p) => {
        if (!p) return p;
        if (p.persen >= sampai) return { ...p, teks };
        return { persen: Math.min(sampai, p.persen + 1), teks };
      });
    }, 400);
  };

  const kirimFile = (file: File) =>
    new Promise<any>((resolve, reject) => {
      const data = new FormData();
      data.append("file", file);
      data.append("pengisi", pengisi());
      const xhr = new XMLHttpRequest();
      xhr.open("POST", urlApi("/api/unggah/pratinjau"));
      xhr.withCredentials = true;
      let tahapValidasi = false;
      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        const persen = Math.round((e.loaded / e.total) * 100);
        if (persen < 100) {
          setProses({ persen: persen * 0.7, teks: `Mengunggah file… ${persen}%` });
        } else if (!tahapValidasi) {
          tahapValidasi = true;
          naikPerlahan(72, 95, "File terkirim. Memeriksa isi file (validasi)…");
        }
      };
      xhr.onload = () => {
        let isi: any = {};
        try { isi = JSON.parse(xhr.responseText); } catch { /* bukan JSON */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(isi);
        else reject(new Error(isi?.detail ?? "Gagal mengunggah file."));
      };
      xhr.onerror = () =>
        reject(new Error("Koneksi terputus saat mengunggah. Periksa jaringan lalu coba lagi."));
      xhr.send(data);
    });

  const pilihFile = async (f: File | undefined | null) => {
    if (!f) return;
    setGalat(null); setPratinjau(null); setSelesai(null); setTahap("pilih");
    setProses({ persen: 2, teks: `Menyiapkan ${f.name}…` });
    try {
      const j = await kirimFile(f);
      hentikanJam();
      setProses({ persen: 100, teks: "Pratinjau siap diperiksa." });
      setPratinjau(j);
      setTahap("pratinjau");
    } catch (e: any) {
      hentikanJam();
      setProses(null);
      setGalat(e?.message ?? "Gagal mengunggah file.");
    }
  };

  const konfirmasi = async () => {
    if (!pratinjau?.token) return;
    setGalat(null);
    naikPerlahan(8, 92, "Menyimpan ke database & menghitung ulang mart…");
    try {
      const r = await fetch(
        urlApi(`/api/unggah/pratinjau/${pratinjau.token}/konfirmasi`),
        { method: "POST", credentials: "include" },
      );
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail ?? "Gagal menyimpan data.");
      hentikanJam();
      setProses({ persen: 100, teks: "Selesai." });
      setSelesai(j);
      setTahap("selesai");
      qc.invalidateQueries(); // semua angka di aplikasi menyegarkan diri
    } catch (e: any) {
      hentikanJam();
      setProses(null);
      setGalat(e?.message ?? "Gagal menyimpan data.");
    }
  };

  const batal = async (pesan?: string) => {
    hentikanJam();
    if (pratinjau?.token && tahap !== "selesai") {
      try {
        await fetch(urlApi(`/api/unggah/pratinjau/${pratinjau.token}`),
                    { method: "DELETE", credentials: "include" });
      } catch { /* jaringan putus: file sementara kedaluwarsa sendiri */ }
    }
    setPratinjau(null); setSelesai(null); setProses(null);
    setGalat(pesan ?? null); setTahap("pilih");
  };

  const sedangProses = proses !== null && proses.persen < 100;

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="unggah" judul="Unggah file data"
             keterangan="Alur tiga langkah: pilih file → periksa pratinjau → konfirmasi simpan. Data baru masuk database setelah Anda menekan Konfirmasi."
             anak={
        <>
          {/* penunjuk langkah */}
          <ol className="mb-4 grid grid-cols-3 gap-2 text-xs">
            {[
              { n: 1, teks: "Pilih file", aktif: tahap === "pilih" },
              { n: 2, teks: "Periksa pratinjau", aktif: tahap === "pratinjau" },
              { n: 3, teks: "Konfirmasi simpan", aktif: tahap === "selesai" },
            ].map((l) => (
              <li key={l.n}
                  className={`rounded-sm border px-2.5 py-2 ${l.aktif
                    ? "border-[#FF1313] bg-[#FFF1F1] text-[#1D2434] font-semibold"
                    : "border-[#E4E5E8] bg-white text-[#64676C]"}`}>
                <span className={`mr-1.5 inline-flex h-4 w-4 items-center justify-center
                                  rounded-full text-[10px] ${l.aktif
                    ? "bg-[#FF1313] text-white" : "bg-[#EDEFF2] text-[#64676C]"}`}>
                  {l.n}
                </span>
                {l.teks}
              </li>
            ))}
          </ol>

          {/* ---------------------------------------------- langkah 1: pilih */}
          {tahap === "pilih" && (
            <>
              <div className="grid sm:grid-cols-2 gap-3 mb-4 text-xs text-[#64676C]">
                <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                  <p className="font-semibold text-[#1D2434] mb-1">
                    1. Tiket intake — ekspor "Master Data"
                  </p>
                  Langsung dari aplikasi internal (judul di baris 1–4, header baris 7,
                  boleh beberapa sheet tahun sekaligus). Baris subtotal otomatis
                  dibuang; vendor/DRC/wilayah divalidasi.
                </div>
                <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                  <p className="font-semibold text-[#1D2434] mb-1">
                    2. Data berkala — format template
                  </p>
                  File berisi sheet: Pembelian_Harian, Stok_Harian, SICOM_Harian,
                  Kurs, Target_Margin, Parameter_Pabrik, Perencanaan, Master_Vendor,
                  Master_Grade (boleh sebagian saja, mis. hanya Stok_Harian).
                </div>
              </div>

              <div
                className={`rounded-sm border-2 border-dashed p-10 text-center cursor-pointer
                            transition-colors ${sedangProses ? "pointer-events-none opacity-60"
                              : seret
                                ? "border-[#FF1313] bg-[#FFF1F1]"
                                : "border-[#E4E5E8] bg-[#F8F8F8] hover:bg-[#FFF1F1]"}`}
                onClick={() => inputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setSeret(true); }}
                onDragLeave={() => setSeret(false)}
                onDrop={(e) => {
                  e.preventDefault(); setSeret(false);
                  if (!sedangProses) pilihFile(e.dataTransfer.files?.[0]);
                }}
              >
                <p className="text-3xl mb-2">⬆</p>
                <p className="text-sm text-[#1D2434] font-medium">
                  {sedangProses
                    ? "Sedang memproses file…"
                    : "Tarik & lepas file .xlsx ke sini, atau klik untuk memilih"}
                </p>
                <p className="mt-1 text-xs text-[#64676C]">
                  Hanya .xlsx, maksimal 20 MB. Jenis file dikenali otomatis. File
                  yang sama diunggah dua kali tidak menggandakan data.
                </p>
                <input ref={inputRef} type="file" accept=".xlsx" className="hidden"
                       onChange={(e) => {
                         const f = e.target.files?.[0];
                         e.target.value = "";
                         if (f && !sedangProses) pilihFile(f);
                       }} />
              </div>

              {proses && <BilahProgres proses={proses} />}
              {galat && <Pesan jenis="error" teks={galat} />}
            </>
          )}

          {/* ------------------------------------------- langkah 2: pratinjau */}
          {tahap === "pratinjau" && pratinjau && (
            <>
              <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                <p className="text-sm font-semibold text-[#1D2434]">
                  {pratinjau.jenis} — {pratinjau.nama_file}
                </p>
                <p className="mt-1 text-xs text-[#64676C]">
                  Belum ada satu baris pun yang masuk database. Periksa angkanya,
                  lalu tekan <b>Konfirmasi simpan ke database</b> di bagian bawah.
                  Pratinjau berlaku {pratinjau.kedaluwarsa_menit ?? 60} menit.
                </p>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-sm border border-[#E4E5E8] bg-white p-3">
                  <p className="text-xs text-[#64676C]">Siap disimpan</p>
                  <p className="text-lg font-semibold text-[#1D2434]">
                    {fmtAngka(pratinjau.total_jumlah ?? 0, 0)} baris
                  </p>
                </div>
                <div className={`rounded-sm border p-3 ${(pratinjau.total_ditolak ?? 0) > 0
                  ? "border-[#FECACA] bg-[#FEF2F2]" : "border-[#E4E5E8] bg-white"}`}>
                  <p className="text-xs text-[#64676C]">Bermasalah (tidak dimasukkan)</p>
                  <p className={`text-lg font-semibold ${(pratinjau.total_ditolak ?? 0) > 0
                    ? "text-[#B91C1C]" : "text-[#1D2434]"}`}>
                    {fmtAngka(pratinjau.total_ditolak ?? 0, 0)} baris
                  </p>
                </div>
              </div>

              <DaftarAngka jumlah={pratinjau.jumlah ?? {}} />

              {pratinjau.duplikat_file && (
                <p className="mt-3 rounded-sm border border-[#FDE68A] bg-[#FFFBEB] px-3 py-2 text-xs text-[#B45309]">
                  File ini sama persis dengan file yang pernah diunggah. Bila
                  dikonfirmasi, data lama akan diperbarui (tidak digandakan).
                </p>
              )}

              {(pratinjau.total_ditolak ?? 0) > 0 && (
                <>
                  <div className="mt-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-[#B91C1C]">
                        Data mismatch — {(pratinjau.jumlah_mismatch ?? 0)} baris tidak
                        akan dimasukkan
                      </p>
                      <UnduhMismatch token={pratinjau.token}
                                     jumlah={pratinjau.jumlah_mismatch ?? 0} />
                    </div>
                    <p className="mt-1 text-xs text-[#64676C]">
                      Unduh Excelnya, perbaiki baris yang ditandai (alasan tertulis di
                      kolom paling kanan), lalu unggah ulang — baris lain tidak perlu
                      diulang. Sisa file tetap bisa disimpan sekarang.
                    </p>
                    <TabelMismatch daftar={pratinjau.mismatch ?? []}
                                   jumlah={pratinjau.jumlah_mismatch ?? 0} />
                  </div>
                </>
              )}

              {(pratinjau.jumlah_peringatan ?? 0) > 0 && (
                <details className="mt-3 rounded-sm border border-[#FDE68A] bg-[#FFFBEB] px-3 py-2">
                  <summary className="cursor-pointer text-xs font-semibold text-[#B45309]">
                    {pratinjau.jumlah_peringatan} catatan pemeriksaan — barisnya tetap
                    dimuat, hanya perlu dicek
                  </summary>
                  <ul className="mt-2 list-disc pl-5 text-xs text-[#92400E] max-h-72 overflow-y-auto">
                    {(pratinjau.peringatan ?? []).map((p: string, i: number) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </details>
              )}

              {proses && <BilahProgres proses={proses} />}
              {galat && <Pesan jenis="error" teks={galat} />}

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <button className={kelasTombol} onClick={konfirmasi}
                        disabled={sedangProses || (pratinjau.total_jumlah ?? 0) === 0}>
                  Konfirmasi simpan ke database
                </button>
                <button className={kelasTombolKecil} onClick={() => batal()}
                        disabled={sedangProses}>
                  Batalkan, jangan simpan
                </button>
                {(pratinjau.total_jumlah ?? 0) === 0 && (
                  <span className="text-xs text-[#B91C1C]">
                    Tidak ada baris yang bisa disimpan — perbaiki file lalu unggah ulang.
                  </span>
                )}
              </div>
            </>
          )}

          {/* --------------------------------------------- langkah 3: selesai */}
          {tahap === "selesai" && selesai && (
            <>
              <Pesan jenis="sukses"
                     teks={`${selesai.jenis} — ${selesai.nama_file} (unggahan #${selesai.unggahan_id}). ${selesai.pesan}`} />
              <DaftarAngka jumlah={selesai.jumlah ?? {}} />

              {(selesai.total_ditolak ?? 0) > 0 && selesai.mismatch_tersedia && (
                <div className="mt-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-[#B91C1C]">
                      {selesai.jumlah_mismatch} baris tidak masuk database
                    </p>
                    <UnduhMismatch token={selesai.token}
                                   jumlah={selesai.jumlah_mismatch ?? 0} />
                  </div>
                  <p className="mt-1 text-xs text-[#64676C]">
                    Perbaiki baris tersebut di Excel, lalu unggah ulang filenya —
                    data yang sudah masuk tidak akan tergandakan.
                  </p>
                  <TabelMismatch daftar={selesai.mismatch ?? []}
                                 jumlah={selesai.jumlah_mismatch ?? 0} />
                </div>
              )}

              {(selesai.jumlah_peringatan ?? 0) > 0 && (
                <details className="mt-3 rounded-sm border border-[#FDE68A] bg-[#FFFBEB] px-3 py-2">
                  <summary className="cursor-pointer text-xs font-semibold text-[#B45309]">
                    {selesai.jumlah_peringatan} catatan pemeriksaan — klik untuk lihat
                  </summary>
                  <ul className="mt-2 list-disc pl-5 text-xs text-[#92400E] max-h-72 overflow-y-auto">
                    {(selesai.peringatan ?? []).map((p: string, i: number) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </details>
              )}

              <div className="mt-4">
                <button className={kelasTombolKecil} onClick={() => batal()}>
                  Unggah file lain
                </button>
              </div>
            </>
          )}

          <p className="mt-4 text-xs text-[#64676C]">
            SICOM & kurs harian tetap paling cepat lewat tab <b>Input Harian</b>.
            Amount pembelian per hari adalah hasil kalkulasi total pembayaran getah
            intake per hari dari aplikasi internal — unggah filenya di sini. Setiap
            unggahan tercatat (siapa, kapan, file apa) dan bisa ditelusuri dari
            angka mana pun.
          </p>
        </>
      } />
    </div>
  );
}
