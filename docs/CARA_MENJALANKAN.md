# CARA MENJALANKAN (Fase 1 — fondasi data & rumus)

Fase 1 belum punya tampilan web; semuanya lewat perintah di terminal.
Penjelasan tiap perintah ada di bawahnya.

## Cara paling cepat (Windows): klik dua kali `start.bat`
File `op-margin\start.bat` menjalankan semuanya sekaligus:
menyiapkan Python + pustaka, membuat database, memuat data awal dari
template, menjalankan 19 unit test, lalu menampilkan contoh hasil
(ringkasan 2026, rekomendasi harga, rencana 2027). Aman diulang kapan
saja — data tidak akan berganda. Bila ingin menjalankan langkah demi
langkah secara manual, ikuti bagian di bawah ini.

## 1. Persiapan satu kali
Buka terminal (di Windows: tombol Start → ketik "PowerShell" → Enter), lalu:

```powershell
cd op-margin\backend
python -m venv .venv            # membuat "ruang kerja" Python terpisah untuk proyek ini
.venv\Scripts\activate          # mengaktifkan ruang kerja itu (muncul tulisan (.venv))
pip install -r requirements.txt # memasang pustaka yang dibutuhkan
```

Di Linux/Mac, ganti baris kedua dengan `source .venv/bin/activate`.

## 2. Membuat database dan memuat data awal

```powershell
python -m app.cli init-db
python -m app.cli import-template ..\sample_data\Template_dan_Data_Awal_OP_Margin_v3.xlsx --pengunggah nama_anda
```

- `init-db` membuat file database `opmargin.db` beserta semua tabelnya.
- `import-template` memuat seluruh data awal 2020–Okt 2026. Perintah ini juga
  langsung membangun tabel siap-pakai (mart) dan menampilkan daftar peringatan
  data (bila ada). Mengulang perintah yang sama **tidak** menggandakan data.

## 3. Melihat hasil

```powershell
python -m app.cli ringkasan 2026        # SICOM, OP Price, OP Margin, ton, target per bulan + Avg YTD
python -m app.cli rekomendasi            # harga beli maksimum hari terakhir, beserta alasannya
python -m app.cli rekomendasi --tanggal 31/08/2026
python -m app.cli rencana 2027           # perencanaan tahun depan (pengganti sheet Y27)
```

## 4. Mengimpor data (tiket, stok, pembelian, dll.)

Cara termudah: tab **Unggah Data** di aplikasi web — tarik & lepas file .xlsx
(ekspor Master Data atau file format template, boleh hanya sebagian sheet,
mis. hanya Stok_Harian). Hasil impor, baris ditolak, dan peringatan langsung
tampil. Alternatif lewat terminal:

```powershell
python -m app.cli import-tiket "C:\folder\Master Data 2026.xlsx" --pengunggah nama_anda
```

Importer otomatis mengenali format ekspor (header di baris 7) maupun format
template (header di baris 1), membuang baris subtotal, dan menampilkan
peringatan (vendor tak dikenal, Dry tidak cocok, wilayah kosong, dst.).

## 5. Menjalankan pengujian (memastikan rumus persis Excel lama)

```powershell
python -m pytest
```

Harus tertulis `119 passed`. Pengujian mencakup semua kasus uji emas:
harian 3 Jan 2026, bulan Jan/Feb 2026, Jan 2023, Mar 2020 (kurs berubah
tengah bulan), Apr 2022 (koreksi salah ketik Excel), Days/rasio stok,
dan perencanaan Jan 2027.

## 6. Halaman web input cepat harian — SICOM & kurs (Fase 2)

Cara paling cepat (Windows): klik dua kali **`start-web.bat`**. Skrip akan
membuka dua jendela (API dan tampilan web) lalu membuka browser ke
`http://localhost:5173`. Syarat: sudah menjalankan `start.bat` sekali, dan
Node.js terpasang (unduh versi LTS dari https://nodejs.org).

Secara manual (dua terminal):

```powershell
# Terminal 1 — API (hanya mendengarkan 127.0.0.1 sesuai aturan keamanan)
cd op-margin\backend
.venv\Scripts\activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — tampilan web
cd op-margin\frontend
npm install          # hanya pertama kali
npm run dev
```

Lalu buka `http://localhost:5173`. Sejak Fase 3 aplikasi punya lima tab:

- **Ringkasan** — tabel per tahun ala Excel lama (SICOM, OP Price, OP Margin,
  Ton, Target, Pencapaian, vs Target per bulan + Avg YTD sederhana &
  tertimbang), catatan koreksi Apr 2022, grafik margin antar tahun, dan
  telusur: klik angka OP Margin → hari penyusun → baris pembelian/tiket +
  unggahan asal.
- **Analisis** — kartu tonase (drill-down provinsi → kabupaten → kecamatan →
  desa), konsentrasi vendor top 5/10, bauran grade & porsi EUDR, KPI reject%,
  margin harian, margin per grade/vendor (tampil "data harga belum tersedia"
  bila Amount belum rinci). Semua kartu punya tombol "Cara dihitung" dan
  "Ekspor Excel".
- **Rekonsiliasi** — selisih yang sudah diketahui (Jul & Agu 2026) dan
  pemeriksaan harian tiket vs pembelian.
- **Kualitas Data** — kesegaran data, hari pembelian tanpa SICOM, lonjakan
  harga, rekap peringatan impor.
- **Stok** — Days, rasio, status per hari; grafik stok vs safety; daftar hari
  di bawah safety. **Stok vs Margin** — analisis hubungan (informasi, bukan
  aturan). **Aturan Harga** — rekomendasi harga beli maksimum dengan alasan,
  editor aturan berversi, parameter pabrik, audit log. **Simulasi** — geser
  SICOM/kurs/stok tanpa menyimpan. **Perencanaan** — pengganti sheet Y27,
  tertaut otomatis ke aktual. **Alarm** — daftar alarm aktif + pengaturan admin.
- **Input Harian** — form SICOM & kurs seperti Fase 2. Di halaman itu Anda bisa:
- mengisi **SICOM harian** (hari libur tidak perlu diisi — otomatis memakai
  harga terakhir) dan melihat riwayat 10 hari terakhir;
- mengisi **kurs USD/IDR** yang berlaku sejak tanggal tertentu (boleh di
  tengah bulan) dan melihat riwayat perubahan;
- setiap simpanan dicatat (siapa & kapan) dan langsung memperbarui
  perhitungan OP Margin. Menyimpan tanggal yang sama menimpa nilai lama
  dengan pemberitahuan, tidak menggandakan.

## Deploy ke internet (Fase 5)
Panduan lengkap ada di folder `deploy/`: mulai dari `deploy/install-windows.md`
(service Windows + Cloudflare Tunnel), lalu `deploy/cloudflare-pages-access.md`
(frontend + login), `deploy/backup.ps1` + `deploy/restore.md` (backup harian &
uji restore), dan `deploy/checklist-keamanan.md`.

## Pindah ke PostgreSQL (nanti)
Salin `.env.example` menjadi `.env` dan isi `DATABASE_URL` dengan alamat
PostgreSQL. Tidak ada kode yang perlu diubah.
