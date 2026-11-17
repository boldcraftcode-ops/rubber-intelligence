import { useEffect, useState } from "react";
import { kelasInput, kelasTombol, kelasTombolKecil, PREFERENSI_TAMPILAN_BAKU, PreferensiFormat } from "../bersama";
import { useBahasa } from "../i18n";
import { usePreferensi } from "../Preferensi";

const angka = (n: number, d: number, lang: string) => new Intl.NumberFormat(lang === "id" ? "id-ID" : "en-US", {
  minimumFractionDigits: d, maximumFractionDigits: d,
}).format(n);

export default function Pengaturan() {
  const { t, lang } = useBahasa();
  const pref = usePreferensi();
  const [form, setForm] = useState<PreferensiFormat>(pref.efektif);
  const [bawaan, setBawaan] = useState<PreferensiFormat>(pref.bawaan);
  const [terkunci, setTerkunci] = useState(pref.terkunci);
  const [simpan, setSimpan] = useState(false);
  const [pesan, setPesan] = useState("");

  useEffect(() => { setForm(pref.efektif); setBawaan(pref.bawaan); setTerkunci(pref.terkunci); },
    [pref.efektif, pref.bawaan, pref.terkunci]);

  const perbarui = <K extends keyof PreferensiFormat>(key: K, value: PreferensiFormat[K]) =>
    setForm((lama) => ({ ...lama, [key]: value }));
  const perbaruiBawaan = <K extends keyof PreferensiFormat>(key: K, value: PreferensiFormat[K]) =>
    setBawaan((lama) => ({ ...lama, [key]: value }));
  const simpanPribadi = async () => {
    setSimpan(true); setPesan("");
    try {
      await pref.simpanPribadi(form);
      setPesan(t("Preferensi berhasil disimpan."));
    } catch { setPesan(t("Preferensi gagal disimpan.")); }
    finally { setSimpan(false); }
  };
  const reset = async (key: keyof PreferensiFormat) => {
    setSimpan(true); setPesan("");
    try {
      await pref.simpanPribadi({ [key]: null });
      setPesan(t("Bagian dikembalikan ke bawaan."));
    } catch { setPesan(t("Preferensi gagal disimpan.")); }
    finally { setSimpan(false); }
  };
  const simpanCompany = async () => {
    setSimpan(true); setPesan("");
    try {
      await pref.simpanBawaan(bawaan, terkunci);
      setPesan(t("Bawaan perusahaan berhasil disimpan."));
    } catch { setPesan(t("Preferensi gagal disimpan.")); }
    finally { setSimpan(false); }
  };

  const desimal = form.desimal_angka;
  const unit = form.satuan_berat === "otomatis" ? "ton" : form.satuan_berat;
  const berat = form.satuan_berat === "kg" ? 1234.5678 : 1.2345678;
  const labelBerat = unit === "kg" ? "kg" : lang === "id" ? "ton" : "MT";

  return <div className="grid gap-5">
    <header>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#FF1313]">{t("Tampilan")}</p>
      <h2 className="mt-1 text-xl font-bold text-[#1D2434]">{t("Pengaturan Basic")}</h2>
      <p className="mt-1 text-sm text-[#64676C]">{t("Atur tampilan angka dan satuan. Nilai perhitungan dan ekspor tidak berubah.")}</p>
    </header>

    <section className="rounded-sm border border-[#E4E5E8] bg-white p-4">
      <h3 className="text-sm font-semibold text-[#1D2434]">{t("Preferensi tampilan pribadi")}</h3>
      <p className="mt-1 text-xs text-[#64676C]">{t("Preferensi pribadi menimpa bawaan perusahaan, kecuali pengaturan yang dikunci admin.")}</p>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <div className="rounded-sm border border-[#E4E5E8] p-3">
          <label className="block text-sm font-semibold">{t("Desimal angka")}</label>
          <p className="mt-1 text-xs text-[#64676C]">{t("Jumlah angka di belakang koma untuk nilai umum.")}</p>
          <select className={`${kelasInput} mt-3`} value={form.desimal_angka}
            disabled={pref.terkunci.desimal_angka}
            onChange={(e) => perbarui("desimal_angka", Number(e.target.value))}>
            {[0, 1, 2, 3, 4].map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
          <button className={`${kelasTombolKecil} mt-3 w-full`} disabled={simpan || pref.terkunci.desimal_angka}
            onClick={() => void reset("desimal_angka")}>{t("Kembalikan ke bawaan")}</button>
        </div>
        <div className="rounded-sm border border-[#E4E5E8] p-3">
          <label className="block text-sm font-semibold">{t("Desimal persen")}</label>
          <p className="mt-1 text-xs text-[#64676C]">{t("Jumlah angka di belakang koma untuk persentase.")}</p>
          <select className={`${kelasInput} mt-3`} value={form.desimal_persen}
            disabled={pref.terkunci.desimal_persen}
            onChange={(e) => perbarui("desimal_persen", Number(e.target.value))}>
            {[0, 1, 2].map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
          <button className={`${kelasTombolKecil} mt-3 w-full`} disabled={simpan || pref.terkunci.desimal_persen}
            onClick={() => void reset("desimal_persen")}>{t("Kembalikan ke bawaan")}</button>
        </div>
        <div className="rounded-sm border border-[#E4E5E8] p-3">
          <label className="block text-sm font-semibold">{t("Satuan berat")}</label>
          <p className="mt-1 text-xs text-[#64676C]">{t("Satuan berat ditampilkan dari nilai kilogram tanpa mengubah perhitungan.")}</p>
          <select className={`${kelasInput} mt-3`} value={form.satuan_berat}
            disabled={pref.terkunci.satuan_berat}
            onChange={(e) => perbarui("satuan_berat", e.target.value as PreferensiFormat["satuan_berat"])}>
            <option value="kg">kg</option><option value="ton">{t("ton (MT)")}</option>
            <option value="otomatis">{t("Otomatis (kg atau ton)")}</option>
          </select>
          <button className={`${kelasTombolKecil} mt-3 w-full`} disabled={simpan || pref.terkunci.satuan_berat}
            onClick={() => void reset("satuan_berat")}>{t("Kembalikan ke bawaan")}</button>
        </div>
      </div>
      <div className="mt-4 rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] p-3">
        <p className="text-xs font-semibold text-[#1D2434]">{t("Pratinjau langsung")}</p>
        <p className="mt-2 text-sm text-[#64676C]">{t("Berat")}: <b className="text-[#1D2434]">{angka(berat, desimal, lang)} {labelBerat}</b></p>
        <p className="mt-1 text-sm text-[#64676C]">{t("Persentase")}: <b className="text-[#1D2434]">{angka(12.345, form.desimal_persen, lang)}%</b></p>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button className={kelasTombol} disabled={simpan || pref.memuat} onClick={() => void simpanPribadi()}>{t("Simpan preferensi saya")}</button>
        {pesan && <p role="status" className="text-sm text-[#64676C]">{pesan}</p>}
        {pref.gagal && <p className="text-xs text-[#92400E]">{t("Preferensi belum dimuat; nilai bawaan digunakan.")}</p>}
      </div>
    </section>

    {pref.admin && <section className="rounded-sm border border-[#E4E5E8] bg-white p-4">
      <h3 className="text-sm font-semibold text-[#1D2434]">{t("Bawaan perusahaan (admin)")}</h3>
      <p className="mt-1 text-xs text-[#64676C]">{t("Atur nilai awal untuk pengguna dan kunci pengaturan bila perlu.")}</p>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        {(["desimal_angka", "desimal_persen", "satuan_berat"] as const).map((key) => <div key={key} className="rounded-sm border border-[#E4E5E8] p-3">
          <label className="block text-sm font-semibold">{t(key === "desimal_angka" ? "Desimal angka" : key === "desimal_persen" ? "Desimal persen" : "Satuan berat")}</label>
          {key === "satuan_berat" ? <select className={`${kelasInput} mt-2`} value={bawaan[key]} onChange={(e) => perbaruiBawaan(key, e.target.value as PreferensiFormat["satuan_berat"])}>
            <option value="kg">kg</option><option value="ton">{t("ton (MT)")}</option><option value="otomatis">{t("Otomatis (kg atau ton)")}</option>
          </select> : <select className={`${kelasInput} mt-2`} value={bawaan[key]} onChange={(e) => perbaruiBawaan(key, Number(e.target.value))}>
            {(key === "desimal_angka" ? [0, 1, 2, 3, 4] : [0, 1, 2]).map((v) => <option key={v}>{v}</option>)}
          </select>}
          <label className="mt-3 flex items-center gap-2 text-xs text-[#64676C]">
            <input type="checkbox" checked={terkunci[key]} onChange={(e) => setTerkunci((x) => ({ ...x, [key]: e.target.checked }))} />
            {t("Kunci untuk semua pengguna")}
          </label>
        </div>)}
      </div>
      <button className={`${kelasTombol} mt-4`} disabled={simpan} onClick={() => void simpanCompany()}>{t("Simpan bawaan perusahaan")}</button>
      <button className={`${kelasTombolKecil} ml-2 mt-4`} disabled={simpan}
        onClick={() => { setBawaan(PREFERENSI_TAMPILAN_BAKU); setTerkunci({ desimal_angka: false, desimal_persen: false, satuan_berat: false }); }}>
        {t("Pulihkan bawaan awal")}
      </button>
    </section>}
  </div>;
}
