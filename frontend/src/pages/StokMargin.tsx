import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { Kartu, NAMA_BULAN, ambilJson, fmtAngka, kelasTombolKecil } from "../bersama";
import { useBahasa } from "../i18n";

/* ---------- warna per tahun ----------
   Yang terbaru selalu merah (paling relevan), tahun-tahun sebelumnya makin
   pudar. Tidak memakai warna baru di luar palet: merah, navy, abu. */
const WARNA_TERBARU = ["#FF1313", "#1D2434", "#64676C", "#9AA0A6", "#C9CCD2"];

const warnaTahun = (daftar: number[], tahun: number) => {
  const dariAkhir = daftar.length - 1 - daftar.indexOf(tahun);
  return WARNA_TERBARU[Math.min(Math.max(dariAkhir, 0), WARNA_TERBARU.length - 1)];
};

/* ---------- bahasa manusia untuk angka korelasi ----------
   Korelasi tidak boleh disimpulkan dari warna/garis saja: selalu ada kata. */
function bacaKorelasi(r: number | null): { kata: string; arah: string } {
  if (r === null) return { kata: "belum bisa dihitung", arah: "" };
  const a = Math.abs(r);
  const kata = a >= 0.7 ? "kuat" : a >= 0.4 ? "sedang" : a >= 0.2 ? "lemah" : "sangat lemah";
  return { kata, arah: r > 0 ? "searah" : r < 0 ? "berlawanan arah" : "tanpa arah" };
}

/* ---------- regresi sederhana untuk garis tren ---------- */
function garisTren(titik: { rasio_stok: number; op_margin: number }[]) {
  const n = titik.length;
  if (n < 3) return null;
  const rx = titik.reduce((s, t) => s + t.rasio_stok, 0) / n;
  const ry = titik.reduce((s, t) => s + t.op_margin, 0) / n;
  const atas = titik.reduce((s, t) => s + (t.rasio_stok - rx) * (t.op_margin - ry), 0);
  const bawah = titik.reduce((s, t) => s + (t.rasio_stok - rx) ** 2, 0);
  if (bawah === 0) return null;
  const m = atas / bawah;
  const xs = titik.map((t) => t.rasio_stok);
  const x1 = Math.min(...xs);
  const x2 = Math.max(...xs);
  return [{ x: x1, y: ry + m * (x1 - rx) },
          { x: x2, y: ry + m * (x2 - rx) }] as [{ x: number; y: number },
                                                { x: number; y: number }];
}

type Titik = {
  tahun: number; bulan: number; rasio_stok: number; op_margin: number; ton: number;
};

type Kelompok = {
  label: string; jumlah_bulan: number; margin_rata: number | null; ton_rata: number | null;
};

type RingkasTahun = {
  tahun: number; jumlah_bulan: number; korelasi: number | null;
  margin_rata: number | null; rasio_rata: number | null;
};

type Hasil = {
  tahun: number | null;
  tahun_tersedia: number[];
  titik: Titik[];
  jumlah_bulan: number;
  korelasi: number | null;
  rasio_rata: number | null;
  margin_rata: number | null;
  margin_stok_rendah: number | null;
  jumlah_bulan_stok_rendah: number;
  margin_stok_tinggi: number | null;
  jumlah_bulan_stok_tinggi: number;
  selisih_tinggi_rendah: number | null;
  kelompok: Kelompok[];
  per_tahun: RingkasTahun[];
  peringatan: string[];
  catatan: string;
};

export default function StokMargin() {
  const { t } = useBahasa();
  const [tahun, setTahun] = useState<number | null>(null);
  const q = useQuery({
    queryKey: ["stok-margin", tahun],
    queryFn: () => ambilJson(`/api/analisis/stok-margin${tahun ? `?tahun=${tahun}` : ""}`),
  });
  const d = q.data as Hasil | undefined;

  const tahunAda = d?.tahun_tersedia ?? [];
  const titik = d?.titik ?? [];
  const tren = garisTren(titik);
  const korelasi = bacaKorelasi(d?.korelasi ?? null);

  /* Empat kemungkinan arti: dihitung dari jumlah bulan, bukan dari warna. */
  const batasAman = 0.8;
  const rataMargin = d?.margin_rata ?? null;
  const kotak = [
    {
      kunci: "tipis_atas",
      judul: t("Stok tipis, margin di atas rata-rata"),
      arti: t("Stok ketat tetapi margin tetap bagus — kebijakan menahan stok tidak merugikan pada bulan-bulan ini."),
      jumlah: titik.filter((x) => x.rasio_stok < batasAman
        && rataMargin !== null && x.op_margin >= rataMargin).length,
    },
    {
      kunci: "tipis_bawah",
      judul: t("Stok tipis, margin di bawah rata-rata"),
      arti: t("Risiko ganda: bahan bisa habis dan margin ikut tertekan."),
      jumlah: titik.filter((x) => x.rasio_stok < batasAman
        && rataMargin !== null && x.op_margin < rataMargin).length,
    },
    {
      kunci: "tebal_atas",
      judul: t("Stok tebal, margin di atas rata-rata"),
      arti: t("Posisi paling aman: stok cukup dan margin bagus."),
      jumlah: titik.filter((x) => x.rasio_stok >= batasAman
        && rataMargin !== null && x.op_margin >= rataMargin).length,
    },
    {
      kunci: "tebal_bawah",
      judul: t("Stok tebal, margin di bawah rata-rata"),
      arti: t("Uang tertahan di stok sementara margin tipis — periksa harga beli dan biaya simpan."),
      jumlah: titik.filter((x) => x.rasio_stok >= batasAman
        && rataMargin !== null && x.op_margin < rataMargin).length,
    },
  ];

  return (
    <div className="grid gap-6">
      <Kartu idMetrik="stok_margin"
             judul={t("Hubungan rasio stok dengan OP Margin per bulan")}
             keterangan={t("INFORMASI, bukan aturan. Setiap titik = satu bulan.")}
             urlEkspor={`/api/analisis/stok-margin${tahun ? `?tahun=${tahun}` : ""}`}
             anak={
        <>
          {/* ===== cara membaca ===== */}
          <section className="mb-5 rounded-sm border border-[#E4E5E8] border-l-2
                              border-l-[#FF1313] bg-[#F8F8F8] px-4 py-3">
            <h3 className="text-sm font-semibold text-[#1D2434]">
              {t("Cara membaca grafik ini")}
            </h3>
            <ol className="mt-1.5 space-y-1 text-xs leading-relaxed text-[#64676C]">
              <li>
                <b className="text-[#1D2434]">1.</b>{" "}
                {t("Mendatar = rasio stok ÷ safety. 1,0 artinya stok tepat di batas aman; 0,5 artinya tinggal separuh batas aman.")}
              </li>
              <li>
                <b className="text-[#1D2434]">2.</b>{" "}
                {t("Menegak = OP Margin bulan itu (US¢/kg). Titik makin ke atas, margin makin bagus.")}
              </li>
              <li>
                <b className="text-[#1D2434]">3.</b>{" "}
                {t("Lihat bentuk awannya, bukan satu titik. Miring naik = bulan berstok tebal cenderung bermargin lebih baik; miring turun = sebaliknya; menyebar tanpa arah = tidak ada hubungan.")}
              </li>
            </ol>
            <p className="mt-1.5 text-xs text-[#64676C]">
              {t("Garis putus-putus tegak = batas 50% dan 80% safety. Garis putus-putus mendatar = margin rata-rata periode ini. Garis tren hanya menunjukkan arah umum, bukan janji.")}
            </p>
          </section>

          {/* ===== pilih tahun ===== */}
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.1em] text-[#64676C]">
              {t("Tahun")}
            </span>
            {[null, ...tahunAda].map((th) => {
              const aktif = tahun === th;
              return (
                <button key={String(th)}
                        className={aktif
                          ? "rounded-sm bg-[#1D2434] px-2.5 py-1 text-xs font-semibold text-white"
                          : `${kelasTombolKecil}`}
                        aria-pressed={aktif}
                        onClick={() => setTahun(th)}>
                  {th ?? t("Semua tahun")}
                </button>
              );
            })}
            <span className="text-xs text-[#64676C]">
              {t("Pilih satu tahun untuk melihat apakah hubungannya sama seperti gabungan semua tahun.")}
            </span>
          </div>

          {/* ===== angka kunci ===== */}
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              [t("Bulan berdata"), fmtAngka(d?.jumlah_bulan, 0)],
              [t("Korelasi (Pearson)"), fmtAngka(d?.korelasi, 2)],
              [`${t("Margin saat stok tipis")} (<50% ${t("safety")})`,
                fmtAngka(d?.margin_stok_rendah, 2)],
              [`${t("Margin saat stok tebal")} (≥80% ${t("safety")})`,
                fmtAngka(d?.margin_stok_tinggi, 2)],
            ].map(([label, nilai]) => (
              <div key={label as string}
                   className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
                <p className="text-xs text-[#64676C]">{label}</p>
                <p className="font-semibold text-[#1D2434]">{nilai}</p>
              </div>
            ))}
          </div>

          {d && (
            <p className="mb-4 rounded-sm border border-[#E4E5E8] bg-white px-3 py-2 text-xs leading-relaxed text-[#64676C]">
              {d.korelasi === null
                ? t("Bulan berdata belum cukup untuk menghitung korelasi.")
                : `${t("Kesimpulan singkat")}: ${t("korelasi")} ${fmtAngka(d.korelasi, 2)} (${t(korelasi.kata)}, ${t(korelasi.arah)}). `}
              {d.selisih_tinggi_rendah !== null && (
                <>
                  {`${t("Bulan dengan stok tebal menghasilkan margin")} ${fmtAngka(d.selisih_tinggi_rendah, 2)} US¢/kg ${t("lebih tinggi daripada bulan berstok tipis")} `}
                  ({fmtAngka(d.margin_stok_tinggi, 2)} {t("vs")} {fmtAngka(d.margin_stok_rendah, 2)}).{" "}
                </>
              )}
              {t("Ini asosiasi, bukan sebab-akibat: margin bisa naik/turun karena harga pasar, bukan karena stoknya.")}
            </p>
          )}

          {/* ===== grafik ===== */}
          <div className="h-80" role="img"
               aria-label={t("Grafik sebar bulan: rasio stok dibanding OP Margin")}>
            <ResponsiveContainer>
              <ScatterChart margin={{ top: 5, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid stroke="#EDEFF2" strokeDasharray="3 3" />
                <XAxis dataKey="rasio_stok" name={t("Rasio stok/safety")} fontSize={11}
                       type="number" domain={[0, "dataMax + 0.2"]}
                       label={{ value: t("Rasio stok ÷ safety (1,0 = tepat di batas aman)"),
                                position: "insideBottom", offset: -10, fontSize: 12 }}
                       tickFormatter={(v) => fmtAngka(v as number, 1)} />
                <YAxis dataKey="op_margin" name="OP Margin" fontSize={11} type="number"
                       label={{ value: t("OP Margin (US¢/kg)"), angle: -90,
                                position: "insideLeft", fontSize: 12 }} />
                <ReferenceLine x={0.5} stroke="#9AA0A6" strokeDasharray="4 4"
                               label={{ value: "50%", fontSize: 10, fill: "#64676C",
                                        position: "insideTopLeft" }} />
                <ReferenceLine x={batasAman} stroke="#64676C" strokeDasharray="4 4"
                               label={{ value: "80%", fontSize: 10, fill: "#64676C",
                                        position: "insideTopLeft" }} />
                {rataMargin !== null && (
                  <ReferenceLine y={rataMargin} stroke="#64676C" strokeDasharray="4 4"
                                 label={{ value: t("margin rata-rata"), fontSize: 10,
                                          fill: "#64676C", position: "insideBottomRight" }} />
                )}
                {tren && (
                  <ReferenceLine segment={tren} stroke="#1D2434" strokeWidth={2}
                                 strokeDasharray="7 4" ifOverflow="extendDomain" />
                )}
                <Tooltip
                  content={({ payload }) => {
                    const p = payload?.[0]?.payload as Titik | undefined;
                    if (!p) return null;
                    return (
                      <div className="rounded-sm border border-[#E4E5E8] bg-white p-2 text-xs shadow">
                        <b>{NAMA_BULAN[p.bulan]} {p.tahun}</b><br />
                        {t("rasio stok")} {fmtAngka(p.rasio_stok, 2)} ·{" "}
                        {t("OP Margin")} {fmtAngka(p.op_margin, 2)} US¢/kg<br />
                        {fmtAngka(p.ton, 0)} {t("ton")}
                      </div>
                    );
                  }} />
                {(tahun ? [tahun] : tahunAda).map((th) => (
                  <Scatter key={th} name={String(th)}
                           data={titik.filter((x) => x.tahun === th)}
                           fill={warnaTahun(tahunAda, th)} />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {/* ===== legenda per tahun ===== */}
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
            {(tahun ? [tahun] : tahunAda).map((th) => {
              const r = d?.per_tahun.find((p) => p.tahun === th);
              return (
                <span key={th} className="flex items-center gap-1.5 text-xs text-[#64676C]">
                  <span aria-hidden className="h-2.5 w-2.5 rounded-sm"
                        style={{ background: warnaTahun(tahunAda, th) }} />
                  <b className="text-[#1D2434]">{th}</b>
                  <span>
                    {t("korelasi")} {fmtAngka(r?.korelasi, 2)}
                    {r?.korelasi !== null && r?.korelasi !== undefined
                      ? ` (${t(bacaKorelasi(r.korelasi).kata)})` : ""}
                    {" · "}{fmtAngka(r?.jumlah_bulan, 0)} {t("bulan")}
                  </span>
                </span>
              );
            })}
          </div>

          {/* ===== empat kemungkinan arti ===== */}
          <h3 className="mt-6 text-sm font-semibold text-[#1D2434]">
            {t("Empat kemungkinan arti sebuah titik")}
          </h3>
          <p className="mb-2 text-xs text-[#64676C]">
            {t("Dibatasi 80% safety (tegak) dan margin rata-rata periode ini (datar). Angka = jumlah bulan.")}
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {kotak.map((k) => (
              <div key={k.kunci}
                   className="rounded-sm border border-[#E4E5E8] bg-white px-3 py-2">
                <p className="flex items-baseline justify-between gap-2 text-xs font-semibold text-[#1D2434]">
                  <span>{k.judul}</span>
                  <span className="shrink-0 rounded-sm bg-[#F8F8F8] px-1.5 py-0.5">
                    {k.jumlah} {t("bulan")}
                  </span>
                </p>
                <p className="mt-0.5 text-xs text-[#64676C]">{k.arti}</p>
              </div>
            ))}
          </div>

          {/* ===== tabel kelompok ===== */}
          <h3 className="mt-6 text-sm font-semibold text-[#1D2434]">
            {t("Margin rata-rata menurut kelompok stok")}
          </h3>
          <p className="mb-2 text-xs text-[#64676C]">
            {t("Membandingkan tiga kelompok ini lebih aman daripada menebak dari sebaran titik.")}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#E4E5E8] text-left text-[#64676C]">
                  <th className="py-1.5 font-semibold">{t("Kelompok stok")}</th>
                  <th className="py-1.5 text-right font-semibold">{t("Jumlah bulan")}</th>
                  <th className="py-1.5 text-right font-semibold">
                    {t("Margin rata-rata (US¢/kg)")}
                  </th>
                  <th className="py-1.5 text-right font-semibold">
                    {t("Rata-rata ton/bulan")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {(d?.kelompok ?? []).map((k) => (
                  <tr key={k.label} className="border-b border-[#EDEFF2]">
                    <td className="py-1.5 text-[#1D2434]">{t(k.label)}</td>
                    <td className="py-1.5 text-right">{fmtAngka(k.jumlah_bulan, 0)}</td>
                    <td className="py-1.5 text-right font-semibold text-[#1D2434]">
                      {fmtAngka(k.margin_rata, 2)}
                    </td>
                    <td className="py-1.5 text-right text-[#64676C]">
                      {fmtAngka(k.ton_rata, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ===== tabel per tahun ===== */}
          <h3 className="mt-6 text-sm font-semibold text-[#1D2434]">
            {t("Korelasi per tahun — uji apakah hubungan ini stabil")}
          </h3>
          <p className="mb-2 text-xs text-[#64676C]">
            {t("Kalau angkanya berubah jauh antar tahun, hubungan itu bukan aturan — hanya kebetulan pada satu kondisi pasar.")}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#E4E5E8] text-left text-[#64676C]">
                  <th className="py-1.5 font-semibold">{t("Tahun")}</th>
                  <th className="py-1.5 text-right font-semibold">{t("Jumlah bulan")}</th>
                  <th className="py-1.5 text-right font-semibold">{t("Korelasi")}</th>
                  <th className="py-1.5 font-semibold">{t("Sifat hubungan")}</th>
                  <th className="py-1.5 text-right font-semibold">
                    {t("Margin rata-rata (US¢/kg)")}
                  </th>
                  <th className="py-1.5 text-right font-semibold">
                    {t("Rasio stok rata-rata")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {(d?.per_tahun ?? []).map((p) => {
                  const k = bacaKorelasi(p.korelasi);
                  return (
                    <tr key={p.tahun}
                        className={`border-b border-[#EDEFF2] ${tahun === p.tahun ? "bg-[#F8F8F8]" : ""}`}>
                      <td className="py-1.5">
                        <span className="mr-1.5 inline-block h-2 w-2 rounded-sm align-middle"
                              style={{ background: warnaTahun(tahunAda, p.tahun) }} />
                        {p.tahun}
                      </td>
                      <td className="py-1.5 text-right">{fmtAngka(p.jumlah_bulan, 0)}</td>
                      <td className="py-1.5 text-right font-semibold text-[#1D2434]">
                        {fmtAngka(p.korelasi, 2)}
                      </td>
                      <td className="py-1.5 text-[#64676C]">
                        {p.korelasi === null ? "–" : `${t(k.kata)}, ${t(k.arah)}`}
                      </td>
                      <td className="py-1.5 text-right">{fmtAngka(p.margin_rata, 2)}</td>
                      <td className="py-1.5 text-right">{fmtAngka(p.rasio_rata, 2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* ===== peringatan & catatan ===== */}
          {(d?.peringatan ?? []).map((w) => (
            <p key={w} className="mt-4 rounded-sm border border-[#FDE68A] bg-[#FFFBEB]
                                  px-3 py-2 text-xs leading-relaxed text-[#B45309]">
              <b>⚠ {t("Perhatian")}:</b> {w}
            </p>
          ))}
          {d && (
            <p className="mt-3 rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-3 py-2
                          text-xs leading-relaxed text-[#64676C]">
              {d.catatan}
            </p>
          )}

          {q.isError && (
            <p className="mt-3 text-xs text-[#FF1313]">
              {t("Data gagal dimuat. Coba muat ulang halaman ini.")}
            </p>
          )}
        </>
      } />
    </div>
  );
}
