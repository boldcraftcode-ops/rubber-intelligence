import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { ambilJson } from "./bersama";
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
] as const;

type TabId = (typeof TAB)[number]["id"];

export default function App() {
  const { lang, setLang, t } = useBahasa();
  const [tab, setTab] = useState<TabId>("ringkasan");
  const [pengisi, setPengisi] = useState(
    () => localStorage.getItem("op-margin.pengisi") ?? ""
  );
  const alarm = useQuery({
    queryKey: ["alarm"],
    queryFn: () => ambilJson("/api/alarm"),
    refetchInterval: 60_000,
  });
  const jumlahAlarm = alarm.data?.alarm.length ?? 0;

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
          {TAB.map((tb) => (
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

        <div className="px-5 py-4 border-t border-violet-500/20">
          <label className="block text-xs text-indigo-300/80 mb-1">
            {t("Nama Anda (untuk catatan)")}
          </label>
          <input
            className="w-full rounded-md border border-violet-400/30 bg-[#0b0a26]/80
                       px-3 py-1.5 text-sm text-slate-100 placeholder-slate-500
                       focus:outline-none focus:ring-2 focus:ring-violet-500"
            placeholder={t("nama pengisi")}
            value={pengisi}
            onChange={(e) => {
              setPengisi(e.target.value);
              localStorage.setItem("op-margin.pengisi", e.target.value);
            }}
          />
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
          {tab === "input" && <InputHarian pengisi={pengisi} />}
        </div>
      </main>
    </div>
  );
}
