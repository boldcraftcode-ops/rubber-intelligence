import { FormEvent, useState } from "react";
import type { CSSProperties } from "react";
import { kelasInput, kelasLabel, kelasTombol, kirimJson, simpanToken } from "../bersama";
import { VERSI_UI } from "../versi";

/* ---------------------------------------------------------------------------
   Layar bila API menjawab tetapi login sedang tidak aktif (mis. mode
   development tanpa .env) — supaya tidak bingung melihat form yang tak bisa
   dipakai.
--------------------------------------------------------------------------- */
export function LayarGalat({ detail, ulangi }:
  { detail?: string; ulangi: () => void }) {
  return (
    <div className="galaxy min-h-screen flex items-center justify-center p-4 text-[#1D2434]">
      <div className="w-full max-w-md rounded-sm bg-white border border-[#E4E5E8]
                      border-t-2 border-t-[#FF1313] p-8 shadow-[0_1px_3px_rgba(29,36,52,0.08)]">
        <p className="text-3xl text-center mb-3">⚠️</p>
        <h1 className="text-lg font-bold text-[#1D2434] text-center">
          Aplikasi belum bisa dibuka
        </h1>
        <p className="mt-3 text-sm text-[#1D2434] leading-relaxed">
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
  const [tampilSandi, setTampilSandi] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [hitungGalat, setHitungGalat] = useState(0);
  const [berhasil, setBerhasil] = useState(false);

  const kirim = async (e: FormEvent) => {
    e.preventDefault();
    if (sibuk || berhasil || !username || !sandi) return;
    setGalat(null);
    setSibuk(true);
    let sukses = false;
    try {
      const j = await kirimJson("/api/auth/login", { username, sandi });
      simpanToken(j.token);          // cadangan bila cookie diblokir
      localStorage.setItem("op-margin.pengisi", j.nama ?? username);
      setBerhasil(true);
      sukses = true;
      await new Promise((r) => setTimeout(r, 350));
      onSukses();
    } catch (err) {
      setGalat((err as Error).message);
      setHitungGalat((n) => n + 1);
    } finally {
      if (!sukses) setSibuk(false);
    }
  };

  return (
    <div className="galaxy min-h-screen flex items-center justify-center p-4 text-[#1D2434]">
      <div className={`login-kartu transition duration-300 w-full max-w-3xl overflow-hidden rounded-sm bg-white border border-[#E4E5E8] grid md:grid-cols-[42%_58%] ${berhasil ? "opacity-0 scale-[.98]" : ""}`}>

        {/* ===== panel kiri: identitas (navy) ===== */}
        <aside className="relative bg-[#1D2434] px-8 py-10 text-white flex flex-col justify-between overflow-hidden">
          {/* garis merah vertikal di tepi kanan, seperti materi korporat */}
          <span className="hidden md:block absolute top-8 bottom-8 right-0 w-[3px] bg-[#FF1313]" />

          {/* latar grid data yang bergerak perlahan + lapisan aksen */}
          <div aria-hidden className="login-grid pointer-events-none absolute -top-12 bottom-0 inset-x-0" />
          <div aria-hidden className="login-selimut pointer-events-none absolute inset-0" />

          <div className="relative flex flex-col items-start">
            <p className="text-[11px] uppercase tracking-[0.18em] text-white/60">
              Rubber Raw Material
            </p>
            <h1 className="mt-1 text-2xl font-bold leading-tight">
              Rubber<br />Intelligence <span className="whitespace-nowrap text-sm font-semibold text-white/70">V.{VERSI_UI}</span>
            </h1>
            <img src="/rubber-intelligence-logo.svg" alt="Rubber Intelligence"
                 className="mt-6 h-16 w-16 bg-white rounded-sm p-1.5" />
          </div>

          {/* Garis tren merangkum gerak data tanpa kolom dekoratif. */}
          <svg aria-hidden="true" viewBox="0 0 240 96" className="relative mt-10 w-full h-24">
            <line x1="0" y1="88" x2="240" y2="88" stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
            <path d="M8 72 C28 68 32 56 52 60 S78 76 96 54 S124 28 144 42 S174 58 188 30 S218 22 232 10"
                  pathLength={1} fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="2"
                  className="login-garis-tren" />
            <circle cx="232" cy="10" r="3.5" fill="#FF1313" className="login-titik-tren" />
          </svg>
        </aside>

        {/* ===== panel kanan: form ===== */}
        <form onSubmit={kirim} aria-busy={sibuk} className="px-8 py-10">
          <div className="login-item" style={{ "--i": 0 } as CSSProperties}>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#FF1313]">Masuk</p>
            <h2 className="mt-1 text-xl font-bold text-[#1D2434]">Silakan masuk ke akun Anda</h2>
            <p className="mt-2 text-sm text-[#64676C]">Gunakan akun yang diberikan oleh admin aplikasi.</p>
          </div>

          <div className="login-item mt-6" style={{ "--i": 1 } as CSSProperties}>
            <label className={kelasLabel} htmlFor="login-username">Username</label>
            <input id="login-username" className={kelasInput} value={username} autoFocus
                   autoComplete="username" placeholder="username" disabled={sibuk || berhasil}
                   onChange={(e) => setUsername(e.target.value)} />
          </div>

          <div className="login-item mt-4" style={{ "--i": 2 } as CSSProperties}>
            <label className={kelasLabel} htmlFor="login-sandi">Sandi</label>
            <div className="relative">
              <input id="login-sandi" className={`${kelasInput} pr-16`} type={tampilSandi ? "text" : "password"} value={sandi}
                     autoComplete="current-password" placeholder="••••••••" disabled={sibuk || berhasil}
                     onChange={(e) => setSandi(e.target.value)}
                     onKeyUp={(e) => setCapsLock(e.getModifierState("CapsLock"))} />
              <button type="button" className="absolute inset-y-0 right-2 text-xs text-[#64676C]"
                      aria-label={tampilSandi ? "Sembunyikan sandi" : "Lihat sandi"}
                      aria-pressed={tampilSandi} disabled={sibuk || berhasil}
                      onClick={() => setTampilSandi((v) => !v)}>
                {tampilSandi ? "Sembunyi" : "Lihat"}
              </button>
            </div>
            {capsLock && <p className="mt-1 text-[11px] text-[#92400E]">Caps Lock aktif</p>}
          </div>

          {galat && (
            <p key={hitungGalat} role="alert" className="login-goyang mt-4 rounded-sm bg-[#FEF2F2] border border-[#FECACA] px-3 py-2 text-sm text-[#B91C1C]">{galat}</p>
          )}

          <button type="submit" className={`login-item ${kelasTombol} w-full mt-6`}
                  style={{ "--i": 3 } as CSSProperties}
                  disabled={sibuk || berhasil || !username || !sandi}>
            {sibuk ? <><span aria-hidden="true" className="login-putar h-3.5 w-3.5 rounded-full border-2 border-white/40 border-t-white" />Memeriksa…</> : "Masuk"}
          </button>

          <p className="login-item mt-4 text-[11px] text-[#9AA0A6]" style={{ "--i": 4 } as CSSProperties}>
            Lupa sandi? Hubungi admin aplikasi untuk reset.
          </p>
          <p className="mt-2 text-[11px] text-[#9AA0A6]">
            Created and designed by AR
          </p>
        </form>
      </div>
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
    <div className="galaxy min-h-screen flex items-center justify-center p-4 text-[#1D2434]">
      <div className="w-full max-w-lg rounded-sm bg-white border border-[#E4E5E8]
                      border-t-2 border-t-[#FF1313] p-8 shadow-[0_1px_3px_rgba(29,36,52,0.08)]">
        <p className="text-3xl text-center mb-3">🧩</p>
        <h1 className="text-lg font-bold text-[#1D2434] text-center">
          Aplikasi dan servernya beda versi
        </h1>
        <p className="mt-3 text-sm text-[#1D2434] leading-relaxed">
          Halaman ini versi <b>{versiUi}</b>, tetapi API yang menjawab di
          port 8000 {versiApi ? <>versi <b>{versiApi}</b></> : "masih versi lama"}.
          Karena itu login tidak bisa diproses.
        </p>
        {folder && (
          <div className="mt-3 rounded-sm bg-[#FFF1F1] border border-[#E4E5E8]
                          px-3 py-2 text-[12px] text-[#1D2434] leading-relaxed">
            API lama itu dijalankan dari folder:
            <br />
            <code className="break-all">{folder}</code>
            {pid ? <> — PID <b>{pid}</b></> : null}
            <br />
            Tutup proses itu, lalu jalankan <b>start-web.bat</b> dari folder
            aplikasi yang baru.
          </div>
        )}

        <div className="mt-4 rounded-sm bg-[#FFFBEB] border border-[#FDE68A]
                        px-3 py-2 text-[12px] text-[#92400E] leading-relaxed">
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
        <p className="mt-3 text-[11px] text-[#64676C] leading-relaxed">
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
          <p className="mt-3 text-[11px] text-[#9AA0A6] leading-relaxed">
            Pesan dari server: {detail}
          </p>
        )}
      </div>
    </div>
  );
}
