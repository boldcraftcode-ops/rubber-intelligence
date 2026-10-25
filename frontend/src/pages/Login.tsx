import { FormEvent, useState } from "react";
import { kelasInput, kelasLabel, kelasTombol, kirimJson, simpanToken } from "../bersama";

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

  const kirim = async (e: FormEvent) => {
    e.preventDefault();
    setGalat(null);
    setSibuk(true);
    try {
      const j = await kirimJson("/api/auth/login", { username, sandi });
      simpanToken(j.token);          // cadangan bila cookie diblokir
      localStorage.setItem("op-margin.pengisi", j.nama ?? username);
      onSukses();
    } catch (err) {
      setGalat((err as Error).message);
    } finally {
      setSibuk(false);
    }
  };

  return (
    <div className="galaxy min-h-screen flex items-center justify-center p-4 text-[#1D2434]">
      <div className="w-full max-w-3xl overflow-hidden rounded-sm bg-white shadow-xl
                      shadow-[#1D2434]/10 border border-[#E4E5E8] grid md:grid-cols-[42%_58%]">

        {/* ===== panel kiri: identitas (navy) ===== */}
        <aside className="relative bg-[#1D2434] px-8 py-10 text-white flex flex-col justify-between">
          {/* garis merah vertikal di tepi kanan, seperti materi korporat */}
          <span className="hidden md:block absolute top-8 bottom-8 right-0 w-[3px] bg-[#FF1313]" />

          <div>
            <img src="/logo-rubber-intelligence.svg" alt="Rubber Intelligence"
                 className="h-16 w-16 bg-white rounded-sm p-1.5" />
            <p className="mt-6 text-[11px] uppercase tracking-[0.18em] text-white/60">
              Rubber Raw Material
            </p>
            <h1 className="mt-1 text-2xl font-bold leading-tight">
              Rubber<br />Intelligence
            </h1>
            <p className="mt-3 text-sm leading-relaxed text-white/70">
              Big data karet alam: harga, mutu, stok, dan margin dalam satu
              tempat — untuk keputusan beli yang lebih tenang.
            </p>
          </div>

          {/* aksen pola titik */}
          <span aria-hidden className="pola-titik pointer-events-none absolute
                                       bottom-6 right-5 h-24 w-16 opacity-70" />

          <ul className="mt-8 space-y-2 text-xs text-white/60">
            <li className="flex gap-2"><span className="text-[#FF1313]">—</span> SICOM &amp; OP Margin harian</li>
            <li className="flex gap-2"><span className="text-[#FF1313]">—</span> Intake, stok, dan days of cover</li>
            <li className="flex gap-2"><span className="text-[#FF1313]">—</span> Penjelasan angka dalam bahasa manusia</li>
          </ul>
        </aside>

        {/* ===== panel kanan: form ===== */}
        <form onSubmit={kirim} className="px-8 py-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#FF1313]">
            Masuk
          </p>
          <h2 className="mt-1 text-xl font-bold text-[#1D2434]">
            Silakan masuk ke akun Anda
          </h2>
          <p className="mt-1 text-sm text-[#64676C]">
            Gunakan username dan sandi kantor Anda.
          </p>

          <div className="mt-6">
            <label className={kelasLabel}>Username</label>
            <input className={kelasInput} value={username} autoFocus
                   autoComplete="username" placeholder="username"
                   onChange={(e) => setUsername(e.target.value)} />
          </div>

          <div className="mt-4">
            <label className={kelasLabel}>Sandi</label>
            <input className={kelasInput} type="password" value={sandi}
                   autoComplete="current-password" placeholder="••••••••"
                   onChange={(e) => setSandi(e.target.value)} />
          </div>

          {galat && (
            <p className="mt-4 rounded-sm bg-[#FEF2F2] border border-[#FECACA]
                          px-3 py-2 text-sm text-[#B91C1C]">{galat}</p>
          )}

          <button type="submit" className={`${kelasTombol} w-full mt-6`}
                  disabled={sibuk || !username || !sandi}>
            {sibuk ? "Memeriksa…" : "Masuk"}
          </button>

          <p className="mt-4 text-[11px] text-[#9AA0A6]">
            Lupa sandi? Hubungi admin aplikasi untuk reset.
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
