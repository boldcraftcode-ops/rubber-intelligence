import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, Pesan, ambilJson, fmtAngka, fmtTanggal, hariIni,
  kelasInput, kelasLabel, kelasTombol, kelasTombolKecil, kirimJson, urlApi,
} from "../bersama";

const pengisi = () => localStorage.getItem("op-margin.pengisi") || "?";

/* ================= master grade ================= */
function KartuMasterGrade() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["grade"], queryFn: () => ambilJson("/api/grade") });
  const [form, setForm] = useState({ item_code: "", kelompok: "", eudr: false, keterangan: "" });
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  const simpan = useMutation({
    mutationFn: () => kirimJson("/api/grade", { ...form, pengisi: pengisi() }),
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      setForm({ item_code: "", kelompok: "", eudr: false, keterangan: "" });
      qc.invalidateQueries({ queryKey: ["grade"] });
      qc.invalidateQueries({ queryKey: ["harga-terkini"] });
    },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });

  return (
    <Kartu idMetrik="grade_harga" judul="Master grade"
           keterangan="Daftar Item Code yang dikenal sistem. Kode mengandung TTSR otomatis ditandai EUDR; LATEX OP = getah cair."
           anak={
      <>
        <table className="w-full text-xs mb-4">
          <thead>
            <tr className="text-left text-[#64676C] border-b">
              <th className="py-1">Item Code</th><th>Kelompok</th><th>EUDR</th>
              <th>Keterangan</th><th></th>
            </tr>
          </thead>
          <tbody>
            {q.data?.map((g: any) => (
              <tr key={g.item_code} className="border-b border-[#EDEFF2]">
                <td className="py-1 font-mono text-[#1D2434]">{g.item_code}</td>
                <td className="text-[#1D2434]">{g.kelompok ?? "-"}</td>
                <td>{g.eudr
                  ? <span className="rounded bg-[#DCFCE7] text-[#15803D] px-1.5 py-0.5">EUDR</span>
                  : "–"}</td>
                <td className="text-[#64676C]">{g.keterangan ?? "-"}</td>
                <td>
                  <button className={kelasTombolKecil}
                          onClick={() => setForm({
                            item_code: g.item_code, kelompok: g.kelompok ?? "",
                            eudr: g.eudr, keterangan: g.keterangan ?? "" })}>
                    ubah
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 className="text-sm font-semibold text-[#1D2434] mb-2">
          {q.data?.some((g: any) => g.item_code === form.item_code)
            ? `Ubah grade ${form.item_code}` : "Tambah grade baru"}
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 items-end">
          <div>
            <label className={kelasLabel}>Item Code</label>
            <input className={kelasInput} placeholder="mis. SLAB4" value={form.item_code}
                   onChange={(e) => setForm({ ...form, item_code: e.target.value })} />
          </div>
          <div>
            <label className={kelasLabel}>Kelompok</label>
            <input className={kelasInput} placeholder="mis. Slab 4" value={form.kelompok}
                   onChange={(e) => setForm({ ...form, kelompok: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm text-[#1D2434] pb-2">
            <input type="checkbox" className="accent-[#FF1313]" checked={form.eudr}
                   onChange={(e) => setForm({ ...form, eudr: e.target.checked })} />
            EUDR
          </label>
          <div>
            <label className={kelasLabel}>Keterangan</label>
            <input className={kelasInput} value={form.keterangan}
                   onChange={(e) => setForm({ ...form, keterangan: e.target.value })} />
          </div>
          <button className={kelasTombol} disabled={simpan.isPending || !form.item_code.trim()}
                  onClick={() => { setInfo(null); simpan.mutate(); }}>
            Simpan grade
          </button>
        </div>
        {info && <Pesan jenis={info.jenis} teks={info.teks} />}
      </>
    } />
  );
}

/* ================= harga per grade ================= */
function KartuHargaGrade() {
  const qc = useQueryClient();
  const [tanggal, setTanggal] = useState(hariIni());
  const [harga, setHarga] = useState<Record<string, string>>({});
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  const terkini = useQuery({
    queryKey: ["harga-terkini", tanggal],
    queryFn: () => ambilJson(`/api/harga-grade/terkini?tanggal=${tanggal}`),
  });
  const riwayat = useQuery({
    queryKey: ["harga-riwayat"],
    queryFn: () => ambilJson("/api/harga-grade?limit=30"),
  });

  // Harga acuan langsung mengisi pratinjau grade turunan sebelum disimpan.
  useEffect(() => { setHarga({}); }, [tanggal]);

  const ubahHarga = (kode: string, nilai: string) => {
    setHarga((sebelum) => {
      const baru = { ...sebelum, [kode]: nilai };
      const bersihkanTurunan = () => {
        for (const turunan of ["SLAB1", "SLAB1 TTSR", "SLAB2", "SLAB2 TTSR", "SLAB3", "SLAB3 TTSR"])
          delete baru[turunan];
      };
      const angkaHarga = (s: string) => Number(s.replace(/\\./g, "").replace(",", "."));
      const aturTurunan = (item: string, nilaiTurunan: string) => {
        if (terkini.data?.baris.some((b: any) => b.item_code === item)) baru[item] = nilaiTurunan;
      };
      if (kode.trim().toUpperCase() === "SLAB") {
        bersihkanTurunan();
        if (nilai.trim()) {
          const slab = angkaHarga(nilai);
          aturTurunan("SLAB1", String(slab));
          aturTurunan("SLAB1 TTSR", String(slab));
          aturTurunan("SLAB2", String(slab - 300));
          aturTurunan("SLAB2 TTSR", String(slab - 300));
          aturTurunan("SLAB3", String(slab - 2300));
          aturTurunan("SLAB3 TTSR", String(slab - 2300));
        }
      } else if (kode.trim().toUpperCase() === "SLAB2") {
        delete baru["SLAB3"]; delete baru["SLAB3 TTSR"];
        if (nilai.trim()) {
          const slab3 = angkaHarga(nilai) - 2000;
          aturTurunan("SLAB2 TTSR", nilai);
          aturTurunan("SLAB3", String(slab3));
          aturTurunan("SLAB3 TTSR", String(slab3));
        }
      } else if (kode.trim().toUpperCase() === "SLAB1") {
        aturTurunan("SLAB1 TTSR", nilai);
      }
      return baru;
    });
  };

  const hargaSlabUtama = (harga.SLAB ?? "").trim() !== "";
  const hargaSlab2Utama = !hargaSlabUtama && (harga.SLAB2 ?? "").trim() !== "";
  const turunanOtomatis = (kode: string) => hargaSlabUtama && ["SLAB1", "SLAB1 TTSR", "SLAB2", "SLAB2 TTSR", "SLAB3", "SLAB3 TTSR"].includes(kode)
    || hargaSlab2Utama && ["SLAB2 TTSR", "SLAB3", "SLAB3 TTSR"].includes(kode);

  const simpan = useMutation({
    mutationFn: () => {
      const baris = Object.entries(harga)
        .filter(([, v]) => v.trim() !== "")
        .map(([kode, v]) => ({
          item_code: kode,
          harga_rp_per_kg: Number(v.replace(/\./g, "").replace(",", ".")),
        }));
      if (!baris.length) throw new Error("Isi dulu minimal satu harga.");
      return kirimJson("/api/harga-grade", { tanggal, baris, pengisi: pengisi() });
    },
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      setHarga({});
      qc.invalidateQueries({ queryKey: ["harga-terkini"] });
      qc.invalidateQueries({ queryKey: ["harga-riwayat"] });
    },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });

  return (
    <Kartu idMetrik="grade_harga" judul="Harga beli per grade (Rp/kg)"
           keterangan="Berlaku sejak tanggal yang dipilih sampai ada harga baru. Kolom US¢ & margin dihitung otomatis dari kurs dan SICOM yang berlaku."
           anak={
      <>
        <div className="flex flex-wrap items-end gap-3 mb-3">
          <div>
            <label className={kelasLabel}>Berlaku sejak</label>
            <input type="date" className={kelasInput} value={tanggal}
                   onChange={(e) => setTanggal(e.target.value)} />
          </div>
          <button className={kelasTombol} disabled={simpan.isPending}
                  onClick={() => { setInfo(null); simpan.mutate(); }}>
            Simpan semua harga terisi
          </button>
          <a className={kelasTombolKecil} href={urlApi("/api/harga-grade/template")}>
            ⬇ Unduh template bulk import
          </a>
          <span className="text-xs text-[#64676C]">
            Bulk import: unduh template → isi kolom harga → unggah di tab
            <b> Unggah Data</b> (sheet Harga_Grade; boleh banyak tanggal sekaligus).
          </span>
        </div>

        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[#64676C] border-b">
              <th className="py-1">Grade</th>
              <th className="text-right">Harga berlaku</th>
              <th>Sejak</th>
              <th className="text-right">US¢/kg</th>
              <th className="text-right">Margin indikatif</th>
              <th className="pl-3">Harga baru (Rp/kg)</th>
            </tr>
          </thead>
          <tbody>
            {terkini.data?.baris.map((b: any) => (
              <tr key={b.item_code} className="border-b border-[#EDEFF2]">
                <td className="py-1.5 font-mono text-[#1D2434]">
                  {b.item_code}
                  {b.eudr && <span className="ml-1.5 rounded bg-[#DCFCE7] text-[#15803D] px-1 py-0.5 text-[10px]">EUDR</span>}
                </td>
                <td className="text-right font-mono">
                  {b.harga_rp_per_kg ? fmtAngka(b.harga_rp_per_kg, 0) : "–"}
                </td>
                <td className="text-[#64676C]">
                  {b.berlaku_sejak ? fmtTanggal(b.berlaku_sejak) : "belum ada"}
                </td>
                <td className="text-right font-mono">
                  {b.harga_usc_per_kg ? fmtAngka(b.harga_usc_per_kg, 2) : "–"}
                </td>
                <td className={`text-right font-mono ${
                  b.margin_indikatif_usc === null ? "" :
                  b.margin_indikatif_usc >= 0 ? "text-[#15803D]" : "text-[#DC2626]"}`}>
                  {b.margin_indikatif_usc !== null ? fmtAngka(b.margin_indikatif_usc, 2) : "–"}
                </td>
                <td className="pl-3">
                  <input className={`${kelasInput} w-32 text-right`}
                         inputMode="decimal" placeholder="kosong = tetap"
                         value={harga[b.item_code] ?? ""}
                         readOnly={turunanOtomatis(b.item_code)}
                         onChange={(e) => ubahHarga(b.item_code, e.target.value)} />
                </td>
              </tr>
            ))}
            {terkini.data?.baris.length === 0 && (
              <tr><td colSpan={6} className="py-3 text-[#64676C]">
                Belum ada grade di master — tambahkan dulu di kartu Master grade.
              </td></tr>
            )}
          </tbody>
        </table>
        {info && <Pesan jenis={info.jenis} teks={info.teks} />}

        <p className="mt-2 text-xs text-[#64676C]">
          SICOM {terkini.data?.sicom_usc ? fmtAngka(terkini.data.sicom_usc, 2) : "–"} US¢/kg ·
          kurs {terkini.data?.kurs ? fmtAngka(terkini.data.kurs, 0) : "–"} IDR/USD
          ({fmtTanggal(tanggal)}).
        </p>
        {terkini.data && (
          <p className="mt-2 rounded-sm bg-[#FFFBEB] border border-[#FDE68A] px-3 py-2 text-xs text-[#B45309]">
            {terkini.data.catatan}
          </p>
        )}

        <h3 className="mt-4 mb-1 text-sm font-semibold text-[#1D2434]">
          30 isian terakhir
        </h3>
        <div className="max-h-56 overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[#64676C] border-b">
                <th className="py-1">Berlaku sejak</th><th>Grade</th>
                <th className="text-right">Rp/kg</th><th>Diisi oleh</th>
              </tr>
            </thead>
            <tbody>
              {riwayat.data?.map((h: any, i: number) => (
                <tr key={i} className="border-b border-[#EDEFF2]">
                  <td className="py-1">{fmtTanggal(h.tanggal)}</td>
                  <td className="font-mono">{h.item_code}</td>
                  <td className="text-right font-mono">{fmtAngka(h.harga_rp_per_kg, 0)}</td>
                  <td className="text-[#64676C]">{h.diisi_oleh ?? "-"}</td>
                </tr>
              ))}
              {riwayat.data?.length === 0 && (
                <tr><td colSpan={4} className="py-2 text-[#64676C]">Belum ada isian.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </>
    } />
  );
}

export default function GradeHarga() {
  return (
    <div className="grid gap-6">
      <KartuHargaGrade />
      <KartuMasterGrade />
    </div>
  );
}
