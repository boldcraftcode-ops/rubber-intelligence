import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ambilJson, fmtAngka, fmtTanggal, kelasInput, kelasLabel,
  kelasTombol, kelasTombolKecil, kirimMetode,
} from "../bersama";

type IntakeBaris = {
  id: number;
  ticket_no: string;
  line_seq: number;
  ticket_date: string | null;
  kode_vendor: string;
  nama_vendor_asli: string | null;
  vehicle_no: string | null;
  item_code: string | null;
  drc_date: string | null;
  wet_kg: number | null;
  sample_kg: number | null;
  reject_kg: number | null;
  drc_pct: number | null;
  dry_kg: number | null;
  provinsi: string | null;
  kabupaten: string | null;
  kecamatan: string | null;
  desa: string | null;
  asal_getah: string | null;
  bin: string | null;
  location: string | null;
  peringatan: string | null;
};

type FormIntake = Record<string, string>;
type FilterIntake = { tahun: string; provinsi: string; supplier: string };
type HasilDaftar = { baris: IntakeBaris[]; total: number; page: number; page_size: number; pages: number };
type OpsiWilayah = { value: string; label: string };
type ResponsOpsiWilayah = { options: OpsiWilayah[]; available?: boolean; catatan?: string };
type BarisPratinjau = {
  id: number; ticket_no: string; line_seq: number;
  sebelumnya: string | number | null; sesudah: string | number | null;
  berubah: boolean;
};
type GalatPratinjau = {
  id: number; ticket_no: string; line_seq: number; alasan: string;
};
type HasilPratinjau = {
  status: "siap" | "ada_galat";
  token: string | null;
  kolom: string;
  jumlah: number;
  berubah: number;
  baris: BarisPratinjau[];
  galat: GalatPratinjau[];
  pesan: string;
  kedaluwarsa_detik?: number;
};
type PerubahanExcel = {
  kolom: string; label: string;
  sebelumnya: string | number | null; sesudah: string | number | null;
};
type BarisExcel = {
  id: number; ticket_no: string; line_seq: number;
  perubahan: PerubahanExcel[]; berubah: boolean;
};
type HasilExcel = {
  status: "siap" | "ada_galat" | "kosong";
  token: string | null;
  nama_file: string;
  jumlah: number;
  berubah: number;
  jumlah_perubahan: number;
  baris: BarisExcel[];
  galat: GalatPratinjau[];
  pesan: string;
  kedaluwarsa_detik?: number;
};

const LABEL: Record<string, string> = {
  ticket_date: "Tanggal tiket",
  kode_vendor: "Kode supplier",
  nama_vendor_asli: "Nama supplier",
  vehicle_no: "Nomor kendaraan",
  item_code: "Item / grade",
  drc_date: "Tanggal DRC",
  wet_kg: "Wet (kg)",
  sample_kg: "Sample (kg)",
  reject_kg: "Reject (kg)",
  drc_pct: "DRC (%)",
  dry_kg: "Dry (kg)",
  provinsi: "Provinsi",
  kabupaten: "Kabupaten/Kota",
  kecamatan: "Kecamatan / Sub-district",
  desa: "Desa",
  bin: "Bin",
  location: "Location",
};

const KOLOM_FORM = [
  "ticket_date", "kode_vendor", "nama_vendor_asli", "vehicle_no", "item_code", "drc_date",
  "wet_kg", "sample_kg", "reject_kg", "drc_pct", "dry_kg", "provinsi", "kabupaten",
  "kecamatan", "desa", "bin", "location",
];
const KOLOM_QUICK_FILL = KOLOM_FORM;

const KELOMPOK = [
  { label: "Informasi tiket", kolom: ["ticket_date", "kode_vendor", "nama_vendor_asli", "vehicle_no", "item_code", "drc_date"] },
  { label: "Berat & kualitas", kolom: ["wet_kg", "sample_kg", "reject_kg", "drc_pct", "dry_kg"] },
  { label: "Wilayah asal", kolom: ["provinsi", "kabupaten", "kecamatan", "desa", "bin", "location"] },
];

function nilaiForm(row: IntakeBaris): FormIntake {
  return Object.fromEntries(KOLOM_FORM.map((key) => [key, (row as any)[key] == null ? "" : String((row as any)[key])]));
}

function normalisasiOpsiWilayah(kolom: string, nilai: string) {
  let hasil = nilai.trim().replace(/\s+/g, " ").toLocaleUpperCase("id-ID");
  if (kolom === "kabupaten") hasil = hasil.replace(/^(KABUPATEN|KAB\.|KOTA)\s+/, "");
  return hasil;
}

function IsiForm({ kolom, form, ubah, opsi, memuat, nonaktif, catatan }: {
  kolom: string; form: FormIntake; ubah: (kolom: string, nilai: string) => void;
  opsi?: OpsiWilayah[]; memuat?: boolean; nonaktif?: boolean; catatan?: string | null;
}) {
  const angka = ["wet_kg", "sample_kg", "reject_kg", "drc_pct", "dry_kg"].includes(kolom);
  const wilayahDropdown = ["provinsi", "kabupaten", "kecamatan", "desa"].includes(kolom);
  if (wilayahDropdown) {
    const pilihan = opsi ?? [];
    const sekarang = form[kolom] ?? "";
    const padanan = pilihan.find((item) =>
      normalisasiOpsiWilayah(kolom, item.value) === normalisasiOpsiWilayah(kolom, sekarang));
    const nilaiSelect = padanan?.value ?? sekarang;
    return (
      <label className="block min-w-0">
        <span className={kelasLabel}>{LABEL[kolom]}</span>
        <select className={kelasInput} value={nilaiSelect}
                disabled={Boolean(nonaktif || memuat)}
                onChange={(e) => ubah(kolom, e.target.value)}>
          <option value="">{memuat ? "Memuat referensi SCDF…" : `Pilih ${LABEL[kolom]} SCDF`}</option>
          {sekarang && !padanan && <option value={sekarang} disabled>{sekarang} · nilai intake, bukan opsi SCDF</option>}
          {pilihan.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        {kolom === "provinsi" && catatan && <span className="mt-1 block text-[10px] leading-relaxed text-[#B45309]">{catatan}</span>}
        {sekarang && !padanan && <span className="mt-1 block text-[10px] text-[#64676C]">Nilai saat ini dipertahankan sampai pilihan SCDF dipilih.</span>}
      </label>
    );
  }
  return (
    <label className="block min-w-0">
      <span className={kelasLabel}>{LABEL[kolom]}</span>
      <input
        className={kelasInput}
        type={kolom === "ticket_date" || kolom === "drc_date" ? "date" : angka ? "number" : "text"}
        min={angka ? "0" : undefined}
        max={kolom === "drc_pct" ? "100" : undefined}
        step={kolom === "drc_pct" ? "0.01" : angka ? "0.001" : undefined}
        value={form[kolom] ?? ""}
        required={kolom === "ticket_date" || kolom === "kode_vendor"}
        onChange={(e) => ubah(kolom, e.target.value)}
      />
    </label>
  );
}

function ModalEdit({ row, tutup, simpan, menyimpan, error }: {
  row: IntakeBaris; tutup: () => void; simpan: (form: FormIntake) => void;
  menyimpan: boolean; error: string | null;
}) {
  const [form, setForm] = useState(() => nilaiForm(row));
  const provinceOptions = useQuery<ResponsOpsiWilayah>({
    queryKey: ["intake-edit-scdf-provinsi"],
    queryFn: () => ambilJson("/api/intake/options/scdf/provinsi") as Promise<ResponsOpsiWilayah>,
    staleTime: 15 * 60_000,
  });
  const countyParams = new URLSearchParams();
  if (form.provinsi) countyParams.set("provinsi", form.provinsi);
  const countyOptions = useQuery<ResponsOpsiWilayah>({
    queryKey: ["intake-edit-scdf-kabupaten", form.provinsi],
    queryFn: () => ambilJson(`/api/intake/options/scdf/kabupaten?${countyParams}`) as Promise<ResponsOpsiWilayah>,
    staleTime: 15 * 60_000,
  });
  const districtParams = new URLSearchParams({ kabupaten: form.kabupaten ?? "" });
  if (form.provinsi) districtParams.set("provinsi", form.provinsi);
  const districtOptions = useQuery<ResponsOpsiWilayah>({
    queryKey: ["intake-edit-scdf-kecamatan", form.provinsi, form.kabupaten],
    queryFn: () => ambilJson(`/api/intake/options/scdf/kecamatan?${districtParams}`) as Promise<ResponsOpsiWilayah>,
    enabled: Boolean(form.kabupaten),
    staleTime: 15 * 60_000,
  });
  const villageParams = new URLSearchParams({
    kabupaten: form.kabupaten ?? "", kecamatan: form.kecamatan ?? "",
  });
  if (form.provinsi) villageParams.set("provinsi", form.provinsi);
  const villageOptions = useQuery<ResponsOpsiWilayah>({
    queryKey: ["intake-edit-scdf-desa", form.provinsi, form.kabupaten, form.kecamatan],
    queryFn: () => ambilJson(`/api/intake/options/scdf/desa?${villageParams}`) as Promise<ResponsOpsiWilayah>,
    enabled: Boolean(form.kabupaten && form.kecamatan),
    staleTime: 15 * 60_000,
  });
  const ubah = (kolom: string, nilai: string) => setForm((sebelum) => {
    const hasil = { ...sebelum, [kolom]: nilai };
    if (kolom === "provinsi") {
      hasil.kabupaten = ""; hasil.kecamatan = ""; hasil.desa = "";
    } else if (kolom === "kabupaten") {
      hasil.kecamatan = ""; hasil.desa = "";
    } else if (kolom === "kecamatan") {
      hasil.desa = "";
    }
    return hasil;
  });
  const opsiUntuk = (kolom: string) => {
    if (kolom === "provinsi") return provinceOptions.data?.options ?? [];
    if (kolom === "kabupaten") return countyOptions.data?.options ?? [];
    if (kolom === "kecamatan") return districtOptions.data?.options ?? [];
    if (kolom === "desa") return villageOptions.data?.options ?? [];
    return undefined;
  };
  const memuatOpsi = (kolom: string) =>
    (kolom === "provinsi" && provinceOptions.isLoading) ||
    (kolom === "kabupaten" && countyOptions.isLoading) ||
    (kolom === "kecamatan" && districtOptions.isLoading) ||
    (kolom === "desa" && villageOptions.isLoading);
  const nonaktifOpsi = (kolom: string) =>
    (kolom === "provinsi" && (provinceOptions.isError || provinceOptions.data?.available === false)) ||
    (kolom === "kabupaten" && countyOptions.isError) ||
    (kolom === "kecamatan" && (!form.kabupaten || districtOptions.isError)) ||
    (kolom === "desa" && (!form.kabupaten || !form.kecamatan || villageOptions.isError));
  const catatanProvinsi = provinceOptions.isError
    ? `Gagal memuat Provinsi SCDF: ${(provinceOptions.error as Error).message}`
    : provinceOptions.data?.catatan ?? null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3 sm:p-5" onMouseDown={tutup}>
      <section className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-sm border border-[#E4E5E8] bg-white shadow-2xl"
               onMouseDown={(e) => e.stopPropagation()}>
        <header className="flex items-start justify-between gap-3 border-b border-[#E4E5E8] bg-[#F8F8F8] px-5 py-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#FF1313]">Edit baris intake</p>
            <h2 className="mt-1 text-lg font-bold text-[#1D2434]">
              Tiket {row.ticket_no} <span className="font-normal text-[#64676C]">· baris {row.line_seq}</span>
            </h2>
            <p className="text-xs text-[#64676C]">ID data: {row.id}</p>
          </div>
          <button className={kelasTombolKecil} type="button" onClick={tutup}>Tutup</button>
        </header>
        <div className="overflow-y-auto px-5 py-4">
          <div className="mb-4 rounded-sm border border-[#D7E7FF] bg-[#EFF6FF] px-3 py-2 text-xs leading-relaxed text-[#1D4ED8]">
            Kolom wilayah dapat diperbaiki untuk dicocokkan dengan referensi <b>SCDF</b>;
            perubahan wilayah tersimpan pada intake dan kunci wilayah analisis/traceability diperbarui.
            <div className="mt-1 text-[#475569]">
              Ticket No dan Asal Getah asli dipertahankan sebagai identitas serta jejak sumber.
              Asal Getah: <b>{row.asal_getah || "belum tercatat"}</b>
            </div>
          </div>
          {KELOMPOK.map((grup) => (
            <section key={grup.label} className="mb-5">
              <h3 className="mb-3 border-b border-[#E4E5E8] pb-1 text-sm font-semibold text-[#1D2434]">{grup.label}</h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {grup.kolom.map((kolom) => (
                  <IsiForm key={kolom} kolom={kolom} form={form} ubah={ubah}
                           opsi={opsiUntuk(kolom)} memuat={memuatOpsi(kolom)}
                           nonaktif={nonaktifOpsi(kolom)}
                           catatan={kolom === "provinsi" ? catatanProvinsi : null} />
                ))}
              </div>
            </section>
          ))}
          {error && <p role="alert" className="mb-3 rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-sm text-[#B91C1C]">{error}</p>}
        </div>
        <footer className="flex justify-end gap-2 border-t border-[#E4E5E8] bg-[#F8F8F8] px-5 py-3">
          <button type="button" className={kelasTombolKecil} onClick={tutup}>Batal</button>
          <button type="button" className={kelasTombol} disabled={menyimpan || !form.ticket_date || !form.kode_vendor.trim()}
                  onClick={() => simpan(form)}>
            {menyimpan ? "Menyimpan…" : "Simpan perubahan"}
          </button>
        </footer>
      </section>
    </div>
  );
}

function PanelQuickFill({ terpilih, rows, epoch, onBersihkan, onSelesai }: {
  terpilih: number[]; rows: IntakeBaris[]; epoch: number;
  onBersihkan: () => void; onSelesai: (pesan: string) => Promise<void>;
}) {
  const [kolom, setKolom] = useState("kode_vendor");
  const [nilai, setNilai] = useState("");
  const [kosongkan, setKosongkan] = useState(false);
  const [hasil, setHasil] = useState<HasilPratinjau | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [galat, setGalat] = useState<string | null>(null);
  const angka = ["wet_kg", "sample_kg", "reject_kg", "drc_pct", "dry_kg"].includes(kolom);
  const tanggal = kolom === "ticket_date" || kolom === "drc_date";
  const wajib = kolom === "ticket_date" || kolom === "kode_vendor";
  const wilayah = ["provinsi", "kabupaten", "kecamatan", "desa"].includes(kolom);
  const diHalamanIni = rows.filter((r) => terpilih.includes(r.id)).length;
  const diHalamanLain = terpilih.length - diHalamanIni;

  const pratinjau = useMutation({
    mutationFn: () => kirimMetode("/api/intake/quick-fill/pratinjau", "POST", {
      ids: terpilih, kolom, nilai, kosongkan,
    }) as Promise<HasilPratinjau>,
    onSuccess: (data) => {
      setHasil(data);
      setToken(data.token);
      setGalat(null);
    },
    onError: (e: Error) => {
      setHasil(null);
      setToken(null);
      setGalat(e.message);
    },
  });
  const terapkan = useMutation({
    mutationFn: (t: string) => kirimMetode("/api/intake/quick-fill/terapkan", "POST", {
      token: t,
    }) as Promise<{ pesan: string }>,
    onSuccess: async (data) => {
      setHasil(null);
      setToken(null);
      setGalat(null);
      await onSelesai(data.pesan);
    },
    onError: (e: Error) => {
      setHasil(null);
      setToken(null);
      setGalat(e.message);
    },
  });
  const batal = useMutation({
    mutationFn: (t: string) => kirimMetode(
      `/api/intake/quick-fill/pratinjau/${encodeURIComponent(t)}`, "DELETE"),
    onSuccess: () => {
      setHasil(null);
      setToken(null);
      setGalat(null);
    },
  });

  useEffect(() => {
    setHasil(null);
    setToken(null);
    setGalat(null);
  }, [terpilih, epoch, kolom, nilai, kosongkan]);

  if (terpilih.length === 0) return null;

  const ubahKolom = (k: string) => {
    setKolom(k);
    setNilai("");
    setKosongkan(false);
  };
  const tampil = (v: string | number | null) => {
    if (v === null || v === "") return "—";
    if (angka && typeof v === "number") return fmtAngka(v, 3);
    return String(v);
  };
  const konfirmasiTerapkan = () => {
    if (!token || !hasil || hasil.status !== "siap") return;
    const ok = window.confirm(
      `Terapkan ${hasil.berubah} perubahan pada ${hasil.jumlah} baris untuk kolom ${LABEL[kolom]}?\n\n` +
      "Perubahan tercatat per baris di audit log, menyegarkan ringkasan/alarm, dan tidak dibatalkan otomatis. " +
      "Lanjutkan hanya bila pratinjau sudah benar.");
    if (ok) terapkan.mutate(token);
  };

  return (
    <section className="mt-4 rounded-sm border border-[#D7E7FF] bg-[#F8FBFF] p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-[#1D2434]">Quick-fill koreksi intake</h3>
          <p className="mt-0.5 text-[11px] leading-relaxed text-[#64676C]">
            <b>{terpilih.length}</b> baris dipilih · {diHalamanIni} di halaman ini
            {diHalamanLain > 0 && ` · ${diHalamanLain} di halaman lain`}.
            Pilihan tetap tersimpan saat berpindah halaman; ubah <b>satu kolom</b> lalu pratinjau dulu.
          </p>
        </div>
        <button type="button" className={kelasTombolKecil} onClick={onBersihkan}>Hapus pilihan</button>
      </div>

      <div className="mt-3 grid grid-cols-1 items-end gap-2 md:grid-cols-[minmax(180px,1fr)_minmax(200px,1.2fr)_auto_auto]">
        <label className="block">
          <span className={kelasLabel}>Kolom yang diubah</span>
          <select className={kelasInput} value={kolom} onChange={(e) => ubahKolom(e.target.value)}>
            {KOLOM_QUICK_FILL.map((k) => <option key={k} value={k}>{LABEL[k]}</option>)}
          </select>
        </label>
        <label className="block">
          <span className={kelasLabel}>Nilai baru</span>
          <input className={kelasInput}
                 type={tanggal ? "date" : angka ? "number" : "text"}
                 min={angka ? "0" : undefined}
                 max={kolom === "drc_pct" ? "100" : undefined}
                 step={angka ? (kolom === "drc_pct" ? "0.01" : "0.001") : undefined}
                 value={nilai}
                 disabled={kosongkan}
                 onChange={(e) => setNilai(e.target.value)}
                 placeholder={kosongkan ? "Dikosongkan" : "Isi nilai yang sama untuk semua baris"} />
        </label>
        <label className="flex items-center gap-1.5 pb-2 text-[11px] text-[#64676C]">
          <input type="checkbox" checked={kosongkan}
                 disabled={wajib}
                 onChange={(e) => setKosongkan(e.target.checked)} />
          Kosongkan nilai
        </label>
        <div className="flex flex-wrap gap-1.5 pb-0.5">
          <button type="button" className={kelasTombolKecil}
                  disabled={pratinjau.isPending || (!kosongkan && nilai.trim() === "")}
                  onClick={() => pratinjau.mutate()}>
            {pratinjau.isPending ? "Memeriksa…" : "Pratinjau"}
          </button>
        </div>
      </div>

      <p className="mt-2 text-[10px] leading-relaxed text-[#64676C]">
        Hanya admin yang dapat menerapkan. {wilayah
          ? "Kolom wilayah divalidasi per baris terhadap SCDF; ketik nama persis sesuai referensi."
          : "Ticket No, Asal Getah, sidik sumber, dan file unggahan asli tetap tidak berubah."}
        {wajib && kosongkan === false && ""}
        {hasil?.kedaluwarsa_detik ? ` Pratinjau berlaku ${Math.round(hasil.kedaluwarsa_detik / 60)} menit.` : ""}
        {hasil?.status === "siap" && token && " Tombol konfirmasi ada di blok hijau di bawah tabel diff."}
      </p>
      {wajib && (
        <p className="mt-1 text-[10px] text-[#B45309]">
          {LABEL[kolom]} wajib diisi, jadi opsi “Kosongkan nilai” tidak tersedia untuk kolom ini.
        </p>
      )}
      {galat && <p role="alert" className="mt-2 rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">{galat}</p>}

      {hasil && (
        <div className="mt-3 rounded-sm border border-[#E4E5E8] bg-white p-3">
          <p className={`text-xs font-semibold ${hasil.status === "siap" ? "text-[#15803D]" : "text-[#B42318]"}`}>
            {hasil.pesan}
          </p>
          {hasil.galat.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-[11px] text-[#B42318]">
              {hasil.galat.slice(0, 8).map((g) => (
                <li key={g.id}>{g.ticket_no} · baris {g.line_seq}: {g.alasan}</li>
              ))}
              {hasil.galat.length > 8 && <li>…{hasil.galat.length - 8} baris lain ditolak.</li>}
            </ul>
          )}
          {hasil.baris.length > 0 && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-[11px]">
                <thead className="bg-[#F8F8F8] text-left uppercase tracking-wider text-[#64676C]">
                  <tr>
                    <th className="px-2 py-1.5">Tiket / baris</th>
                    <th className="px-2 py-1.5">Sebelumnya</th>
                    <th className="px-2 py-1.5">Sesudah</th>
                    <th className="px-2 py-1.5">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {hasil.baris.slice(0, 20).map((b) => (
                    <tr key={b.id} className="border-t border-[#EDEFF2]">
                      <td className="px-2 py-1.5 font-mono">{b.ticket_no} · {b.line_seq}</td>
                      <td className="px-2 py-1.5">{tampil(b.sebelumnya)}</td>
                      <td className="px-2 py-1.5 font-semibold">{tampil(b.sesudah)}</td>
                      <td className="px-2 py-1.5">
                        <span className={b.berubah ? "text-[#15803D]" : "text-[#9AA0A6]"}>
                          {b.berubah ? "Berubah" : "Sudah sama"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {hasil.baris.length > 20 && (
                <p className="mt-1 text-[10px] text-[#64676C]">
                  Menampilkan 20 dari {hasil.baris.length} baris; ringkasan lengkap ada di pesan di atas.
                </p>
              )}
            </div>
          )}
          {hasil.status === "siap" && token ? (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-sm border border-[#BBF7D0] bg-[#F0FDF4] px-3 py-2">
              <div>
                <p className="text-xs font-semibold text-[#15803D]">Konfirmasi pratinjau</p>
                <p className="mt-0.5 text-[11px] leading-relaxed text-[#475569]">
                  Klik <b>Konfirmasi &amp; terapkan {hasil.berubah} perubahan</b>, lalu pilih <b>OK</b> pada dialog browser.
                  Token berlaku {Math.round((hasil.kedaluwarsa_detik ?? 900) / 60)} menit dan hanya sekali pakai.
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button type="button" className={kelasTombol}
                        disabled={terapkan.isPending} onClick={konfirmasiTerapkan}>
                  {terapkan.isPending ? "Menyimpan…" : `Konfirmasi & terapkan ${hasil.berubah} perubahan`}
                </button>
                <button type="button" className={kelasTombolKecil}
                        disabled={batal.isPending} onClick={() => batal.mutate(token)}>
                  Batalkan pratinjau
                </button>
              </div>
            </div>
          ) : (
            <p className="mt-2 text-[11px] text-[#B42318]">
              Pratinjau belum bisa dikonfirmasi. Perbaiki baris yang ditolak, lalu tekan <b>Pratinjau</b> lagi.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function PanelExcelDiff({ filter, cari, epoch, onSelesai }: {
  filter: FilterIntake; cari: string; epoch: number;
  onSelesai: (pesan: string) => Promise<void>;
}) {
  const [berkas, setBerkas] = useState<File | null>(null);
  const [hasil, setHasil] = useState<HasilExcel | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [galat, setGalat] = useState<string | null>(null);
  const inputBerkas = useRef<HTMLInputElement>(null);

  const params = new URLSearchParams();
  if (filter.tahun) params.set("tahun", filter.tahun);
  if (filter.provinsi) params.set("provinsi", filter.provinsi);
  if (filter.supplier) params.set("supplier", filter.supplier);
  if (cari) params.set("q", cari);
  const urlBerisi = `/api/intake/excel-diff/template?${params.toString()}`;
  const urlKosong = "/api/intake/excel-diff/template?kosong=1";

  const bersihkanBerkas = () => {
    setBerkas(null);
    if (inputBerkas.current) inputBerkas.current.value = "";
  };
  const resetHasil = () => {
    setHasil(null);
    setToken(null);
    setGalat(null);
  };

  const pratinjau = useMutation({
    mutationFn: () => {
      if (!berkas) throw new Error("Pilih file .xlsx terlebih dahulu.");
      const form = new FormData();
      form.append("file", berkas);
      return kirimMetode("/api/intake/excel-diff/pratinjau", "POST", form) as Promise<HasilExcel>;
    },
    onSuccess: (data) => {
      setHasil(data);
      setToken(data.token);
      setGalat(null);
    },
    onError: (e: Error) => {
      resetHasil();
      setGalat(e.message);
    },
  });
  const terapkan = useMutation({
    mutationFn: (t: string) => kirimMetode("/api/intake/excel-diff/terapkan", "POST", {
      token: t,
    }) as Promise<{ pesan: string }>,
    onSuccess: async (data) => {
      resetHasil();
      bersihkanBerkas();
      await onSelesai(data.pesan);
    },
    onError: (e: Error) => {
      resetHasil();
      setGalat(e.message);
    },
  });
  const batal = useMutation({
    mutationFn: (t: string) => kirimMetode(
      `/api/intake/excel-diff/pratinjau/${encodeURIComponent(t)}`, "DELETE"),
    onSuccess: () => {
      resetHasil();
      bersihkanBerkas();
    },
    onError: (e: Error) => setGalat(e.message),
  });

  useEffect(() => {
    resetHasil();
    bersihkanBerkas();
  }, [epoch, filter, cari]);
  useEffect(() => {
    resetHasil();
  }, [berkas]);

  const tampil = (v: string | number | null) => {
    if (v === null || v === "") return "—";
    if (typeof v === "number") return fmtAngka(v, 3);
    return String(v);
  };
  const diff = useMemo(() => (hasil?.baris ?? []).flatMap((b) =>
    b.perubahan.map((p) => ({
      kunci: `${b.id}-${p.kolom}`,
      ticket: `${b.ticket_no} · ${b.line_seq}`,
      ...p,
    }))), [hasil]);
  const konfirmasiTerapkan = () => {
    if (!token || !hasil || hasil.status !== "siap" || hasil.berubah === 0) return;
    const ok = window.confirm(
      `Terapkan ${hasil.jumlah_perubahan} perubahan pada ${hasil.berubah} baris dari file ${hasil.nama_file}?\n\n` +
      "Perubahan tercatat per baris di audit log, menyegarkan ringkasan/alarm, dan tidak dibatalkan otomatis. " +
      "Lanjutkan hanya bila pratinjau sudah benar.");
    if (ok) terapkan.mutate(token);
  };

  return (
    <section className="mt-4 rounded-sm border border-[#D7E7FF] bg-[#F8FBFF] p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-[#1D2434]">Excel diff koreksi intake</h3>
          <p className="mt-0.5 max-w-3xl text-[11px] leading-relaxed text-[#64676C]">
            Untuk koreksi yang <b>berbeda-beda per baris</b>. Unduh Excel berisi nilai lama sesuai filter,
            ubah sel yang perlu, lalu unggah kembali untuk pratinjau dan konfirmasi.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <a className={kelasTombolKecil} href={urlBerisi} download>Unduh Excel baris filter ini</a>
          <a className={kelasTombolKecil} href={urlKosong} download>Unduh template kosong</a>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 items-end gap-2 md:grid-cols-[minmax(260px,1fr)_auto]">
        <label className="block">
          <span className={kelasLabel}>File koreksi .xlsx</span>
          <input ref={inputBerkas} className={kelasInput} type="file"
                 accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                 onChange={(e) => setBerkas(e.target.files?.[0] ?? null)} />
        </label>
        <div className="flex flex-wrap gap-1.5 pb-0.5">
          <button type="button" className={kelasTombolKecil}
                  disabled={!berkas || pratinjau.isPending}
                  onClick={() => pratinjau.mutate()}>
            {pratinjau.isPending ? "Memeriksa…" : "Pratinjau"}
          </button>
        </div>
      </div>
      {berkas && (
        <p className="mt-1 text-[10px] text-[#64676C]">
          Berkas: <b>{berkas.name}</b> · {(berkas.size / 1024).toFixed(1)} KB
        </p>
      )}
      <p className="mt-2 text-[10px] leading-relaxed text-[#64676C]">
        Maksimal 500 baris / 5 MB. Hanya admin yang dapat menerapkan. Nilai lama sudah terisi pada
        unduhan utama; <b>sel kosong berarti menghapus nilai opsional</b>. Template kosong hanya
        untuk melihat format. Ticket No, Baris, Asal Getah, sidik sumber, dan file unggahan asli
        tetap tidak berubah.
      </p>
      {galat && <p role="alert" className="mt-2 rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">{galat}</p>}

      {hasil && (
        <div className="mt-3 rounded-sm border border-[#E4E5E8] bg-white p-3">
          <p className={`text-xs font-semibold ${hasil.status === "siap" ? "text-[#15803D]" : hasil.status === "kosong" ? "text-[#B45309]" : "text-[#B42318]"}`}>
            {hasil.pesan}
          </p>
          {hasil.galat.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-[11px] text-[#B42318]">
              {hasil.galat.slice(0, 8).map((g, i) => (
                <li key={`${g.id}-${i}`}>{g.ticket_no} · baris {g.line_seq}: {g.alasan}</li>
              ))}
              {hasil.galat.length > 8 && <li>…{hasil.galat.length - 8} baris lain ditolak.</li>}
            </ul>
          )}
          {diff.length > 0 && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-[11px]">
                <thead className="bg-[#F8F8F8] text-left uppercase tracking-wider text-[#64676C]">
                  <tr>
                    <th className="px-2 py-1.5">Tiket / baris</th>
                    <th className="px-2 py-1.5">Kolom</th>
                    <th className="px-2 py-1.5">Sebelumnya</th>
                    <th className="px-2 py-1.5">Sesudah</th>
                  </tr>
                </thead>
                <tbody>
                  {diff.slice(0, 30).map((d) => (
                    <tr key={d.kunci} className="border-t border-[#EDEFF2]">
                      <td className="px-2 py-1.5 font-mono">{d.ticket}</td>
                      <td className="px-2 py-1.5">{d.label}</td>
                      <td className="px-2 py-1.5">{tampil(d.sebelumnya)}</td>
                      <td className="px-2 py-1.5 font-semibold">{tampil(d.sesudah)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {diff.length > 30 && (
                <p className="mt-1 text-[10px] text-[#64676C]">
                  Menampilkan 30 dari {diff.length} perubahan; ringkasan lengkap ada di pesan di atas.
                </p>
              )}
            </div>
          )}
          {hasil.status === "kosong" && (
            <p className="mt-2 text-[11px] text-[#B45309]">
              Tidak ada nilai yang berubah. Isi nilai baru pada Excel, lalu tekan <b>Pratinjau</b> lagi.
            </p>
          )}
          {hasil.status === "siap" && token ? (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-sm border border-[#BBF7D0] bg-[#F0FDF4] px-3 py-2">
              <div>
                <p className="text-xs font-semibold text-[#15803D]">Konfirmasi pratinjau</p>
                <p className="mt-0.5 text-[11px] leading-relaxed text-[#475569]">
                  Klik <b>Konfirmasi &amp; terapkan {hasil.jumlah_perubahan} perubahan</b>, lalu pilih <b>OK</b> pada dialog browser.
                  Token berlaku {Math.round((hasil.kedaluwarsa_detik ?? 900) / 60)} menit dan hanya sekali pakai.
                  {hasil.status === "siap" && " Tombol konfirmasi ada di blok hijau di bawah tabel diff."}
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button type="button" className={kelasTombol}
                        disabled={terapkan.isPending || hasil.berubah === 0} onClick={konfirmasiTerapkan}>
                  {terapkan.isPending ? "Menyimpan…" : `Konfirmasi & terapkan ${hasil.jumlah_perubahan} perubahan`}
                </button>
                <button type="button" className={kelasTombolKecil}
                        disabled={batal.isPending} onClick={() => batal.mutate(token)}>
                  Batalkan pratinjau
                </button>
              </div>
            </div>
          ) : hasil.status === "ada_galat" ? (
            <p className="mt-2 text-[11px] text-[#B42318]">
              Pratinjau belum bisa dikonfirmasi. Perbaiki baris yang ditolak, lalu tekan <b>Pratinjau</b> lagi.
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}

export default function IntakeData() {
  const qc = useQueryClient();
  const [filterDraft, setFilterDraft] = useState<FilterIntake>({ tahun: "", provinsi: "", supplier: "" });
  const [filterAktif, setFilterAktif] = useState<FilterIntake | null>(null);
  const [supplierSearch, setSupplierSearch] = useState("");
  const [supplierMenuOpen, setSupplierMenuOpen] = useState(false);
  const provinceOptions = useQuery({
    queryKey: ["intake-options-provinsi"],
    queryFn: () => ambilJson("/api/intake/options/provinsi") as Promise<{ options: string[] }>,
    staleTime: 5 * 60_000,
  });
  const supplierParams = new URLSearchParams({ q: supplierSearch.trim() });
  if (filterDraft.tahun) supplierParams.set("tahun", filterDraft.tahun);
  if (filterDraft.provinsi) supplierParams.set("provinsi", filterDraft.provinsi);
  const supplierOptions = useQuery({
    queryKey: ["intake-options-supplier", supplierSearch.trim(), filterDraft.tahun, filterDraft.provinsi],
    queryFn: async (): Promise<{ options: string[]; has_more: boolean }> =>
      await ambilJson(`/api/intake/options/supplier?${supplierParams}`),
    enabled: supplierSearch.trim().length >= 2 && supplierMenuOpen,
    staleTime: 30_000,
  });
  const [cariInput, setCariInput] = useState("");
  const [cari, setCari] = useState("");
  const [page, setPage] = useState(1);
  const [edit, setEdit] = useState<IntakeBaris | null>(null);
  const [pesan, setPesan] = useState<{ ok: boolean; teks: string } | null>(null);
  const [galatEdit, setGalatEdit] = useState<string | null>(null);
  const [terpilih, setTerpilih] = useState<Set<number>>(() => new Set());
  const [quickFillEpoch, setQuickFillEpoch] = useState(0);
  const terpilihIds = useMemo(() => Array.from(terpilih), [terpilih]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setCari(cariInput.trim());
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [cariInput]);

  useEffect(() => {
    setTerpilih(new Set());
    setQuickFillEpoch((n) => n + 1);
  }, [filterAktif, cari]);

  const params = new URLSearchParams({ page: String(page), page_size: "50" });
  if (filterAktif?.tahun) params.set("tahun", filterAktif.tahun);
  if (filterAktif?.provinsi) params.set("provinsi", filterAktif.provinsi);
  if (filterAktif?.supplier) params.set("supplier", filterAktif.supplier);
  if (cari) params.set("q", cari);
  const daftar = useQuery({
    queryKey: ["intake-baris", filterAktif, cari, page],
    queryFn: () => ambilJson(`/api/intake?${params.toString()}`) as Promise<HasilDaftar>,
    enabled: Boolean(filterAktif),
  });

  const ubahFilter = (key: "tahun" | "provinsi", nilai: string) => {
    setFilterDraft((f) => ({ ...f, [key]: nilai }));
    setFilterAktif(null);
    setPage(1);
    setCariInput("");
    setCari("");
  };
  const cariSupplier = (nilai: string) => {
    setSupplierSearch(nilai);
    setSupplierMenuOpen(true);
    setFilterDraft((f) => ({ ...f, supplier: "" }));
    setFilterAktif(null);
    setPage(1);
    setCariInput("");
    setCari("");
  };
  const pilihSupplier = (nama: string) => {
    setSupplierSearch(nama);
    setFilterDraft((f) => ({ ...f, supplier: nama }));
    setSupplierMenuOpen(false);
    setFilterAktif(null);
    setPage(1);
    setCariInput("");
    setCari("");
  };
  const adaFilter = Boolean(filterDraft.tahun || filterDraft.provinsi || filterDraft.supplier);
  const supplierBelumDipilih = Boolean(supplierSearch.trim() && !filterDraft.supplier);
  const terapkanFilter = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!adaFilter || supplierBelumDipilih) return;
    setFilterAktif({
      tahun: filterDraft.tahun.trim(),
      provinsi: filterDraft.provinsi.trim(),
      supplier: filterDraft.supplier.trim(),
    });
    setCariInput("");
    setCari("");
    setPage(1);
    setPesan(null);
  };

  const invalidasiDataTurunan = () => Promise.all([
    "intake-baris", "penerimaan", "penerimaan-provinsi", "penerimaan-vendor",
    "peta-intake-provinsi", "tonase", "konsentrasi", "grade", "intake-terakhir",
    "reject", "margin-harian", "margin-per", "margin-bulanan-grafik", "grafik-margin",
    "ringkasan", "ringkasan-elemen", "margin-bridge", "days-of-cover", "doc-strip",
    "bridge-strip", "alarm-strip", "kualitas-strip", "rekomendasi-strip",
    "traceability", "traceability-actors", "traceability-actor-detail",
  ].map((kunci) => qc.invalidateQueries({ queryKey: [kunci] })));

  const ubah = useMutation({
    mutationFn: ({ id, form }: { id: number; form: FormIntake }) => {
      const body: Record<string, unknown> = { ...form };
      for (const key of ["wet_kg", "sample_kg", "reject_kg", "drc_pct", "dry_kg"]) {
        body[key] = form[key].trim() === "" ? null : Number(form[key]);
      }
      for (const key of ["nama_vendor_asli", "vehicle_no", "item_code", "drc_date", "provinsi", "kabupaten", "kecamatan", "desa", "bin", "location"]) {
        body[key] = form[key].trim() || null;
      }
      body.kode_vendor = form.kode_vendor.trim().toUpperCase();
      return kirimMetode(`/api/intake/${id}`, "PUT", body);
    },
    onSuccess: async (data) => {
      setPesan({ ok: true, teks: data.pesan });
      setEdit(null);
      setGalatEdit(null);
      setQuickFillEpoch((n) => n + 1);
      await invalidasiDataTurunan();
    },
    onError: (error: Error) => setGalatEdit(error.message),
  });
  const hapus = useMutation({
    mutationFn: (id: number) => kirimMetode(`/api/intake/${id}`, "DELETE"),
    onSuccess: async (data, id) => {
      setPesan({ ok: true, teks: data.pesan });
      setTerpilih((sebelum) => {
        const berikut = new Set(sebelum);
        berikut.delete(id);
        return berikut;
      });
      setQuickFillEpoch((n) => n + 1);
      if ((daftar.data?.baris.length ?? 0) === 1 && page > 1) setPage((n) => Math.max(1, n - 1));
      await invalidasiDataTurunan();
    },
    onError: (error: Error) => setPesan({ ok: false, teks: error.message }),
  });
  const konfirmasiHapus = (row: IntakeBaris) => {
    const konfirmasi = window.confirm(
      `Hapus permanen baris intake ini?\nTiket: ${row.ticket_no} · baris ${row.line_seq}\nDry: ${row.dry_kg ?? "—"} kg\n\nPerubahan ini akan tercatat pada audit log dan memengaruhi ringkasan.`);
    if (konfirmasi) hapus.mutate(row.id);
  };

  const rows = filterAktif ? (daftar.data?.baris ?? []) : [];
  const total = filterAktif ? (daftar.data?.total ?? 0) : 0;
  const pages = filterAktif ? (daftar.data?.pages ?? 0) : 0;
  const semuaHalamanTerpilih = rows.length > 0 && rows.every((r) => terpilih.has(r.id));
  const toggleBaris = (id: number) => setTerpilih((sebelum) => {
    const berikut = new Set(sebelum);
    if (berikut.has(id)) berikut.delete(id); else berikut.add(id);
    return berikut;
  });
  const toggleSemuaHalaman = () => setTerpilih((sebelum) => {
    const berikut = new Set(sebelum);
    if (semuaHalamanTerpilih) rows.forEach((r) => berikut.delete(r.id));
    else rows.forEach((r) => berikut.add(r.id));
    return berikut;
  });
  const bersihkanPilihan = () => setTerpilih(new Set());
  const selesaiQuickFill = async (pesan: string) => {
    setPesan({ ok: true, teks: pesan });
    setTerpilih(new Set());
    setQuickFillEpoch((n) => n + 1);
    await invalidasiDataTurunan();
  };

  const labelFilterAktif = filterAktif ? [
    filterAktif.tahun && `Tahun ${filterAktif.tahun}`,
    filterAktif.provinsi && `Provinsi ${filterAktif.provinsi}`,
    filterAktif.supplier && `Supplier ${filterAktif.supplier}`,
  ].filter(Boolean).join(" · ") : "";

  return (
    <div className="space-y-4">
      <section className="rounded-sm border border-[#E4E5E8] border-l-[3px] border-l-[#FF1313] bg-white p-5 shadow-[0_1px_3px_rgba(29,36,52,0.08)]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-[#1D2434]">Data Intake Details — Penerimaan Karet</h2>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-[#64676C]">
              Gunakan satu atau beberapa filter. Data baris hanya dimuat setelah tombol
              Tampilkan Data ditekan, agar daftar tetap ringan untuk volume intake besar.
            </p>
          </div>
          <div className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-3 py-2 text-right">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#64676C]">Total baris intake</p>
            <p className="text-lg font-bold tabular-nums text-[#1D2434]">{!filterAktif ? "—" : daftar.isLoading ? "…" : fmtAngka(total, 0)}</p>
          </div>
        </div>

        <form className="mt-4 rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3" onSubmit={terapkanFilter}>
          <div className="grid grid-cols-1 items-end gap-3 md:grid-cols-[150px_minmax(200px,1fr)_minmax(240px,1.2fr)_auto]">
            <label>
              <span className={kelasLabel}>Tahun (opsional)</span>
              <input className={kelasInput} type="number" min="1900" max="2200" step="1"
                     value={filterDraft.tahun}
                     onChange={(e) => ubahFilter("tahun", e.target.value)} placeholder="Semua tahun" />
            </label>
            <label>
              <span className={kelasLabel}>Provinsi (opsional)</span>
              <select className={kelasInput} value={filterDraft.provinsi}
                      onChange={(e) => ubahFilter("provinsi", e.target.value)}>
                <option value="">Semua provinsi</option>
                {(provinceOptions.data?.options ?? []).map((nama) => (
                  <option key={nama} value={nama}>{nama}</option>
                ))}
              </select>
              {provinceOptions.isLoading && <span className="mt-1 block text-[10px] text-[#9AA0A6]">Memuat pilihan provinsi…</span>}
            </label>
            <div className="relative">
              <label htmlFor="intake-supplier-filter" className={kelasLabel}>Nama supplier (opsional)</label>
              <input id="intake-supplier-filter" className={kelasInput} type="search" maxLength={200}
                     value={supplierSearch}
                     onFocus={() => setSupplierMenuOpen(true)}
                     onBlur={() => window.setTimeout(() => setSupplierMenuOpen(false), 120)}
                     onChange={(e) => cariSupplier(e.target.value)}
                     placeholder="Ketik awal nama, lalu pilih dari dropdown" />
              {filterDraft.supplier && <p className="mt-1 text-[10px] text-[#15803D]">Terpilih: {filterDraft.supplier}</p>}
              {supplierMenuOpen && supplierSearch.trim().length >= 2 && (
                <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-56 overflow-y-auto rounded-sm border border-[#D5D7DB] bg-white shadow-lg">
                  {supplierOptions.isLoading ? (
                    <p className="px-3 py-2 text-xs text-[#64676C]">Mencari nama supplier…</p>
                  ) : (supplierOptions.data?.options ?? []).length > 0 ? (
                    <>
                      {(supplierOptions.data?.options ?? []).map((nama) => (
                        <button key={nama} type="button"
                                className="block w-full border-b border-[#EDEFF2] px-3 py-2 text-left text-xs text-[#1D2434] hover:bg-[#F8F8F8]"
                                onMouseDown={(e) => e.preventDefault()}
                                onClick={() => pilihSupplier(nama)}>
                          {nama}
                        </button>
                      ))}
                      {supplierOptions.data?.has_more && <p className="px-3 py-2 text-[10px] text-[#64676C]">Ada hasil lain; tambahkan huruf agar lebih spesifik.</p>}
                    </>
                  ) : (
                    <p className="px-3 py-2 text-xs text-[#64676C]">Tidak ada nama supplier dengan awalan tersebut.</p>
                  )}
                </div>
              )}
            </div>
            {adaFilter && <button className={kelasTombol} type="submit" disabled={supplierBelumDipilih}>Tampilkan Data</button>}
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-[#64676C]">
            Pilih minimal satu filter. Provinsi dan supplier berasal dari nilai yang tercatat di database;
            dropdown supplier mencari berdasarkan awalan nama dan menampilkan maksimal 50 pilihan.
            {!adaFilter && <span className="ml-1 font-semibold">Isi filter untuk menampilkan tombol.</span>}
            {supplierBelumDipilih && <span className="ml-1 font-semibold text-[#B45309]">Pilih nama supplier dari dropdown atau hapus teks pencarian tersebut.</span>}
          </p>
        </form>

        {filterAktif && (
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <label className="min-w-[260px] flex-1">
              <span className={kelasLabel}>Pencarian tambahan (opsional)</span>
              <input className={kelasInput} type="search" value={cariInput}
                     onChange={(e) => setCariInput(e.target.value)}
                     placeholder="Ticket No, kendaraan, grade, kabupaten, kecamatan, desa…" />
            </label>
            {cariInput && <button type="button" className={kelasTombolKecil} onClick={() => setCariInput("")}>Hapus pencarian</button>}
            {daftar.isFetching && !daftar.isLoading && <span className="pb-2 text-xs text-[#64676C]">Memperbarui hasil…</span>}
          </div>
        )}
        {filterAktif && (
          <PanelExcelDiff filter={filterAktif} cari={cari} epoch={quickFillEpoch}
                          onSelesai={selesaiQuickFill} />
        )}
        {filterAktif && rows.length > 0 && (
          <PanelQuickFill terpilih={terpilihIds} rows={rows} epoch={quickFillEpoch}
                          onBersihkan={bersihkanPilihan} onSelesai={selesaiQuickFill} />
        )}
        {pesan && <p role="status" className={`mt-3 rounded-sm border px-3 py-2 text-sm ${pesan.ok ? "border-[#BBF7D0] bg-[#F0FDF4] text-[#15803D]" : "border-[#FECACA] bg-[#FEF2F2] text-[#B91C1C]"}`}>{pesan.teks}</p>}
        {filterAktif && daftar.error && <p role="alert" className="mt-3 rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-sm text-[#B91C1C]">{(daftar.error as Error).message}</p>}

        <div className="mt-4 overflow-x-auto rounded-sm border border-[#E4E5E8]">
          <table className="w-full min-w-[1120px] border-collapse text-xs">
            <thead className="sticky top-0 bg-[#F8F8F8] text-left text-[10px] uppercase tracking-wider text-[#64676C]">
              <tr>
                <th className="w-8 px-3 py-2">
                  <input type="checkbox" checked={semuaHalamanTerpilih}
                         onChange={toggleSemuaHalaman}
                         aria-label="Pilih semua baris di halaman ini" />
                </th>
                <th className="px-3 py-2">Tanggal</th>
                <th className="px-3 py-2">Ticket No / baris</th>
                <th className="px-3 py-2">Supplier</th>
                <th className="px-3 py-2">Grade</th>
                <th className="px-3 py-2">Provinsi</th>
                <th className="px-3 py-2">Kabupaten/Kota</th>
                <th className="px-3 py-2">Kecamatan</th>
                <th className="px-3 py-2">Desa</th>
                <th className="px-3 py-2 text-right">Dry (kg)</th>
                <th className="px-3 py-2 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {!filterAktif ? (
                <tr><td colSpan={11} className="px-3 py-10 text-center text-sm text-[#64676C]">
                  Pilih satu atau beberapa filter, lalu tekan <b>Tampilkan Data</b>. Belum ada baris intake yang dimuat.
                </td></tr>
              ) : daftar.isLoading ? (
                <tr><td colSpan={11} className="px-3 py-10 text-center text-sm text-[#64676C]">Memuat hasil filter…</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={11} className="px-3 py-10 text-center text-sm text-[#64676C]">
                  {cari ? `Tidak ada intake yang cocok dengan “${cari}”.` : "Tidak ada intake yang cocok dengan filter yang dipilih."}
                </td></tr>
              ) : rows.map((row) => (
                <tr key={row.id} className="border-t border-[#EDEFF2] hover:bg-[#FAFAFA]">
                  <td className="px-3 py-2">
                    <input type="checkbox" checked={terpilih.has(row.id)}
                           onChange={() => toggleBaris(row.id)}
                           aria-label={`Pilih ${row.ticket_no} baris ${row.line_seq}`} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">{row.ticket_date ? fmtTanggal(row.ticket_date) : "—"}</td>
                  <td className="px-3 py-2 font-mono font-semibold text-[#1D2434]">
                    {row.ticket_no}<span className="ml-1 font-sans text-[10px] font-normal text-[#9AA0A6]">· {row.line_seq}</span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-semibold text-[#1D2434]">{row.nama_vendor_asli || row.kode_vendor}</div>
                    <div className="font-mono text-[10px] text-[#64676C]">{row.kode_vendor}{row.vehicle_no ? ` · ${row.vehicle_no}` : ""}</div>
                  </td>
                  <td className="px-3 py-2">{row.item_code || "—"}</td>
                  <td className="max-w-36 truncate px-3 py-2" title={row.provinsi || ""}>{row.provinsi || "—"}</td>
                  <td className="max-w-44 truncate px-3 py-2" title={row.kabupaten || ""}>{row.kabupaten || "—"}</td>
                  <td className="max-w-40 truncate px-3 py-2" title={row.kecamatan || ""}>{row.kecamatan || "—"}</td>
                  <td className="max-w-40 truncate px-3 py-2" title={row.desa || ""}>{row.desa || "—"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-right font-mono">{row.dry_kg == null ? "—" : fmtAngka(row.dry_kg, 0)}</td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex justify-end gap-1.5">
                      <button type="button" className={kelasTombolKecil}
                              onClick={() => { setEdit(row); setGalatEdit(null); setPesan(null); }}>Edit</button>
                      <button type="button"
                              className="rounded-sm border border-[#FECACA] px-2 py-1 text-[11px] font-semibold text-[#B42318] hover:bg-[#FEF2F2] disabled:cursor-not-allowed disabled:opacity-50"
                              disabled={hapus.isPending}
                              onClick={() => konfirmasiHapus(row)}>
                        {hapus.isPending && hapus.variables === row.id ? "Menghapus…" : "Hapus"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-[#64676C]">
          <span>
            {!filterAktif ? "Belum ada baris dimuat" : total === 0 ? "0 baris" : `Menampilkan ${(page - 1) * 50 + 1}–${Math.min(page * 50, total)} dari ${fmtAngka(total, 0)} baris`}
            {labelFilterAktif ? ` · ${labelFilterAktif}` : ""}
            {cari ? ` · pencarian: “${cari}”` : ""}
          </span>
          <div className="flex items-center gap-2">
            <button className={kelasTombolKecil} disabled={page <= 1 || daftar.isFetching} onClick={() => setPage((n) => Math.max(1, n - 1))}>Sebelumnya</button>
            <span className="tabular-nums">Halaman {pages ? page : 0} / {pages}</span>
            <button className={kelasTombolKecil} disabled={!pages || page >= pages || daftar.isFetching} onClick={() => setPage((n) => Math.min(pages, n + 1))}>Berikutnya</button>
          </div>
        </div>
      </section>

      {edit && <ModalEdit row={edit} tutup={() => setEdit(null)}
                          simpan={(form) => ubah.mutate({ id: edit.id, form })}
                          menyimpan={ubah.isPending} error={galatEdit} />}
    </div>
  );
}
