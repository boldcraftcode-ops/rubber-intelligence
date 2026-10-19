import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Pesan, ambilJson, fmtAngka, fmtTanggal, hariIni,
  kelasInput, kelasLabel, kelasTombol, kirimJson,
} from "../bersama";

function KartuSicom({ pengisi }: { pengisi: string }) {
  const qc = useQueryClient();
  const [tanggal, setTanggal] = useState(hariIni());
  const [harga, setHarga] = useState("");
  const [kontrak, setKontrak] = useState("");
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  const riwayat = useQuery({
    queryKey: ["sicom"],
    queryFn: () => ambilJson("/api/sicom?limit=10"),
  });

  const simpan = useMutation({
    mutationFn: () =>
      kirimJson("/api/sicom", {
        tanggal,
        usc_per_kg: Number(harga.replace(",", ".")),
        kontrak: kontrak || null,
        pengisi: pengisi || "?",
      }),
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      setHarga("");
      qc.invalidateQueries({ queryKey: ["sicom"] });
    },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });

  return (
    <section className="rounded-xl bg-[#15143a]/90 p-5 shadow-lg shadow-black/30 border border-violet-500/20">
      <h2 className="text-lg font-semibold text-slate-100">SICOM harian (TSR20)</h2>
      <p className="text-sm text-slate-400 mb-4">
        Dicek tiap hari dari website SICOM. Hari libur otomatis memakai harga terakhir —
        tidak perlu diisi.
      </p>
      <form
        className="grid grid-cols-1 sm:grid-cols-3 gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setInfo(null);
          if (!harga) {
            setInfo({ jenis: "error", teks: "Isi dulu harga SICOM (US¢/kg)." });
            return;
          }
          simpan.mutate();
        }}
      >
        <div>
          <label className={kelasLabel}>Tanggal</label>
          <input type="date" className={kelasInput} value={tanggal}
                 onChange={(e) => setTanggal(e.target.value)} required />
        </div>
        <div>
          <label className={kelasLabel}>Harga (US¢/kg)</label>
          <input type="text" inputMode="decimal" placeholder="contoh: 259,3"
                 className={kelasInput} value={harga}
                 onChange={(e) => setHarga(e.target.value)} />
        </div>
        <div>
          <label className={kelasLabel}>Kontrak (boleh kosong)</label>
          <input type="text" placeholder="belum ditentukan" className={kelasInput}
                 value={kontrak} onChange={(e) => setKontrak(e.target.value)} />
        </div>
        <div className="sm:col-span-3">
          <button className={kelasTombol} disabled={simpan.isPending}>
            {simpan.isPending ? "Menyimpan…" : "Simpan SICOM"}
          </button>
        </div>
      </form>
      {info && <Pesan jenis={info.jenis} teks={info.teks} />}

      <h3 className="mt-5 mb-2 text-sm font-semibold text-slate-300">10 hari terakhir</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 border-b border-violet-500/20">
            <th className="py-1">Tanggal</th>
            <th className="py-1 text-right">US¢/kg</th>
            <th className="py-1 pl-4">Sumber</th>
          </tr>
        </thead>
        <tbody>
          {riwayat.data?.map((b: any) => (
            <tr key={b.tanggal} className="border-b border-white/5">
              <td className="py-1">{fmtTanggal(b.tanggal)}</td>
              <td className="py-1 text-right font-mono">{fmtAngka(b.usc_per_kg, 2)}</td>
              <td className="py-1 pl-4 text-slate-400">{b.sumber ?? "-"}</td>
            </tr>
          ))}
          {riwayat.data?.length === 0 && (
            <tr><td colSpan={3} className="py-2 text-slate-500">Belum ada data.</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

function KartuKurs({ pengisi }: { pengisi: string }) {
  const qc = useQueryClient();
  const [berlakuDari, setBerlakuDari] = useState(hariIni());
  const [nilai, setNilai] = useState("");
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  const riwayat = useQuery({
    queryKey: ["kurs"],
    queryFn: () => ambilJson("/api/kurs?limit=10"),
  });

  const simpan = useMutation({
    mutationFn: () =>
      kirimJson("/api/kurs", {
        berlaku_dari: berlakuDari,
        idr_per_usd: Number(nilai.replace(/\./g, "").replace(",", ".")),
        pengisi: pengisi || "?",
      }),
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      setNilai("");
      qc.invalidateQueries({ queryKey: ["kurs"] });
    },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });

  return (
    <section className="rounded-xl bg-[#15143a]/90 p-5 shadow-lg shadow-black/30 border border-violet-500/20">
      <h2 className="text-lg font-semibold text-slate-100">Kurs USD/IDR</h2>
      <p className="text-sm text-slate-400 mb-4">
        Ditetapkan perusahaan dari data bank. Isi hanya saat kurs berubah — berlaku
        sejak tanggal yang dipilih (boleh di tengah bulan).
      </p>
      <form
        className="grid grid-cols-1 sm:grid-cols-3 gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setInfo(null);
          if (!nilai) {
            setInfo({ jenis: "error", teks: "Isi dulu nilai kurs (IDR per USD)." });
            return;
          }
          simpan.mutate();
        }}
      >
        <div>
          <label className={kelasLabel}>Berlaku sejak</label>
          <input type="date" className={kelasInput} value={berlakuDari}
                 onChange={(e) => setBerlakuDari(e.target.value)} required />
        </div>
        <div>
          <label className={kelasLabel}>Kurs (IDR per USD)</label>
          <input type="text" inputMode="decimal" placeholder="contoh: 16.644"
                 className={kelasInput} value={nilai}
                 onChange={(e) => setNilai(e.target.value)} />
        </div>
        <div className="flex items-end">
          <button className={kelasTombol} disabled={simpan.isPending}>
            {simpan.isPending ? "Menyimpan…" : "Simpan kurs"}
          </button>
        </div>
      </form>
      {info && <Pesan jenis={info.jenis} teks={info.teks} />}

      <h3 className="mt-5 mb-2 text-sm font-semibold text-slate-300">
        10 perubahan terakhir
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-400 border-b border-violet-500/20">
            <th className="py-1">Berlaku sejak</th>
            <th className="py-1 text-right">IDR/USD</th>
            <th className="py-1 pl-4">Sumber</th>
          </tr>
        </thead>
        <tbody>
          {riwayat.data?.map((b: any) => (
            <tr key={b.berlaku_dari} className="border-b border-white/5">
              <td className="py-1">{fmtTanggal(b.berlaku_dari)}</td>
              <td className="py-1 text-right font-mono">{fmtAngka(b.idr_per_usd, 0)}</td>
              <td className="py-1 pl-4 text-slate-400">{b.sumber ?? "-"}</td>
            </tr>
          ))}
          {riwayat.data?.length === 0 && (
            <tr><td colSpan={3} className="py-2 text-slate-500">Belum ada data.</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

export default function InputHarian({ pengisi }: { pengisi: string }) {
  return (
    <div className="grid grid-cols-1 gap-6">
      <KartuSicom pengisi={pengisi} />
      <KartuKurs pengisi={pengisi} />
      <p className="text-xs text-slate-500">
        Setiap simpanan dicatat (siapa &amp; kapan) dan langsung memperbarui perhitungan
        OP Margin. Tanggal ditampilkan dd/mm/yyyy, angka memakai format Indonesia.
      </p>
    </div>
  );
}
