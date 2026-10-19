# Panduan Cloudflare Pages (frontend) + Cloudflare Access (login)

## 1. Frontend di Cloudflare Pages

1. Taruh repo di GitHub (ingat: `sample_data/` tidak boleh berisi data
   rahasia asli bila repo publik — lebih aman repo private).
2. Dasbor Cloudflare → **Workers & Pages → Create → Pages → Connect to Git**
   → pilih repo `op-margin`.
3. Pengaturan build:
   - **Framework preset**: Vite
   - **Root directory**: `frontend`
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
4. **Environment variables** (Production):
   - `VITE_API_URL` = `https://api.[ISI-DOMAIN]`
     (tanpa garis miring di akhir; frontend otomatis memanggil
     `https://api.[ISI-DOMAIN]/api/...` dan mengirim cookie login).
5. Deploy. Alamat default: `https://[ISI-NAMA-PROYEK].pages.dev`.
   (Boleh juga dipasangi custom domain, mis. `opmargin.[ISI-DOMAIN]` —
   kalau begitu, pakai alamat itu di kebijakan Access dan FRONTEND_ORIGIN.)
6. Di PC server: isi `FRONTEND_ORIGIN=https://[ISI-NAMA-PROYEK].pages.dev`
   di `backend\.env` (CORS ketat — hanya origin ini yang diizinkan),
   lalu restart service API.

## 2. Login dengan Cloudflare Access

Access = gerbang login di depan aplikasi. Hanya email yang ada di kebijakan
yang bisa masuk; lainnya ditolak sebelum menyentuh server Anda.

### a. Aktifkan Zero Trust
1. Dasbor Cloudflare → **Zero Trust** (one.dash.cloudflare.com) → pilih
   paket Free.
2. Saat pertama kali, Anda diminta memilih **team name**, misalnya
   `perusahaanku` → team domain Anda menjadi
   `perusahaanku.cloudflareaccess.com`. **Catat — ini nilai
   `CF_ACCESS_TEAM_DOMAIN` untuk `.env`.**

### b. Aplikasi Access untuk API
1. Zero Trust → **Access → Applications → Add an application →
   Self-hosted**.
2. Name: `OP Margin API`; Application domain: `api.[ISI-DOMAIN]`
   (persis hostname tunnel).
3. Session duration: mis. 24 jam.
4. **Policy**: Name `Karyawan diizinkan`, Action **Allow**, Include →
   **Emails** → daftarkan satu per satu email yang boleh masuk
   (atau **Emails ending in** `@perusahaanku.co.id` bila semua karyawan
   domain itu boleh). Email di luar daftar otomatis DITOLAK.
5. Simpan. Buka kembali aplikasi itu → tab **Overview** → salin
   **Application Audience (AUD) Tag** — string heksadesimal panjang.
   **Ini nilai `CF_ACCESS_AUD` untuk `.env`.**

### c. Aplikasi Access untuk frontend
1. Add an application → Self-hosted → Name: `OP Margin App`;
   domain: `[ISI-NAMA-PROYEK].pages.dev` (atau custom domain frontend).
   Untuk melindungi `*.pages.dev` perlu custom domain; paling sederhana:
   pasang custom domain `opmargin.[ISI-DOMAIN]` di Pages lalu lindungi
   domain itu dengan Access.
2. Policy: SAMA dengan kebijakan API (email yang sama). Dengan begitu satu
   kali login berlaku untuk halaman dan API.

### d. Hubungkan ke backend
Di `C:\op-margin\backend\.env`:
```
APP_ENV=produksi
CF_ACCESS_TEAM_DOMAIN=perusahaanku.cloudflareaccess.com
CF_ACCESS_AUD=<AUD tag dari langkah b-5>
FRONTEND_ORIGIN=https://opmargin.[ISI-DOMAIN]
```
Restart service API. Backend kini MEMVERIFIKASI SENDIRI setiap permintaan
(tanda tangan JWKS dari team domain, audience, masa berlaku) — lapisan kedua
setelah gerbang Access. Permintaan tanpa token yang sah dijawab 401.

### e. Uji
- HP + data seluler → buka frontend → login email terdaftar → data tampil.
- Email tidak terdaftar → ditolak Access.
- `https://api.[ISI-DOMAIN]/api/health` → terbuka (tanpa data sensitif).
- `https://api.[ISI-DOMAIN]/api/tahun` langsung di browser baru/incognito
  → diminta login; tanpa login valid → 401.
