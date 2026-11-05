import {
  Children, cloneElement, createContext, createElement, isValidElement, ReactNode, useContext,
  useEffect, useMemo, useState,
} from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, LabelList,
  Legend, Line, LineChart, ReferenceDot, ReferenceLine, Scatter, ScatterChart,
} from "recharts";

type Bentuk = "asli" | "garis" | "batang" | "area" | "titik-bulat" | "titik-kotak" | "titik-wajik" | "titik-segitiga";
type JenisAnotasi = "target" | "rata-rata" | "minimum" | "maksimum" | "catatan";
type Anotasi = {
  id: string;
  jenis: JenisAnotasi;
  seri: string;
  nilai?: number;
  periode?: string | number;
  teks?: string;
};
type Setelan = {
  bentuk: Bentuk;
  palet: string;
  kisi: boolean;
  legenda: boolean;
  label: boolean;
  warnaSeri: Record<string, string>;
  seriTersembunyi: string[];
  anotasi: Anotasi[];
};
type Seri = { kunci: string; nilaiKey: string; nama: string; komponen: any; sumbu?: string; data?: any[]; kunciX?: string; warnaAsli?: string };
type Konteks = { pengguna: string };

export const KonteksPenggunaGrafik = createContext<Konteks>({ pengguna: "anonim" });

const bawaan: Setelan = {
  bentuk: "asli", palet: "asli", kisi: true, legenda: true, label: false,
  warnaSeri: {}, seriTersembunyi: [], anotasi: [],
};
const paletWarna: Record<string, string[]> = {
  biru: ["#2563EB", "#06B6D4", "#4F46E5", "#0F766E", "#7C3AED", "#0284C7", "#0891B2"],
  kontras: ["#111827", "#DC2626", "#15803D", "#7C3AED", "#D97706", "#0369A1", "#BE185D"],
};
const jenisGrafik = [BarChart, LineChart, AreaChart, ComposedChart, ScatterChart];
const jenisSeri = [Bar, Line, Area, Scatter];
const kelasKontrol = "rounded border border-[#D5D7DB] bg-white px-2 py-1 text-xs text-[#1D2434]";
const kelasLabel = "block text-[11px] font-medium text-[#64676C]";

function bacaSetelan(kunci: string): Setelan {
  try {
    const s = JSON.parse(localStorage.getItem(kunci) || "null");
    if (!s || typeof s !== "object") return bawaan;
    return {
      ...bawaan, ...s,
      warnaSeri: s.warnaSeri && typeof s.warnaSeri === "object" ? s.warnaSeri : {},
      seriTersembunyi: Array.isArray(s.seriTersembunyi) ? s.seriTersembunyi : [],
      anotasi: Array.isArray(s.anotasi) ? s.anotasi.filter((a: any) => a && a.id && a.jenis && a.seri) : [],
    };
  } catch { return bawaan; }
}

function namaKomponen(t: any): string {
  return t?.displayName || t?.name || "";
}

function cariGrafik(node: ReactNode): any | null {
  let ditemukan: any = null;
  Children.forEach(node, (anak) => {
    if (!isValidElement(anak)) return;
    if (jenisGrafik.includes(anak.type as any)) { ditemukan = anak; return; }
    if (!ditemukan) ditemukan = cariGrafik((anak.props as any).children);
  });
  return ditemukan;
}

function kumpulkan(node: ReactNode, hasil: any[] = []): any[] {
  Children.forEach(node, (anak) => {
    if (!isValidElement(anak)) return;
    hasil.push(anak);
    kumpulkan((anak.props as any).children, hasil);
  });
  return hasil;
}

function daftarSeri(grafik: any): Seri[] {
  if (!grafik) return [];
  const elemen = kumpulkan(grafik.props.children);
  const xKey = elemen.find((e) => namaKomponen(e.type) === "XAxis")?.props.dataKey;
  const yAxis = elemen.find((e) => namaKomponen(e.type) === "YAxis")?.props;
  const daftar: Seri[] = [];
  let scatterIndex = 0;
  for (const e of elemen) {
    const nama = namaKomponen(e.type);
    if (!["Bar", "Line", "Area", "Scatter"].includes(nama)) continue;
    const p = e.props as any;
    const nilaiKey = p.dataKey ?? (nama === "Scatter" ? yAxis?.dataKey : undefined);
    if (nilaiKey === undefined || nilaiKey === null) continue;
    const namaSeri = String(p.name ?? nilaiKey);
    const kunci = nama === "Scatter" ? `${namaSeri}-${scatterIndex++}` : String(nilaiKey);
    daftar.push({
      kunci, nilaiKey: String(nilaiKey), nama: namaSeri, komponen: e.type,
      sumbu: p.yAxisId ?? yAxis?.yAxisId,
      data: Array.isArray(p.data) ? p.data : undefined,
      kunciX: xKey === undefined ? undefined : String(xKey),
      warnaAsli: String(p.stroke ?? p.fill ?? (Children.toArray(p.children).find((c: any) => isValidElement(c) && c.type === Cell) as any)?.props?.fill ?? "#1D2434"),
    });
  }
  return daftar;
}

function dataGrafik(grafik: any, seri?: Seri): any[] {
  if (seri?.data) return seri.data;
  return Array.isArray(grafik?.props?.data) ? grafik.props.data : [];
}

function statistik(data: any[], kunci: string) {
  const nilai = data.map((d) => d?.[kunci])
    .filter((v) => v !== null && v !== undefined && v !== "")
    .map(Number).filter(Number.isFinite);
  if (!nilai.length) return { rata: null, min: null, maks: null };
  return {
    rata: nilai.reduce((a, b) => a + b, 0) / nilai.length,
    min: Math.min(...nilai), maks: Math.max(...nilai),
  };
}

function turunkanNode(node: ReactNode, s: Setelan, grafik: any, seriList: Seri[]): ReactNode {
  if (Array.isArray(node)) return node.map((n) => turunkanNode(n, s, grafik, seriList));
  if (!isValidElement(node)) return node;
  const tipe: any = node.type;
  if (!s.kisi && tipe === CartesianGrid) return null;
  if (!s.legenda && tipe === Legend) return null;
  if ((tipe === Line || tipe === Bar || tipe === Area || tipe === Scatter)) {
    const p = node.props as any;
    const info = seriList.find((x) => x.komponen === tipe && (tipe === Scatter
      ? x.nama === String(p.name ?? x.nama) && x.data === p.data
      : x.nilaiKey === String(p.dataKey)));
    const kunci = info?.kunci ?? String(p.dataKey ?? "");
    if (s.seriTersembunyi.includes(kunci)) return null;
    let jenisBaru: any = tipe;
    if (s.bentuk !== "asli" && tipe !== Scatter) {
      jenisBaru = s.bentuk === "garis" ? Line : s.bentuk === "batang" ? Bar : Area;
    }
    const index = Math.max(0, seriList.findIndex((x) => x.kunci === kunci));
    const warna = s.warnaSeri[kunci] ?? paletWarna[s.palet]?.[index % (paletWarna[s.palet]?.length || 1)];
    const props: any = { ...p };
    if (warna) { props.stroke = warna; props.fill = warna; }
    if (tipe === Scatter && s.bentuk.startsWith("titik-")) {
      props.shape = ({ "titik-bulat": "circle", "titik-kotak": "square", "titik-wajik": "diamond", "titik-segitiga": "triangle" } as Record<string, string>)[s.bentuk];
    }
    if (jenisBaru === Line) {
      delete props.stackId; delete props.maxBarSize; delete props.barSize; delete props.minPointSize;
      props.dot = p.dot ?? false;
    } else if (jenisBaru === Bar) {
      delete props.dot; delete props.activeDot; delete props.connectNulls;
    } else if (jenisBaru === Area) {
      delete props.maxBarSize; delete props.barSize; delete props.minPointSize;
      props.fillOpacity = p.fillOpacity ?? 0.25;
    }
    const anak = Children.map(p.children, (c) => {
      if (isValidElement(c) && c.type === Cell) {
        if (warna) return cloneElement(c as any, { fill: warna, stroke: warna });
        if (jenisBaru !== Bar) return null;
      }
      return turunkanNode(c, s, grafik, seriList);
    });
    const memilikiLabel = Children.toArray(p.children).some((c: any) => isValidElement(c) && c.type === LabelList);
    const tambahan = s.label && !memilikiLabel && jenisBaru !== Scatter
      ? <LabelList dataKey={p.dataKey} position="top" fontSize={10} /> : null;
    return createElement(jenisBaru, { ...props, key: (node as any).key }, ...(Children.toArray(anak)), tambahan);
  }
  if (jenisGrafik.includes(tipe)) {
    const anak = Children.map((node.props as any).children, (c) => turunkanNode(c, s, grafik, seriList));
    const garisAnotasi: ReactNode[] = [];
    for (const a of s.anotasi) {
      const seri = seriList.find((x) => x.kunci === a.seri);
      if (!seri) continue;
      if (a.jenis === "catatan") {
        const rows = dataGrafik(grafik, seri);
        const xKey = seri.kunciX ?? kumpulkan(node.props.children).find((e: any) => namaKomponen(e.type) === "XAxis")?.props.dataKey;
        const row = rows.find((r: any) => String(r?.[xKey]) === String(a.periode));
        const y = Number(row?.[seri.nilaiKey]);
        if (row && Number.isFinite(y)) garisAnotasi.push(
          <ReferenceDot key={a.id} x={row[xKey]} y={y} r={5} fill="#FF1313" stroke="#fff"
            label={{ value: a.teks || "Catatan", position: "top", fontSize: 10, fill: "#1D2434" }} />,
        );
      } else {
        const rows = dataGrafik(grafik, seri);
        const stat = statistik(rows, seri.nilaiKey);
        const y = a.jenis === "target" ? a.nilai
          : a.jenis === "rata-rata" ? stat.rata
          : a.jenis === "minimum" ? stat.min : stat.maks;
        if (y !== null && y !== undefined && Number.isFinite(Number(y))) {
          const label = a.jenis === "target" ? (a.teks || "Target")
            : `${a.jenis}: ${a.teks || seri.nama}`;
          garisAnotasi.push(<ReferenceLine key={a.id} y={Number(y)} yAxisId={seri.sumbu}
            stroke={a.jenis === "target" ? "#FF1313" : "#0F766E"} strokeDasharray="5 4"
            label={{ value: label, position: "insideTopRight", fontSize: 10 }} />);
        }
      }
    }
    const tipeBaru = s.bentuk === "asli" || tipe === ComposedChart || tipe === ScatterChart ? tipe
      : s.bentuk === "garis" ? LineChart : s.bentuk === "batang" ? BarChart : AreaChart;
    return createElement(tipeBaru, { ...node.props, key: (node as any).key },
      ...Children.toArray(anak), ...garisAnotasi);
  }
  const anakBaru = Children.map((node.props as any).children, (c) => turunkanNode(c, s, grafik, seriList));
  return cloneElement(node as any, { ...node.props, key: (node as any).key }, anakBaru);
}

export function AlatGrafik({ id, children }: { id: string; children: ReactNode }) {
  const { pengguna } = useContext(KonteksPenggunaGrafik);
  const kunci = `rubber-intelligence:chart:${encodeURIComponent(pengguna)}:${id}`;
  const [s, setS] = useState<Setelan>(() => bacaSetelan(kunci));
  const [jenis, setJenis] = useState<JenisAnotasi>("target");
  const [seriTerpilih, setSeriTerpilih] = useState("");
  const [nilai, setNilai] = useState("");
  const [periode, setPeriode] = useState("");
  const [teks, setTeks] = useState("");
  const grafik = useMemo(() => cariGrafik(children), [children]);
  const isScatter = grafik?.type === ScatterChart;
  const seri = useMemo(() => daftarSeri(grafik), [grafik]);
  const seriAktif = seri.find((x) => x.kunci === seriTerpilih) ?? seri[0];
  const rows = dataGrafik(grafik, seriAktif);
  const xKey = (seriAktif as any)?.kunciX ?? kumpulkan(grafik?.props?.children).find((e: any) => namaKomponen(e.type) === "XAxis")?.props.dataKey;
  const periodeTersedia = [...new Set(rows.map((r: any, i) => r?.[xKey] ?? i).filter((v) => v !== undefined && v !== null))];

  useEffect(() => setS(bacaSetelan(kunci)), [kunci]);
  useEffect(() => {
    try { localStorage.setItem(kunci, JSON.stringify(s)); } catch { /* penyimpanan browser dapat dinonaktifkan */ }
  }, [kunci, s]);
  useEffect(() => {
    if (!seri.some((x) => x.kunci === seriTerpilih) && seri.length) setSeriTerpilih(seri[0].kunci);
  }, [seri, seriTerpilih]);

  const ubah = (perubahan: Partial<Setelan>) => setS((lama) => ({ ...lama, ...perubahan }));
  const tambahAnotasi = () => {
    if (!seriAktif) return;
    const a: Anotasi = { id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      jenis, seri: seriAktif.kunci, teks: teks.trim() };
    if (jenis === "target") {
      const angka = Number(nilai.replace(",", "."));
      if (!nilai.trim() || !Number.isFinite(angka)) return;
      a.nilai = angka;
    }
    if (jenis === "catatan") {
      if (periode === "" || !teks.trim()) return;
      a.periode = periode;
    }
    ubah({ anotasi: [...s.anotasi, a] });
    setNilai(""); setTeks("");
  };
  const labelJenis: Record<JenisAnotasi, string> = {
    target: "Target", "rata-rata": "Rata-rata", minimum: "Minimum", maksimum: "Maksimum", catatan: "Catatan titik/periode",
  };
  const hasil = turunkanNode(children, s, grafik, seri);

  return <div className="relative h-full w-full min-w-0" data-grafik={id}>
    <details className="absolute right-1 top-1 z-20 text-left">
      <summary className="cursor-pointer list-none rounded border border-[#D5D7DB] bg-white/95 px-2.5 py-1.5 text-[11px] font-semibold text-[#1D2434] shadow-sm hover:border-[#FF1313]">
        ⚙ Sesuaikan grafik
      </summary>
      <div className="absolute right-0 mt-1 max-h-[70vh] w-[min(22rem,calc(100vw-2rem))] overflow-y-auto rounded border border-[#D5D7DB] bg-white p-3 shadow-xl">
        <div className="mb-2 flex items-center justify-between">
          <b className="text-xs text-[#1D2434]">Tampilan grafik</b>
          <button type="button" className="text-[11px] text-[#FF1313] underline" onClick={() => setS(bawaan)}>Atur ulang</button>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label className={kelasLabel}>Bentuk
            <select className={`${kelasKontrol} mt-1 w-full`} value={isScatter && s.bentuk !== "asli" && !s.bentuk.startsWith("titik-") ? "asli" : s.bentuk} onChange={(e) => ubah({ bentuk: e.target.value as Bentuk })}>
              {isScatter ? <>
                <option value="asli">Bentuk asli</option><option value="titik-bulat">Titik bulat</option>
                <option value="titik-kotak">Titik kotak</option><option value="titik-wajik">Titik wajik</option>
                <option value="titik-segitiga">Titik segitiga</option>
              </> : <>
                <option value="asli">Asli</option><option value="garis">Garis</option>
                <option value="batang">Batang</option><option value="area">Area</option>
              </>}
            </select>
          </label>
          <label className={kelasLabel}>Warna seri
            <select className={`${kelasKontrol} mt-1 w-full`} value={s.palet} onChange={(e) => ubah({ palet: e.target.value })}>
              <option value="asli">Warna asli</option><option value="biru">Biru & teal</option><option value="kontras">Kontras tinggi</option>
            </select>
          </label>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-[#1D2434]">
          <label className="flex items-center gap-1"><input type="checkbox" checked={s.kisi} onChange={(e) => ubah({ kisi: e.target.checked })} /> Kisi</label>
          <label className="flex items-center gap-1"><input type="checkbox" checked={s.legenda} onChange={(e) => ubah({ legenda: e.target.checked })} /> Legenda</label>
          <label className="flex items-center gap-1"><input type="checkbox" checked={s.label} onChange={(e) => ubah({ label: e.target.checked })} /> Label angka</label>
        </div>
        {seri.length > 0 && <div className="mt-3 border-t border-[#EDEFF2] pt-2">
          <div className="mb-1 text-[11px] font-semibold text-[#1D2434]">Seri yang ditampilkan</div>
          <div className="max-h-20 space-y-1 overflow-y-auto">
            {seri.map((x, i) => <div key={x.kunci} className="flex items-center justify-between gap-2 text-[11px] text-[#1D2434]">
              <label className="flex min-w-0 items-center gap-1.5">
                <input type="checkbox" checked={!s.seriTersembunyi.includes(x.kunci)} onChange={(e) => ubah({ seriTersembunyi: e.target.checked ? s.seriTersembunyi.filter((k) => k !== x.kunci) : [...s.seriTersembunyi, x.kunci] })} />
                <span className="truncate">{x.nama}</span>
              </label>
              <input type="color" aria-label={`Pilih warna ${x.nama}`} title={`Pilih warna ${x.nama}`}
                className="h-6 w-8 shrink-0 cursor-pointer rounded border border-[#D5D7DB] bg-white p-0.5"
                value={s.warnaSeri[x.kunci] ?? paletWarna[s.palet]?.[i % (paletWarna[s.palet]?.length || 1)] ?? x.warnaAsli ?? "#1D2434"}
                onChange={(e) => ubah({ warnaSeri: { ...s.warnaSeri, [x.kunci]: e.target.value } })} />
            </div>)}
          </div>
        </div>}
        {seri.length > 0 && <div className="mt-3 border-t border-[#EDEFF2] pt-2">
          <div className="mb-1 text-[11px] font-semibold text-[#1D2434]">Penanda & catatan</div>
          <div className="grid grid-cols-2 gap-2">
            <label className={kelasLabel}>Jenis
              <select className={`${kelasKontrol} mt-1 w-full`} value={jenis} onChange={(e) => setJenis(e.target.value as JenisAnotasi)}>
                {Object.entries(labelJenis).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className={kelasLabel}>Seri / ukuran
              <select className={`${kelasKontrol} mt-1 w-full`} value={seriAktif?.kunci ?? ""} onChange={(e) => setSeriTerpilih(e.target.value)}>
                {seri.map((x) => <option key={x.kunci} value={x.kunci}>{x.nama}</option>)}
              </select>
            </label>
          </div>
          {jenis === "target" && <label className={`${kelasLabel} mt-2`}>Nilai target
            <input className={`${kelasKontrol} mt-1 w-full`} inputMode="decimal" value={nilai} onChange={(e) => setNilai(e.target.value)} placeholder="Contoh: 125.5" />
          </label>}
          {jenis === "catatan" && <label className={`${kelasLabel} mt-2`}>Titik / periode
            <select className={`${kelasKontrol} mt-1 w-full`} value={periode} onChange={(e) => setPeriode(e.target.value)}>
              <option value="">Pilih titik</option>{periodeTersedia.map((x, i) => <option key={`${i}-${x}`} value={String(x)}>{String(x)}</option>)}
            </select>
          </label>}
          {(jenis === "catatan" || jenis === "target") && <label className={`${kelasLabel} mt-2`}>{jenis === "catatan" ? "Catatan" : "Label target (opsional)"}
            <input className={`${kelasKontrol} mt-1 w-full`} value={teks} onChange={(e) => setTeks(e.target.value)} placeholder={jenis === "catatan" ? "Tulis catatan…" : "Target"} />
          </label>}
          <button type="button" className="mt-2 w-full rounded bg-[#1D2434] px-2 py-1.5 text-xs font-semibold text-white hover:bg-[#30394C]" onClick={tambahAnotasi}>
            Tambahkan {labelJenis[jenis].toLowerCase()}
          </button>
          {s.anotasi.length > 0 && <ul className="mt-2 space-y-1">
            {s.anotasi.map((a) => <li key={a.id} className="flex items-start justify-between gap-2 rounded bg-[#F8F8F8] px-2 py-1 text-[10px] text-[#1D2434]">
              <span>{labelJenis[a.jenis]} · {seri.find((x) => x.kunci === a.seri)?.nama ?? a.seri}{a.jenis === "target" ? ` · ${a.nilai}` : a.jenis === "catatan" ? ` · ${String(a.periode)}: ${a.teks}` : ""}</span>
              <button type="button" className="shrink-0 text-[#B91C1C]" aria-label="Hapus penanda" onClick={() => ubah({ anotasi: s.anotasi.filter((x) => x.id !== a.id) })}>Hapus</button>
            </li>)}
          </ul>}
        </div>}
        <p className="mt-2 text-[10px] leading-snug text-[#64676C]">Pengaturan hanya mengubah tampilan dan tersimpan di browser untuk pengguna ini. Data dan agregasi tidak berubah. Pada grafik sebar, bentuk titik dapat diubah; jenis grafik tetap sebar.</p>
      </div>
    </details>
    {hasil}
  </div>;
}
