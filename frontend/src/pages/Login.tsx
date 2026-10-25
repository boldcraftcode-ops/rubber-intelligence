import { FormEvent, useState } from "react";
import { kelasInput, kelasLabel, kelasTombol, kirimJson } from "../bersama";

/* ---------------------------------------------------------------------------
   Layar bila API menjawab tetapi login sedang tidak aktif (mis. mode
   development tanpa .env) — supaya tidak bingung melihat form yang tak bisa
   dipakai.
--------------------------------------------------------------------------- */
export function LayarGalat({ detail, ulangi }:
  { detail?: string; ulangi: () => void }) {
  return (
    <div className="galaxy min-h-screen flex items-center justify-center p-4 text-slate-200">
      <div className="w-full max-w-md rounded-2xl bg-[#15143a]/90 border border-red-400/20 p-8">
        <p className="text-4xl text-center mb-3">⚠️</p>
        <h1 className="text-lg font-bold text-white text-center">
          Aplikasi belum bisa dibuka
        </h1>
        <p className="mt-3 text-sm text-slate-300 leading-relaxed">
          {detail ?? "Server tidak merespons seperti yang diharapkan."}
        </p>
        <button className={`${kelasTombol} w-full mt-5`} onClick={ulangi}>
          Coba lagi
        </button>
      </div>
    </div>
  );
}

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

/* ---------------------------------------------------------------------------
   Layar bila API yang menjawab BUKAN kode di folder ini (versi berbeda).

   Penyebab yang paling sering: jendela "OP Margin - API" dari sesi sebelumnya
   masih hidup dan memegang port 8000, jadi yang menjawab adalah kode lama.
   Kode lama bisa menjawab dengan pesan yang membingungkan (mis. "Belum login
   ... Cloudflare Access") — layar ini menggantinya dengan penjelasan dan
   langkah perbaikan.
--------------------------------------------------------------------------- */
export function LayarApiLama({ versiApi, versiUi, detail, folder, pid }:
  { versiApi?: string; versiUi: string; detail?: string;
    folder?: string; pid?: number }) {
  const perintah = pid ? `taskkill /f /pid ${pid}` : undefined;
  return (
    <div className="galaxy min-h-screen flex items-center justify-center p-4 text-slate-200">
      <div className="w-full max-w-lg rounded-2xl bg-[#15143a]/90 border border-amber-400/30 p-8">
        <p className="text-4xl text-center mb-3">🧩</p>
        <h1 className="text-lg font-bold text-white text-center">
          Aplikasi dan servernya beda versi
        </h1>
        <p className="mt-3 text-sm text-slate-300 leading-relaxed">
          Halaman ini versi <b>{versiUi}</b>, tetapi API yang menjawab di
          port 8000 {versiApi ? <>versi <b>{versiApi}</b></> : "masih versi lama"}.
          Karena itu login tidak bisa diproses.
        </p>
        {folder && (
          <div className="mt-3 rounded-md bg-violet-500/10 border border-violet-400/30
                          px-3 py-2 text-[12px] text-violet-200 leading-relaxed">
            API lama itu dijalankan dari folder:
            <br />
            <code className="break-all">{folder}</code>
            {pid ? <> — PID <b>{pid}</b></> : null}
            <br />
            Tutup proses itu, lalu jalankan <b>start-web.bat</b> dari folder
            aplikasi yang baru.
          </div>
        )}

        <div className="mt-4 rounded-md bg-amber-500/10 border border-amber-400/30
                        px-3 py-2 text-[12px] text-amber-200 leading-relaxed">
          Perbaikan (pilih salah satu):
          <ol className="list-decimal list-inside mt-1 space-y-1">
            <li>
              Jalankan <b>hentikan-api.bat</b> (klik kanan → Run as
              administrator bila perlu). Skrip itu menutup semua proses API
              dan web di komputer ini, lalu melaporkan apakah port 8000 sudah
              bebas.
            </li>
            <li>
              Lalu jalankan <b>start-web.bat</b> dari folder yang ada
              <code>VERSI.txt</code> berisi <b>{versiUi}</b>. Tunggu tulisan
              "API siap: kode {versiUi}".
            </li>
            <li>Muat ulang halaman ini (Ctrl+F5).</li>
          </ol>
          {perintah && (
            <p className="mt-2">
              Cara cepat menutup API lama: buka Command Prompt, jalankan
              <br />
              <code className="inline-block mt-1">{perintah}</code>
            </p>
          )}
        </div>
        <p className="mt-3 text-[11px] text-indigo-300/60 leading-relaxed">
          Periksa juga <code>http://localhost:8000/api/health</code> — nilai
          <code>versi</code> harus {versiUi}. Bila tetap beda, jalankan
          <b> diagnosa.bat</b>, atau <b>perbarui-kode.bat</b> bila folder ini
          hasil unduhan ZIP.
        </p>
        <div className="mt-4 flex gap-2">
          <button className={`${kelasTombol} flex-1`}
                  onClick={() => window.location.reload()}>
            Muat ulang halaman
          </button>
          <a className={`${kelasTombol} flex-1 text-center`}
             href="http://localhost:8000/api/health" target="_blank"
             rel="noreferrer">
            Buka /api/health
          </a>
        </div>
        {detail && (
          <p className="mt-3 text-[11px] text-indigo-300/40 leading-relaxed">
            Pesan dari server: {detail}
          </p>
        )}
      </div>
    </div>
  );
}
