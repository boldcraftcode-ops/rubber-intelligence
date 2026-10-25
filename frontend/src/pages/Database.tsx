import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, Pesan, fmtAngka, kelasInput, kelasTombol, kelasTombolKecil,
  kirimJson, ambilJson, urlApi,
} from "../bersama";

const pengisi = () => localStorage.getItem("op-margin.pengisi") || "?";

const NAMA_TABEL: Record<string, string> = {
  raw_unggahan: "Riwayat unggahan (raw)",
  raw_baris: "Baris mentah (raw)",
  vendor: "Vendor",
  grade: "Grade",
  tiket_baris: "Baris tiket intake",
  pembelian: "Pembelian",
  sicom: "SICOM",
  kurs: "Kurs",
  stok: "Stok",
  parameter_pabrik: "Parameter pabrik",
  aturan_stok_harga: "Aturan stok→harga",
  target_margin: "Target margin",
  perencanaan: "Perencanaan",
  peringatan_data: "Peringatan data",
  harga_grade: "Harga per grade",
  audit_log: "Audit log",
  pengaturan_alarm: "Pengaturan alarm",
  alarm: "Alarm aktif",
  mart_harian: "Mart harian",
  mart_bulanan: "Mart bulanan",
};

/* Panduan "mulai dari nol": ditampilkan saat database kosong */
const PANDUAN: { langkah: string; dimana: string; wajib: string }[] = [
  { langkah: "Unggah file template (Pembelian_Harian, Stok_Harian, SICOM_Harian, Kurs, Parameter_Pabrik, Target_Margin, Master_Vendor, Master_Grade — boleh sebagian)",
    dimana: "tab Unggah Data", wajib: "Wajib — sumber data utama" },
  { langkah: "Unggah ekspor \"Master Data\" tiket intake dari aplikasi internal",
    dimana: "tab Unggah Data", wajib: "Wajib untuk rekonsiliasi & kualitas" },
  { langkah: "Isi harga SICOM & kurs harian secara cepat",
    dimana: "tab Input Harian", wajib: "Wajib untuk margin harian" },
  { langkah: "Isi parameter pabrik (kapasitas, safety stock) bila belum ada di template",
    dimana: "tab Aturan Harga", wajib: "Wajib untuk Days & rasio stok" },
  { langkah: "Susun aturan stok→harga (penyesuaian target per rentang rasio)",
    dimana: "tab Aturan Harga", wajib: "Wajib untuk rekomendasi harga" },
  { langkah: "Isi penyesuaian manual & effort untuk tahun depan",
    dimana: "tab Perencanaan", wajib: "Opsional" },
  { langkah: "Isi harga beli indikatif per grade",
    dimana: "tab Grade & Harga", wajib: "Opsional" },
];

export default function Database() {
  const qc = useQueryClient();
  const info = useQuery({
    queryKey: ["db-info"],
    queryFn: () => ambilJson("/api/database/info"),
  });

  const [pesan, setPesan] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);
  const [bukaKosongkan, setBukaKosongkan] = useState(false);
  const [ketik, setKetik] = useState("");
  const inputImpor = useRef<HTMLInputElement>(null);

  const selesai = (teks: string) => {
    setPesan({ jenis: "sukses", teks });
    qc.invalidateQueries(); // semua angka aplikasi menyegarkan diri
  };
  const gagal = (e: Error) => setPesan({ jenis: "error", teks: e.message });

  const kosongkan = useMutation({
    mutationFn: () => kirimJson("/api/database/kosongkan",
      { konfirmasi: ketik, pengisi: pengisi() }),
    onSuccess: (j) => { setBukaKosongkan(false); setKetik(""); selesai(j.pesan); },
    onError: gagal,
  });

  const impor = useMutation({
    mutationFn: async (file: File) => {
      const data = new FormData();
      data.append("file", file);
      data.append("pengisi", pengisi());
      const r = await fetch(urlApi("/api/database/impor"), {
        method: "POST", body: data, credentials: "include",
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail ?? "Gagal mengimpor database.");
      return j;
    },
    onSuccess: (j) => selesai(j.pesan),
    onError: gagal,
  });

  const jumlah: Record<string, number> = info.data?.jumlah ?? {};
  const kosong = info.data?.kosong ?? false;

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="database" judul="Database"
             keterangan="Kelola isi database: lihat jumlah data, ekspor cadangan, impor cadangan, atau kosongkan untuk mulai dari nol."
             anak={
        <>
          {/* ---- ringkasan isi ---- */}
          {info.isLoading && <p className="text-sm text-[#64676C]">Memuat info database…</p>}
          {info.error && <Pesan jenis="error" teks={(info.error as Error).message} />}
          {info.data && (
            <>
              <p className="text-sm text-[#1D2434] mb-3">
                Jenis: <b className="text-[#1D2434]">{info.data.jenis}</b>
                {info.data.ukuran_kb != null && (
                  <> · Ukuran file: <b className="text-[#1D2434]">
                    {fmtAngka(info.data.ukuran_kb, 1)} KB</b></>
                )}
                {" "}· Total baris: <b className="text-[#1D2434]">
                  {fmtAngka(info.data.total_baris, 0)}</b>
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {Object.entries(jumlah).map(([k, v]) => (
                  <div key={k}
                       className={`rounded-sm border p-2.5 ${v > 0
                         ? "border-[#E4E5E8] bg-[#F8F8F8]"
                         : "border-[#EDEFF2] bg-[#FAFAFB] opacity-60"}`}>
                    <p className="text-xs text-[#64676C]">{NAMA_TABEL[k] ?? k}</p>
                    <p className="font-semibold text-[#1D2434]">{fmtAngka(v, 0)} baris</p>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ---- aksi ---- */}
          <div className="mt-5 grid sm:grid-cols-3 gap-3">
            <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-4">
              <p className="font-semibold text-[#1D2434] text-sm mb-1">⬇ Ekspor database</p>
              <p className="text-xs text-[#64676C] mb-3">
                Unduh seluruh database sebagai satu file .db — untuk cadangan
                atau dipindah ke komputer lain.
              </p>
              <a className={kelasTombolKecil} href={urlApi("/api/database/ekspor")}>
                Unduh file .db
              </a>
            </div>

            <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-4">
              <p className="font-semibold text-[#1D2434] text-sm mb-1">⬆ Impor database</p>
              <p className="text-xs text-[#64676C] mb-3">
                Ganti seluruh isi dengan file .db hasil ekspor. Database lama
                otomatis dicadangkan dulu di folder <code>cadangan/</code>.
              </p>
              <button className={kelasTombolKecil} disabled={impor.isPending}
                      onClick={() => inputImpor.current?.click()}>
                {impor.isPending ? "Mengimpor…" : "Pilih file .db"}
              </button>
              <input ref={inputImpor} type="file" accept=".db" className="hidden"
                     onChange={(e) => {
                       const f = e.target.files?.[0];
                       if (f) { setPesan(null); impor.mutate(f); }
                       e.target.value = "";
                     }} />
            </div>

            <div className="rounded-sm border border-[#FECACA] bg-red-500/5 p-4">
              <p className="font-semibold text-[#B91C1C] text-sm mb-1">⚠ Kosongkan database</p>
              <p className="text-xs text-[#64676C] mb-3">
                Hapus SEMUA data (cadangan otomatis dibuat dulu). Aplikasi
                kembali seperti baru dipasang.
              </p>
              <button
                className="rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-2.5 py-1 text-xs font-medium text-[#B91C1C] hover:bg-[#FEE2E2]"
                onClick={() => { setPesan(null); setBukaKosongkan(true); }}>
                Kosongkan…
              </button>
            </div>
          </div>

          {pesan && <Pesan jenis={pesan.jenis} teks={pesan.teks} />}

          {/* ---- panduan mulai dari nol ---- */}
          <details className="mt-5 rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-4"
                     open={kosong}>
              <summary className="cursor-pointer text-sm font-semibold text-[#FF1313]">
                🧭 Mulai dari database kosong — di mana saya input data?
              </summary>
              <table className="mt-3 w-full text-xs">
                <thead>
                  <tr className="text-left text-[#64676C] border-b border-[#E4E5E8]">
                    <th className="py-1.5 pr-2">Data yang diisi</th>
                    <th className="py-1.5 pr-2">Di mana</th>
                    <th className="py-1.5">Keterangan</th>
                  </tr>
                </thead>
                <tbody>
                  {PANDUAN.map((p, i) => (
                    <tr key={i} className="border-b border-[#EDEFF2] align-top">
                      <td className="py-1.5 pr-2 text-[#1D2434]">{p.langkah}</td>
                      <td className="py-1.5 pr-2 font-semibold text-[#FF1313] whitespace-nowrap">{p.dimana}</td>
                      <td className="py-1.5 text-[#64676C]">{p.wajib}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-xs text-[#64676C]">
                Setelah data masuk, Margin Performance / Intake Analisis / Stok / Alarm terisi
                otomatis — mart & alarm dihitung ulang setiap ada data baru.
              </p>
            </details>
        </>
      } />

      {/* ---- modal konfirmasi kosongkan ---- */}
      {bukaKosongkan && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
             onClick={() => setBukaKosongkan(false)}>
          <div className="w-full max-w-md rounded-sm bg-white border border-[#FECACA] p-6 shadow-2xl"
               onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-[#B91C1C] mb-2">
              ⚠ Kosongkan seluruh database?
            </h3>
            <p className="text-sm text-[#1D2434]">
              Semua data (unggahan, tiket, pembelian, SICOM, kurs, stok, aturan,
              target, perencanaan, audit) akan dihapus. Cadangan otomatis dibuat
              dulu, tetapi pastikan Anda juga sudah <b>Ekspor database</b> bila perlu.
            </p>
            <label className="block text-xs text-[#64676C] mt-4 mb-1">
              Ketik <b className="text-[#B91C1C]">KOSONGKAN</b> untuk melanjutkan:
            </label>
            <input className={kelasInput} value={ketik} autoFocus
                   onChange={(e) => setKetik(e.target.value)}
                   placeholder="KOSONGKAN" />
            <div className="mt-4 flex gap-2 justify-end">
              <button className={kelasTombolKecil}
                      onClick={() => { setBukaKosongkan(false); setKetik(""); }}>
                Batal
              </button>
              <button
                className="rounded-sm bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-40"
                disabled={ketik.trim().toUpperCase() !== "KOSONGKAN" || kosongkan.isPending}
                onClick={() => kosongkan.mutate()}>
                {kosongkan.isPending ? "Menghapus…" : "Ya, hapus semua data"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
