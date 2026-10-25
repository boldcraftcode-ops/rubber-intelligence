import { FormEvent, useState } from "react";
import { kelasInput, kelasLabel, kelasTombol, kirimJson } from "../bersama";

/* ---------------------------------------------------------------------------
   Layar untuk mode login Cloudflare Access.

   Pada mode ini tidak ada form username+sandi: yang memeriksa identitas
   adalah Cloudflare Access di depan aplikasi. Kalau layar ini muncul di
   localhost, itu tanda setelan .env tidak cocok dengan cara aplikasi dibuka —
   karena itu petunjuknya ditulis eksplisit, bukan sekadar "belum login".
--------------------------------------------------------------------------- */
export function LayarAccess({ detail, produksi }:
  { detail?: string; produksi?: boolean }) {
  return (
    <div className="galaxy min-h-screen flex items-center justify-center p-4 text-slate-200">
      <div className="w-full max-w-md rounded-2xl bg-[#15143a]/90 border border-violet-500/20
                      p-8 shadow-2xl shadow-violet-950/50 backdrop-blur">
        <div className="text-center mb-5">
          <p className="text-4xl mb-2">🔐</p>
          <h1 className="text-lg font-bold text-white">Masuk lewat Cloudflare Access</h1>
          <p className="mt-2 text-xs text-indigo-300/80 leading-relaxed">
            Aplikasi ini memakai <b>Cloudflare Access</b>, bukan form username
            dan sandi. Karena itu tidak ada kolom sandi di halaman ini.
          </p>
        </div>

        <ol className="text-sm space-y-2 list-decimal list-inside text-slate-300">
          <li>Buka aplikasi lewat <b>alamat resminya</b> (domain yang dilindungi
              Access), bukan lewat localhost.</li>
          <li>Masuk dengan <b>email kantor</b> Anda saat halaman Access muncul.</li>
          <li>Setelah itu halaman ini akan terbuka sendiri.</li>
        </ol>

        <button className={`${kelasTombol} w-full mt-6`}
                onClick={() => window.location.reload()}>
          Muat ulang halaman
        </button>

        {!produksi && (
          <div className="mt-5 rounded-md bg-amber-500/10 border border-amber-400/30
                          px-3 py-2 text-[12px] text-amber-200 leading-relaxed">
            <b>Membuka di komputer sendiri (localhost)?</b> Cloudflare Access
            tidak bisa dipakai di localhost. Ubah <code>backend/.env</code>{" "}
            menjadi <code>AUTH_MODE=lokal</code>, lalu jalankan ulang
            API &amp; halaman ini. Cara cepat dari folder <code>backend</code>:
            <br />
            <code className="mt-1 inline-block">.venv\Scripts\python -m app.cli atur-login-lokal</code>
            <br />
            (atau jalankan ulang <code>start-web.bat</code> — skrip itu
            menawarkan perbaikannya).
          </div>
        )}

        {detail && (
          <p className="mt-4 text-[11px] text-indigo-300/50 leading-relaxed">
            Pesan dari server: {detail}
          </p>
        )}
      </div>
    </div>
  );
}

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

        {galat && /cloudflare access/i.test(galat) ? (
          <div className="mt-4 rounded-md bg-amber-500/10 border border-amber-400/30
                          px-3 py-2 text-[12px] text-amber-200 leading-relaxed">
            <b>Proses API yang berjalan memakai login Cloudflare Access.</b>
            <br />
            Access tidak bisa dipakai di localhost, jadi form ini tidak akan
            pernah berhasil. Tutup jendela <code>OP Margin - API</code>, lalu
            jalankan ulang <code>start-web.bat</code> (skrip menawarkan
            perbaikannya), atau dari folder <code>backend</code> jalankan:
            <br />
            <code className="mt-1 inline-block">.venv\Scripts\python -m app.cli atur-login-lokal</code>
            <p className="mt-1 text-amber-300/70">Pesan server: {galat}</p>
          </div>
        ) : galat && (
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
