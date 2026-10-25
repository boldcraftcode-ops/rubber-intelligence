import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, Pesan, ambilJson, fmtTanggal, kelasInput, kelasTombol,
  kelasTombolKecil, kirimJson,
} from "../bersama";

const pengisi = () => localStorage.getItem("op-margin.pengisi") || "?";

const NAMA_ALARM: Record<string, string> = {
  STOK_DI_BAWAH_SAFETY: "Stok di bawah safety",
  MARGIN_DI_BAWAH_TARGET: "Margin di bawah target",
  SICOM_TERLAMBAT: "SICOM terlambat",
  KURS_TERLAMBAT: "Kurs terlambat",
  STOK_TERLAMBAT: "Stok terlambat",
  TIKET_TERLAMBAT: "Tiket terlambat",
  SELISIH_REKONSILIASI: "Selisih rekonsiliasi",
  HARGA_DI_ATAS_MAKS: "Harga beli di atas maksimum",
};

function BarisPengaturan({ p, sesudah }: { p: any; sesudah: () => void }) {
  const [aktif, setAktif] = useState(p.aktif);
  const [ambang, setAmbang] = useState(p.ambang !== null ? String(p.ambang) : "");
  const [galat, setGalat] = useState<string | null>(null);

  const simpan = useMutation({
    mutationFn: () => kirimJson("/api/alarm/pengaturan", {
      kode: p.kode, aktif,
      ambang: ambang.trim() === "" ? null : Number(ambang.replace(",", ".")),
      pengisi: pengisi(),
    }),
    onSuccess: () => { setGalat(null); sesudah(); },
    onError: (e: Error) => setGalat(e.message),
  });

  return (
    <>
      <tr className="border-b border-[#EDEFF2]">
        <td className="py-1.5 font-medium">{NAMA_ALARM[p.kode] ?? p.kode}</td>
        <td className="text-center">
          <input type="checkbox" className="accent-[#FF1313]" checked={aktif}
                 onChange={(e) => setAktif(e.target.checked)} />
        </td>
        <td>
          <input className={`${kelasInput} w-24 text-right`} value={ambang}
                 placeholder="-" onChange={(e) => setAmbang(e.target.value)} />
        </td>
        <td className="text-[#64676C]">{p.satuan ?? "-"}</td>
        <td className="text-xs text-[#64676C]">{p.keterangan}</td>
        <td>
          <button className={kelasTombolKecil} disabled={simpan.isPending}
                  onClick={() => simpan.mutate()}>simpan</button>
        </td>
      </tr>
      {galat && <tr><td colSpan={6}><Pesan jenis="error" teks={galat} /></td></tr>}
    </>
  );
}

export default function AlarmPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["alarm"], queryFn: () => ambilJson("/api/alarm") });

  const evaluasi = useMutation({
    mutationFn: () => kirimJson("/api/alarm/evaluasi", {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alarm"] }),
  });

  const segarkan = () => {
    qc.invalidateQueries({ queryKey: ["alarm"] });
    qc.invalidateQueries({ queryKey: ["audit-aturan"] });
  };

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="alarm" judul={`Alarm aktif (${q.data?.alarm.length ?? 0})`}
             keterangan="Dievaluasi ulang otomatis setelah tiap unggahan/perubahan data."
             anak={
        <>
          <button className={`${kelasTombol} mb-3`} disabled={evaluasi.isPending}
                  onClick={() => evaluasi.mutate()}>
            {evaluasi.isPending ? "Mengevaluasi…" : "Evaluasi ulang sekarang"}
          </button>
          {q.data?.alarm.length === 0 ? (
            <p className="rounded-sm bg-[#F0FDF4] border border-[#BBF7D0] px-3 py-3 text-sm text-[#15803D]">
              Tidak ada alarm. ✓
            </p>
          ) : (
            <div className="grid gap-2">
              {q.data?.alarm.map((a: any, i: number) => (
                <div key={i} className="rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2">
                  <p className="text-sm font-semibold text-[#B91C1C]">
                    {NAMA_ALARM[a.kode] ?? a.kode}
                    {a.tanggal_data && (
                      <span className="ml-2 font-normal text-[#DC2626]">
                        (data {fmtTanggal(a.tanggal_data)})
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-[#DC2626]">{a.pesan}</p>
                </div>
              ))}
            </div>
          )}
        </>
      } />

      <Kartu idMetrik="alarm" judul="Pengaturan alarm (admin)"
             keterangan="Ambang adalah data yang bisa diubah — tidak ada angka yang ditanam di kode. Perubahan tercatat di audit log."
             anak={
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[#64676C] border-b text-xs">
              <th className="py-1">Alarm</th><th>Aktif</th><th>Ambang</th>
              <th>Satuan</th><th>Keterangan</th><th></th>
            </tr>
          </thead>
          <tbody>
            {q.data?.pengaturan.map((p: any) => (
              <BarisPengaturan key={p.kode} p={p} sesudah={segarkan} />
            ))}
          </tbody>
        </table>
      } />
    </div>
  );
}
