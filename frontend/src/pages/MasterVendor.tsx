import { Fragment, useRef, useState } from "react";
import { useBahasa } from "../i18n";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, Pesan, ambilJson, fmtAngka, fmtTanggal,
  kelasInput, kelasLabel, kelasTombol, kelasTombolKecil, kirimMetode, urlApi,
} from "../bersama";

const pengisi = () => {
  try { return localStorage.getItem("op-margin.pengisi") || "?"; } catch { return "?"; }
};

const KOSONG = {
  kode: "", nama_baku: "", varian_nama: "", kategori: "", status: "aktif",
  alamat: "", kontak_person: "", klasifikasi: "", is_direct_producer: false,
};

/* Klasifikasi pemasok: tiga pilihan yang diminta pemilik. Kode dipakai API,
   label yang dilihat pengguna. */
const KLASIFIKASI = [
  { kode: "small_holder", label: "Small holder" },
  { kode: "small_estate", label: "Small estate" },
  { kode: "rubber_trader", label: "Rubber trader" },
];

const WARNA_KLASIFIKASI: Record<string, string> = {
  small_holder: "bg-[#F0F9FF] text-[#0369A1] border-[#BAE6FD]",
  small_estate: "bg-[#F5F3FF] text-[#5B21B6] border-[#DDD6FE]",
  rubber_trader: "bg-[#FFFBEB] text-[#B45309] border-[#FDE68A]",
};

const labelKlasifikasi = (kode: string | null) =>
  KLASIFIKASI.find((k) => k.kode === kode)?.label ?? null;

const URUTAN_VENDOR_CLASS: Record<string, number> = { SS: 0, S: 1, A: 2, B: 3, D: 4, "–": 5 };

const WARNA_VENDOR_CLASS: Record<string, string> = {
  SS: "bg-[#1D2434] text-white",
  S: "bg-[#2E4A7D] text-white",
  A: "bg-[#4F73B3] text-white",
  B: "bg-[#8FADD9] text-[#1D2434]",
  D: "bg-[#D5DEEE] text-[#1D2434]",
};

const WARNA_STATUS: Record<string, string> = {
  aktif: "bg-[#ECFDF5] text-[#166534] border-[#A7F3D0]",
  nonaktif: "bg-[#F3F4F6] text-[#4B5563] border-[#E5E7EB]",
  diblokir: "bg-[#FEF2F2] text-[#B91C1C] border-[#FECACA]",
};

/* ================= daftar + form (CRUD) ================= */
export function KartuDaftarVendor() {
  const { t } = useBahasa();
  const qc = useQueryClient();
  const [cari, setCari] = useState("");
  const [saring, setSaring] = useState("");
  const [saringKlasifikasi, setSaringKlasifikasi] = useState("");
  const [form, setForm] = useState({ ...KOSONG });
  const [ubahKode, setUbahKode] = useState<string | null>(null);
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  const params = new URLSearchParams();
  if (cari.trim()) params.set("q", cari.trim());
  if (saring) params.set("status", saring);
  if (saringKlasifikasi) params.set("klasifikasi", saringKlasifikasi);
  const url = `/api/vendor${params.toString() ? `?${params.toString()}` : ""}`;
  const q = useQuery({ queryKey: ["vendor", url], queryFn: () => ambilJson(url) });
  const barisVendor = [...(q.data?.baris ?? [])].sort((a: any, b: any) =>
    (URUTAN_VENDOR_CLASS[a.vendor_class] ?? 5) - (URUTAN_VENDOR_CLASS[b.vendor_class] ?? 5)
    || a.nama_baku.localeCompare(b.nama_baku, "id")
    || a.kode.localeCompare(b.kode, "id"));

  const segarkan = () => {
    qc.invalidateQueries({ queryKey: ["vendor"] });
    qc.invalidateQueries({ queryKey: ["penerimaan"] });
    qc.invalidateQueries({ queryKey: ["tonase"] });
    qc.invalidateQueries({ queryKey: ["intake-terakhir"] });
    qc.invalidateQueries({ queryKey: ["intake-terakhir-opsi"] });
  };

  const simpan = useMutation({
    mutationFn: () => ubahKode
      ? kirimMetode(`/api/vendor/${encodeURIComponent(ubahKode)}`, "PUT", {
          nama_baku: form.nama_baku, varian_nama: form.varian_nama || null,
          kategori: form.kategori || null, status: form.status,
          alamat: form.alamat || null,
          kontak_person: form.kontak_person || null,
          klasifikasi: form.klasifikasi || null,
          is_direct_producer: Boolean(form.is_direct_producer), pengisi: pengisi(),
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
              kategori: b.kategori ?? "", status: b.status ?? "aktif",
              alamat: b.alamat ?? "", kontak_person: b.kontak_person ?? "",
              klasifikasi: b.klasifikasi ?? "",
              is_direct_producer: Boolean(b.is_direct_producer) });
    setInfo(null);
  };

  /* {t("Hapus")} dua langkah: klik {t("Hapus")} -> tombol konfirmasi. Vendor yang sudah
     dipakai tiket tetap ditolak server; tombol kedua dinamai jelas. */
  const [konfirmasi, setKonfirmasi] = useState<string | null>(null);
  const [detailTerbuka, setDetailTerbuka] = useState<string | null>(null);

  return (
    <Kartu idMetrik="master_vendor" judul="Daftar vendor"
           keterangan="Kode vendor adalah kunci yang dipakai tiket intake dan pembelian. Selain itu tersimpan alamat, contact person, dan klasifikasi pemasok (Small holder / Small estate / Rubber trader). Menambah/mengubah di sini langsung berlaku; riwayat lama tidak berubah."
           anak={
      <>
        <div className="mb-3 flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-48">
            <label className={kelasLabel}>{t("Cari")}</label>
            <input className={kelasInput} placeholder={t("kode, nama, klasifikasi, kontak, alamat")}
                   value={cari} onChange={(e) => setCari(e.target.value)} />
          </div>
          <div>
            <label className={kelasLabel}>{t("Status")}</label>
            <select className={kelasInput + " min-w-36"} value={saring}
                    onChange={(e) => setSaring(e.target.value)}>
              <option value="">{t("Semua status")}</option>
              {(q.data?.status_baku ?? ["aktif", "nonaktif", "diblokir"]).map((s: string) => (
                <option key={s} value={s}>{t(s)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={kelasLabel}>{t("Klasifikasi")}</label>
            <select className={kelasInput + " min-w-40"} value={saringKlasifikasi}
                    onChange={(e) => setSaringKlasifikasi(e.target.value)}>
              <option value="">{t("Semua klasifikasi")}</option>
              {KLASIFIKASI.map((k) => (
                <option key={k.kode} value={k.kode}>{t(k.label)}</option>
              ))}
              <option value="-">{t("Belum diisi")}</option>
            </select>
          </div>
          <p className="pb-2 text-xs text-[#64676C]">
            {q.data ? `${fmtAngka(q.data.jumlah, 0)} ${t("dari")} ${fmtAngka(q.data.jumlah_total, 0)} ${t("vendor")}` : t("memuat…")}
          </p>
        </div>

        <p className="mb-2 text-[11px] text-[#64676C]">
          {t("Vendor Class dihitung dari total Dry per supplier selama enam bulan data terakhir")}
          {q.data?.periode_vendor_class ? ` (${q.data.periode_vendor_class})` : ` ${t("yang tersedia")}`}.
          {" "}{t("Ambang total 6 bulan: SS ≥ 1.500 MT · S ≥ 1.000 MT · A ≥ 500 MT · B ≥ 250 MT · D di bawahnya.")}
        </p>
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-white">
              <tr className="text-left text-[#64676C] border-b">
                <th className="py-2 pr-3">{t("Kode")}</th>
                <th className="py-2 pr-3">{t("Nama Vendor")}</th>
                <th className="py-2 pr-3">{t("Vendor Class")}</th>
                <th className="py-2 pr-3">{t("Klasifikasi")}</th>
                <th className="py-2 pr-3">{t("Status")}</th>
                <th className="py-2 text-right">{t("Detail")}</th>
              </tr>
            </thead>
            <tbody>
              {barisVendor.map((b: any) => (
                <Fragment key={b.kode}>
                  <tr key={b.kode} className="border-b border-[#EDEFF2]">
                    <td className="py-2 pr-3 font-mono font-semibold text-[#1D2434]">{b.kode}</td>
                    <td className="py-2 pr-3 text-[#1D2434]">{b.nama_baku}</td>
                    <td className="py-2 pr-3">
                      <span title={`${fmtAngka(b.dry_total_6bulan_mt, 3)} MT Dry total 6 bulan · ${q.data?.periode_vendor_class ?? "belum ada data"}`}
                            className={`inline-flex min-w-8 justify-center rounded-sm px-2 py-1 text-[11px] font-bold ${WARNA_VENDOR_CLASS[b.vendor_class] ?? "bg-[#F3F4F6] text-[#64676C]"}`}>
                        {b.vendor_class}
                      </span>
                    </td>
                    <td className="py-2 pr-3">
                      {b.klasifikasi_label ? (
                        <span className={`rounded-sm border px-1.5 py-0.5 text-[10px] whitespace-nowrap ${WARNA_KLASIFIKASI[b.klasifikasi] ?? WARNA_STATUS.nonaktif}`}>
                          {b.klasifikasi_label}
                        </span>
                      ) : <span className="text-[10px] text-[#9AA0A6]">belum diisi</span>}
                    </td>
                    <td className="py-2 pr-3">
                      <span className={`rounded-sm border px-1.5 py-0.5 text-[10px] ${WARNA_STATUS[b.status] ?? WARNA_STATUS.nonaktif}`}>
                        {t(b.status)}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      <button type="button" className={kelasTombolKecil}
                              aria-expanded={detailTerbuka === b.kode}
                              onClick={() => setDetailTerbuka(detailTerbuka === b.kode ? null : b.kode)}>
                        {detailTerbuka === b.kode ? t("Tutup") : t("Details")}
                      </button>
                    </td>
                  </tr>
                  {detailTerbuka === b.kode && (
                    <tr key={`${b.kode}-detail`} className="border-b border-[#E4E5E8] bg-[#F8F8F8]">
                      <td colSpan={6} className="px-3 py-3">
                        <div className="grid gap-x-5 gap-y-2 sm:grid-cols-2 lg:grid-cols-4 text-xs">
                          <div><span className="text-[#64676C]">{t("Varian nama")}</span><p className="text-[#1D2434]">{b.varian_nama || "–"}</p></div>
                          <div><span className="text-[#64676C]">{t("Produsen langsung")}</span><p className="text-[#1D2434]">{b.is_direct_producer ? "Ya" : "Tidak"}</p></div>
                          <div><span className="text-[#64676C]">{t("Kategori")}</span><p className="text-[#1D2434]">{b.kategori || "–"}</p></div>
                          <div><span className="text-[#64676C]">{t("Contact person")}</span><p className="text-[#1D2434]">{b.kontak_person || "–"}</p></div>
                          <div className="sm:col-span-2"><span className="text-[#64676C]">{t("Alamat")}</span><p className="text-[#1D2434]">{b.alamat || "–"}</p></div>
                          <div><span className="text-[#64676C]">{t("Jumlah tiket")}</span><p className="font-mono text-[#1D2434]">{fmtAngka(b.jumlah_tiket, 0)}</p></div>
                          <div><span className="text-[#64676C]">{t("Dry historis")}</span><p className="font-mono text-[#1D2434]">{fmtAngka(b.ton_kering, 3)} MT</p></div>
                          <div><span className="text-[#64676C]">{t("Total Dry 6 bulan")}</span><p className="font-mono text-[#1D2434]">{fmtAngka(b.dry_total_6bulan_mt, 3)} MT</p></div>
                          <div><span className="text-[#64676C]">{t("Rata-rata Dry per bulan")}</span><p className="font-mono text-[#1D2434]">{fmtAngka(b.dry_rata_bulanan_mt, 3)} MT/bulan</p></div>
                          <div><span className="text-[#64676C]">{t("Intake terakhir")}</span><p className="text-[#1D2434]">{b.intake_terakhir ? fmtTanggal(b.intake_terakhir) : "belum pernah"}</p></div>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button className={kelasTombolKecil} onClick={() => mulaiUbah(b)}>{t("Ubah")}</button>
                          {konfirmasi === b.kode ? (
                            <>
                              <button className={`${kelasTombolKecil} border-[#DC2626] text-[#B91C1C]`}
                                      disabled={hapus.isPending}
                                      onClick={() => { hapus.mutate(b.kode); setKonfirmasi(null); }}>
                                {t("Ya, hapus")}
                              </button>
                              <button className={kelasTombolKecil} onClick={() => setKonfirmasi(null)}>{t("Batal")}</button>
                            </>
                          ) : (
                            <button className={`${kelasTombolKecil} border-[#FECACA] text-[#B91C1C]`}
                                    onClick={() => { setInfo(null); setKonfirmasi(b.kode); }}>
                              {t("Hapus")}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {q.data?.baris.length === 0 && (
                <tr><td colSpan={6} className="py-3 text-[#64676C]">
                  {t("Tidak ada vendor yang cocok. Kosongkan pencarian, atau tambahkan")}
                  {t("vendor baru di bawah.")}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>

        <p className="mt-2 text-[11px] text-[#64676C]">
          {t("Vendor yang sudah dipakai tiket tidak bisa dihapus begitu saja — server menolak agar tonase tidak kehilangan pemiliknya. Jalankan lewat status nonaktif. Tombol ya, hapus mengirim hapus paksa dan tetap tercatat di audit.")}
        </p>

        <h3 className="mt-5 mb-2 text-sm font-semibold text-[#1D2434]">
          {ubahKode ? `${t("Ubah vendor")} ${ubahKode}` : t("Tambah vendor baru")}
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-6 gap-2 items-end">
          <div>
            <label className={kelasLabel}>{t("Kode vendor")}</label>
            <input className={`${kelasInput} font-mono ${ubahKode ? "bg-[#F8F8F8] text-[#64676C]" : ""}`}
                   placeholder={t("mis. V005")} value={form.kode} disabled={Boolean(ubahKode)}
                   onChange={(e) => setForm({ ...form, kode: e.target.value.toUpperCase() })} />
          </div>
          <div className="sm:col-span-2">
            <label className={kelasLabel}>{t("Nama baku")}</label>
            <input className={kelasInput} placeholder={t("mis. PT Karet Nusantara")}
                   value={form.nama_baku}
                   onChange={(e) => setForm({ ...form, nama_baku: e.target.value })} />
          </div>
          <div>
            <label className={kelasLabel}>{t("Klasifikasi")}</label>
            <select className={kelasInput} value={form.klasifikasi}
                    onChange={(e) => setForm({ ...form, klasifikasi: e.target.value })}>
              <option value="">{t("belum diisi")}</option>
              {KLASIFIKASI.map((k) => (
                <option key={k.kode} value={k.kode}>{t(k.label)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={kelasLabel}>{t("Status")}</label>
            <select className={kelasInput} value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value })}>
              {["aktif", "nonaktif", "diblokir"].map((s) => (
                <option key={s} value={s}>{t(s)}</option>))}
            </select>
          </div>
          <button className={kelasTombol} disabled={simpan.isPending
                    || !form.kode.trim() || !form.nama_baku.trim()}
                  onClick={() => { setInfo(null); simpan.mutate(); }}>
            {ubahKode ? t("Simpan perubahan") : t("Tambah vendor")}
          </button>
        </div>
        <div className="mt-2 grid grid-cols-1 sm:grid-cols-6 gap-2">
          <div className="sm:col-span-3">
            <label className={kelasLabel}>{t("Varian nama (nama lain di tiket, pisahkan dengan |)")}</label>
            <input className={kelasInput} placeholder={t("mis. PT Karet Nusantara|CV Karet Nusantara")}
                   value={form.varian_nama}
                   onChange={(e) => setForm({ ...form, varian_nama: e.target.value })} />
          </div>
          <div className="sm:col-span-1">
            <label className={kelasLabel}>{t("Kategori")}</label>
            <input className={kelasInput} placeholder={t("nasional / lokal")}
                   value={form.kategori}
                   onChange={(e) => setForm({ ...form, kategori: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className={kelasLabel}>{t("Contact person")}</label>
            <input className={kelasInput} placeholder={t("nama — nomor HP")}
                   value={form.kontak_person}
                   onChange={(e) => setForm({ ...form, kontak_person: e.target.value })} />
          </div>
        </div>
        <div className="mt-2">
          <label className={kelasLabel}>{t("Alamat")}</label>
          <textarea className={`${kelasInput} min-h-16`} rows={2}
                    placeholder={t("mis. Jl. Gatot Subroto No. 12, Medan, Sumatera Utara")}
                    value={form.alamat}
                    onChange={(e) => setForm({ ...form, alamat: e.target.value })} />
        </div>
        <label className="mt-2 inline-flex items-start gap-2 text-xs text-[#374151]">
          <input type="checkbox" className="mt-0.5"
                 checked={Boolean(form.is_direct_producer)}
                 onChange={(e) => setForm({ ...form, is_direct_producer: e.target.checked })} />
          <span><b>{t("Produsen langsung")}</b> <span className="text-[#64676C]">{t("(penanda sementara; default tidak)")}</span></span>
        </label>
        {ubahKode && (
          <button className={`${kelasTombolKecil} mt-2`}
                  onClick={() => { setUbahKode(null); setForm({ ...KOSONG }); setInfo(null); }}>
            {t("batal ubah — kembali ke tambah baru")}
          </button>
        )}
        {info && <Pesan jenis={info.jenis} teks={info.teks} />}
      </>
    } />
  );
}

/* ================= bulk import ================= */
export function KartuBulkVendor() {
  const { t } = useBahasa();
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
            ⬇ {t("Unduh template")}
          </a>
          <button className={kelasTombolKecil} disabled={unggah.isPending}
                  onClick={() => inputRef.current?.click()}>
            {unggah.isPending ? t("Mengimpor…") : t("Pilih file .xlsx untuk diimpor")}
          </button>
          <input ref={inputRef} type="file" accept=".xlsx" className="hidden"
                 onChange={(e) => { pilih(e.target.files?.[0]); e.target.value = ""; }} />
          <span className="text-xs text-[#64676C]">
            {t("Template berisi sheet")} <b>Master_Vendor</b> + {t("sheet Petunjuk. Bisa juga")}
            {t("diunggah lewat tab")} <b>{t("Unggah Data")}</b>.
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
            {t("Tarik & lepas file .xlsx ke sini, atau klik untuk memilih")}
          </p>
          <p className="mt-1 text-[#64676C]">
            {t("Hanya file bersheet Master_Vendor. Baris rusak dilaporkan per baris dan tidak membatalkan baris lain.")}
          </p>
        </div>

        {galat && <Pesan jenis="error" teks={galat} />}

        {hasil && (
          <>
            <Pesan jenis="sukses" teks={`${hasil.nama_file} — ${hasil.pesan}`} />
            <div className="mt-3 grid grid-cols-3 gap-2">
              {[[t("Vendor baru"), hasil.ditambah, "#15803D"],
                [t("Diperbarui"), hasil.diperbarui, "#1D2434"],
                [t("Ditolak"), hasil.ditolak, hasil.ditolak ? "#B91C1C" : "#64676C"]].map(
                ([label, nilai, warna]) => (
                  <div key={label as string}
                       className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-2.5">
                    <p className="text-xs text-[#64676C]">{label}</p>
                    <p className="font-semibold" style={{ color: warna as string }}>
                      {fmtAngka(nilai as number, 0)} {t("baris")}
                    </p>
                  </div>
                ))}
            </div>
            {hasil.peringatan?.length > 0 && (
              <div className="mt-3 max-h-52 overflow-y-auto rounded-sm border border-[#FECACA] bg-[#FEF2F2] p-2">
                <p className="mb-1 text-xs font-semibold text-[#B91C1C]">
                  {t("Baris yang tidak diimpor:")}
                </p>
                <table className="w-full text-xs">
                  <tbody>
                    {hasil.peringatan.map((p: any, i: number) => (
                      <tr key={i} className="border-b border-[#FECACA]">
                        <td className="py-0.5 pr-2 text-[#B91C1C]">{t("baris")} {p.baris}</td>
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

/* ================= supplier class berbasis intake =================
   Ringkasan kelas dipindah dari halaman Traceability ke Master Vendor atas
   permintaan pemilik: di sini pemilik mengelola data vendor, jadi distribusi
   kelas intake paling pas dibaca berdampingan dengan daftar & komposisi. */
const WARNA_KELAS_INTAKE: Record<string, string> = {
  SS: "bg-[#1D2434] text-white", S: "bg-[#175CD3] text-white",
  A: "bg-[#027A48] text-white", B: "bg-[#B54708] text-white",
  C: "bg-[#B45309] text-white", D: "bg-[#E4E5E8] text-[#374151]",
};

export function KartuKelasIntake() {
  const { t } = useBahasa();
  /* Tanpa parameter `tahun`, backend otomatis memakai tahun intake terbaru. */
  const ki = useQuery({
    queryKey: ["master-vendor-kelas-intake"],
    queryFn: () => ambilJson("/api/traceability/kelas-intake"),
  });
  return (
    <Kartu idMetrik="master_vendor"
      judul="Supplier class berbasis intake · Dry (MT) per supplier per bulan"
      keterangan="Kelas dihitung dari volume Dry bulanan per supplier, bukan dari isian master. Tanda ≥ berlaku di setiap batas; ringkasan hanya menghitung vendor yang terdaftar di Master Vendor."
      anak={
        <>
          {ki.error && <Pesan jenis="error" teks={(ki.error as Error).message} />}
          {ki.isLoading && <p className="text-xs text-[#64676C]">Memuat distribusi kelas…</p>}
          {ki.data && (() => {
            const d = ki.data;
            const dist: any[] = d.distribusi ?? [];
            const batas: any[] = d.batas ?? [];
            const maks = Math.max(1, ...dist.map((x) => x.jumlah));
            const bulan: string[] = d.bulan_tersedia ?? [];
            return <>
              <div className="mb-2 flex flex-wrap items-end justify-between gap-2 text-[11px] text-[#64676C]">
                <span><b className="text-[#1D2434]">{fmtAngka(d.total_supplier_bulan, 0)} supplier-bulan</b> · {t("tahun")} {d.filters?.year ?? "—"} · {bulan.length} {t("bulan")} ({bulan[0] || "—"} s.d. {bulan[bulan.length - 1] || "—"}) · total {fmtAngka(d.total_dry_mt, 3)} MT</span>
                <span>{t("Tanda ≥ di setiap batas")}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
                {dist.map((x: any) => {
                  const b = batas.find((t: any) => t.kelas === x.kelas);
                  return <div key={x.kelas} className="rounded-sm border border-[#E4E5E8] p-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className={`rounded-sm px-1.5 py-0.5 font-mono text-[11px] font-bold ${WARNA_KELAS_INTAKE[x.kelas] ?? WARNA_KELAS_INTAKE.D}`}>{x.kelas}</span>
                      <span className="font-mono text-lg font-bold tabular-nums text-[#1D2434]">{fmtAngka(x.jumlah, 0)}</span>
                    </div>
                    <p className="mt-1 text-[10px] text-[#64676C]">{b ? (b.batas_mt === null ? t("< 100 MT") : `≥ ${fmtAngka(b.batas_mt, 0)} MT`) : "—"}</p>
                    <div className="mt-1.5 h-1.5 rounded bg-[#EDEFF2]"><div className="h-1.5 rounded bg-[#FF1313]" style={{ width: `${Math.max(2, x.jumlah / maks * 100)}%` }} /></div>
                  </div>;
                })}
              </div>
              {d.supplier_bulan_tanpa_master > 0 && <p className="mt-2 text-[10px] text-[#9AA0A6]">{d.supplier_bulan_tanpa_master} supplier-bulan dari kode tanpa Master Vendor ({d.kode_tanpa_master.join(", ")}) tidak masuk ringkasan.</p>}
              <p className="mt-2 text-[10px] leading-relaxed text-[#9AA0A6]">{d.catatan}</p>
            </>;
          })()}
        </>
      } />
  );
}

export default function MasterVendor() {
  return (
    <div className="grid gap-6">
      <KartuKelasIntake />
      <KartuDaftarVendor />
      <KartuBulkVendor />
    </div>
  );
}
