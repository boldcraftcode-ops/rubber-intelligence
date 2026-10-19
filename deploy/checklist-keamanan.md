# Checklist keamanan akhir — OP Margin

Centang semua sebelum dan sesudah go-live; ulangi tiap ada perubahan besar.

## Jaringan
- [ ] TIDAK ada port yang dibuka/diteruskan di router kantor (backend hanya
      lewat Cloudflare Tunnel; cek router: tidak ada port forwarding).
- [ ] Backend uvicorn mendengarkan **127.0.0.1:8000** saja (bukan 0.0.0.0) —
      cek: `netstat -ano | findstr :8000` harus menunjukkan 127.0.0.1.
- [ ] `config.yml` tunnel punya baris terakhir `service: http_status:404`.

## Login & otorisasi
- [ ] Cloudflare Access aktif untuk **frontend dan api** dengan kebijakan
      email yang sama; email di luar daftar ditolak (diuji sungguhan).
- [ ] `.env` produksi: `APP_ENV=produksi`, TANPA `AUTH_DISABLED`
      (aplikasi menolak start bila `AUTH_DISABLED=true` di produksi — jangan
      dilemahkan).
- [ ] `CF_ACCESS_TEAM_DOMAIN` dan `CF_ACCESS_AUD` terisi benar; backend
      memverifikasi sendiri tanda tangan/audience/masa berlaku token
      (uji: panggil API tanpa login → 401).
- [ ] Uji dari HP (data seluler): login email terdaftar = bisa; email lain =
      ditolak.

## Aplikasi
- [ ] CORS: `FRONTEND_ORIGIN` hanya berisi alamat frontend resmi.
- [ ] Halaman dokumentasi API (/docs, /openapi.json) otomatis MATI di
      produksi — cek `https://api.[DOMAIN]/docs` → 404.
- [ ] `/api/health` tidak memuat data bisnis (hanya status/versi/waktu).
- [ ] Tidak ada SQL dari klien: semua kartu memakai query terdefinisi dan
      filter berdaftar-putih (bawaan desain; jangan menambah endpoint SQL).
- [ ] Unggahan hanya .xlsx dengan batas ukuran (berlaku saat endpoint unggah
      web dibuat; saat ini impor lewat CLI di PC server).
- [ ] Audit log berfungsi: ubah satu pengaturan alarm → muncul di tab
      Aturan Harga → Audit log.

## Rahasia & data
- [ ] `.env` TIDAK pernah di-commit ke repo (ada di .gitignore); salinan
      cadangannya disimpan terpisah di tempat aman.
- [ ] Repo publik tidak berisi data rahasia asli (folder `sample_data/`).
- [ ] Backup harian terjadwal (Task Scheduler), log backup terisi, retensi
      30 hari berjalan.
- [ ] **Uji restore** terakhir dilakukan pada tanggal: ______ (ulangi tiap
      3 bulan; prosedur di deploy/restore.md).

## Pemeliharaan
- [ ] Windows Update aktif di PC server; PC tidak dipakai browsing harian.
- [ ] Akun Windows server ber-password; layar terkunci otomatis.
- [ ] Daftar email Access ditinjau saat ada karyawan keluar/masuk.
