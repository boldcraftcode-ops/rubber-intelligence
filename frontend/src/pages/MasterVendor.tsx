import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, Pesan, ambilJson, fmtAngka, fmtTanggal,
  kelasInput, kelasLabel, kelasTombol, kelasTombolKecil, kirimMetode, urlApi,
} from "../bersama";

const pengisi = () => {
  try { return localStorage.getItem("op-margin.pengisi") || "?"; } catch { return "?"; }
};

const KOSONG = { kode: "", nama_baku: "", varian_nama: "", kategori: "", status: "aktif" };

const WARNA_STATUS: Record<string, string> = {
  aktif: "bg-[#ECFDF5] text-[#166534] border-[#A7F3D0]",
  nonaktif: "bg-[#F3F4F6] text-[#4B5563] border-[#E5E7EB]",
  diblokir: "bg-[#FEF2F2] text-[#B91C1C] border-[#FECACA]",
};

/* ================= daftar + form (CRUD) ================= */
export function KartuDaftarVendor() {
  const qc = useQueryClient();
  const [cari, setCari] = useState("");
  const [saring, setSaring] = useState("");
  const [form, setForm] = useState({ ...KOSONG });
  const [ubahKode, setUbahKode] = useState<string | null>(null);
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  const params = new URLSearchParams();
  if (cari.trim()) params.set("q", cari.trim());
  if (saring) params.set("status", saring);
  const url = `/api/vendor${params.toString() ? `?${params.toString()}` : ""}`;
  const q = useQuery({ queryKey: ["vendor", url], queryFn: () => ambilJson(url) });

  const segarkan = () => {
    qc.invalidateQueries({ queryKey: ["vendor"] });
    qc.invalidateQueries({ queryKey: ["penerimaan"] });
    qc.invalidateQueries({ queryKey: ["tonase"] });
    qc.invalidateQueries({ queryKey: ["intake-terakhir"] });
  };

  const simpan = useMutation({
    mutationFn: () => ubahKode
      ? kirimMetode(`/api/vendor/${encodeURIComponent(ubahKode)}`, "PUT", {
          nama_baku: form.nama_baku, varian_nama: form.varian_nama || null,
          kategori: form.kategori || null, status: form.status, pengisi: pengisi(),
        })
      : kirimMetode("/api/vendor", "POST", { ...form, pengisi: pengisi() }),
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      setForm({ ...KOSONG });
      setUbahKode(null);
      segarkan();
    },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });

  const hapus = useMutation({
    mutationFn: (kode: string) =>
      kirimMetode(`/api/vendor/${encodeURIComponent(kode)}`
        + `?paksa=true&pengisi=${encodeURIComponent(pengisi())}`, "DELETE"),
    onSuccess: (d) => { setInfo({ jenis: "sukses", teks: d.pesan }); segarkan(); },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });

  const mulaiUbah = (b: any) => {
    setUbahKode(b.kode);
    setForm({ kode: b.kode, nama_baku: b.nama_baku, varian_nama: b.varian_nama ?? "",
              kategori: b.kategori ?? "", status: b.status ?? "aktif" });
    setInfo(null);
  };

  /* Hapus dua langkah: klik Hapus -> tombol konfirmasi. Vendor yang sudah
     dipakai tiket tetap ditolak server; tombol kedua dinamai jelas. */
  const [konfirmasi, setKonfirmasi] = useState<string | null>(null);

  return (
    <Kartu idMetrik="master_vendor" judul="Daftar vendor"
           keterangan="Kode vendor adalah kunci yang dipakai tiket intake dan pembelian. Menambah/mengubah di sini langsung berlaku; riwayat lama tidak berubah."
           anak={
      <>
        <div className="mb-3 flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-48">
            <label className={kelasLabel}>Cari</label>
            <input className={kelasInput} placeholder="kode, nama, varian, atau kategori"
                   value={cari} onChange={(e) => setCari(e.target.value)} />
          </div>
          <div>
            <label className={kelasLabel}>Status</label>
            <select className={kelasInput + " min-w-36"} value={saring}
                    onChange={(e) => setSaring(e.target.value)}>
              <option value="">Semua status</option>
              {(q.data?.status_baku ?? ["aktif", "nonaktif", "diblokir"]).map((s: string) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <p className="pb-2 text-xs text-[#64676C]">
            {q.data ? `${q.data.jumlah} dari ${q.data.jumlah_total} vendor` : "memuat…"}
          </p>
        </div>

        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-white">
              <tr className="text-left text-[#64676C] border-b">
                <th className="py-1">Kode</th><th>Nama baku</th><th>Varian nama</th>
                <th>Kategori</th><th>Status</th>
                <th className="text-right">Tiket</th>
                <th className="text-right">Ton kering</th>
                <th>Intake terakhir</th><th></th>
              </tr>
            </thead>
            <tbody>
              {q.data?.baris.map((b: any) => (
                <tr key={b.kode} className="border-b border-[#EDEFF2]">
                  <td className="py-1.5 font-mono text-[#1D2434]">{b.kode}</td>
                  <td className="text-[#1D2434]">{b.nama_baku}</td>
                  <td className="max-w-40 truncate text-[#64676C]" title={b.varian_nama ?? ""}>
                    {b.varian_nama ?? "–"}
                  </td>
                  <td className="text-[#64676C]">{b.kategori ?? "–"}</td>
                  <td>
                    <span className={`rounded-sm border px-1.5 py-0.5 text-[10px] ${WARNA_STATUS[b.status] ?? WARNA_STATUS.nonaktif}`}>
                      {b.status}
                    </span>
                  </td>
                  <td className="text-right font-mono">{fmtAngka(b.jumlah_tiket, 0)}</td>
                  <td className="text-right font-mono">{fmtAngka(b.ton_kering, 3)}</td>
                  <td className="text-[#64676C]">
                    {b.intake_terakhir ? fmtTanggal(b.intake_terakhir) : "belum pernah"}
                  </td>
                  <td className="whitespace-nowrap text-right">
                    <button className={`${kelasTombolKecil} mr-1`} onClick={() => mulaiUbah(b)}>
                      ubah
                    </button>
                    {konfirmasi === b.kode ? (
                      <>
                        <button className={`${kelasTombolKecil} mr-1 border-[#DC2626] text-[#B91C1C]`}
                                disabled={hapus.isPending}
                                onClick={() => { hapus.mutate(b.kode); setKonfirmasi(null); }}>
                          ya, hapus
                        </button>
                        <button className={kelasTombolKecil}
                                onClick={() => setKonfirmasi(null)}>batal</button>
                      </>
                    ) : (
                      <button className={`${kelasTombolKecil} border-[#FECACA] text-[#B91C1C]`}
                              onClick={() => { setInfo(null); setKonfirmasi(b.kode); }}>
                        hapus
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {q.data?.baris.length === 0 && (
                <tr><td colSpan={9} className="py-3 text-[#64676C]">
                  Tidak ada vendor yang cocok. Kosongkan pencarian, atau tambahkan
                  vendor baru di bawah.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>

        <p className="mt-2 text-[11px] text-[#64676C]">
          Vendor yang sudah dipakai tiket tidak bisa dihapus begitu saja — server
          menolak agar tonase tidak kehilangan pemiliknya. Jalankan lewat status
          <b> nonaktif</b>. Tombol “ya, hapus” mengirim hapus paksa dan tetap
          tercatat di audit.
        </p>

        <h3 className="mt-5 mb-2 text-sm font-semibold text-[#1D2434]">
          {ubahKode ? `Ubah vendor ${ubahKode}` : "Tambah vendor baru"}
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-6 gap-2 items-end">
          <div>
            <label className={kelasLabel}>Kode vendor</label>
            <input className={`${kelasInput} font-mono ${ubahKode ? "bg-[#F8F8F8] text-[#64676C]" : ""}`}
                   placeholder="mis. V005" value={form.kode} disabled={Boolean(ubahKode)}
                   onChange={(e) => setForm({ ...form, kode: e.target.value.toUpperCase() })} />
          </div>
          <div className="sm:col-span-2">
            <label className={kelasLabel}>Nama baku</label>
            <input className={kelasInput} placeholder="mis. PT Karet Nusantara"
                   value={form.nama_baku}
                   onChange={(e) => setForm({ ...form, nama_baku: e.target.value })} />
          </div>
          <div>
            <label className={kelasLabel}>Kategori</label>
            <input className={kelasInput} placeholder="nasional / lokal"
                   value={form.kategori}
                   onChange={(e) => setForm({ ...form, kategori: e.target.value })} />
          </div>
          <div>
            <label className={kelasLabel}>Status</label>
            <select className={kelasInput} value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value })}>
              {["aktif", "nonaktif", "diblokir"].map((s) => (
                <option key={s} value={s}>{s}</option>))}
            </select>
          </div>
          <button className={kelasTombol} disabled={simpan.isPending
                    || !form.kode.trim() || !form.nama_baku.trim()}
                  onClick={() => { setInfo(null); simpan.mutate(); }}>
            {ubahKode ? "Simpan perubahan" : "Tambah vendor"}
          </button>
        </div>
        <div className="mt-2">
          <label className={kelasLabel}>Varian nama (nama lain di tiket, pisahkan dengan |)</label>
          <input className={kelasInput} placeholder="mis. PT Karet Nusantara|CV Karet Nusantara"
                 value={form.varian_nama}
                 onChange={(e) => setForm({ ...form, varian_nama: e.target.value })} />
        </div>
        {ubahKode && (
          <button className={`${kelasTombolKecil} mt-2`}
                  onClick={() => { setUbahKode(null); setForm({ ...KOSONG }); setInfo(null); }}>
            batal ubah — kembali ke tambah baru
          </button>
        )}
        {info && <Pesan jenis={info.jenis} teks={info.teks} />}
      </>
    } />
  );
}

/* ================= bulk import ================= */
export function KartuBulkVendor() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [hasil, setHasil] = useState<any>(null);
  const [galat, setGalat] = useState<string | null>(null);

  const unggah = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("pengisi", pengisi());
      return kirimMetode("/api/vendor/impor", "POST", fd);
    },
    onSuccess: (d) => {
      setHasil(d); setGalat(null);
      qc.invalidateQueries({ queryKey: ["vendor"] });
    },
    onError: (e: Error) => { setGalat(e.message); setHasil(null); },
  });

  const pilih = (f: File | undefined | null) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".xlsx")) {
      setGalat(`File '${f.name}' bukan .xlsx. Simpan ulang sebagai .xlsx lalu unggah lagi.`);
      return;
    }
    setHasil(null); setGalat(null);
    unggah.mutate(f);
  };

  return (
    <Kartu idMetrik="master_vendor" judul="Bulk import vendor (Excel)"
           keterangan="Unduh template, isi/tambah baris di Excel, lalu unggah kembali. Kode yang sudah ada DIPERBARUI, bukan digandakan."
           anak={
      <>
        <div className="flex flex-wrap items-center gap-2">
          <a className={kelasTombol} href={urlApi("/api/vendor/template")}>
            ⬇ Unduh template
          </a>
          <button className={kelasTombolKecil} disabled={unggah.isPending}
                  onClick={() => inputRef.current?.click()}>
            {unggah.isPending ? "Mengimpor…" : "Pilih file .xlsx untuk diimpor"}
          </button>
          <input ref={inputRef} type="file" accept=".xlsx" className="hidden"
                 onChange={(e) => { pilih(e.target.files?.[0]); e.target.value = ""; }} />
          <span className="text-xs text-[#64676C]">
            Template berisi sheet <b>Master_Vendor</b> + sheet Petunjuk. Bisa juga
            diunggah lewat tab <b>Unggah Data</b>.
          </span>
        </div>

        <div
          className={`mt-3 rounded-sm border-2 border-dashed p-6 text-center text-xs cursor-pointer
                      transition-colors ${unggah.isPending
                        ? "border-[#FF1313] bg-[#FFF1F1]"
                        : "border-[#E4E5E8] bg-[#F8F8F8] hover:bg-[#FFF1F1]"}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); pilih(e.dataTransfer.files?.[0]); }}>
          <p className="text-sm text-[#1D2434] font-medium">
            Tarik & lepas file .xlsx ke sini, atau klik untuk memilih
          </p>
          <p className="mt-1 text-[#64676C]">
            Hanya file bersheet Master_Vendor. Baris rusak dilaporkan per baris dan
            tidak membatalkan baris lain.
          </p>
        </div>

        {galat && <Pesan jenis="error" teks={galat} />}

        {hasil && (
          <>
            <Pesan jenis="sukses" teks={`${hasil.nama_file} — ${hasil.pesan}`} />
            <div className="mt-3 grid grid-cols-3 gap-2">
              {[["Vendor baru", hasil.ditambah, "#15803D"],
                ["Diperbarui", hasil.diperbarui, "#1D2434"],
                ["Ditolak", hasil.ditolak, hasil.ditolak ? "#B91C1C" : "#64676C"]].map(
                ([label, nilai, warna]) => (
                  <div key={label as string}
                       className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-2.5">
                    <p className="text-xs text-[#64676C]">{label}</p>
                    <p className="font-semibold" style={{ color: warna as string }}>
                      {fmtAngka(nilai as number, 0)} baris
                    </p>
                  </div>
                ))}
            </div>
            {hasil.peringatan?.length > 0 && (
              <div className="mt-3 max-h-52 overflow-y-auto rounded-sm border border-[#FECACA] bg-[#FEF2F2] p-2">
                <p className="mb-1 text-xs font-semibold text-[#B91C1C]">
                  Baris yang tidak diimpor:
                </p>
                <table className="w-full text-xs">
                  <tbody>
                    {hasil.peringatan.map((p: any, i: number) => (
                      <tr key={i} className="border-b border-[#FECACA]">
                        <td className="py-0.5 pr-2 text-[#B91C1C]">baris {p.baris}</td>
                        <td className="pr-2 font-mono text-[#1D2434]">{p.kode ?? "(kosong)"}</td>
                        <td className="text-[#64676C]">{p.alasan}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </>
    } />
  );
}

export default function MasterVendor() {
  return (
    <div className="grid gap-6">
      <KartuDaftarVendor />
      <KartuBulkVendor />
    </div>
  );
}
