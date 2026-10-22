import { FormEvent, useState } from "react";
import { kelasInput, kelasLabel, kelasTombol, kirimJson } from "../bersama";

export default function Login({ onSukses }: { onSukses: () => void }) {
  const [username, setUsername] = useState("");
  const [sandi, setSandi] = useState("");
  const [galat, setGalat] = useState<string | null>(null);
  const [sibuk, setSibuk] = useState(false);

  const kirim = async (e: FormEvent) => {
    e.preventDefault();
    setGalat(null);
    setSibuk(true);
    try {
      const j = await kirimJson("/api/auth/login", { username, sandi });
      localStorage.setItem("op-margin.pengisi", j.nama ?? username);
      onSukses();
    } catch (err) {
      setGalat((err as Error).message);
    } finally {
      setSibuk(false);
    }
  };

  return (
    <div className="galaxy min-h-screen flex items-center justify-center p-4 text-slate-200">
      <form onSubmit={kirim}
            className="w-full max-w-sm rounded-2xl bg-[#15143a]/90 border border-violet-500/20
                       p-8 shadow-2xl shadow-violet-950/50 backdrop-blur">
        <div className="text-center mb-6">
          <p className="text-4xl mb-2">🪐</p>
          <h1 className="text-xl font-bold text-white tracking-wide">
            Rubber Intelligence
          </h1>
          <p className="mt-1 text-xs text-indigo-300/80">
            Rubber Raw Material Big Data — silakan masuk
          </p>
        </div>

        <label className={kelasLabel}>Username</label>
        <input className={kelasInput} value={username} autoFocus
               autoComplete="username" placeholder="username"
               onChange={(e) => setUsername(e.target.value)} />

        <label className={`${kelasLabel} mt-4`}>Sandi</label>
        <input className={kelasInput} type="password" value={sandi}
               autoComplete="current-password" placeholder="••••••••"
               onChange={(e) => setSandi(e.target.value)} />

        {galat && (
          <p className="mt-4 rounded-md bg-red-500/10 border border-red-400/30
                        px-3 py-2 text-sm text-red-300">{galat}</p>
        )}

        <button type="submit" className={`${kelasTombol} w-full mt-6`}
                disabled={sibuk || !username || !sandi}>
          {sibuk ? "Memeriksa…" : "Masuk"}
        </button>

        <p className="mt-4 text-center text-[11px] text-indigo-300/50">
          Lupa sandi? Hubungi admin aplikasi untuk reset.
        </p>
      </form>
    </div>
  );
}
