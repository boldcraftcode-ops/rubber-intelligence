import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, Pesan, ambilJson, fmtTanggal, kelasInput, kelasTombol,
  kelasTombolKecil, kirimJson,
} from "../bersama";
import { useBahasa } from "../i18n";

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

/* Kelompok alarm di layar. Urutannya = urutan mendesak menurut backend
   (core/tindakan_alarm.URUTAN_KATEGORI). */
const KATEGORI: [string, string][] = [
  ["stok", "Stok & operasional"],
  ["data", "Data belum masuk"],
  ["selisih", "Selisih angka"],
  ["harga", "Harga beli"],
  ["margin", "Margin vs target"],
];

type Tindakan = {
  kategori: string;
  halaman: string;
  halaman_label: string;
  judul: string;
  langkah: string[];
};

type AlarmItem = {
  kode: string;
  pesan: string;
  tanggal_data: string | null;
  tindakan?: Tindakan;
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

/* ---------- satu kartu alarm + jalan keluarnya ---------- */
function KartuAlarm({ a, ke }: { a: AlarmItem; ke?: (id: string) => void }) {
  const { t } = useBahasa();
  const tindakan = a.tindakan;
  return (
    <div className="rounded-sm border border-[#FECACA] bg-[#FEF2F2] px-3 py-2.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#B91C1C]">
            {t(NAMA_ALARM[a.kode] ?? a.kode)}
            {a.tanggal_data && (
              <span className="ml-2 font-normal text-[#DC2626]">
                ({t("data per")} {fmtTanggal(a.tanggal_data)})
              </span>
            )}
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-[#DC2626]">{a.pesan}</p>
        </div>
        {tindakan && ke && (
          <button
            className="shrink-0 rounded-sm bg-[#1D2434] px-3 py-1.5 text-xs font-semibold
                       text-white transition-colors hover:bg-[#2A3345]"
            onClick={() => ke(tindakan.halaman)}
            title={`${t("Buka")} ${tindakan.halaman_label}`}
          >
            {t("Buka")} {tindakan.halaman_label} →
          </button>
        )}
      </div>
      {tindakan && (
        <div className="mt-2 rounded-sm border border-[#E4E5E8] bg-white px-3 py-2">
          <p className="text-xs font-semibold text-[#1D2434]">
            <span aria-hidden className="mr-1 text-[#FF1313]">▶</span>
            {tindakan.judul}
          </p>
          <ol className="mt-1 list-decimal space-y-0.5 pl-4 text-xs leading-relaxed text-[#64676C]">
            {tindakan.langkah.map((l, i) => <li key={i}>{l}</li>)}
          </ol>
        </div>
      )}
    </div>
  );
}

export default function AlarmPage({ ke }: { ke?: (id: string) => void }) {
  const { t } = useBahasa();
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
      <Kartu idMetrik="alarm" judul={`${t("Alarm aktif")} (${q.data?.alarm.length ?? 0})`}
             keterangan={t("Dievaluasi ulang otomatis setelah tiap unggahan/perubahan data.")}
             anak={
        <>
          <button className={`${kelasTombol} mb-3`} disabled={evaluasi.isPending}
                  onClick={() => evaluasi.mutate()}>
            {evaluasi.isPending ? t("Mengevaluasi…") : t("Evaluasi ulang sekarang")}
          </button>
          {q.data?.alarm.length === 0 ? (
            <p className="rounded-sm bg-[#F0FDF4] border border-[#BBF7D0] px-3 py-3 text-sm text-[#15803D]">
              {t("Tidak ada alarm. ✓")}
            </p>
          ) : (
            <>
              <p className="mb-3 rounded-sm border border-[#E4E5E8] border-l-2 border-l-[#FF1313]
                            bg-[#F8F8F8] px-3 py-2 text-xs leading-relaxed text-[#64676C]">
                {t("Setiap alarm di bawah sudah dilengkapi tombol ke halaman yang harus dibuka dan langkah perbaikannya. Alarm padam sendiri setelah datanya benar dan evaluasi ulang dijalankan.")}
              </p>
              <div className="grid gap-4">
                {KATEGORI.map(([id, judul]) => {
                  const isi = (q.data?.alarm as AlarmItem[])
                    .filter((a) => (a.tindakan?.kategori ?? "data") === id);
                  if (!isi.length) return null;
                  return (
                    <section key={id}>
                      <h3 className="mb-1.5 flex items-center gap-2 text-xs font-semibold
                                     uppercase tracking-[0.1em] text-[#1D2434]">
                        {t(judul)}
                        <span className="rounded-sm bg-[#F8F8F8] border border-[#E4E5E8]
                                         px-1.5 py-0.5 text-[10px] font-semibold text-[#64676C]">
                          {isi.length}
                        </span>
                      </h3>
                      <div className="grid gap-2">
                        {isi.map((a, i) => (
                          <KartuAlarm key={`${a.kode}-${i}`} a={a} ke={ke} />
                        ))}
                      </div>
                    </section>
                  );
                })}
              </div>
            </>
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
