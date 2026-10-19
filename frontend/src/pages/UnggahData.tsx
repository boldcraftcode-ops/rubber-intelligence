import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Kartu, Pesan, fmtAngka, urlApi } from "../bersama";

const pengisi = () => localStorage.getItem("op-margin.pengisi") || "?";

const NAMA_TABEL: Record<string, string> = {
  tiket_baris: "Baris tiket",
  pembelian: "Pembelian",
  sicom: "SICOM",
  kurs: "Kurs",
  stok: "Stok",
  parameter_pabrik: "Parameter pabrik",
  target_margin: "Target margin",
  perencanaan: "Perencanaan",
  vendor: "Vendor",
  grade: "Grade",
  aturan_stok_harga: "Aturan stok→harga",
};

export default function UnggahData() {
  const qc = useQueryClient();
  const [hasil, setHasil] = useState<any | null>(null);
  const [galat, setGalat] = useState<string | null>(null);
  const [seret, setSeret] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const kirim = useMutation({
    mutationFn: async (file: File) => {
      const data = new FormData();
      data.append("file", file);
      data.append("pengisi", pengisi());
      const r = await fetch(urlApi("/api/unggah"), {
        method: "POST", body: data, credentials: "include",
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail ?? "Gagal mengunggah.");
      return j;
    },
    onSuccess: (j) => {
      setHasil(j); setGalat(null);
      qc.invalidateQueries(); // semua angka di aplikasi menyegarkan diri
    },
    onError: (e: Error) => { setGalat(e.message); setHasil(null); },
  });

  const pilihFile = (f: File | undefined | null) => {
    if (!f) return;
    setHasil(null); setGalat(null);
    kirim.mutate(f);
  };

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="unggah" judul="Unggah file data"
             keterangan="Format mengikuti file yang sudah Anda pakai — tidak perlu diubah. Hanya .xlsx, maksimal 20 MB."
             anak={
        <>
          <div className="grid sm:grid-cols-2 gap-3 mb-4 text-xs text-slate-400">
            <div className="rounded-lg border border-violet-500/20 bg-white/5 p-3">
              <p className="font-semibold text-slate-200 mb-1">
                1. Tiket intake — ekspor "Master Data"
              </p>
              Langsung dari aplikasi internal (judul di baris 1–4, header baris 7,
              boleh beberapa sheet tahun sekaligus). Baris subtotal otomatis
              dibuang; vendor/DRC/wilayah divalidasi.
            </div>
            <div className="rounded-lg border border-violet-500/20 bg-white/5 p-3">
              <p className="font-semibold text-slate-200 mb-1">
                2. Data berkala — format template
              </p>
              File berisi sheet: Pembelian_Harian, Stok_Harian, SICOM_Harian,
              Kurs, Target_Margin, Parameter_Pabrik, Perencanaan, Master_Vendor,
              Master_Grade (boleh sebagian saja, mis. hanya Stok_Harian).
            </div>
          </div>

          <div
            className={`rounded-xl border-2 border-dashed p-10 text-center cursor-pointer
                        transition-colors ${seret
                          ? "border-violet-400 bg-violet-500/20"
                          : "border-violet-500/30 bg-white/5 hover:bg-violet-500/10"}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setSeret(true); }}
            onDragLeave={() => setSeret(false)}
            onDrop={(e) => {
              e.preventDefault(); setSeret(false);
              pilihFile(e.dataTransfer.files?.[0]);
            }}
          >
            <p className="text-3xl mb-2">⬆</p>
            <p className="text-sm text-slate-200 font-medium">
              {kirim.isPending
                ? "Mengunggah & memvalidasi… (file besar bisa 1–2 menit)"
                : "Tarik & lepas file .xlsx ke sini, atau klik untuk memilih"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Jenis file dikenali otomatis. Mengunggah file yang sama dua kali
              tidak menggandakan data.
            </p>
            <input ref={inputRef} type="file" accept=".xlsx" className="hidden"
                   onChange={(e) => { pilihFile(e.target.files?.[0]); e.target.value = ""; }} />
          </div>

          {galat && <Pesan jenis="error" teks={galat} />}

          {hasil && (
            <div className="mt-4">
              <Pesan jenis="sukses"
                     teks={`${hasil.jenis} — ${hasil.nama_file} (unggahan #${hasil.unggahan_id}). ${hasil.pesan}`} />
              <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
                {Object.entries(hasil.jumlah ?? {})
                  .filter(([, v]) => (v as number) > 0)
                  .map(([k, v]) => (
                  <div key={k} className="rounded-lg border border-violet-500/20 bg-white/5 p-2.5">
                    <p className="text-xs text-slate-400">{NAMA_TABEL[k] ?? k}</p>
                    <p className="font-semibold text-slate-100">{fmtAngka(v as number, 0)} baris</p>
                  </div>
                ))}
              </div>
              {Object.keys(hasil.ditolak ?? {}).length > 0 && (
                <p className="mt-3 rounded-md bg-red-500/10 border border-red-400/30 px-3 py-2 text-xs text-red-300">
                  Baris DITOLAK:{" "}
                  {Object.entries(hasil.ditolak).map(([s, n]) => `${s}: ${n}`).join(" · ")}
                  {" "}— rincian & cara memperbaiki ada di daftar peringatan di bawah.
                </p>
              )}
              {hasil.jumlah_peringatan > 0 && (
                <details className="mt-3 rounded-md border border-amber-400/30 bg-amber-400/10 px-3 py-2">
                  <summary className="cursor-pointer text-xs font-semibold text-amber-300">
                    {hasil.jumlah_peringatan} peringatan — klik untuk lihat
                    {hasil.jumlah_peringatan > hasil.peringatan.length &&
                      ` (${hasil.peringatan.length} pertama ditampilkan; lengkapnya di tab Kualitas Data)`}
                  </summary>
                  <ul className="mt-2 list-disc pl-5 text-xs text-amber-200/90 max-h-72 overflow-y-auto">
                    {hasil.peringatan.map((p: string, i: number) => <li key={i}>{p}</li>)}
                  </ul>
                </details>
              )}
            </div>
          )}

          <p className="mt-4 text-xs text-slate-500">
            SICOM & kurs harian tetap paling cepat lewat tab <b>Input Harian</b>.
            Amount pembelian per hari adalah hasil kalkulasi total pembayaran
            getah intake per hari dari aplikasi internal — unggah filenya di sini.
            Setiap unggahan tercatat (siapa, kapan, file apa) dan bisa ditelusuri
            dari angka mana pun.
          </p>
        </>
      } />
    </div>
  );
}
