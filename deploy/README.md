# Folder deploy

- `install-windows.md` — panduan lengkap: backend sebagai service (NSSM /
  Task Scheduler), cloudflared tunnel sebagai service, verifikasi akhir.
- `cloudflared-config.example.yml` — contoh konfigurasi tunnel
  (api.[ISI-DOMAIN] → http://127.0.0.1:8000).
- `cloudflare-pages-access.md` — frontend di Pages (build, VITE_API_URL)
  dan Access (kebijakan email, cara ambil AUD & team domain).
- `backup.ps1` — backup harian (retensi 30 hari) + verifikasi integritas.
- `restore.md` — prosedur restore dan UJI restore di folder uji.
- `checklist-keamanan.md` — checklist keamanan akhir.
