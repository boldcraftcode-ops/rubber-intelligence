import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, Pesan, ambilJson, fmtAngka, fmtTanggal, hariIni,
  kelasInput, kelasLabel, kelasTombol, kelasTombolKecil, kirimJson,
} from "../bersama";

const pengisi = () => localStorage.getItem("op-margin.pengisi") || "?";

/* ---------- rekomendasi hari ini ---------- */
function KartuRekomendasi() {
  const q = useQuery({ queryKey: ["rekomendasi"], queryFn: () => ambilJson("/api/rekomendasi") });
  const r = q.data;

  return (
    <Kartu idMetrik="aturan" judul="Harga beli maksimum (hari berdata terakhir)"
           keterangan="Dihitung di level rata-rata semua grade — selisih antar grade belum ditetapkan [TERBUKA]."
           anak={
      !r ? null : r.status !== "OK" ? (
        <p className={`rounded-md px-3 py-4 text-sm font-semibold ${
          r.status === "ATURAN BELUM DIISI"
            ? "bg-red-500/10 text-red-300 border border-red-400/30"
            : "bg-amber-400/10 text-amber-300 border border-amber-400/30"}`}>
          {r.status}
          {r.alasan.map((a: string, i: number) => (
            <span key={i} className="block font-normal mt-1">{a}</span>
          ))}
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
            {[
              ["Harga maks (US¢/kg)", fmtAngka(r.harga_beli_maks_usc)],
              ["Harga maks (Rp/kg)", fmtAngka(r.harga_beli_maks_rp_kg, 2)],
              ["Harga aktual terakhir", fmtAngka(r.harga_beli_aktual_terakhir_usc)],
              ["Selisih vs maks",
               r.harga_beli_aktual_terakhir_usc !== null
                 ? fmtAngka(r.harga_beli_maks_usc - r.harga_beli_aktual_terakhir_usc)
                 : "–"],
            ].map(([label, nilai]) => (
              <div key={label as string} className="rounded-lg border border-violet-500/20 bg-white/5 p-3">
                <p className="text-xs text-slate-400">{label}</p>
                <p className="font-semibold text-slate-100">{nilai}</p>
              </div>
            ))}
          </div>
          <p className="text-xs font-semibold text-slate-300 mb-1">Alasan (selalu ditampilkan):</p>
          <ul className="list-disc pl-5 text-xs text-slate-300">
            {r.alasan.map((a: string, i: number) => <li key={i}>{a}</li>)}
          </ul>
          {r.aturan_contoh && (
            <p className="mt-2 rounded-md bg-red-500/10 border border-red-400/30 px-3 py-2 text-xs text-red-300">
              Aturan yang berlaku masih CONTOH dari template — buat versi resmi di bawah.
            </p>
          )}
        </>
      )
    } />
  );
}

/* ---------- editor versi aturan ---------- */
type Baris = { batas_bawah: string; batas_atas: string; penyesuaian_usc: string; keterangan: string };
const barisKosong = (): Baris => ({ batas_bawah: "", batas_atas: "", penyesuaian_usc: "", keterangan: "" });

function KartuAturan() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["aturan"], queryFn: () => ambilJson("/api/aturan") });
  const [berlaku, setBerlaku] = useState(hariIni());
  const [baris, setBaris] = useState<Baris[]>([barisKosong()]);
  const [alasan, setAlasan] = useState("");
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  const angka = (s: string) => (s.trim() === "" ? null : Number(s.replace(",", ".")));

  const simpan = useMutation({
    mutationFn: () => kirimJson("/api/aturan", {
      berlaku_dari: berlaku,
      baris: baris.map((b) => ({
        batas_bawah: angka(b.batas_bawah), batas_atas: angka(b.batas_atas),
        penyesuaian_usc: angka(b.penyesuaian_usc) ?? 0,
        keterangan: b.keterangan || null,
      })),
      alasan: alasan || null, pengisi: pengisi(),
    }),
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      setBaris([barisKosong()]); setAlasan("");
      qc.invalidateQueries({ queryKey: ["aturan"] });
      qc.invalidateQueries({ queryKey: ["rekomendasi"] });
      qc.invalidateQueries({ queryKey: ["audit-aturan"] });
      qc.invalidateQueries({ queryKey: ["alarm"] });
    },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });

  return (
    <Kartu idMetrik="aturan" judul="Aturan stok → harga (berversi, dengan riwayat)"
           keterangan="Baris = rentang rasio stok (batas bawah ≤, batas atas <) → penyesuaian target margin. Semua angka adalah data, bukan kode."
           anak={
      <>
        {q.data?.kosong && (
          <p className="mb-3 rounded-md bg-red-500/10 border border-red-400/30 px-3 py-2 text-sm font-semibold text-red-300">
            ATURAN BELUM DIISI
          </p>
        )}
        {q.data?.versi.map((v: any) => (
          <div key={v.berlaku_dari} className="mb-3 rounded-lg border border-violet-500/20 p-3">
            <p className="text-sm font-semibold text-slate-200">
              Berlaku sejak {fmtTanggal(v.berlaku_dari)}
              {v.contoh && <span className="ml-2 rounded bg-red-500/20 text-red-400 px-1.5 py-0.5 text-xs">CONTOH</span>}
            </p>
            <table className="mt-1 w-full text-xs">
              <thead>
                <tr className="text-left text-slate-400 border-b">
                  <th className="py-1">Rasio ≥</th><th>Rasio &lt;</th>
                  <th className="text-right">Penyesuaian US¢/kg</th><th className="pl-3">Keterangan</th>
                  <th>Oleh</th>
                </tr>
              </thead>
              <tbody>
                {v.baris.map((b: any, i: number) => (
                  <tr key={i} className="border-b border-white/5">
                    <td className="py-1 font-mono">{b.batas_bawah ?? "–∞"}</td>
                    <td className="font-mono">{b.batas_atas ?? "∞"}</td>
                    <td className="text-right font-mono">{fmtAngka(b.penyesuaian_usc, 2)}</td>
                    <td className="pl-3 text-slate-400">{b.keterangan ?? "-"}</td>
                    <td className="text-slate-500">{b.dibuat_oleh}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

        <h3 className="mt-4 mb-2 text-sm font-semibold text-slate-200">Buat versi baru</h3>
        <div className="grid sm:grid-cols-2 gap-3 mb-2">
          <div>
            <label className={kelasLabel}>Berlaku sejak</label>
            <input type="date" className={kelasInput} value={berlaku}
                   onChange={(e) => setBerlaku(e.target.value)} />
          </div>
          <div>
            <label className={kelasLabel}>Alasan perubahan</label>
            <input type="text" className={kelasInput} value={alasan}
                   placeholder="mis. keputusan rapat harga 18/10/2026"
                   onChange={(e) => setAlasan(e.target.value)} />
          </div>
        </div>
        {baris.map((b, i) => (
          <div key={i} className="grid grid-cols-9 gap-2 mb-2 items-center">
            <input className={`${kelasInput} col-span-2`} placeholder="rasio ≥ (mis. 0)"
                   value={b.batas_bawah}
                   onChange={(e) => setBaris(baris.map((x, j) => j === i ? { ...x, batas_bawah: e.target.value } : x))} />
            <input className={`${kelasInput} col-span-2`} placeholder="rasio < (kosong = ∞)"
                   value={b.batas_atas}
                   onChange={(e) => setBaris(baris.map((x, j) => j === i ? { ...x, batas_atas: e.target.value } : x))} />
            <input className={`${kelasInput} col-span-2`} placeholder="penyesuaian US¢/kg"
                   value={b.penyesuaian_usc}
                   onChange={(e) => setBaris(baris.map((x, j) => j === i ? { ...x, penyesuaian_usc: e.target.value } : x))} />
            <input className={`${kelasInput} col-span-2`} placeholder="keterangan"
                   value={b.keterangan}
                   onChange={(e) => setBaris(baris.map((x, j) => j === i ? { ...x, keterangan: e.target.value } : x))} />
            <button className={kelasTombolKecil}
                    onClick={() => setBaris(baris.filter((_, j) => j !== i))}>hapus</button>
          </div>
        ))}
        <div className="flex gap-2">
          <button className={kelasTombolKecil} onClick={() => setBaris([...baris, barisKosong()])}>
            + tambah baris
          </button>
          <button className={kelasTombol} disabled={simpan.isPending}
                  onClick={() => { setInfo(null); simpan.mutate(); }}>
            Simpan versi baru
          </button>
        </div>
        {info && <Pesan jenis={info.jenis} teks={info.teks} />}
        <p className="mt-2 text-xs text-slate-500">
          Versi lama tidak dihapus: tanggal sebelum "berlaku sejak" tetap memakai versi lama,
          jadi hasil historis tidak berubah. Semua perubahan tercatat di audit log di bawah.
        </p>
      </>
    } />
  );
}

/* ---------- parameter pabrik ---------- */
function KartuParameter() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["parameter"], queryFn: () => ambilJson("/api/parameter") });
  const [form, setForm] = useState({ berlaku_dari: hariIni(), kapasitas: "", safety_ton: "", safety_hari: "", catatan: "" });
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  const simpan = useMutation({
    mutationFn: () => kirimJson("/api/parameter", {
      berlaku_dari: form.berlaku_dari,
      kapasitas_ton_per_hari: Number(form.kapasitas.replace(",", ".")),
      safety_stock_ton: form.safety_ton ? Number(form.safety_ton.replace(",", ".")) : null,
      safety_stock_hari: form.safety_hari ? Number(form.safety_hari.replace(",", ".")) : null,
      catatan: form.catatan || null, pengisi: pengisi(),
    }),
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      qc.invalidateQueries({ queryKey: ["parameter"] });
      qc.invalidateQueries({ queryKey: ["stok"] });
      qc.invalidateQueries({ queryKey: ["audit-aturan"] });
    },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });

  return (
    <Kartu idMetrik="stok" judul="Parameter pabrik (kapasitas & safety stock)"
           keterangan="Berversi tanggal berlaku — menambah versi baru tidak mengubah Days historis."
           anak={
      <>
        <table className="w-full text-xs mb-3">
          <thead>
            <tr className="text-left text-slate-400 border-b">
              <th className="py-1">Berlaku sejak</th><th className="text-right">Kapasitas ton/hari</th>
              <th className="text-right">Safety ton</th><th className="text-right">Safety hari</th>
              <th className="pl-3">Catatan</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.map((p: any) => (
              <tr key={p.berlaku_dari} className="border-b border-white/5">
                <td className="py-1">{fmtTanggal(p.berlaku_dari)}</td>
                <td className="text-right font-mono">{fmtAngka(p.kapasitas_ton_per_hari, 2)}</td>
                <td className="text-right font-mono">{p.safety_stock_ton !== null ? fmtAngka(p.safety_stock_ton, 1) : "–"}</td>
                <td className="text-right font-mono">{p.safety_stock_hari !== null ? fmtAngka(p.safety_stock_hari, 0) : "–"}</td>
                <td className="pl-3 text-slate-400">{p.catatan ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 items-end">
          <div>
            <label className={kelasLabel}>Berlaku sejak</label>
            <input type="date" className={kelasInput} value={form.berlaku_dari}
                   onChange={(e) => setForm({ ...form, berlaku_dari: e.target.value })} />
          </div>
          <input className={kelasInput} placeholder="kapasitas ton/hari" value={form.kapasitas}
                 onChange={(e) => setForm({ ...form, kapasitas: e.target.value })} />
          <input className={kelasInput} placeholder="safety ton (opsional)" value={form.safety_ton}
                 onChange={(e) => setForm({ ...form, safety_ton: e.target.value })} />
          <input className={kelasInput} placeholder="safety hari (opsional)" value={form.safety_hari}
                 onChange={(e) => setForm({ ...form, safety_hari: e.target.value })} />
          <button className={kelasTombol} disabled={simpan.isPending}
                  onClick={() => { setInfo(null); simpan.mutate(); }}>
            Simpan
          </button>
        </div>
        {info && <Pesan jenis={info.jenis} teks={info.teks} />}
      </>
    } />
  );
}

/* ---------- audit ---------- */
function KartuAudit() {
  const q = useQuery({
    queryKey: ["audit-aturan"],
    queryFn: () => ambilJson("/api/audit?limit=30"),
  });
  return (
    <Kartu idMetrik="alarm" judul="Audit log"
           keterangan="Siapa mengubah aturan/parameter/perencanaan/alarm, kapan, dan apa isinya."
           anak={
      <div className="max-h-72 overflow-y-auto">
        {q.data?.length === 0 && <p className="text-sm text-slate-500">Belum ada perubahan.</p>}
        {q.data?.map((a: any, i: number) => (
          <div key={i} className="mb-2 rounded-md border border-violet-500/20 p-2 text-xs">
            <b>{a.objek}</b> — {a.aksi} oleh <b>{a.siapa}</b> · {a.waktu.replace("T", " ")} UTC
            <pre className="mt-1 whitespace-pre-wrap text-slate-400">
              {JSON.stringify(a.detail, null, 1)}
            </pre>
          </div>
        ))}
      </div>
    } />
  );
}

export default function AturanHarga() {
  return (
    <div className="grid gap-6">
      <KartuRekomendasi />
      <KartuAturan />
      <KartuParameter />
      <KartuAudit />
    </div>
  );
}
