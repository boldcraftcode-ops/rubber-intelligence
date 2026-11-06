import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Kartu, ambilJson, fmtAngka, fmtTanggal, kelasInput, kelasTombolAnalisa,
  kelasTombolKecil, kirimMetode, pesanGalat,
} from "../bersama";
import { useBahasa } from "../i18n";

type Baris = any;
type Pesan = { jenis: "sukses" | "galat"; teks: string } | null;

function Selisih({ baris, satuan }: { baris: Baris; satuan: "kg" | "ton" }) {
  const { t } = useBahasa();
  const desimal = satuan === "kg" ? 1 : 3;
  const asli = baris[`selisih_${satuan}`];
  const efektif = baris[`selisih_efektif_${satuan}`];
  if (!baris.direvisi) {
    return <span className="font-mono font-semibold text-[#B45309]">
      {fmtAngka(asli, desimal)}
    </span>;
  }
  return (
    <span className="font-mono">
      <span className="text-[#9AA0A6] line-through">{fmtAngka(asli, desimal)}</span>
      <br />
      <span className="font-semibold text-[#15803D]">{fmtAngka(efektif, desimal)}</span>
      <span className="ml-1 text-[10px] text-[#64676C]">{t("setelah revisi")}</span>
    </span>
  );
}

function KeteranganKeputusan({ baris, satuan }: {
  baris: Baris; satuan: "kg" | "ton";
}) {
  const { t } = useBahasa();
  const desimal = satuan === "kg" ? 0 : 3;
  const nilai = baris[`nilai_dipakai_${satuan}`];
  if (!baris.direvisi) {
    return <span className="text-xs text-[#64676C]">{baris.status}</span>;
  }
  return (
    <div className="text-xs">
      <span className="font-semibold text-[#15803D]">{baris.status}</span>
      <p className="mt-0.5 text-[#64676C]">
        {t("Nilai dipakai")}: <b className="font-mono text-[#1D2434]">
          {fmtAngka(nilai, desimal)} {satuan}
        </b>
        {baris.koreksi?.oleh && <> · {baris.koreksi.oleh}</>}
        {baris.koreksi?.pada && <> · {baris.koreksi.pada}</>}
      </p>
      {baris.koreksi?.alasan && (
        <p className="mt-0.5 text-[#64676C]">
          {t("Alasan")}: {baris.koreksi.alasan}
        </p>
      )}
    </div>
  );
}

function FormKeputusan({ baris, jenis, satuan, bisa, sedang, simpan, batal }: {
  baris: Baris;
  jenis: "harian" | "diketahui";
  satuan: "kg" | "ton";
  bisa: boolean;
  sedang: boolean;
  simpan: (v: any) => void;
  batal: (v: any) => void;
}) {
  const { t } = useBahasa();
  const kunciNilai = `nilai_${satuan}`;
  const desimal = satuan === "kg" ? 0 : 3;
  const [pilih, setPilih] = useState<string>(baris.sumber_dipakai ?? "");
  const [alasan, setAlasan] = useState<string>(baris.koreksi?.alasan ?? "");

  useEffect(() => {
    setPilih(baris.sumber_dipakai ?? "");
    setAlasan(baris.koreksi?.alasan ?? "");
  }, [baris.kunci, baris.sumber_dipakai, baris.koreksi?.alasan]);

  if (!bisa) {
    return <span className="text-[11px] text-[#64676C]">
      {t("Hanya admin yang dapat menyimpan revisi.")}
    </span>;
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <select
        className={`${kelasInput} w-48 disabled:opacity-50`}
        value={pilih}
        onChange={(e) => setPilih(e.target.value)}
        disabled={sedang}
        aria-label={t("Data mana yang benar?")}
      >
        <option value="">{t("Pilih sumber yang benar")}</option>
        {(baris.pilihan_sumber ?? []).map((o: Baris) => (
          <option key={o.kode} value={o.kode}>
            {`${t(o.label)} · ${fmtAngka(o[kunciNilai], desimal)} ${satuan}`}
          </option>
        ))}
      </select>
      <input
        className={`${kelasInput} w-44 disabled:opacity-50`}
        value={alasan}
        onChange={(e) => setAlasan(e.target.value)}
        placeholder={t("Alasan revisi (opsional)")}
        disabled={sedang}
        maxLength={300}
        aria-label={t("Alasan revisi (opsional)")}
      />
      <button
        type="button"
        className={`${kelasTombolAnalisa} disabled:cursor-not-allowed disabled:opacity-50`}
        disabled={!pilih || sedang}
        onClick={() => simpan({
          jenis, kunci: baris.kunci, sumber_benar: pilih,
          alasan: alasan.trim() || null,
        })}
      >
        {sedang ? `⏳ ${t("Memuat…")}` : baris.direvisi
          ? t("Perbarui revisi") : t("Simpan revisi")}
      </button>
      {baris.direvisi && (
        <button
          type="button"
          className={`${kelasTombolKecil} disabled:opacity-50`}
          disabled={sedang}
          onClick={() => batal({ jenis, kunci: baris.kunci })}
        >
          {t("Batalkan revisi")}
        </button>
      )}
    </div>
  );
}

export default function Rekonsiliasi() {
  const { t } = useBahasa();
  const qc = useQueryClient();
  const [pesan, setPesan] = useState<Pesan>(null);
  const q = useQuery({
    queryKey: ["rekonsiliasi"],
    queryFn: () => ambilJson("/api/rekonsiliasi"),
  });

  const segarkan = () => {
    qc.invalidateQueries({ queryKey: ["rekonsiliasi"] });
    qc.invalidateQueries({ queryKey: ["alarm"] });
    qc.invalidateQueries({ queryKey: ["ringkasan-elemen"] });
    qc.invalidateQueries({ queryKey: ["audit"] });
  };
  const simpan = useMutation({
    mutationFn: (v: any) => kirimMetode("/api/rekonsiliasi/keputusan", "POST", v),
    onSuccess: (d: any) => {
      setPesan({ jenis: "sukses", teks: d.pesan });
      segarkan();
    },
    onError: (e: unknown) => setPesan({ jenis: "galat", teks: pesanGalat(e) }),
  });
  const batal = useMutation({
    mutationFn: (v: any) => kirimMetode(
      `/api/rekonsiliasi/keputusan?jenis=${encodeURIComponent(v.jenis)}` +
      `&kunci=${encodeURIComponent(v.kunci)}`, "DELETE"),
    onSuccess: (d: any) => {
      setPesan({ jenis: "sukses", teks: d.pesan });
      segarkan();
    },
    onError: (e: unknown) => setPesan({ jenis: "galat", teks: pesanGalat(e) }),
  });

  const bisa = q.data?.bisa_revisi === true;
  const sedang = simpan.isPending || batal.isPending;
  const harian: Baris[] = q.data?.harian ?? [];
  const diketahui: Baris[] = q.data?.diketahui ?? [];
  const takCocok = harian.filter((h) => !h.cocok);
  const sudahDirevisi = harian.filter((h) => h.direvisi);

  return (
    <div className="grid gap-6">
      {pesan && (
        <p className={`rounded-sm border px-3 py-2 text-sm ${
          pesan.jenis === "sukses"
            ? "border-[#BBF7D0] bg-[#F0FDF4] text-[#15803D]"
            : "border-[#FECACA] bg-[#FEF2F2] text-[#B91C1C]"
        }`}>
          {pesan.teks}
        </p>
      )}
      <p className="rounded-sm border border-[#E4E5E8] bg-white px-3 py-2 text-xs text-[#64676C]">
        {t("Data asli tidak diubah; keputusan tercatat dan dapat dibatalkan.")}
        {!bisa && <> {t("Hanya admin yang dapat menyimpan revisi.")}</>}
      </p>

      <Kartu idMetrik="rekonsiliasi" judul={t("Selisih yang sudah diketahui")}
             keterangan={t("Tiket vs Excel lama. Pilih sumber yang benar untuk menutup selisih.")}
             urlEkspor="/api/rekonsiliasi"
             anak={
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] text-sm">
              <thead>
                <tr className="text-left text-[#64676C] border-b">
                  <th className="py-1">{t("Periode")}</th>
                  <th className="text-right">{t("Tiket (ton)")}</th>
                  <th className="text-right">{t("Excel lama (ton)")}</th>
                  <th className="text-right">{t("Selisih (ton)")}</th>
                  <th className="pl-3">{t("Status")}</th>
                  <th className="pl-3">{t("Keputusan")}</th>
                </tr>
              </thead>
              <tbody>
                {diketahui.map((d: Baris) => (
                  <tr key={d.kunci} className="border-b border-[#EDEFF2] align-top">
                    <td className="py-1.5 font-medium">{d.periode}</td>
                    <td className="text-right font-mono">{fmtAngka(d.tiket_ton, 3)}</td>
                    <td className="text-right font-mono">{fmtAngka(d.excel_ton, 3)}</td>
                    <td className="text-right"><Selisih baris={d} satuan="ton" /></td>
                    <td className="pl-3"><KeteranganKeputusan baris={d} satuan="ton" /></td>
                    <td className="pl-3 py-1.5">
                      <FormKeputusan baris={d} jenis="diketahui" satuan="ton"
                                     bisa={bisa} sedang={sedang}
                                     simpan={(v) => simpan.mutate(v)}
                                     batal={(v) => batal.mutate(v)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(q.data?.catatan ?? []).map((c: string, i: number) => (
            <p key={i} className="mt-2 rounded-sm bg-[#F8F8F8] border border-[#E4E5E8] px-3 py-2 text-xs text-[#1D2434]">
              {c}
            </p>
          ))}
        </>
      } />

      <Kartu idMetrik="rekonsiliasi" judul={t("Pemeriksaan harian: tiket vs pembelian")}
             keterangan={t("Baris berselisih bisa direvisi dengan memilih sumber yang benar.")}
             anak={
        q.isLoading ? (
          <p className="text-sm text-[#64676C]">{t("Memuat…")}</p>
        ) : q.error ? (
          <p className="text-sm text-[#B91C1C]">{pesanGalat(q.error)}</p>
        ) : harian.length === 0 ? (
          <p className="text-sm text-[#64676C]">
            {t("Belum ada data tiket historis untuk dibandingkan — unggah ekspor \"Master Data\" terlebih dahulu.")}
          </p>
        ) : (
          <>
            <p className="mb-2 text-sm text-[#1D2434]">
              {harian.length} {t("tanggal diperiksa")} ·{" "}
              <b className={takCocok.length ? "text-[#B45309]" : "text-[#15803D]"}>
                {takCocok.length} {t("tidak cocok")}
              </b> {t("(toleransi 1 kg)")}
              {sudahDirevisi.length > 0 && <> · <b className="text-[#15803D]">
                {sudahDirevisi.length} {t("direvisi")}
              </b></>}
            </p>
            <div className="max-h-80 overflow-auto">
              <table className="w-full min-w-[1160px] text-xs">
                <thead className="sticky top-0 bg-white">
                  <tr className="text-left text-[#64676C] border-b">
                    <th className="py-1">{t("Tanggal")}</th>
                    <th className="text-right">{t("Dry tiket (kg)")}</th>
                    <th className="text-right">{t("Qty pembelian (kg)")}</th>
                    <th className="text-right">{t("Selisih (kg)")}</th>
                    <th className="pl-3">{t("Status")}</th>
                    <th className="pl-3">{t("Keputusan")}</th>
                  </tr>
                </thead>
                <tbody>
                  {harian.map((h: Baris) => (
                    <tr key={h.kunci}
                        className={`border-b border-[#EDEFF2] align-top ${h.cocok ? "" : "bg-[#FFFBEB]"}`}>
                      <td className="py-1">{fmtTanggal(h.tanggal)}</td>
                      <td className="text-right font-mono">{fmtAngka(h.dry_tiket_kg, 0)}</td>
                      <td className="text-right font-mono">{fmtAngka(h.qty_pembelian_kg, 0)}</td>
                      <td className="text-right"><Selisih baris={h} satuan="kg" /></td>
                      <td className="pl-3"><KeteranganKeputusan baris={h} satuan="kg" /></td>
                      <td className="pl-3 py-1">
                        {h.cocok_asli && !h.direvisi ? (
                          <span className="text-[11px] text-[#15803D]">{t("Cocok")}</span>
                        ) : (
                          <FormKeputusan baris={h} jenis="harian" satuan="kg"
                                         bisa={bisa} sedang={sedang}
                                         simpan={(v) => simpan.mutate(v)}
                                         batal={(v) => batal.mutate(v)} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )
      } />
    </div>
  );
}
