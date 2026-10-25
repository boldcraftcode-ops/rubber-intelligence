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
import Database from "./pages/Database";
import Pengguna from "./pages/Pengguna";
import Login, { LayarApiLama, LayarGalat } from "./pages/Login";
import { VERSI_UI } from "./versi";
import { ambilJson, kirimJson, pesanGalat, kelasInput, kelasLabel,
         kelasTombol, kelasTombolKecil } from "./bersama";
import { useBahasa } from "./i18n";

const TAB = [
  { id: "ringkasan", label: "Ringkasan", ikon: "✦" },
  { id: "analisis", label: "Analisis", ikon: "✧" },
  { id: "stok", label: "Stok", ikon: "☄" },
  { id: "stokmargin", label: "Stok vs Margin", ikon: "✶" },
  { id: "aturan", label: "Aturan Harga", ikon: "✹" },
  { id: "simulasi", label: "Simulasi", ikon: "✺" },
  { id: "rencana", label: "Perencanaan", ikon: "✵" },
  { id: "alarm", label: "Alarm", ikon: "✴" },
  { id: "rekonsiliasi", label: "Rekonsiliasi", ikon: "✷" },
  { id: "kualitas", label: "Kualitas Data", ikon: "✳" },
  { id: "gradeharga", label: "Grade & Harga", ikon: "◈" },
  { id: "unggah", label: "Unggah Data", ikon: "⬆" },
  { id: "input", label: "Input Harian", ikon: "✎" },
  { id: "database", label: "Database", ikon: "⛁", hanyaAdmin: true },
  { id: "pengguna", label: "Pengguna", ikon: "☺", hanyaAdmin: true },
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
      <div className="w-full max-w-sm rounded-xl bg-[#1a1844] border border-violet-500/30 p-6 shadow-2xl"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-slate-100 mb-3">Ganti sandi</h3>
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
          <p className="mt-2 text-xs text-amber-300">Sandi baru tidak sama.</p>
        )}
        {pesan && (
          <p className={`mt-3 rounded-md px-3 py-2 text-sm border ${pesan.ok
            ? "bg-emerald-500/10 text-emerald-300 border-emerald-400/30"
            : "bg-red-500/10 text-red-300 border-red-400/30"}`}>{pesan.teks}</p>
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

  // nama pengisi otomatis mengikuti akun login
  useEffect(() => {
    if (saya.data?.nama) localStorage.setItem("op-margin.pengisi", saya.data.nama);
  }, [saya.data?.nama]);

  const keluar = useMutation({
    mutationFn: () => kirimJson("/api/auth/logout", {}),
    onSettled: () => qc.resetQueries(),
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
      <div className="galaxy min-h-screen flex items-center justify-center text-slate-300">
        <p className="text-sm animate-pulse">🪐 Memuat…</p>
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
    <div className="galaxy min-h-screen flex text-slate-200">
      {/* ===== Menu samping kiri (atas ke bawah) ===== */}
      <aside className="w-56 shrink-0 sticky top-0 h-screen overflow-y-auto
                        bg-[#0b0a26]/80 backdrop-blur border-r border-violet-500/20
                        flex flex-col">
        <div className="px-5 pt-6 pb-4">
          <h1 className="text-xl font-bold text-white tracking-wide">
            <span className="mr-2">🪐</span>Rubber Intelligence
          </h1>
          <p className="mt-1 text-xs leading-snug text-indigo-300/80">
            Rubber Raw Material Big Data
          </p>
          <div className="mt-3 inline-flex rounded-lg border border-violet-500/30 overflow-hidden">
            {([["id", "ID"], ["en", "EN"]] as const).map(([kode, label]) => (
              <button key={kode}
                className={`px-3 py-1 text-xs font-semibold ${lang === kode
                  ? "bg-violet-600 text-white"
                  : "bg-transparent text-slate-400 hover:bg-white/10"}`}
                onClick={() => setLang(kode)}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <nav className="flex-1 px-3 flex flex-col gap-1">
          {tabTampil.map((tb) => (
            <button
              key={tb.id}
              className={`w-full flex items-center justify-between rounded-lg px-3 py-2
                          text-sm text-left transition-colors ${
                tab === tb.id
                  ? "bg-violet-600/30 text-white border border-violet-400/40 shadow-lg shadow-violet-950/40"
                  : "text-slate-300 hover:bg-white/10 border border-transparent"
              }`}
              onClick={() => setTab(tb.id)}
            >
              <span>
                <span className="mr-2 text-violet-300/90">{tb.ikon}</span>
                {t(tb.label)}
              </span>
              {tb.id === "alarm" && jumlahAlarm > 0 && (
                <span className="rounded-full bg-red-600 text-white text-xs px-1.5 py-0.5 shadow">
                  {jumlahAlarm}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* ===== info akun ===== */}
        <div className="px-5 py-4 border-t border-violet-500/20">
          <p className="text-sm font-semibold text-slate-100 truncate">
            ☺ {saya.data?.nama}
          </p>
          <p className="text-[11px] text-indigo-300/70 mb-2">
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
          <p className="mt-3 text-[10px] text-indigo-300/50">
            ✦ tema: Milky Way
          </p>
        </div>
      </aside>

      {/* ===== Isi halaman ===== */}
      <main className="flex-1 min-w-0 px-6 py-6">
        <div className="max-w-6xl mx-auto">
          {tab === "ringkasan" && <Ringkasan />}
          {tab === "analisis" && <Analisis />}
          {tab === "stok" && <Stok />}
          {tab === "stokmargin" && <StokMargin />}
          {tab === "aturan" && <AturanHarga />}
          {tab === "simulasi" && <Simulasi />}
          {tab === "rencana" && <Perencanaan />}
          {tab === "alarm" && <AlarmPage />}
          {tab === "rekonsiliasi" && <Rekonsiliasi />}
          {tab === "kualitas" && <Kualitas />}
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
