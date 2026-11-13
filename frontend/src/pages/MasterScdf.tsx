import { Fragment, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Kartu, Pesan, ambilJson, fmtAngka, kelasTombolKecil,
} from "../bersama";

type Tingkat = "provinsi" | "kabupaten" | "kecamatan" | "desa";
type Induk = {
  provinsi?: string; kabupaten?: string;
  kecamatan?: string; desa?: string;
};
type Simpul = {
  tingkat: Tingkat; label_tingkat: string; name: string; norm: string;
  jumlah_anak: number; jumlah_baris: number; status_provinsi: string;
};
type DetailTerpilih = { simpul: Simpul; induk: Induk; kunci: string };

const BERIKUTNYA: Record<Tingkat, Tingkat | null> = {
  provinsi: "kabupaten", kabupaten: "kecamatan",
  kecamatan: "desa", desa: null,
};
const BATAS_BARIS = 50;

function paramsPohon(tingkat: Tingkat, induk: Induk) {
  const p = new URLSearchParams({ tingkat });
  if (tingkat !== "provinsi") p.set("provinsi_norm", induk.provinsi ?? "");
  if (tingkat === "kecamatan" || tingkat === "desa") {
    p.set("kabupaten_norm", induk.kabupaten ?? "");
  }
  if (tingkat === "desa") p.set("kecamatan_norm", induk.kecamatan ?? "");
  return p;
}

function paramsDetail(detail: DetailTerpilih, offset: number) {
  const p = new URLSearchParams({
    tingkat: detail.simpul.tingkat,
    limit: String(BATAS_BARIS), offset: String(offset),
  });
  p.set("provinsi_norm", detail.induk.provinsi ?? "");
  if (detail.induk.kabupaten !== undefined) p.set("kabupaten_norm", detail.induk.kabupaten);
  if (detail.induk.kecamatan !== undefined) p.set("kecamatan_norm", detail.induk.kecamatan);
  if (detail.induk.desa !== undefined) p.set("desa_norm", detail.induk.desa);
  return p;
}

function paramsCari(kata: string, offset: number) {
  const p = new URLSearchParams({
    q: kata, cari: kata,
    limit: String(BATAS_BARIS), offset: String(offset),
  });
  return p;
}

function BadgeStatus({ status }: { status: string }) {
  const belum = status === "belum_dipetakan";
  return <span className={`rounded-sm px-1.5 py-0.5 text-[10px] ${belum
    ? "bg-[#FFFAEB] text-[#B54708]"
    : "bg-[#ECFDF3] text-[#027A48]"}`}>
    {belum ? "Belum dipetakan" : "Terpetakan"}
  </span>;
}

function CabangScdf({ simpul, tingkat, induk, depth, onPilih, kunciDipilih }: {
  simpul: Simpul; tingkat: Tingkat; induk: Induk; depth: number;
  onPilih: (d: DetailTerpilih) => void; kunciDipilih?: string;
}) {
  const [buka, setBuka] = useState(false);
  const anakTingkat = BERIKUTNYA[tingkat];
  const indukAnak: Induk = { ...induk, [tingkat]: simpul.norm };
  const kunci = `${tingkat}:${simpul.norm}:${JSON.stringify(induk)}`;
  const punyaAnak = Boolean(anakTingkat && simpul.jumlah_anak > 0);
  const anak = useQuery({
    queryKey: ["master-scdf-pohon", anakTingkat, JSON.stringify(indukAnak)],
    queryFn: () => anakTingkat
      ? ambilJson(`/api/master/scdf/pohon?${paramsPohon(anakTingkat, indukAnak)}`)
      : Promise.resolve({ nodes: [] }),
    enabled: Boolean(buka && anakTingkat),
  });
  const pilih = (bukaJuga = false) => {
    if (bukaJuga && punyaAnak) setBuka(true);
    onPilih({ simpul, induk: indukAnak, kunci });
  };

  return <Fragment>
    <tr className={`border-t border-[#EDEFF2] ${kunciDipilih === kunci ? "bg-[#FFFAEB]" : "hover:bg-[#FAFAFA]"}`}>
      <td className="py-2 pl-3" style={{ paddingLeft: `${12 + depth * 18}px` }}>
        <div className="flex items-center gap-1.5">
          {punyaAnak
            ? <button type="button" aria-label={buka ? "Tutup cabang SCDF" : "Buka cabang SCDF"}
                      className="w-5 text-[#64676C]" onClick={() => setBuka(!buka)}>{buka ? "▾" : "▸"}</button>
            : <span className="w-5" />}
          <button type="button" className="text-left font-semibold text-[#1D2434] hover:text-[#B91C1C]"
                  onClick={() => pilih(true)}>{simpul.name}</button>
          <span className="text-[9px] uppercase tracking-wide text-[#9AA0A6]">{simpul.label_tingkat}</span>
        </div>
      </td>
      <td className="px-2 text-[10px] text-[#64676C]">{simpul.label_tingkat}</td>
      <td className="px-2 text-right font-mono">{fmtAngka(simpul.jumlah_anak, 0)}</td>
      <td className="px-2 text-right font-mono">{fmtAngka(simpul.jumlah_baris, 0)}</td>
      <td className="px-2"><BadgeStatus status={simpul.status_provinsi} /></td>
      <td className="px-2 pr-3 text-right">
        <button type="button" className={kelasTombolKecil} onClick={() => pilih(false)}>Rincian</button>
      </td>
    </tr>
    {buka && anak.isLoading && <tr><td colSpan={6} className="py-2 text-center text-[10px] text-[#64676C]">Memuat cabang…</td></tr>}
    {buka && anak.error && <tr><td colSpan={6} className="py-2 text-center text-[10px] text-[#B42318]">{(anak.error as Error).message}</td></tr>}
    {buka && anakTingkat && (anak.data?.nodes ?? []).map((node: Simpul) =>
      <CabangScdf key={`${anakTingkat}:${node.norm}:${JSON.stringify(indukAnak)}`}
                  simpul={node} tingkat={anakTingkat} induk={indukAnak}
                  depth={depth + 1} onPilih={onPilih} kunciDipilih={kunciDipilih} />)}
    {buka && anak.data && !(anak.data.nodes ?? []).length &&
      <tr><td colSpan={6} className="py-2 text-center text-[10px] text-[#9AA0A6]">Tidak ada cabang pada node ini.</td></tr>}
  </Fragment>;
}

export default function MasterScdf() {
  const [detail, setDetail] = useState<DetailTerpilih | null>(null);
  const [offsetDetail, setOffsetDetail] = useState(0);
  const [teksCari, setTeksCari] = useState("");
  const [kataCari, setKataCari] = useState("");
  const [offsetCari, setOffsetCari] = useState(0);

  useEffect(() => {
    const tunggu = window.setTimeout(() => {
      setKataCari(teksCari.trim());
      setOffsetCari(0);
    }, 250);
    return () => window.clearTimeout(tunggu);
  }, [teksCari]);

  const cariAktif = kataCari.length > 0;
  const ringkasan = useQuery({
    queryKey: ["master-scdf-ringkasan"],
    queryFn: () => ambilJson("/api/master/scdf/ringkasan"),
  });
  const akar = useQuery({
    queryKey: ["master-scdf-pohon", "provinsi", "{}"],
    queryFn: () => ambilJson(`/api/master/scdf/pohon?${paramsPohon("provinsi", {})}`),
  });
  const rincian = useQuery({
    queryKey: ["master-scdf-detail", detail?.kunci, offsetDetail],
    queryFn: () => ambilJson(`/api/master/scdf/detail?${paramsDetail(detail!, offsetDetail)}`),
    enabled: Boolean(detail) && !cariAktif,
  });
  const pencarian = useQuery({
    queryKey: ["master-scdf-cari", kataCari, offsetCari],
    queryFn: () => ambilJson(`/api/master/scdf/cari?${paramsCari(kataCari, offsetCari)}`),
    enabled: cariAktif,
  });
  const pilih = (d: DetailTerpilih) => {
    setDetail(d);
    setOffsetDetail(0);
    setTeksCari("");
    setKataCari("");
    setOffsetCari(0);
  };
  const hapusCari = () => {
    setTeksCari("");
    setKataCari("");
    setOffsetCari(0);
  };
  const s = ringkasan.data;
  const ringkas: { label: string; nilai: number | undefined; satuan: string }[] = [
    { label: "Provinsi terpetakan", nilai: s?.provinsi, satuan: "provinsi" },
    { label: "Kabupaten/Kota", nilai: s?.kabupaten_kota, satuan: "wilayah" },
    { label: "Kecamatan", nilai: s?.kecamatan, satuan: "wilayah" },
    { label: "Desa/Kelurahan", nilai: s?.desa_kelurahan, satuan: "kombinasi" },
    { label: "Kunci tanpa Provinsi", nilai: s?.kunci_tanpa_provinsi, satuan: "kunci" },
    { label: "Baris tanpa Provinsi", nilai: s?.baris_tanpa_provinsi, satuan: "baris" },
  ];
  const dataTabel = cariAktif ? pencarian.data : rincian.data;
  const sedangMuat = cariAktif ? pencarian.isLoading : rincian.isLoading;
  const sedangSegarkan = cariAktif ? pencarian.isFetching : rincian.isFetching;
  const galat = cariAktif ? pencarian.error : rincian.error;
  const offsetAktif = cariAktif ? offsetCari : offsetDetail;
  const setOffsetAktif = cariAktif ? setOffsetCari : setOffsetDetail;

  return <section data-uji="modul-master-scdf" className="space-y-4">
    <Kartu idMetrik="master_scdf" judul="SCDF — Referensi lokasi Indonesia"
      keterangan="Katalog baca saja Provinsi → Kabupaten/Kota → Kecamatan → Desa/Kelurahan dari ID_AUX dan crosswalk Provinsi resmi. Klik node untuk membuka rincian nama resmi, normalized key, dan status pemetaan Provinsi."
      anak={<>
        <div data-uji="ringkasan-scdf" className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
          {ringkas.map((k) => <div key={k.label} className="rounded-sm border border-[#E4E5E8] bg-[#F8F8F8] px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-[#64676C]">{k.label}</p>
            <p className="mt-1 text-lg font-bold tabular-nums text-[#1D2434]">{k.nilai == null ? "—" : fmtAngka(k.nilai, 0)}<span className="ml-1 text-[10px] font-medium text-[#64676C]">{k.satuan}</span></p>
          </div>)}
        </div>
        {ringkasan.isError && <Pesan jenis="error" teks={(ringkasan.error as Error).message} />}
        <p className="mt-3 rounded-sm bg-[#F8F8F8] p-3 text-[10px] leading-relaxed text-[#64676C]">
          <b className="text-[#1D2434]">Sumber & batas.</b> {s?.catatan ?? "Sumber: traceability_wilayah dari ID_AUX; Provinsi berasal dari crosswalk resmi Kepmendagri."} Tidak ada tombol Tambah/Edit/Hapus maupun Ekspor Excel: modul ini hanya menampilkan referensi yang dipakai Traceability dan validasi Data Intake.
        </p>
      </>} />

    <section data-uji="pencarian-scdf" className="kartu-aksen rounded-sm border border-[#E4E5E8] bg-white p-5 shadow-[0_1px_3px_rgba(29,36,52,0.08)]">
      <label htmlFor="cari-scdf" className="block text-sm font-semibold text-[#1D2434]">Cari lokasi SCDF</label>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <input id="cari-scdf" data-uji="input-pencarian-scdf" type="text"
               autoComplete="off" value={teksCari}
               onChange={(e) => setTeksCari(e.target.value)}
               placeholder="Cari Provinsi, Kabupaten/Kota, Kecamatan, Desa, normalized key, atau Belum dipetakan…"
               className="min-w-[260px] flex-1 rounded-sm border border-[#D9DCE1] px-3 py-2 text-sm text-[#1D2434] outline-none focus:border-[#B91C1C]" />
        {teksCari && <button type="button" className={kelasTombolKecil}
                            onClick={hapusCari} aria-label="Hapus pencarian"
                            title="Hapus pencarian">✕</button>}
      </div>
      <p className="mt-2 text-[10px] leading-relaxed text-[#64676C]">
        Mencari <b>4 nama resmi</b> + <b>4 normalized key</b> + <b>status Provinsi</b> di seluruh
        <code className="mx-1 font-mono">traceability_wilayah</code>, case-insensitive dan tetap baca saja.
        Baris <b>Belum dipetakan</b> ikut terindeks; Provinsi tidak ditebak.
      </p>
      {cariAktif && <p data-uji="status-pencarian-scdf" className="mt-2 rounded-sm bg-[#FFFAEB] p-2 text-[10px] leading-relaxed text-[#B54708]">
        Mode pencarian: <b>"{kataCari}"</b> · {fmtAngka(dataTabel?.total ?? 0, 0)} baris cocok.
        Klik ✕ atau pilih node pohon untuk kembali ke rincian per node.
      </p>}
    </section>

    <section className="kartu-aksen rounded-sm border border-[#E4E5E8] bg-white p-5 shadow-[0_1px_3px_rgba(29,36,52,0.08)]">
      <h2 className="text-lg font-semibold text-[#1D2434]">Hierarki wilayah SCDF</h2>
      <p className="text-sm text-[#64676C]">Buka cabang untuk menelusuri 4 tingkat. Angka <b>Jumlah anak</b> adalah jumlah wilayah tepat di bawahnya; <b>Baris SCDF</b> adalah jumlah kombinasi Desa/Kelurahan pada node itu.</p>
      {akar.isError && <Pesan jenis="error" teks={(akar.error as Error).message} />}
      <div className="mt-3 max-h-[52vh] overflow-auto rounded-sm border border-[#E4E5E8]">
        <table data-uji="pohon-scdf" className="w-full min-w-[880px] text-xs">
          <thead className="sticky top-0 bg-[#F8F8F8] text-left text-[10px] uppercase tracking-wide text-[#64676C]">
            <tr><th className="py-2 pl-3">Wilayah</th><th className="px-2">Tingkat</th><th className="px-2 text-right">Jumlah anak</th><th className="px-2 text-right">Baris SCDF</th><th className="px-2">Status Provinsi</th><th className="px-2 pr-3 text-right">Aksi</th></tr>
          </thead>
          <tbody>
            {akar.isLoading && <tr><td colSpan={6} className="py-8 text-center text-[#64676C]">Memuat Provinsi…</td></tr>}
            {(akar.data?.nodes ?? []).map((node: Simpul) =>
              <CabangScdf key={`provinsi:${node.norm}`} simpul={node} tingkat="provinsi"
                          induk={{}} depth={0} onPilih={pilih} kunciDipilih={detail?.kunci} />)}
            {akar.data && !(akar.data.nodes ?? []).length && <tr><td colSpan={6} className="py-8 text-center text-[#9AA0A6]">Referensi SCDF belum tersedia.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[10px] leading-relaxed text-[#9AA0A6]">Baris dengan <b>Belum dipetakan</b> tetap ditampilkan apa adanya; Provinsi tidak ditebak dari nama Kabupaten/Kota maupun data intake.</p>
    </section>

    <section data-uji={cariAktif ? "hasil-pencarian-scdf" : undefined}
             className="kartu-aksen rounded-sm border border-[#E4E5E8] bg-white p-5 shadow-[0_1px_3px_rgba(29,36,52,0.08)]">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-[#1D2434]">{cariAktif ? "Hasil pencarian SCDF" : "Rincian lokasi"}</h2>
          <p className="text-sm text-[#64676C]">{cariAktif
            ? `Kata kunci: "${kataCari}" · ${fmtAngka(dataTabel?.total ?? 0, 0)} baris cocok · pencarian mencakup seluruh 4 tingkat SCDF.`
            : detail
              ? `${detail.simpul.name} · ${detail.simpul.label_tingkat} · ${fmtAngka(detail.simpul.jumlah_baris, 0)} baris SCDF`
              : "Pilih salah satu node pada hierarki di atas."}</p>
        </div>
        {dataTabel && dataTabel.total > 0 && <p className="text-xs text-[#64676C]">Menampilkan {fmtAngka(dataTabel.offset + 1, 0)}–{fmtAngka(Math.min(dataTabel.offset + dataTabel.baris.length, dataTabel.total), 0)} dari {fmtAngka(dataTabel.total, 0)} baris</p>}
      </div>
      {galat && <Pesan jenis="error" teks={(galat as Error).message} />}
      {cariAktif && sedangMuat && <p className="py-6 text-center text-sm text-[#64676C]">Mencari lokasi SCDF…</p>}
      {!cariAktif && detail && sedangMuat && <p className="py-6 text-center text-sm text-[#64676C]">Memuat rincian lokasi…</p>}
      {(cariAktif || detail) && dataTabel && <>
        <div className="mt-3 max-h-[46vh] overflow-auto rounded-sm border border-[#E4E5E8]">
          <table data-uji="rincian-scdf" className="w-full min-w-[1250px] text-xs">
            <thead className="sticky top-0 bg-[#F8F8F8] text-left text-[10px] uppercase tracking-wide text-[#64676C]">
              <tr><th className="py-2 pl-3">Provinsi</th><th className="px-2">Kabupaten/Kota</th><th className="px-2">Kecamatan</th><th className="px-2">Desa/Kelurahan</th><th className="px-2">Provinsi norm</th><th className="px-2">Kabupaten norm</th><th className="px-2">Kecamatan norm</th><th className="px-2">Desa norm</th><th className="px-2 pr-3">Status Provinsi</th></tr>
            </thead>
            <tbody>
              {dataTabel.baris.map((b: any, i: number) => <tr key={`${b.kabupaten_norm}/${b.kecamatan_norm}/${b.desa_norm}/${i}`} className="border-t border-[#EDEFF2]">
                <td className="py-2 pl-3">{b.provinsi}</td>
                <td className="px-2">{b.kabupaten}</td>
                <td className="px-2">{b.kecamatan}</td>
                <td className="px-2 font-medium text-[#1D2434]">{b.desa}</td>
                <td className="px-2 font-mono text-[10px] text-[#64676C]">{b.provinsi_norm || "—"}</td>
                <td className="px-2 font-mono text-[10px] text-[#64676C]">{b.kabupaten_norm}</td>
                <td className="px-2 font-mono text-[10px] text-[#64676C]">{b.kecamatan_norm}</td>
                <td className="px-2 font-mono text-[10px] text-[#64676C]">{b.desa_norm}</td>
                <td className="px-2 pr-3"><BadgeStatus status={b.status_provinsi} /></td>
              </tr>)}
              {!dataTabel.baris.length && <tr><td colSpan={9} className="py-8 text-center text-[#9AA0A6]">{cariAktif ? "Tidak ada baris SCDF yang cocok dengan pencarian ini." : "Tidak ada baris SCDF pada node/filter ini."}</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <button type="button" className={kelasTombolKecil} disabled={offsetAktif === 0 || sedangSegarkan}
                  onClick={() => setOffsetAktif(Math.max(0, offsetAktif - BATAS_BARIS))}>← Sebelumnya</button>
          <span className="text-[10px] text-[#64676C]">Halaman {fmtAngka(dataTabel.halaman, 0)} / {fmtAngka(dataTabel.jumlah_halaman || 1, 0)} · {sedangSegarkan ? "menyegarkan…" : `${BATAS_BARIS} baris per halaman`}</span>
          <button type="button" className={kelasTombolKecil}
                  disabled={offsetAktif + BATAS_BARIS >= dataTabel.total || sedangSegarkan}
                  onClick={() => setOffsetAktif(offsetAktif + BATAS_BARIS)}>Berikutnya →</button>
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-[#9AA0A6]">{dataTabel.catatan}</p>
      </>}
      {!cariAktif && !detail && <p className="mt-3 rounded-sm bg-[#F8F8F8] p-4 text-center text-sm text-[#64676C]">Klik nama wilayah atau tombol <b>Rincian</b> pada pohon untuk melihat 4 nama resmi, normalized key, dan status pemetaan Provinsi.</p>}
    </section>
  </section>;
}
