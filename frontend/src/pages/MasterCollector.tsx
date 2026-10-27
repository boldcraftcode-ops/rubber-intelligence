import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, Pesan, ambilJson, fmtAngka, kelasInput, kelasLabel,
  kelasTombol, kelasTombolKecil, kirimMetode, urlApi,
} from "../bersama";

const KOSONG = { kode: "", nama: "", nik: "", no_hp: "", kode_vendor: "",
  provinsi: "", kabupaten_kota: "", desa: "" };
const pengisi = () => {
  try { return localStorage.getItem("op-margin.pengisi") || "?"; } catch { return "?"; }
};

export function KartuDaftarCollector() {
  const qc = useQueryClient();
  const [cari, setCari] = useState("");
  const [form, setForm] = useState({ ...KOSONG });
  const [ubahKode, setUbahKode] = useState<string | null>(null);
  const [konfirmasi, setKonfirmasi] = useState<string | null>(null);
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);
  const param = new URLSearchParams();
  if (cari.trim()) param.set("q", cari.trim());
  const url = `/api/collector${param.toString() ? `?${param}` : ""}`;
  const q = useQuery({ queryKey: ["collector", url], queryFn: () => ambilJson(url) });
  const vendors = useQuery({ queryKey: ["vendor", "pilihan-collector"],
    queryFn: () => ambilJson("/api/vendor") });
  const segarkan = () => {
    qc.invalidateQueries({ queryKey: ["collector"] });
    qc.invalidateQueries({ queryKey: ["vendor"] });
  };
  const simpan = useMutation({
    mutationFn: () => ubahKode
      ? kirimMetode(`/api/collector/${encodeURIComponent(ubahKode)}`, "PUT", {
          nama: form.nama, nik: form.nik || null, no_hp: form.no_hp || null,
          kode_vendor: form.kode_vendor, provinsi: form.provinsi || null,
          kabupaten_kota: form.kabupaten_kota || null, desa: form.desa || null,
          pengisi: pengisi(),
        })
      : kirimMetode("/api/collector", "POST", { ...form, pengisi: pengisi() }),
    onSuccess: (d) => { setInfo({ jenis: "sukses", teks: d.pesan });
      setForm({ ...KOSONG }); setUbahKode(null); segarkan(); },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });
  const hapus = useMutation({
    mutationFn: (kode: string) => kirimMetode(
      `/api/collector/${encodeURIComponent(kode)}?pengisi=${encodeURIComponent(pengisi())}`, "DELETE"),
    onSuccess: (d) => { setInfo({ jenis: "sukses", teks: d.pesan }); segarkan(); },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });
  const mulaiUbah = (b: any) => {
    setUbahKode(b.kode);
    setForm({ kode: b.kode, nama: b.nama, nik: b.nik ?? "", no_hp: b.no_hp ?? "",
      kode_vendor: b.kode_vendor, provinsi: b.provinsi ?? "",
      kabupaten_kota: b.kabupaten_kota ?? "", desa: b.desa ?? "" });
    setInfo(null);
  };

  return <Kartu idMetrik="master_collector" judul="Daftar collector"
    keterangan="Collector adalah perorangan yang terafiliasi ke satu vendor. Wilayah operasional dicatat bertingkat: Provinsi, Kabupaten/Kota, dan Desa."
    anak={<>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1"><label className={kelasLabel}>Cari</label>
          <input className={kelasInput} placeholder="kode, nama, NIK, HP, vendor, wilayah"
            value={cari} onChange={(e) => setCari(e.target.value)} /></div>
        <p className="pb-2 text-xs text-[#64676C]">{q.data
          ? `${fmtAngka(q.data.jumlah, 0)} dari ${fmtAngka(q.data.jumlah_total, 0)} collector`
          : "memuat…"}</p>
      </div>
      {q.isError && <Pesan jenis="error" teks={(q.error as Error).message} />}
      <div className="max-h-96 overflow-auto">
        <table className="w-full min-w-[1050px] text-xs">
          <thead className="sticky top-0 bg-white"><tr className="border-b text-left text-[#64676C]">
            <th className="py-2">Kode</th><th>Nama collector</th><th>NIK</th><th>No HP</th>
            <th>Afiliasi vendor</th><th>Provinsi</th><th>Kabupaten/Kota</th><th>Desa</th><th></th>
          </tr></thead>
          <tbody>{q.data?.baris.map((b: any) => <tr key={b.kode} className="border-b border-[#EDEFF2]">
            <td className="py-2 font-mono text-[#1D2434]">{b.kode}</td>
            <td className="font-medium text-[#1D2434]">{b.nama}</td>
            <td className="font-mono">{b.nik ?? "–"}</td><td>{b.no_hp ?? "–"}</td>
            <td><span className="font-mono">{b.kode_vendor}</span><span className="block text-[10px] text-[#64676C]">{b.nama_vendor}</span></td>
            <td>{b.provinsi ?? "–"}</td><td>{b.kabupaten_kota ?? "–"}</td><td>{b.desa ?? "–"}</td>
            <td className="whitespace-nowrap text-right">
              <button className={`${kelasTombolKecil} mr-1`} onClick={() => mulaiUbah(b)}>ubah</button>
              {konfirmasi === b.kode ? <>
                <button className={`${kelasTombolKecil} mr-1 border-[#DC2626] text-[#B91C1C]`}
                  disabled={hapus.isPending} onClick={() => { hapus.mutate(b.kode); setKonfirmasi(null); }}>ya, hapus</button>
                <button className={kelasTombolKecil} onClick={() => setKonfirmasi(null)}>batal</button>
              </> : <button className={`${kelasTombolKecil} border-[#FECACA] text-[#B91C1C]`}
                onClick={() => { setInfo(null); setKonfirmasi(b.kode); }}>hapus</button>}
            </td>
          </tr>)}
          {q.data?.baris.length === 0 && <tr><td colSpan={9} className="py-4 text-[#64676C]">Belum ada collector yang cocok.</td></tr>}
          </tbody>
        </table>
      </div>
      <h3 className="mt-5 mb-2 text-sm font-semibold text-[#1D2434]">
        {ubahKode ? `Ubah collector ${ubahKode}` : "Tambah collector baru"}</h3>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-4 items-end">
        <div><label className={kelasLabel}>Kode kolektor</label><input className={`${kelasInput} font-mono ${ubahKode ? "bg-[#F8F8F8]" : ""}`}
          placeholder="mis. K001" value={ubahKode ?? form.kode} disabled={Boolean(ubahKode)}
          onChange={(e) => setForm({ ...form, kode: e.target.value.toUpperCase() })} /></div>
        <div><label className={kelasLabel}>Nama kolektor</label><input className={kelasInput} value={form.nama}
          onChange={(e) => setForm({ ...form, nama: e.target.value })} placeholder="nama lengkap" /></div>
        <div><label className={kelasLabel}>NIK <span className="font-normal">(16 angka)</span></label><input className={`${kelasInput} font-mono`}
          inputMode="numeric" maxLength={16} value={form.nik} onChange={(e) => setForm({ ...form, nik: e.target.value.replace(/\D/g, "") })} /></div>
        <div><label className={kelasLabel}>No HP</label><input className={kelasInput} type="tel" value={form.no_hp}
          onChange={(e) => setForm({ ...form, no_hp: e.target.value })} placeholder="mis. 0812…" /></div>
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-4 items-end">
        <div className="sm:col-span-2"><label className={kelasLabel}>Afiliasi Vendor</label>
          <select className={kelasInput} value={form.kode_vendor} onChange={(e) => setForm({ ...form, kode_vendor: e.target.value })}>
            <option value="">Pilih vendor…</option>
            {(vendors.data?.baris ?? []).map((v: any) => <option key={v.kode} value={v.kode}>{v.kode} — {v.nama_baku}</option>)}
          </select></div>
        <div><label className={kelasLabel}>Provinsi</label><input className={kelasInput} value={form.provinsi}
          onChange={(e) => setForm({ ...form, provinsi: e.target.value })} placeholder="mis. Sumatera Utara" /></div>
        <div><label className={kelasLabel}>Kabupaten/Kota</label><input className={kelasInput} value={form.kabupaten_kota}
          onChange={(e) => setForm({ ...form, kabupaten_kota: e.target.value })} placeholder="mis. Kota Medan" /></div>
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-4 items-end">
        <div><label className={kelasLabel}>Desa</label><input className={kelasInput} value={form.desa}
          onChange={(e) => setForm({ ...form, desa: e.target.value })} placeholder="nama desa/kelurahan" /></div>
        <button className={`${kelasTombol} sm:col-span-2`} disabled={simpan.isPending || !form.kode.trim() || !form.nama.trim() || !form.kode_vendor}
          onClick={() => { setInfo(null); simpan.mutate(); }}>{simpan.isPending ? "Menyimpan…" : ubahKode ? "Simpan perubahan" : "Tambah collector"}</button>
        {ubahKode && <button className={kelasTombolKecil} onClick={() => { setUbahKode(null); setForm({ ...KOSONG }); setInfo(null); }}>Batal ubah</button>}
      </div>
      <p className="mt-2 text-[11px] text-[#64676C]">NIK boleh dikosongkan; bila diisi harus 16 angka dan tidak boleh dipakai collector lain. Afiliasi vendor wajib dipilih.</p>
      {info && <Pesan jenis={info.jenis} teks={info.teks} />}
    </>} />;
}

export function KartuBulkCollector() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [hasil, setHasil] = useState<any>(null);
  const [galat, setGalat] = useState<string | null>(null);
  const unggah = useMutation({
    mutationFn: (file: File) => { const fd = new FormData(); fd.append("file", file); fd.append("pengisi", pengisi());
      return kirimMetode("/api/collector/impor", "POST", fd); },
    onSuccess: (d) => { setHasil(d); setGalat(null); qc.invalidateQueries({ queryKey: ["collector"] }); },
    onError: (e: Error) => { setGalat(e.message); setHasil(null); },
  });
  const pilih = (f?: File) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".xlsx")) { setGalat("Pilih file Excel .xlsx."); return; }
    setHasil(null); setGalat(null); unggah.mutate(f);
  };
  return <Kartu idMetrik="bulk_collector" judul="Bulk import collector (Excel)"
    keterangan="Unduh template, isi baris kolektor, lalu unggah. Kode yang sudah ada diperbarui; baris yang tidak valid dilaporkan satu per satu."
    anak={<>
      <div className="flex flex-wrap items-center gap-2">
        <a className={kelasTombol} href={urlApi("/api/collector/template")}>⬇ Unduh template</a>
        <button className={kelasTombolKecil} disabled={unggah.isPending} onClick={() => inputRef.current?.click()}>
          {unggah.isPending ? "Mengimpor…" : "Pilih file .xlsx"}</button>
        <input ref={inputRef} type="file" accept=".xlsx" className="hidden"
          onChange={(e) => { pilih(e.target.files?.[0]); e.target.value = ""; }} />
        <span className="text-xs text-[#64676C]">Sheet <b>Master_Collector</b>. NIK disimpan sebagai teks.</span>
      </div>
      <div className="mt-3 cursor-pointer rounded-sm border-2 border-dashed border-[#E4E5E8] bg-[#F8F8F8] p-5 text-center text-xs hover:bg-[#FFF1F1]"
        onClick={() => inputRef.current?.click()} onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); pilih(e.dataTransfer.files?.[0]); }}>
        Tarik & lepas file .xlsx ke sini, atau klik untuk memilih
      </div>
      {galat && <Pesan jenis="error" teks={galat} />}
      {hasil && <><Pesan jenis="sukses" teks={`${hasil.nama_file} — ${hasil.pesan}`} />
        {hasil.peringatan?.length > 0 && <div className="mt-3 max-h-52 overflow-y-auto rounded-sm border border-[#FECACA] bg-[#FEF2F2] p-2 text-xs">
          <b className="text-[#B91C1C]">Baris yang tidak diimpor:</b>
          {hasil.peringatan.map((p: any, i: number) => <p key={i} className="mt-1 text-[#64676C]">Baris {p.baris} ({p.kode ?? "tanpa kode"}): {p.alasan}</p>)}
        </div>}</>}
    </>} />;
}

export default function MasterCollector() {
  return <div className="grid gap-6"><KartuDaftarCollector /><KartuBulkCollector /></div>;
}
