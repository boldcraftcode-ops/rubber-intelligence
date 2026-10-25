# Folder deploy

Login aplikasi memakai **username + sandi** (data di tabel `pengguna`).
Cloudflare Access sudah **dihapus** dan tidak dipakai lagi; berkas panduan
Access yang lama juga sudah dihapus dari repo.

- `install-windows.md` — panduan lengkap: backend sebagai service (NSSM /
  Task Scheduler), cloudflared tunnel sebagai service, verifikasi akhir.
- `cloudflared-config.example.yml` — contoh konfigurasi tunnel
  (api.[ISI-DOMAIN] → http://127.0.0.1:8000). Tunnel hanya untuk menghubungkan
  ke internet tanpa membuka port; **bukan** untuk login.
- `backup.ps1` — backup harian (retensi 30 hari) + verifikasi integritas.
- `restore.md` — prosedur restore dan UJI restore di folder uji.
- `checklist-keamanan.md` — checklist keamanan akhir.

Catatan keamanan: tanpa Cloudflare Access, perlindungan aplikasi bergantung
sepenuhnya pada login username+sandi bawaan aplikasi. Karena itu:
`SECRET_KEY` wajib diisi (minimal 32 karakter), sandi admin diganti dari
`admin123`, dan sebaiknya pasang HTTPS di depan aplikasi (lihat bagian C
`install-windows.md`).
