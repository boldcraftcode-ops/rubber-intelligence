import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Pesan, ambilJson, fmtAngka, fmtTanggal, hariIni,
  kelasInput, kelasLabel, kelasTombol, kelasTombolKecil, kirimJson,
} from "../bersama";
import { useBahasa } from "../i18n";

const pengisiSekarang = () => localStorage.getItem("op-margin.pengisi") || "?";

/** Angka gaya Indonesia: "1.571,5" -> 1571.5 */
const bacaAngka = (teks: string) =>
  Number(teks.replace(/\./g, "").replace(",", "."));

const ke = (id: string) =>
  (document.getElementById(id) as HTMLElement | null)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });

/* ============================================================
   Panel kesegaran: 5 sumber + tanggal yang belum terisi
   ============================================================ */
type Sumber = {
  sumber: string; tanggal_terakhir: string | null; umur_hari: number | null;
  terlambat: boolean; wajib_harian: boolean; catatan: string | null;
};

type Ringkas = {
  hari_ini: string;
  hari_dicek: number;
  sumber: Sumber[];
  stok_terakhir: { tanggal: string; stok_ton: number | null; safety_ton: number | null;
                   days: number | null; rasio_stok: number | null } | null;
  sicom_terakhir: { tanggal: string; usc_per_kg: number } | null;
  kurs_terakhir: { berlaku_dari: string; idr_per_usd: number } | null;
  tanggal_kosong: { stok: string[]; pembelian: string[] };
  riwayat_stok: { tanggal: string; item_code: string; stok_kg: number }[];
  riwayat_pembelian: {
    tanggal: string; item_code: string; kode_vendor: string; ticket_no: string;
    qty_kering_kg: number; amount_rp: number; harga_rp_per_kg: number | null;
  }[];
};

function PanelKesegaran({ data, isiStok, isiBeli }: {
  data?: Ringkas;
  isiStok: (tgl: string) => void;
  isiBeli: (tgl: string) => void;
}) {
  const { t } = useBahasa();
  return (
    <section className="rounded-sm bg-white p-5 shadow-sm border border-[#E4E5E8]">
      <h2 className="text-lg font-semibold text-[#1D2434]">
        {t("Kesegaran data hari ini")}
      </h2>
      <p className="mb-4 text-sm text-[#64676C]">
        {t("Umur tiap sumber data. Yang bertanda ⚠ melewati batas dan sebaiknya diisi sekarang — cukup satu baris per hari, tidak perlu menunggu file Excel.")}
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {(data?.sumber ?? []).map((s) => (
          <div key={s.sumber}
               className={`rounded-sm border p-3 ${s.terlambat
                 ? "border-[#FDE68A] bg-[#FFFBEB]"
                 : "border-[#E4E5E8] bg-[#F8F8F8]"}`}>
            <p className="text-xs text-[#64676C]">{s.sumber}</p>
            <p className="font-semibold text-[#1D2434]">
              {s.tanggal_terakhir ? fmtTanggal(s.tanggal_terakhir) : "–"}
            </p>
            <p className="text-xs text-[#64676C]">
              {s.umur_hari !== null
                ? `${s.umur_hari} ${t("hari lalu")}`
                : t("belum ada")}
              {s.terlambat && <span className="ml-1 font-semibold">⚠</span>}
            </p>
            <p className="mt-1 text-[10px] uppercase tracking-wide text-[#9AA0A6]">
              {s.wajib_harian ? t("wajib harian") : t("saat berubah")}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {([
          ["stok", t("Stok belum terisi"), data?.tanggal_kosong.stok ?? [], isiStok],
          ["beli", t("Pembelian belum terisi"), data?.tanggal_kosong.pembelian ?? [], isiBeli],
        ] as const).map(([id, judul, daftar, aksi]) => (
          <div key={id} className="rounded-sm border border-[#E4E5E8] px-3 py-2">
            <p className="text-xs font-semibold text-[#1D2434]">
              {judul}{" "}
              <span className="font-normal text-[#64676C]">
                ({daftar.length} {t("tanggal")})
              </span>
            </p>
            {daftar.length === 0 ? (
              <p className="mt-1 text-xs text-[#15803D]">
                {t("Semua terisi. ✓")}
              </p>
            ) : (
              <div className="mt-1 flex flex-wrap gap-1">
                {daftar.slice(-7).map((tgl) => (
                  <button key={tgl} className={kelasTombolKecil}
                          onClick={() => aksi(tgl)}
                          title={t("Isi tanggal ini")}>
                    {fmtTanggal(tgl)}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <p className="mt-3 text-xs leading-relaxed text-[#64676C]">
        {t("Tanggal yang belum terisi belum tentu salah — hari libur memang boleh kosong. Yang penting angka terakhir tidak tertinggal jauh, karena alarm stok, Days of Cover, dan harga beli dihitung dari data terakhir.")}
      </p>
    </section>
  );
}

/* ============================================================
   Stok harian
   ============================================================ */
function KartuStok({ pengisi, tanggal, setTanggal, ringkas }: {
  pengisi: string; tanggal: string; setTanggal: (t: string) => void;
  ringkas?: Ringkas;
}) {
  const { t } = useBahasa();
  const qc = useQueryClient();
  const [jenis, setJenis] = useState("");
  const [nilai, setNilai] = useState("");
  const [satuan, setSatuan] = useState<"ton" | "kg">("ton");
  const [catatan, setCatatan] = useState("");
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);
  const [hasil, setHasil] = useState<any>(null);

  const grade = useQuery({
    queryKey: ["grade"], queryFn: () => ambilJson("/api/grade"), staleTime: 300_000,
  });

  const angka = nilai ? bacaAngka(nilai) : 0;
  const kg = satuan === "ton" ? angka * 1000 : angka;

  const simpan = useMutation({
    mutationFn: () => kirimJson("/api/stok", {
      tanggal, item_code: jenis, stok_kg: kg,
      catatan: catatan || null, pengisi: pengisi || "?",
    }),
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      setHasil(d.ringkasan);
      setNilai("");
      setCatatan("");
      qc.invalidateQueries({ queryKey: ["input-harian"] });
      qc.invalidateQueries({ queryKey: ["stok"] });
      qc.invalidateQueries({ queryKey: ["alarm"] });
      qc.invalidateQueries({ queryKey: ["kualitas"] });
    },
    onError: (e: Error) => { setInfo({ jenis: "error", teks: e.message }); setHasil(null); },
  });

  const terakhir = ringkas?.stok_terakhir;

  return (
    <section id="form-stok" className="rounded-sm bg-white p-5 shadow-sm border border-[#E4E5E8]">
      <h2 className="text-lg font-semibold text-[#1D2434]">{t("Stok harian")}</h2>
      <p className="mb-4 text-sm text-[#64676C]">
        {t("Satu angka per hari. Dipakai untuk Days of Cover, rasio safety, dan alarm stok — supaya tidak menunggu unggahan Excel.")}
      </p>

      {terakhir && (
        <p className="mb-3 rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-3 py-2 text-xs text-[#64676C]">
          {t("Stok terakhir")}: <b className="text-[#1D2434]">
            {fmtAngka(terakhir.stok_ton, 1)} {t("ton")}
          </b> ({fmtTanggal(terakhir.tanggal)}) ·{" "}
          {t("rasio")} {fmtAngka(terakhir.rasio_stok, 2)} ·{" "}
          {t("days")} {fmtAngka(terakhir.days, 1)}
          <button className={`${kelasTombolKecil} ml-2`}
                  onClick={() => { setNilai(String(terakhir.stok_ton ?? "")); setSatuan("ton"); }}>
            {t("Pakai angka ini")}
          </button>
        </p>
      )}

      <form className="grid grid-cols-1 gap-3 sm:grid-cols-4"
            onSubmit={(e) => {
              e.preventDefault();
              setInfo(null);
              if (!angka || angka <= 0) {
                setInfo({ jenis: "error", teks: t("Isi dulu jumlah stok (lebih dari 0).") });
                return;
              }
              simpan.mutate();
            }}>
        <div>
          <label className={kelasLabel}>{t("Tanggal")}</label>
          <input type="date" className={kelasInput} value={tanggal}
                 onChange={(e) => setTanggal(e.target.value)} required />
        </div>
        <div>
          <label className={kelasLabel}>{t("Jenis stok")}</label>
          <select className={kelasInput} value={jenis}
                  onChange={(e) => setJenis(e.target.value)}>
            <option value="">{t("Total (semua grade)")}</option>
            {(grade.data ?? [])
              .filter((g: any) => g.item_code !== "ALL")
              .map((g: any) => (
                <option key={g.item_code} value={g.item_code}>{g.item_code}</option>
              ))}
          </select>
        </div>
        <div>
          <label className={kelasLabel}>{t("Jumlah stok")}</label>
          <div className="flex gap-1.5">
            <input type="text" inputMode="decimal" placeholder="contoh: 571,5"
                   className={kelasInput} value={nilai}
                   onChange={(e) => setNilai(e.target.value)} />
            <select className={`${kelasInput} w-20`} value={satuan}
                    onChange={(e) => setSatuan(e.target.value as "ton" | "kg")}>
              <option value="ton">{t("ton")}</option>
              <option value="kg">{t("kg")}</option>
            </select>
          </div>
          <p className="mt-1 text-[11px] text-[#64676C]">
            {nilai && angka > 0 ? `= ${fmtAngka(kg, 0)} kg` : " "}
          </p>
        </div>
        <div>
          <label className={kelasLabel}>{t("Catatan (boleh kosong)")}</label>
          <input type="text" className={kelasInput} value={catatan}
                 onChange={(e) => setCatatan(e.target.value)} />
        </div>
        <div className="sm:col-span-4">
          <button className={kelasTombol} disabled={simpan.isPending}>
            {simpan.isPending ? t("Menyimpan…") : t("Simpan stok")}
          </button>
        </div>
      </form>
      {info && <Pesan jenis={info.jenis} teks={info.teks} />}

      {hasil && (
        <p className="mt-2 rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-3 py-2 text-xs text-[#64676C]">
          {t("Setelah disimpan")}: <b className="text-[#1D2434]">
            {fmtAngka(hasil.stok_ton, 1)} {t("ton")}
          </b> · {t("safety")} {fmtAngka(hasil.safety_ton, 1)} {t("ton")} ·{" "}
          {t("rasio")} {fmtAngka(hasil.rasio_stok, 2)} ·{" "}
          {t("days")} {fmtAngka(hasil.days, 1)}
        </p>
      )}

      <h3 className="mt-5 mb-2 text-sm font-semibold text-[#1D2434]">
        {t("5 stok terakhir")}
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#E4E5E8] text-left text-[#64676C]">
            <th className="py-1">{t("Tanggal")}</th>
            <th className="py-1">{t("Jenis")}</th>
            <th className="py-1 text-right">{t("Stok (kg)")}</th>
          </tr>
        </thead>
        <tbody>
          {(ringkas?.riwayat_stok ?? []).map((r) => (
            <tr key={`${r.tanggal}-${r.item_code}`} className="border-b border-[#EDEFF2]">
              <td className="py-1">{fmtTanggal(r.tanggal)}</td>
              <td className="py-1 text-[#64676C]">{r.item_code || t("Total")}</td>
              <td className="py-1 text-right font-mono">{fmtAngka(r.stok_kg, 0)}</td>
            </tr>
          ))}
          {(ringkas?.riwayat_stok ?? []).length === 0 && (
            <tr><td colSpan={3} className="py-2 text-[#64676C]">{t("Belum ada data.")}</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

/* ============================================================
   Pembelian harian
   ============================================================ */
function KartuPembelian({ pengisi, tanggal, setTanggal, ringkas }: {
  pengisi: string; tanggal: string; setTanggal: (t: string) => void;
  ringkas?: Ringkas;
}) {
  const { t } = useBahasa();
  const qc = useQueryClient();
  const [tingkat, setTingkat] = useState<"total" | "grade" | "vendor" | "tiket">("total");
  const [kodeGrade, setKodeGrade] = useState("ALL");
  const [kodeVendor, setKodeVendor] = useState("");
  const [noTiket, setNoTiket] = useState("");
  const [qty, setQty] = useState("");
  const [amount, setAmount] = useState("");
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);
  const [hasil, setHasil] = useState<any>(null);

  const grade = useQuery({
    queryKey: ["grade"], queryFn: () => ambilJson("/api/grade"), staleTime: 300_000,
  });
  const vendor = useQuery({
    queryKey: ["vendor", "ringkas"], queryFn: () => ambilJson("/api/vendor"),
    staleTime: 300_000,
  });

  const simpan = useMutation({
    mutationFn: () => kirimJson("/api/pembelian", {
      tanggal,
      item_code: tingkat === "total" ? "ALL" : kodeGrade,
      kode_vendor: tingkat === "vendor" ? kodeVendor
        : tingkat === "tiket" ? kodeVendor : "",
      ticket_no: tingkat === "tiket" ? noTiket : "",
      qty_kering_kg: bacaAngka(qty),
      amount_rp: bacaAngka(amount),
      pengisi: pengisi || "?",
    }),
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      setHasil(d);
      setQty(""); setAmount("");
      qc.invalidateQueries({ queryKey: ["input-harian"] });
      qc.invalidateQueries({ queryKey: ["alarm"] });
      qc.invalidateQueries({ queryKey: ["kualitas"] });
      qc.invalidateQueries({ queryKey: ["rekonsiliasi"] });
    },
    onError: (e: Error) => { setInfo({ jenis: "error", teks: e.message }); setHasil(null); },
  });

  const butuhGrade = tingkat !== "total";
  const butuhVendor = tingkat === "vendor" || tingkat === "tiket";

  return (
    <section id="form-beli" className="rounded-sm bg-white p-5 shadow-sm border border-[#E4E5E8]">
      <h2 className="text-lg font-semibold text-[#1D2434]">{t("Pembelian harian")}</h2>
      <p className="mb-4 text-sm text-[#64676C]">
        {t("Isi qty kering & amount; harga Rp/kg, harga US¢/kg, dan margin harian dihitung sendiri memakai kurs & SICOM yang berlaku.")}
      </p>

      <form className="grid grid-cols-1 gap-3 sm:grid-cols-4"
            onSubmit={(e) => {
              e.preventDefault();
              setInfo(null);
              if (!(bacaAngka(qty) > 0) || !(bacaAngka(amount) > 0)) {
                setInfo({ jenis: "error", teks: t("Qty kering dan amount harus lebih dari 0.") });
                return;
              }
              if (butuhVendor && !kodeVendor) {
                setInfo({ jenis: "error", teks: t("Pilih dulu vendornya.") });
                return;
              }
              simpan.mutate();
            }}>
        <div>
          <label className={kelasLabel}>{t("Tanggal")}</label>
          <input type="date" className={kelasInput} value={tanggal}
                 onChange={(e) => setTanggal(e.target.value)} required />
        </div>
        <div>
          <label className={kelasLabel}>{t("Tingkat")}</label>
          <select className={kelasInput} value={tingkat}
                  onChange={(e) => setTingkat(e.target.value as any)}>
            <option value="total">{t("Total hari")}</option>
            <option value="grade">{t("Per grade")}</option>
            <option value="vendor">{t("Per vendor")}</option>
            <option value="tiket">{t("Per tiket")}</option>
          </select>
        </div>
        {butuhGrade && (
          <div>
            <label className={kelasLabel}>{t("Grade")}</label>
            <select className={kelasInput} value={kodeGrade}
                    onChange={(e) => setKodeGrade(e.target.value)}>
              {(grade.data ?? []).filter((g: any) => g.item_code !== "ALL")
                .map((g: any) => (
                  <option key={g.item_code} value={g.item_code}>{g.item_code}</option>
                ))}
            </select>
          </div>
        )}
        {butuhVendor && (
          <div>
            <label className={kelasLabel}>{t("Vendor")}</label>
            <select className={kelasInput} value={kodeVendor}
                    onChange={(e) => setKodeVendor(e.target.value)}>
              <option value="">{t("pilih vendor")}</option>
              {(vendor.data ?? []).map((v: any) => (
                <option key={v.kode} value={v.kode}>{v.kode} — {v.nama_baku}</option>
              ))}
            </select>
          </div>
        )}
        {tingkat === "tiket" && (
          <div>
            <label className={kelasLabel}>{t("No. tiket")}</label>
            <input className={kelasInput} value={noTiket}
                   onChange={(e) => setNoTiket(e.target.value)} />
          </div>
        )}
        <div>
          <label className={kelasLabel}>{t("Qty kering (kg)")}</label>
          <input type="text" inputMode="decimal" className={kelasInput}
                 placeholder="contoh: 19.500" value={qty}
                 onChange={(e) => setQty(e.target.value)} />
        </div>
        <div>
          <label className={kelasLabel}>{t("Amount (Rp)")}</label>
          <input type="text" inputMode="decimal" className={kelasInput}
                 placeholder="contoh: 480.000.000" value={amount}
                 onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div className="flex items-end">
          <button className={kelasTombol} disabled={simpan.isPending}>
            {simpan.isPending ? t("Menyimpan…") : t("Simpan pembelian")}
          </button>
        </div>
      </form>

      <p className="mt-2 text-xs text-[#64676C]">
        {t("Jangan campur baris “Total hari” dengan baris per grade/vendor/tiket pada tanggal yang sama — pilih satu cara saja supaya tidak terhitung dua kali.")}
      </p>
      {info && <Pesan jenis={info.jenis} teks={info.teks} />}

      {hasil && (
        <p className="mt-2 rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-3 py-2 text-xs text-[#64676C]">
          {t("Harga beli")}: <b className="text-[#1D2434]">
            Rp {fmtAngka(hasil.harga_rp_per_kg, 0)}/kg
          </b>{" "}
          {hasil.harga_usc_per_kg !== null && (
            <>≈ {fmtAngka(hasil.harga_usc_per_kg, 2)} US¢/kg</>
          )}
          {hasil.margin_usc !== null && (
            <> · {t("margin harian")} {fmtAngka(hasil.margin_usc, 2)} US¢/kg</>
          )}
        </p>
      )}

      <h3 className="mt-5 mb-2 text-sm font-semibold text-[#1D2434]">
        {t("5 pembelian terakhir")}
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#E4E5E8] text-left text-[#64676C]">
            <th className="py-1">{t("Tanggal")}</th>
            <th className="py-1">{t("Tingkat")}</th>
            <th className="py-1 text-right">{t("Qty (kg)")}</th>
            <th className="py-1 text-right">Rp/kg</th>
          </tr>
        </thead>
        <tbody>
          {(ringkas?.riwayat_pembelian ?? []).map((r, i) => (
            <tr key={`${r.tanggal}-${i}`} className="border-b border-[#EDEFF2]">
              <td className="py-1">{fmtTanggal(r.tanggal)}</td>
              <td className="py-1 text-[#64676C]">
                {r.item_code === "ALL" ? t("Total hari")
                  : [r.item_code, r.kode_vendor, r.ticket_no].filter(Boolean).join(" · ")}
              </td>
              <td className="py-1 text-right font-mono">{fmtAngka(r.qty_kering_kg, 0)}</td>
              <td className="py-1 text-right font-mono">
                {fmtAngka(r.harga_rp_per_kg, 0)}
              </td>
            </tr>
          ))}
          {(ringkas?.riwayat_pembelian ?? []).length === 0 && (
            <tr><td colSpan={4} className="py-2 text-[#64676C]">{t("Belum ada data.")}</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

/* ============================================================
   SICOM & kurs (sudah ada sebelumnya)
   ============================================================ */
function KartuSicom({ pengisi }: { pengisi: string }) {
  const qc = useQueryClient();
  const { t } = useBahasa();
  const [tanggal, setTanggal] = useState(hariIni());
  const [harga, setHarga] = useState("");
  const [kontrak, setKontrak] = useState("");
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  const riwayat = useQuery({
    queryKey: ["sicom"], queryFn: () => ambilJson("/api/sicom?limit=10"),
  });

  const simpan = useMutation({
    mutationFn: () => kirimJson("/api/sicom", {
      tanggal, usc_per_kg: bacaAngka(harga), kontrak: kontrak || null,
      pengisi: pengisi || "?",
    }),
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      setHarga("");
      qc.invalidateQueries({ queryKey: ["sicom"] });
      qc.invalidateQueries({ queryKey: ["input-harian"] });
      qc.invalidateQueries({ queryKey: ["alarm"] });
    },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });

  return (
    <section className="rounded-sm bg-white p-5 shadow-sm border border-[#E4E5E8]">
      <h2 className="text-lg font-semibold text-[#1D2434]">{t("SICOM harian (TSR20)")}</h2>
      <p className="mb-4 text-sm text-[#64676C]">
        {t("Dicek tiap hari dari website SICOM. Hari libur otomatis memakai harga terakhir — tidak perlu diisi.")}
      </p>
      <form className="grid grid-cols-1 gap-3 sm:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              setInfo(null);
              if (!harga) {
                setInfo({ jenis: "error", teks: t("Isi dulu harga SICOM (US¢/kg).") });
                return;
              }
              simpan.mutate();
            }}>
        <div>
          <label className={kelasLabel}>{t("Tanggal")}</label>
          <input type="date" className={kelasInput} value={tanggal}
                 onChange={(e) => setTanggal(e.target.value)} required />
        </div>
        <div>
          <label className={kelasLabel}>{t("Harga (US¢/kg)")}</label>
          <input type="text" inputMode="decimal" placeholder="contoh: 259,3"
                 className={kelasInput} value={harga}
                 onChange={(e) => setHarga(e.target.value)} />
        </div>
        <div>
          <label className={kelasLabel}>{t("Kontrak (boleh kosong)")}</label>
          <input type="text" placeholder="belum ditentukan" className={kelasInput}
                 value={kontrak} onChange={(e) => setKontrak(e.target.value)} />
        </div>
        <div className="sm:col-span-3">
          <button className={kelasTombol} disabled={simpan.isPending}>
            {simpan.isPending ? t("Menyimpan…") : t("Simpan SICOM")}
          </button>
        </div>
      </form>
      {info && <Pesan jenis={info.jenis} teks={info.teks} />}

      <h3 className="mt-5 mb-2 text-sm font-semibold text-[#1D2434]">
        {t("10 hari terakhir")}
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#E4E5E8] text-left text-[#64676C]">
            <th className="py-1">{t("Tanggal")}</th>
            <th className="py-1 text-right">US¢/kg</th>
            <th className="py-1 pl-4">{t("Sumber")}</th>
          </tr>
        </thead>
        <tbody>
          {riwayat.data?.map((b: any) => (
            <tr key={b.tanggal} className="border-b border-[#EDEFF2]">
              <td className="py-1">{fmtTanggal(b.tanggal)}</td>
              <td className="py-1 text-right font-mono">{fmtAngka(b.usc_per_kg, 2)}</td>
              <td className="py-1 pl-4 text-[#64676C]">{b.sumber ?? "-"}</td>
            </tr>
          ))}
          {riwayat.data?.length === 0 && (
            <tr><td colSpan={3} className="py-2 text-[#64676C]">{t("Belum ada data.")}</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

function KartuKurs({ pengisi }: { pengisi: string }) {
  const qc = useQueryClient();
  const { t } = useBahasa();
  const [berlakuDari, setBerlakuDari] = useState(hariIni());
  const [nilai, setNilai] = useState("");
  const [info, setInfo] = useState<{ jenis: "sukses" | "error"; teks: string } | null>(null);

  const riwayat = useQuery({
    queryKey: ["kurs"], queryFn: () => ambilJson("/api/kurs?limit=10"),
  });

  const simpan = useMutation({
    mutationFn: () => kirimJson("/api/kurs", {
      berlaku_dari: berlakuDari, idr_per_usd: bacaAngka(nilai),
      pengisi: pengisi || "?",
    }),
    onSuccess: (d) => {
      setInfo({ jenis: "sukses", teks: d.pesan });
      setNilai("");
      qc.invalidateQueries({ queryKey: ["kurs"] });
      qc.invalidateQueries({ queryKey: ["input-harian"] });
      qc.invalidateQueries({ queryKey: ["alarm"] });
    },
    onError: (e: Error) => setInfo({ jenis: "error", teks: e.message }),
  });

  return (
    <section className="rounded-sm bg-white p-5 shadow-sm border border-[#E4E5E8]">
      <h2 className="text-lg font-semibold text-[#1D2434]">{t("Kurs USD/IDR")}</h2>
      <p className="mb-4 text-sm text-[#64676C]">
        {t("Ditetapkan perusahaan dari data bank. Isi hanya saat kurs berubah — berlaku sejak tanggal yang dipilih (boleh di tengah bulan).")}
      </p>
      <form className="grid grid-cols-1 gap-3 sm:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              setInfo(null);
              if (!nilai) {
                setInfo({ jenis: "error", teks: t("Isi dulu nilai kurs (IDR per USD).") });
                return;
              }
              simpan.mutate();
            }}>
        <div>
          <label className={kelasLabel}>{t("Berlaku sejak")}</label>
          <input type="date" className={kelasInput} value={berlakuDari}
                 onChange={(e) => setBerlakuDari(e.target.value)} required />
        </div>
        <div>
          <label className={kelasLabel}>{t("Kurs (IDR per USD)")}</label>
          <input type="text" inputMode="decimal" placeholder="contoh: 16.644"
                 className={kelasInput} value={nilai}
                 onChange={(e) => setNilai(e.target.value)} />
        </div>
        <div className="flex items-end">
          <button className={kelasTombol} disabled={simpan.isPending}>
            {simpan.isPending ? t("Menyimpan…") : t("Simpan kurs")}
          </button>
        </div>
      </form>
      {info && <Pesan jenis={info.jenis} teks={info.teks} />}

      <h3 className="mt-5 mb-2 text-sm font-semibold text-[#1D2434]">
        {t("10 perubahan terakhir")}
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#E4E5E8] text-left text-[#64676C]">
            <th className="py-1">{t("Berlaku sejak")}</th>
            <th className="py-1 text-right">IDR/USD</th>
            <th className="py-1 pl-4">{t("Sumber")}</th>
          </tr>
        </thead>
        <tbody>
          {riwayat.data?.map((b: any) => (
            <tr key={b.berlaku_dari} className="border-b border-[#EDEFF2]">
              <td className="py-1">{fmtTanggal(b.berlaku_dari)}</td>
              <td className="py-1 text-right font-mono">{fmtAngka(b.idr_per_usd, 0)}</td>
              <td className="py-1 pl-4 text-[#64676C]">{b.sumber ?? "-"}</td>
            </tr>
          ))}
          {riwayat.data?.length === 0 && (
            <tr><td colSpan={3} className="py-2 text-[#64676C]">{t("Belum ada data.")}</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

/* ============================================================ */
export default function InputHarian({ pengisi }: { pengisi: string }) {
  const { t } = useBahasa();
  const [tglStok, setTglStok] = useState(hariIni());
  const [tglBeli, setTglBeli] = useState(hariIni());

  const ringkas = useQuery({
    queryKey: ["input-harian"],
    queryFn: () => ambilJson("/api/input-harian"),
  });

  return (
    <div className="grid grid-cols-1 gap-6">
      <PanelKesegaran
        data={ringkas.data}
        isiStok={(tgl) => { setTglStok(tgl); ke("form-stok"); }}
        isiBeli={(tgl) => { setTglBeli(tgl); ke("form-beli"); }}
      />
      <KartuStok pengisi={pengisi} tanggal={tglStok} setTanggal={setTglStok}
                 ringkas={ringkas.data} />
      <KartuPembelian pengisi={pengisi} tanggal={tglBeli} setTanggal={setTglBeli}
                      ringkas={ringkas.data} />
      <KartuSicom pengisi={pengisi} />
      <KartuKurs pengisi={pengisi} />
      <p className="text-xs text-[#64676C]">
        {t("Setiap simpanan dicatat (siapa & kapan) dan langsung memperbarui perhitungan OP Margin. Tanggal ditampilkan dd/mm/yyyy, angka memakai format Indonesia.")}
      </p>
    </div>
  );
}
