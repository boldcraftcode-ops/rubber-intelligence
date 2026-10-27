import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Ringkasan from "./pages/Ringkasan";
import Analisis from "./pages/Analisis";
import Stok from "./pages/Stok";
import StokMargin from "./pages/StokMargin";
import AturanHarga from "./pages/AturanHarga";
import Simulasi from "./pages/Simulasi";
import Perencanaan from "./pages/Perencanaan";
import AlarmPage from "./pages/AlarmPage";
import Rekonsiliasi from "./pages/Rekonsiliasi";
import Kualitas from "./pages/Kualitas";
import InputHarian from "./pages/InputHarian";
import UnggahData from "./pages/UnggahData";
import GradeHarga from "./pages/GradeHarga";
import MasterVendor from "./pages/MasterVendor";
import Database from "./pages/Database";
import Pengguna from "./pages/Pengguna";
import Login, { LayarApiLama, LayarGalat } from "./pages/Login";
import { VERSI_UI } from "./versi";
import { ambilJson, kirimJson, pesanGalat, kelasInput, kelasLabel, kelasTombol, kelasTombolKecil, simpanToken } from "./bersama";
import { useBahasa } from "./i18n";

/* Menu samping = pohon dua tingkat (grup -> halaman). Urutan grup dan
   anggotanya mengikuti struktur yang diminta pemilik:
   Analytics · Pricing & Planning · Monitoring & Control · Master Data ·
   Data Entry · Administration. `grup` di item = id grup di GRUP. */
const GRUP = [
  { id: "analitik", label: "Analitik", ikon: "📊" },
  { id: "harga", label: "Harga & Perencanaan", ikon: "💰" },
  { id: "pantau", label: "Pengawasan & Kontrol", ikon: "🛡️" },
  { id: "master", label: "Master Data", ikon: "🗂️" },
  { id: "input", label: "Input Data", ikon: "📥" },
  { id: "sistem", label: "Administrasi", ikon: "⚙️", hanyaAdmin: true },
] as const;

const TAB = [
  { id: "ringkasan", label: "Margin Performance", ikon: "◧", grup: "analitik" },
  { id: "analisis", label: "Intake Analisis", ikon: "◨", grup: "analitik" },
  { id: "stok", label: "Stok", ikon: "▤", grup: "analitik" },
  { id: "stokmargin", label: "Stok vs Margin", ikon: "▥", grup: "analitik" },
  { id: "aturan", label: "Aturan Harga", ikon: "▦", grup: "harga" },
  { id: "simulasi", label: "Simulasi", ikon: "▧", grup: "harga" },
  { id: "rencana", label: "Perencanaan", ikon: "▩", grup: "harga" },
  { id: "alarm", label: "Alarm", ikon: "▲", grup: "pantau" },
  { id: "rekonsiliasi", label: "Rekonsiliasi", ikon: "≡", grup: "pantau" },
  { id: "kualitas", label: "Kualitas Data", ikon: "◆", grup: "pantau" },
  { id: "vendor", label: "Master Vendor", ikon: "◈", grup: "master" },
  { id: "gradeharga", label: "Grade & Harga", ikon: "◇", grup: "master" },
  { id: "input", label: "Input Harian", ikon: "✎", grup: "input" },
  { id: "unggah", label: "Unggah Data", ikon: "↑", grup: "input" },
  { id: "database", label: "Database", ikon: "▣", grup: "sistem", hanyaAdmin: true },
  { id: "pengguna", label: "Pengguna", ikon: "●", grup: "sistem", hanyaAdmin: true },
] as const;

type TabId = (typeof TAB)[number]["id"];

/* ---------- modal ganti sandi ---------- */
function ModalGantiSandi({ tutup }: { tutup: () => void }) {
  const [lama, setLama] = useState("");
  const [baru, setBaru] = useState("");
  const [ulang, setUlang] = useState("");
  const [pesan, setPesan] = useState<{ ok: boolean; teks: string } | null>(null);

  const kirim = useMutation({
    mutationFn: () => kirimJson("/api/auth/ganti-sandi",
      { sandi_lama: lama, sandi_baru: baru }),
    onSuccess: (j) => setPesan({ ok: true, teks: j.pesan }),
    onError: (e: Error) => setPesan({ ok: false, teks: e.message }),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
         onClick={tutup}>
      <div className="w-full max-w-sm rounded-sm bg-white border border-[#E4E5E8] p-6 shadow-2xl"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-[#1D2434] mb-3">Ganti sandi</h3>
        <label className={kelasLabel}>Sandi lama</label>
        <input className={kelasInput} type="password" value={lama}
               onChange={(e) => setLama(e.target.value)} />
        <label className={`${kelasLabel} mt-3`}>Sandi baru (min. 8 karakter)</label>
        <input className={kelasInput} type="password" value={baru}
               onChange={(e) => setBaru(e.target.value)} />
        <label className={`${kelasLabel} mt-3`}>Ulangi sandi baru</label>
        <input className={kelasInput} type="password" value={ulang}
               onChange={(e) => setUlang(e.target.value)} />
        {baru && ulang && baru !== ulang && (
          <p className="mt-2 text-xs text-[#B45309]">Sandi baru tidak sama.</p>
        )}
        {pesan && (
          <p className={`mt-3 rounded-sm px-3 py-2 text-sm border ${pesan.ok
            ? "bg-[#F0FDF4] text-[#15803D] border-[#BBF7D0]"
            : "bg-[#FEF2F2] text-[#B91C1C] border-[#FECACA]"}`}>{pesan.teks}</p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button className={kelasTombolKecil} onClick={tutup}>Tutup</button>
          <button className={kelasTombol}
                  disabled={!lama || baru.length < 8 || baru !== ulang || kirim.isPending}
                  onClick={() => kirim.mutate()}>
            {kirim.isPending ? "Menyimpan…" : "Simpan"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const { lang, setLang, t } = useBahasa();
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabId>("ringkasan");
  const [bukaSandi, setBukaSandi] = useState(false);
  /* Grup menu yang sedang terbuka. Bawaannya SEMUA terbuka supaya tidak ada
     menu yang "hilang" pada pemakaian pertama; pilihan pengguna diingat. */
  const [grupTerbuka, setGrupTerbuka] = useState<Record<string, boolean>>(() => {
    try {
      const mentah = localStorage.getItem("ri.menu.grup");
      return mentah ? (JSON.parse(mentah) as Record<string, boolean>) : {};
    } catch {
      return {};        // mode privat / localStorage diblokir
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem("ri.menu.grup", JSON.stringify(grupTerbuka));
    } catch { /* diabaikan: hanya kenyamanan tampilan */ }
  }, [grupTerbuka]);
  /* Pindah halaman (termasuk lewat tombol di Margin Performance) membuka
     grup tempat halaman itu berada, supaya menu tidak terlihat "kosong". */
  useEffect(() => {
    const g = TAB.find((tb) => tb.id === tab)?.grup;
    if (g) setGrupTerbuka((st) => (st[g] === false ? { ...st, [g]: true } : st));
  }, [tab]);

  /* ---- cara login yang berlaku di proses API ini ----
     Dipakai untuk membedakan "belum login" (tampilkan form) dari
     "login dimatikan / API bermasalah" (tampilkan penjelasan). */
  /* ---- versi API yang menjawab (publik, tanpa login) ---- */
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => ambilJson("/api/health"),
    retry: false,
    staleTime: 60_000,
  });

  const caraLogin = useQuery({
    queryKey: ["cara-login"],
    queryFn: () => ambilJson("/api/auth/mode"),
    retry: false,
    staleTime: 5 * 60_000,
  });

  /* ---- sesi login ---- */
  const saya = useQuery({
    queryKey: ["saya"],
    queryFn: () => ambilJson("/api/auth/saya"),
    retry: false,
    staleTime: 5 * 60_000,
  });
  const admin = saya.data?.peran === "admin";
  const modeLokal = saya.data?.mode === "lokal";
  /* Login sedang DIMATIKAN (AUTH_DISABLED=true) — dipakai sementara saat
     pemecahan masalah. Penanda di layar supaya tidak lupa dinyalakan lagi. */
  const tanpaLogin = saya.data?.mode === "nonaktif";

  // nama pengisi otomatis mengikuti akun login
  useEffect(() => {
    if (saya.data?.nama) localStorage.setItem("op-margin.pengisi", saya.data.nama);
  }, [saya.data?.nama]);

  const keluar = useMutation({
    mutationFn: () => kirimJson("/api/auth/logout", {}),
    onSettled: () => {
      simpanToken(null);      // buang token cadangan juga, jangan sampai tertinggal
      qc.resetQueries();
    },
  });

  const alarm = useQuery({
    queryKey: ["alarm"],
    queryFn: () => ambilJson("/api/alarm"),
    refetchInterval: 60_000,
    enabled: !!saya.data,
  });
  const jumlahAlarm = alarm.data?.alarm.length ?? 0;

  /* ---- gerbang: belum login -> form login ---- */
  if (saya.isLoading) {
    return (
      <div className="galaxy min-h-screen flex items-center justify-center text-[#64676C]">
        <p className="text-sm animate-pulse tracking-wide">Memuat…</p>
      </div>
    );
  }
  if (saya.error) {
    const detail = pesanGalat(saya.error);
    const versiApi: string | undefined = health.data?.versi;
    // API yang menjawab bukan kode di folder ini -> jelaskan, jangan tampilkan
    // form yang pasti gagal (kode lama bisa menjawab "Cloudflare Access").
    if (versiApi !== undefined && versiApi !== VERSI_UI) {
      return <LayarApiLama versiApi={versiApi} versiUi={VERSI_UI} detail={detail}
                           folder={health.data?.folder} pid={health.data?.pid} />;
    }
    if (versiApi === undefined && /cloudflare access/i.test(detail)) {
      return <LayarApiLama versiUi={VERSI_UI} detail={detail} />;
    }
    // Login dimatikan di API (mode pengembangan) -> penjelasan, bukan form.
    if (caraLogin.data?.cara === "tanpa-login") {
      return <LayarGalat detail={detail} ulangi={() => qc.invalidateQueries()} />;
    }
    return <Login onSukses={() => qc.invalidateQueries({ queryKey: ["saya"] })} />;
  }

  const tabTampil = TAB.filter((tb: any) => !tb.hanyaAdmin || admin);

  return (
    <div className="galaxy min-h-screen flex text-[#1D2434]">
      {/* ===== Menu samping kiri (atas ke bawah) ===== */}
      <aside className="w-60 shrink-0 sticky top-0 h-screen overflow-y-auto
                        bg-white border-r border-[#E4E5E8] flex flex-col">
        <div className="bg-[#1D2434] px-5 pt-6 pb-5 text-white relative">
          <span className="absolute left-0 top-0 h-full w-[3px] bg-[#FF1313]" />
          <span aria-hidden className="pola-titik pointer-events-none absolute right-4 top-4
                                       h-10 w-14 opacity-60" />
          <div className="flex items-center gap-3">
            <img src="/logo-rubber-intelligence.svg" alt=""
                 className="h-10 w-10 bg-white rounded-sm p-1" />
            <div>
              <h1 className="text-[15px] font-bold leading-tight tracking-tight">
                Rubber<br />Intelligence
              </h1>
              <p className="mt-1 text-[10px] uppercase tracking-[0.14em] text-white/50">
                Raw Material Big Data
              </p>
            </div>
          </div>
          <div className="mt-4 inline-flex rounded-sm border border-white/20 overflow-hidden">
            {([["id", "ID"], ["en", "EN"]] as const).map(([kode, label]) => (
              <button key={kode}
                className={`px-3 py-1 text-[11px] font-semibold transition-colors ${lang === kode
                  ? "bg-[#FF1313] text-white"
                  : "bg-transparent text-white/60 hover:bg-white/10"}`}
                onClick={() => setLang(kode)}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <nav className="flex-1 px-3 pt-1 pb-3 flex flex-col gap-0.5" aria-label={t("Menu utama")}>
          {GRUP.filter((g: any) => !g.hanyaAdmin || admin).map((g: any) => {
            const anak = tabTampil.filter((tb: any) => tb.grup === g.id);
            if (!anak.length) return null;
            const buka = grupTerbuka[g.id] !== false;
            const adaAktif = anak.some((tb: any) => tb.id === tab);
            return (
              <div key={g.id} className="mt-1 first:mt-0">
                <button
                  type="button"
                  className={`w-full flex items-center gap-2 rounded-sm px-2.5 py-1.5 text-left
                              transition-colors ${
                    adaAktif
                      ? "text-[#1D2434]"
                      : "text-[#64676C] hover:text-[#1D2434]"
                  } hover:bg-[#F8F8F8]`}
                  onClick={() => setGrupTerbuka((st) => ({ ...st, [g.id]: !buka }))}
                  aria-expanded={buka}
                  aria-controls={`menu-grup-${g.id}`}
                  title={buka ? t("Tutup grup") : t("Buka grup")}
                >
                  <span aria-hidden className="text-[12px] leading-none">{g.ikon}</span>
                  <span className="flex-1 truncate text-[11px] font-semibold uppercase tracking-[0.1em]">
                    {t(g.label)}
                  </span>
                  <span aria-hidden
                        className={`text-[9px] text-[#9AA0A6] transition-transform ${buka ? "rotate-90" : ""}`}>
                    ▶
                  </span>
                </button>
                {buka && (
                  <div id={`menu-grup-${g.id}`} className="mt-0.5 flex flex-col gap-0.5">
                    {anak.map((tb: any) => (
                      <button
                        key={tb.id}
                        type="button"
                        aria-current={tab === tb.id ? "page" : undefined}
                        className={`w-full flex items-center justify-between rounded-sm pl-6 pr-2.5 py-1.5
                                    text-sm text-left border-l-2 transition-colors ${
                          tab === tb.id
                            ? "bg-[#F8F8F8] border-l-[#FF1313] text-[#1D2434] font-semibold"
                            : "border-l-transparent text-[#64676C] hover:bg-[#F8F8F8] hover:text-[#1D2434]"
                        }`}
                        onClick={() => setTab(tb.id)}
                      >
                        <span className="truncate">
                          <span className={`mr-2 text-[11px] ${tab === tb.id ? "text-[#FF1313]" : "text-[#9AA0A6]"}`}>
                            {tb.ikon}
                          </span>
                          {t(tb.label)}
                        </span>
                        {tb.id === "alarm" && jumlahAlarm > 0 && (
                          <span className="rounded-sm bg-[#FF1313] text-white text-[10px] font-semibold px-1.5 py-0.5">
                            {jumlahAlarm}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* ===== info akun ===== */}
        <div className="px-5 py-4 border-t border-[#E4E5E8] bg-[#F8F8F8]">
          <p className="text-sm font-semibold text-[#1D2434] truncate">
            {saya.data?.nama}
          </p>
          <p className="text-[11px] text-[#64676C] mb-2.5">
            {saya.data?.username} · {saya.data?.peran}
          </p>
          {modeLokal && (
            <div className="flex gap-1.5">
              <button className={kelasTombolKecil} onClick={() => setBukaSandi(true)}>
                {t("Ganti sandi")}
              </button>
              <button className={kelasTombolKecil} onClick={() => keluar.mutate()}>
                {t("Keluar")}
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ===== Isi halaman ===== */}
      <main className="flex-1 min-w-0 px-8 py-7">
        <div className="mx-auto max-w-[1200px]">
          {tanpaLogin && (
            <div className="mb-5 rounded-sm border border-[#FDE68A] bg-[#FFFBEB]
                            border-l-2 border-l-[#FF1313] px-4 py-2.5">
              <p className="text-sm font-semibold text-[#B45309]">
                MODE TANPA LOGIN (SEMENTARA)
              </p>
              <p className="mt-0.5 text-xs leading-snug text-[#64676C]">
                Login dimatikan lewat <code>AUTH_DISABLED=true</code>. Semua
                orang bisa membuka aplikasi ini tanpa sandi. Nyalakan kembali
                login sebelum dipakai bersama atau dipasang di internet.
              </p>
            </div>
          )}
          {/* ===== kepala halaman ===== */}
          <header className="mb-6 border-b border-[#E4E5E8] pb-4">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#FF1313]">
                  Rubber Intelligence
                </p>
                <h1 className="mt-1 text-2xl font-bold text-[#1D2434]">
                  {t(TAB.find((tb) => tb.id === tab)?.label ?? "")}
                </h1>
              </div>
              <p className="text-[11px] text-[#9AA0A6] pb-1">
                Rubber Raw Material Big Data
              </p>
            </div>
          </header>

          {tab === "ringkasan" && <Ringkasan ke={(x) => setTab(x as TabId)} />}
          {tab === "analisis" && <Analisis />}
          {tab === "stok" && <Stok />}
          {tab === "stokmargin" && <StokMargin />}
          {tab === "aturan" && <AturanHarga />}
          {tab === "simulasi" && <Simulasi />}
          {tab === "rencana" && <Perencanaan />}
          {tab === "alarm" && (
            <AlarmPage ke={(x) => setTab(
              // id dari API divalidasi: menu yang tidak dikenal diabaikan,
              // supaya layar tidak pernah kosong karena tautan alarm.
              (TAB.some((tb: any) => tb.id === x) ? x : "alarm") as TabId)} />
          )}
          {tab === "rekonsiliasi" && <Rekonsiliasi />}
          {tab === "kualitas" && <Kualitas />}
          {tab === "vendor" && <MasterVendor />}
          {tab === "gradeharga" && <GradeHarga />}
          {tab === "unggah" && <UnggahData />}
          {tab === "input" && <InputHarian pengisi={saya.data?.nama ?? "?"} />}
          {tab === "database" && admin && <Database />}
          {tab === "pengguna" && admin && <Pengguna saya={saya.data?.username} />}
        </div>
      </main>

      {bukaSandi && <ModalGantiSandi tutup={() => setBukaSandi(false)} />}
    </div>
  );
}
