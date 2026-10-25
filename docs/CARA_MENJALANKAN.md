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

### Membaca tren & musiman di menu Intake Analisis

Di kartu **Penerimaan karet (kg) — biasa vs EUDR** ada blok **Analisis tren &
musiman**. Isinya: grafik total dengan garis **MA3** (rata-rata 3 bulan),
tabel MoM (**bulan ini vs bulan lalu**) dan YoY (**vs bulan sama tahun lalu**),
serta dekomposisi tren-musiman.

Dua hal yang perlu diketahui:

1. **Dekomposisi butuh minimal 24 bulan data** (idealnya 36). Kalau belum
   cukup, blok itu menjelaskan berapa bulan yang masih kurang — bukan
   menampilkan angka yang belum bisa dipercaya. MA3/MoM/YoY tetap jalan.
2. Kotak kuning **"Periksa dulu sebelum angka ini dipakai untuk perkiraan"**
   muncul sendiri bila ada bulan nol, bulan terakhir belum lengkap, pola datar
   tidak wajar, atau nama wilayah yang ejaannya tidak seragam. Baca dulu
   kotaknya sebelum memakai angka untuk perencanaan.

Nama provinsi yang beda huruf besar/kecil ("Sumatera Utara" vs "SUMATERA
UTARA") sekarang otomatis digabung jadi satu baris. Daftar ejaan yang
disatukan bisa dibuka di kartu itu.

### Menambah / mengubah vendor tanpa Excel

Buka tab **Master Vendor**. Di sana bisa menambah vendor baru, mengubah nama,
kategori, dan status, serta menghapus vendor yang belum dipakai. Kolom **Tiket**
dan **Ton kering** pada daftar menunjukkan vendor mana yang benar-benar dipakai,
jadi salah ketik kode langsung kelihatan.

Untuk banyak vendor sekaligus: klik **Unduh template** di kartu *Bulk import*,
isi di Excel, lalu unggah kembali di kartu yang sama. Kode yang sudah ada akan
**diperbarui**, bukan digandakan.

Vendor yang sudah dipakai tiket **tidak bisa dihapus** — aplikasi menolak dan
menyarankan mengubah statusnya menjadi `nonaktif`. Ini disengaja: menghapus
kode akan membuat tonase historis kehilangan pemiliknya di laporan.

## 5. Menjalankan pengujian (memastikan rumus persis Excel lama)

```powershell
python -m pytest
```

Harus tertulis `172 passed`. Pengujian mencakup semua kasus uji emas:
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

## Kalau ada tombol analisa yang bilang "Fitur ini tidak dikenali"

Gejalanya: misalnya **Margin Bridge** atau **Days of Cover** tidak mau terbuka
(muncul pesan error / "Not Found"), padahal **5W1H** jalan normal.

Artinya bukan data Anda yang salah — yang berjalan di port 8000 masih **proses
API dari sesi sebelumnya**, yaitu kode lama yang belum punya fitur baru. 5W1H
sudah ada di kode lama, karena itu ia tetap jalan; Margin Bridge dan Days of
Cover belum, karena itu ia 404.

Cara memastikan (buka di browser):

```
http://localhost:8000/api/health
```

Di situ ada daftar `fitur`. Kalau daftar itu **tidak** memuat
`margin-bridge`, `days-of-cover`, dan `jelaskan`, berarti API-nya versi lama.

Cara memperbaiki:

1. Tutup jendela hitam berjudul **"OP Margin - API"** (atau tekan `Ctrl+C` di
   jendela itu). Kalau lupa mana, jalankan saja `start-web.bat` — skrip itu
   akan menanyakan sendiri: `Tutup proses itu sekarang? [Y] ya / [N] biarkan`.
   Jawab `Y` lalu Enter.
2. Jalankan `start-web.bat` lagi. Skrip ini sekarang:
   - **menutup paksa** proses lama di port 8000 dan 5173 (termasuk proses
     induk `uvicorn --reload` yang menghidupkan ulang anaknya),
   - menjalankan API dan web,
   - **membandingkan versi** API yang menjawab dengan `VERSI.txt`. Bila beda,
     skrip menutup port sekali lagi dan menjalankan API ulang secara otomatis;
     bila tetap beda, muncul **GAGAL: ... tetap VERSI LAIN** dengan langkah
     lanjutan.
3. Di browser, muat ulang dengan **Ctrl+F5** (agar berkas lama tidak dipakai).

`start-web.bat` kini juga **menyiapkan sendiri** apa pun yang belum ada:
ruang kerja Python (`backend\.venv`), database + data awal, dan pustaka
tampilan web. Jadi pesan *"GAGAL: jalankan dulu start.bat"* tidak muncul lagi
— skrip langsung mengerjakannya.

### Kalau muncul pesan aneh seperti `'f' is not recognized`

Itu bukan salah Python atau data Anda: itu cmd.exe salah membaca baris skrip
versi lama. Versi `start-web.bat` sekarang sudah bebas dari penyebabnya
(tanpa blok kurung berlapis, tanpa `for /f`, ASCII saja, akhir baris CRLF).

Yang perlu Anda pastikan: berkas yang dijalankan memang versi terbaru —

```powershell
git pull
```

lalu jalankan `start-web.bat` lagi. Kalau masih muncul, hapus berkas
`start-web.bat` di folder itu dan `git checkout -- start-web.bat`.

## Login aplikasi: username + sandi

Login **Cloudflare Access sudah DIHAPUS** (tidak dipakai lagi). Satu-satunya
cara masuk adalah username + sandi yang tersimpan di tabel `pengguna`:

- Akun pertama dibuat otomatis saat API pertama kali start: **`admin`**,
  sandi dari `ADMIN_SANDI_AWAL` di `.env` (bawaan `admin123`).
- Pengguna lain dibuat admin lewat menu **Pengguna**.
- Lupa sandi / akun terkunci? Dari folder `backend`:

  ```powershell
  .venv\Scripts\python -m app.cli reset-sandi admin
  ```

  Perintah itu mencetak sandi baru dan mengaktifkan kembali akunnya.

Bila `.env` Anda masih menyimpan setelan lama (`AUTH_MODE=...`,
`CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`), semuanya **diabaikan** dan boleh
dihapus. Untuk membersihkannya sekaligus menyiapkan `SECRET_KEY`:

```powershell
cd backend
.venv\Scripts\python -m app.cli atur-login-lokal
```

### Bukti paling cepat: folder ini kode lama atau bukan

Pesan **"Belum login ... Cloudflare Access"** sudah **tidak ada lagi** di kode
sejak versi 0.9.1. Kalau pesan itu masih muncul, yang menjawab di port 8000
pasti kode lama. Cara membuktikannya dari folder aplikasi:

```powershell
findstr /c:"Cloudflare Access" backend\app\main.py
```

- **Ada hasilnya** → folder ini masih kode lama (belum diperbarui). Jalankan
  `perbarui-kode.bat`.
- **Tidak ada hasil** → folder sudah 0.9.1; berarti ada proses lama di port
  8000. Jalankan `start-web.bat` (sekarang menutupnya otomatis).

`diagnosa.bat` juga memeriksa hal ini dan menuliskannya di bagian [0].

### Kalau masih tidak bisa masuk: jalankan `diagnosa.bat`

Klik dua kali **`diagnosa.bat`** di folder aplikasi. Skrip itu mencetak:

1. versi kode yang ada di folder (`git log`) — memastikan `git pull` berhasil;
2. setelan `.env`, **mode login yang benar-benar dipakai**, jumlah akun dan
   status aktifnya;
3. jawaban API yang **sedang berjalan** di port 8000 (versi + mode login).

Bacanya:

| Yang tertulis | Artinya | Tindakan |
|---|---|---|
| `mode login : lokal (username-sandi)` dan API menjawab `0.9.1` + `lokal` | sudah benar | login dengan akun Anda (Ctrl+F5 dulu) |
| API menjawab `mode: nonaktif` | `AUTH_DISABLED=true` masih ada di `.env` | hapus baris itu, lalu jalankan `start-web.bat` lagi |
| API tidak menjawab / `404` di `/api/auth/mode` | prosesnya **kode lama** | tutup jendela API lama, jalankan `start-web.bat` lagi |
| bagian [2] tidak ada akun, atau sandi lupa | akun belum dibuat / sandi salah | `python -m app.cli reset-sandi admin` (dari folder `backend`) |

Bila `SECRET_KEY` belum diisi, di luar produksi aplikasi membuat kunci
sementara otomatis supaya login tetap bisa dipakai (sesi berakhir saat API
dijalankan ulang). `start-web.bat` membuang `AUTH_DISABLED` untuk jendela
API-nya, sehingga login selalu aktif saat dijalankan dari skrip itu.

## Layar "Aplikasi dan servernya beda versi"

Layar ini muncul bila **tampilan web** dan **API** memakai versi berbeda —
hampir selalu karena proses API dari folder/sesi lama masih menjawab di port
8000. Layar itu menyebutkan versi keduanya, dan (bila API-nya versi baru) juga
menampilkan **folder asal & PID** proses lama.

Perbaikan:

1. Klik kanan **`hentikan-api.bat`** → **Run as administrator**. Skrip itu
   menghentikan **service Windows** `OPMargin*` (bila aplikasi pernah dipasang
   sebagai service — service akan menghidupkan ulang API lama bila hanya
   prosesnya yang ditutup), menutup semua proses `uvicorn`/`vite`, lalu
   melaporkan apakah **port 8000 dan 5173 sudah BEBAS**. Kalau ada yang gagal
   ditutup, skrip mengatakannya (tidak diam-diam).
2. Jalankan **`start-web.bat`** dari folder aplikasi yang benar — folder yang
   `VERSI.txt`-nya berisi `0.9.1`. Tunggu tulisan **`API siap: kode 0.9.1`**.
3. Buka `http://localhost:5173`, tekan **Ctrl+F5**.

Cek cepat kapan saja: `http://localhost:8000/api/health` — nilai `versi` dan
`kode` harus `0.9.1`, dan `folder` harus menunjuk folder aplikasi Anda.

## Cara tercepat membereskan: `perbaiki.bat`

Klik dua kali **`perbaiki.bat`** (satu berkas, tidak butuh Git). Skrip itu:

1. menutup semua proses aplikasi lama (port 8000 & 5173);
2. mengunduh kode terbaru ke folder baru `..\rubber-intelligence-baru`;
3. menyalin database lama (`backend\opmargin.db`) ke folder baru — data aman;
4. menyiapkan Python + pustaka di folder baru;
5. **menyetel ulang sandi admin dan mencetak sandi barunya** di layar;
6. menjalankan `start-web.bat` dari folder baru.

Folder lama tidak dihapus dan tidak diubah. Setelah selesai, buka
`http://localhost:5173`, Ctrl+F5, lalu masuk dengan **admin** dan sandi yang
tercetak di langkah 5. `.env` sengaja **tidak** disalin, supaya tidak ada sisa
setelan lama yang mengganggu.

## Kalau folder Anda hasil UNDUHAN ZIP (bukan `git clone`)

Tanda-tandanya: di dalam folder **tidak ada** folder `.git`, path-nya seperti
`Downloads\rubber-intelligence-arena-...\`, dan `diagnosa.bat` melaporkan
*"Folder ini BUKAN hasil git clone"*.

Penting: **unduhan ZIP tidak ikut diperbarui.** Mengunduh satu-dua berkas dari
GitHub tidak memperbarui sisanya — akibatnya muncul campuran berkas baru dan
lama seperti pesan *`invalid choice: 'diagnosa'`* atau *`No module named
app.tanya_api`*. Perbaikan login yang terbaru pun tidak ikut terpakai.

Cara membereskan (pilih salah satu):

1. **Otomatis** — klik dua kali **`perbarui-kode.bat`**. Skrip itu mengunduh
   kode terbaru dari branch resmi, mengekstraknya ke folder baru di sebelah
   folder lama (`..\rubber-intelligence-terbaru`), lalu membuka foldernya.
   Folder lama tidak dihapus. Setelah itu jalankan `start-web.bat` di folder
   baru.
2. **Manual** — unduh alamat ini di browser, lalu ekstrak:

   ```
   https://github.com/boldcraftcode-ops/rubber-intelligence/archive/refs/heads/arena/18670644-rubber-intelligence.zip
   ```
3. **Paling rapi (butuh Git)** — di folder tujuan:

   ```powershell
   git clone -b arena/18670644-rubber-intelligence https://github.com/boldcraftcode-ops/rubber-intelligence.git
   ```

   Setelah itu pembaruan berikutnya cukup `git pull`.

**Data lama tidak hilang.** Bila ingin memakai data yang sudah ada, salin dua
berkas ini dari folder lama ke folder baru **sebelum** menjalankan
`start-web.bat`:

- `backend\opmargin.db` — database (data SICOM, pembelian, stok, target)
- `backend\.env` — setelan login (opsional; bila tidak ada, dibuat otomatis)

Cara memastikan folder baru benar-benar versi terbaru: lihat **`VERSI.txt`** di
akar folder (versi terbaru saat dokumen ini ditulis: **0.9.1**), atau buka
`http://localhost:8000/api/health` dan periksa `"versi"` serta `"kode"`.

## Login berhasil tetapi kembali ke form login lagi

Gejalanya: form login terisi, tombol ditekan, tidak ada pesan galat, tetapi
kembali ke form login. Di log API terlihat `POST /api/auth/login 200` lalu
`GET /api/auth/saya 401`.

Sebabnya **cookie sesi tidak terkirim**, dan itu terjadi bila:

- aplikasi dibuka **di dalam iframe** (halaman preview/embed), atau
- halaman web dan API berada di **situs berbeda**, atau
- browser memblokir cookie pihak ketiga.

Sejak versi 0.9.1 hal ini ditangani otomatis: saat login, API mengirim `token`
di badan respons; tampilan web menyimpannya dan mengirimnya lewat header
`Authorization: Bearer` sebagai **cadangan** di samping cookie. Jadi login tetap
bekerja walau cookie diblokir. Cookie (HttpOnly) tetap cara utama.

Bila masih terjadi pada versi lama:

1. Tarik kode terbaru (`perbarui-kode.bat` atau `git pull`).
2. `hentikan-api.bat`, lalu `start-web.bat`.
3. Muat ulang halaman dengan `Ctrl+F5` (hapus cache).
4. Untuk deploy beda situs, lihat `deploy/install-windows.md` bagian C
   (`COOKIE_SAMESITE=none` atau mode satu-origin `SAJIKAN_WEB=true`).

## Deploy ke internet (Fase 5)
Panduan lengkap ada di folder `deploy/`: mulai dari `deploy/install-windows.md`
(service Windows + Cloudflare Tunnel), `deploy/backup.ps1` +
`deploy/restore.md` (backup harian & uji restore), dan
`deploy/checklist-keamanan.md`. Login memakai username+sandi aplikasi
(Cloudflare Access sudah dihapus); **tunnel tetap dipakai** dan tidak terpengaruh
penghapusan Access.

Dua pilihan pemasangan:

1. **Satu-origin (disarankan).** API sekaligus menyajikan halaman web.
   Jalankan `npm run build` di `frontend`, lalu isi `SAJIKAN_WEB=true` di
   `backend/.env` dan arahkan satu hostname tunnel (mis. `app.domain-anda.com`)
   ke `127.0.0.1:8000`. Cek: `/api/health` → `"web_statistik"` berisi folder
   `dist`, bukan `null`.
2. **Terpisah.** Halaman di Cloudflare Pages/Workers, API di
   `api.domain-anda.com`. Perlu `VITE_API_URL` saat build dan
   `FRONTEND_ORIGIN` di `.env`. **Bila keduanya beda situs** (mis.
   `*.pages.dev` + `api.domain-anda.com`), wajib `COOKIE_SAMESITE=none`,
   kalau tidak login akan berhasil lalu kembali ke form karena browser menolak
   mengirim cookie lintas situs. Bukti: `/api/auth/mode` →
   `"cookie_samesite":"none"`.

## Pindah ke PostgreSQL (nanti)
Salin `.env.example` menjadi `.env` dan isi `DATABASE_URL` dengan alamat
PostgreSQL. Tidak ada kode yang perlu diubah.
