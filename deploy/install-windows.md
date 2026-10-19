# Panduan deploy di PC Windows kantor — langkah demi langkah

Hasil akhir: backend berjalan otomatis sebagai service di PC Windows,
terhubung ke internet lewat **Cloudflare Tunnel** (tanpa membuka port apa pun
di router), dan hanya bisa diakses setelah login **Cloudflare Access**.

Prasyarat: domain perusahaan sudah dikelola di Cloudflare (gratis), dan
aplikasi sudah berjalan normal secara lokal (`start.bat` lulus tes).

> Ganti setiap `[ISI-DOMAIN]` dengan domain Anda (contoh `perusahaanku.co.id`)
> dan `[ISI-NAMA-USER]` dengan nama user Windows Anda.

---

## Bagian A — Pasang backend sebagai service (hidup otomatis setelah restart)

Kita pakai **NSSM** (Non-Sucking Service Manager), alat kecil yang membungkus
program apa pun menjadi service Windows. (Alternatif Task Scheduler ada di
bagian A-alternatif.)

1. Unduh NSSM dari https://nssm.cc/download (zip), ekstrak, salin
   `win64\nssm.exe` ke `C:\nssm\nssm.exe`.
2. Buka **PowerShell sebagai Administrator** (Start → ketik PowerShell →
   klik kanan → Run as administrator).
3. Siapkan file `.env` produksi:
   ```powershell
   cd C:\op-margin\backend
   copy .env.example .env
   notepad .env
   ```
   Isi minimal (nilai Access diisi di Bagian C):
   ```
   DATABASE_URL=sqlite:///opmargin.db
   APP_ENV=produksi
   CF_ACCESS_TEAM_DOMAIN=[ISI-TEAM].cloudflareaccess.com
   CF_ACCESS_AUD=[ISI-AUD]
   FRONTEND_ORIGIN=https://[ISI-NAMA-PROYEK].pages.dev
   ```
   PENTING: jangan tulis `AUTH_DISABLED=true` — aplikasi sengaja MENOLAK
   start di produksi bila itu ada (pengaman).
4. Daftarkan service:
   ```powershell
   C:\nssm\nssm.exe install OPMarginAPI "C:\op-margin\backend\.venv\Scripts\python.exe" "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env"
   C:\nssm\nssm.exe set OPMarginAPI AppDirectory "C:\op-margin\backend"
   C:\nssm\nssm.exe set OPMarginAPI AppStdout "C:\op-margin\backend\log-api.txt"
   C:\nssm\nssm.exe set OPMarginAPI AppStderr "C:\op-margin\backend\log-api-error.txt"
   C:\nssm\nssm.exe set OPMarginAPI Start SERVICE_AUTO_START
   C:\nssm\nssm.exe start OPMarginAPI
   ```
   Catatan: bila uvicorn versi Anda tidak mendukung `--env-file`, hapus opsi
   itu dan set variabel lewat NSSM:
   `C:\nssm\nssm.exe set OPMarginAPI AppEnvironmentExtra APP_ENV=produksi CF_ACCESS_TEAM_DOMAIN=... CF_ACCESS_AUD=... FRONTEND_ORIGIN=...`
5. Uji: buka browser di PC itu ke `http://127.0.0.1:8000/api/health` —
   harus muncul `{"status":"ok",...}`. Perintah cek service:
   `C:\nssm\nssm.exe status OPMarginAPI`

### Bagian A-alternatif — Task Scheduler (tanpa NSSM)
1. Start → "Task Scheduler" → Create Task.
2. Tab General: beri nama `OP Margin API`, centang **Run whether user is
   logged on or not**.
3. Tab Triggers: New → Begin the task: **At startup**.
4. Tab Actions: New → Program: `C:\op-margin\backend\.venv\Scripts\python.exe`
   → Arguments: `-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env`
   → Start in: `C:\op-margin\backend`.
5. Tab Settings: centang "If the task fails, restart every 1 minute".

---

## Bagian B — Pasang cloudflared dan buat tunnel

1. Unduh `cloudflared-windows-amd64.msi` dari
   https://github.com/cloudflare/cloudflared/releases (atau
   `winget install Cloudflare.cloudflared`), pasang.
2. Di PowerShell (user biasa):
   ```powershell
   cloudflared tunnel login
   ```
   Browser terbuka → pilih domain Anda → izinkan. Ini menyimpan sertifikat di
   `C:\Users\[ISI-NAMA-USER]\.cloudflared\cert.pem`.
3. Buat tunnel dan catat ID-nya:
   ```powershell
   cloudflared tunnel create op-margin
   ```
   Outputnya menampilkan `Created tunnel op-margin with id xxxxxxxx-....` —
   itu `[ISI-TUNNEL-ID]`.
4. Buat file konfigurasi `C:\Users\[ISI-NAMA-USER]\.cloudflared\config.yml`
   dengan isi dari `deploy/cloudflared-config.example.yml` (ganti semua
   `[ISI-...]`). Rute: `api.[ISI-DOMAIN]` → `http://127.0.0.1:8000`.
5. Daftarkan DNS untuk hostname itu (sekali saja):
   ```powershell
   cloudflared tunnel route dns op-margin api.[ISI-DOMAIN]
   ```
6. Uji dulu di jendela (jalan sementara):
   ```powershell
   cloudflared tunnel run op-margin
   ```
   Dari HP (matikan WiFi kantor, pakai data seluler) buka
   `https://api.[ISI-DOMAIN]/api/health` → harus muncul `{"status":"ok"}`.
   (Endpoint health memang terbuka dan tanpa data sensitif; endpoint lain
   akan meminta login setelah Bagian C.)
7. Bila sukses, hentikan (Ctrl+C) lalu pasang sebagai service Windows
   (PowerShell **Administrator**):
   ```powershell
   cloudflared service install
   net start cloudflared
   ```
   Service ini otomatis membaca `config.yml` di folder `.cloudflared` dan
   hidup kembali setelah PC restart.

> Tidak ada satu pun port yang dibuka di router/firewall: cloudflared membuat
> koneksi keluar ke Cloudflare, dan backend tetap hanya mendengarkan
> 127.0.0.1.

---

## Bagian C — Cloudflare Pages (frontend) dan Access (login)

Ikuti `deploy/cloudflare-pages-access.md`, lalu kembali ke sini:

8. Isi `CF_ACCESS_TEAM_DOMAIN` dan `CF_ACCESS_AUD` di
   `C:\op-margin\backend\.env` (nilai dari panduan Access), lalu restart:
   ```powershell
   C:\nssm\nssm.exe restart OPMarginAPI
   ```

---

## Bagian D — Backup harian otomatis

1. Salin `deploy\backup.ps1` ke `C:\op-margin\deploy\backup.ps1` (sudah ada
   bila Anda menyalin seluruh folder repo).
2. Uji sekali secara manual (PowerShell):
   ```powershell
   powershell -ExecutionPolicy Bypass -File C:\op-margin\deploy\backup.ps1
   ```
   Harus muncul folder baru di `C:\op-margin-backup\` berisi `opmargin.db`.
3. Jadwalkan harian: Task Scheduler → Create Task → nama `OP Margin Backup`
   → Trigger: Daily jam 21:00 → Action: Program `powershell.exe`, Arguments:
   `-ExecutionPolicy Bypass -File C:\op-margin\deploy\backup.ps1`.
4. Prosedur restore + UJI restore: lihat `deploy/restore.md`. Lakukan uji
   restore minimal sekali setelah pemasangan, dan catat tanggalnya.

---

## Bagian E — Verifikasi akhir (kriteria penerimaan)

Dari HP dengan data seluler (bukan WiFi kantor):
1. Buka `https://[alamat-frontend]` → muncul halaman login Cloudflare Access.
2. Login dengan email yang TERDAFTAR di kebijakan → aplikasi tampil dan data
   terlihat (Ringkasan terisi).
3. Coba login email yang TIDAK terdaftar (mis. Gmail pribadi lain) → Access
   menolak ("You don't have permission").
4. `https://api.[ISI-DOMAIN]/api/tahun` tanpa login → 401 dari backend
   (lapisan kedua; Access biasanya sudah menghadang lebih dulu).
5. Restart PC → tunggu 2 menit → ulangi langkah 1-2 (service hidup sendiri).
6. Cek `deploy/checklist-keamanan.md` dan centang semuanya.
