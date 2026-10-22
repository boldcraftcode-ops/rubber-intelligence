import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, Pesan, ambilJson, kirimJson, kelasInput, kelasLabel,
  kelasTombol, kelasTombolKecil, fmtTanggal,
} from "../bersama";

type Baris = {
  username: string; nama: string; peran: string; aktif: boolean;
  dibuat_pada: string; login_terakhir: string | null;
};

export default function Pengguna({ saya }: { saya: string }) {
  const qc = useQueryClient();
  const q = useQuery<Baris[]>({
    queryKey: ["pengguna"],
    queryFn: () => ambilJson("/api/auth/pengguna"),
  });
  const [pesan, setPesan] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  // form tambah
  const [username, setUsername] = useState("");
  const [nama, setNama] = useState("");
  const [sandi, setSandi] = useState("");
  const [peran, setPeran] = useState("pengguna");

  const segar = (teks: string) => {
    setPesan({ jenis: "sukses", teks });
    qc.invalidateQueries({ queryKey: ["pengguna"] });
  };
  const gagal = (e: Error) => setPesan({ jenis: "error", teks: e.message });

  const tambah = useMutation({
    mutationFn: () => kirimJson("/api/auth/pengguna", { username, nama, sandi, peran }),
    onSuccess: (j) => { segar(j.pesan); setUsername(""); setNama(""); setSandi(""); },
    onError: gagal,
  });

  const ubah = useMutation({
    mutationFn: ({ u, body }: { u: string; body: object }) =>
      kirimJson(`/api/auth/pengguna/${u}`, body),
    onSuccess: (j) => segar(j.pesan),
    onError: gagal,
  });

  const resetSandi = (u: string) => {
    const baru = prompt(`Sandi baru untuk '${u}' (minimal 8 karakter):`);
    if (baru) ubah.mutate({ u, body: { sandi_baru: baru } });
  };

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="pengguna" judul="Pengguna"
             keterangan="Kelola akun login aplikasi. Peran 'admin' boleh mengelola pengguna dan modul Database; 'pengguna' hanya memakai aplikasi."
             anak={
        <>
          {q.isLoading && <p className="text-sm text-slate-400">Memuat…</p>}
          {q.error && <Pesan jenis="error" teks={(q.error as Error).message} />}

          {q.data && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-400 border-b border-violet-500/20">
                    <th className="py-2 pr-3">Username</th>
                    <th className="py-2 pr-3">Nama</th>
                    <th className="py-2 pr-3">Peran</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Login terakhir</th>
                    <th className="py-2">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {q.data.map((p) => (
                    <tr key={p.username} className="border-b border-violet-500/10">
                      <td className="py-2 pr-3 font-semibold text-slate-100">
                        {p.username}{p.username === saya && (
                          <span className="ml-1.5 text-[10px] text-violet-300">(Anda)</span>)}
                      </td>
                      <td className="py-2 pr-3 text-slate-300">{p.nama}</td>
                      <td className="py-2 pr-3">
                        <span className={`rounded-full px-2 py-0.5 text-xs ${
                          p.peran === "admin"
                            ? "bg-violet-600/30 text-violet-200 border border-violet-400/40"
                            : "bg-white/10 text-slate-300"}`}>{p.peran}</span>
                      </td>
                      <td className="py-2 pr-3">
                        <span className={p.aktif ? "text-emerald-300" : "text-red-300"}>
                          {p.aktif ? "aktif" : "nonaktif"}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-xs text-slate-400">
                        {p.login_terakhir
                          ? `${fmtTanggal(p.login_terakhir.slice(0, 10))} ${p.login_terakhir.slice(11, 16)}`
                          : "belum pernah"}
                      </td>
                      <td className="py-2">
                        <div className="flex flex-wrap gap-1.5">
                          <button className={kelasTombolKecil}
                                  onClick={() => resetSandi(p.username)}>
                            Reset sandi
                          </button>
                          {p.username !== saya && (
                            <>
                              <button className={kelasTombolKecil}
                                      onClick={() => ubah.mutate({ u: p.username,
                                        body: { aktif: !p.aktif } })}>
                                {p.aktif ? "Nonaktifkan" : "Aktifkan"}
                              </button>
                              <button className={kelasTombolKecil}
                                      onClick={() => ubah.mutate({ u: p.username,
                                        body: { peran: p.peran === "admin" ? "pengguna" : "admin" } })}>
                                Jadikan {p.peran === "admin" ? "pengguna" : "admin"}
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {pesan && <Pesan jenis={pesan.jenis} teks={pesan.teks} />}

          {/* ---- tambah pengguna ---- */}
          <div className="mt-6 rounded-lg border border-violet-500/20 bg-white/5 p-4">
            <p className="font-semibold text-slate-200 text-sm mb-3">➕ Tambah pengguna</p>
            <div className="grid sm:grid-cols-4 gap-3">
              <div>
                <label className={kelasLabel}>Username</label>
                <input className={kelasInput} value={username}
                       placeholder="huruf kecil/angka"
                       onChange={(e) => setUsername(e.target.value.toLowerCase())} />
              </div>
              <div>
                <label className={kelasLabel}>Nama</label>
                <input className={kelasInput} value={nama} placeholder="Nama lengkap"
                       onChange={(e) => setNama(e.target.value)} />
              </div>
              <div>
                <label className={kelasLabel}>Sandi awal</label>
                <input className={kelasInput} type="password" value={sandi}
                       placeholder="min. 8 karakter"
                       onChange={(e) => setSandi(e.target.value)} />
              </div>
              <div>
                <label className={kelasLabel}>Peran</label>
                <select className={kelasInput} value={peran}
                        onChange={(e) => setPeran(e.target.value)}>
                  <option value="pengguna">pengguna</option>
                  <option value="admin">admin</option>
                </select>
              </div>
            </div>
            <button className={`${kelasTombol} mt-3`}
                    disabled={tambah.isPending || !username || !nama || sandi.length < 8}
                    onClick={() => { setPesan(null); tambah.mutate(); }}>
              {tambah.isPending ? "Menyimpan…" : "Simpan pengguna"}
            </button>
          </div>
        </>
      } />
    </div>
  );
}
