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

## 3b. Menu samping sekarang berbentuk pohon (grup)

Menu kiri dikelompokkan supaya tidak perlu membaca 16 baris sekaligus:

- 📊 **Analitik** — Margin Performance, Intake Analisis, Stok, Stok vs Margin
- 💰 **Harga & Perencanaan** — Aturan Harga, Simulasi, Perencanaan
- 🛡️ **Pengawasan & Kontrol** — Alarm, Rekonsiliasi, Kualitas Data, Kepatuhan vendor sampling
- 🗂️ **Master Data** — Master Vendor, Grade & Harga
- 📥 **Input Data** — Input Harian, Unggah Data
- ⚙️ **Administrasi** — Database, Pengguna (hanya terlihat oleh admin)

Klik **baris grup** untuk membuka/menutup isinya (tanda `▶` berputar). Pada
pemakaian pertama semua grup terbuka, dan pilihan buka/tutup Anda diingat di
browser. Kalau sebuah halaman dibuka dari tempat lain (mis. tombol di Margin
Performance), grupnya otomatis terbuka sehingga menu tidak terlihat kosong.
Di layar Bahasa Inggris nama grupnya: *Analytics, Pricing & Planning,
Monitoring & Control, Master Data, Data Entry, Administration*.

**Tombol Refresh pada kartu berperiode.** Di **Intake Analisis** dan
**Margin Performance**, tombol **Refresh periode ini** berada tepat di samping
kontrol periode kartu itu (Dari/Sampai bulan, pilihan tahun, atau tombol tahun),
bukan lagi di kanan header kartu. Jadi tombol yang ditekan jelas memuat ulang
data untuk periode yang baru dipilih pada kartu yang sama. Kartu yang memang
tidak punya kontrol periode tetap memakai tombol **Refresh** di headernya.
Mengubah periode tidak otomatis memanggil API; tekan Refresh di sampingnya
untuk mengambil data terbaru. **Pengecualian:** kartu **Angka kunci Margin
Performance** memakai query tersendiri yang aktif sejak halaman dibuka, jadi
datanya **auto tampil** dan kartu itu **tidak punya tombol Refresh**. Kartu
lain tetap memakai Refresh seperti di atas.

## 3c. Membaca menu Stok vs Margin

Isi halaman ini **informasi, bukan aturan**: setiap titik = satu bulan.

1. **Mendatar** = rasio stok ÷ safety. `1,0` = stok tepat di batas aman,
   `0,5` = tinggal separuh batas aman.
2. **Menegak** = OP Margin bulan itu (US¢/kg). Makin ke atas, makin bagus.
3. Lihat **bentuk awannya**, bukan satu titik. Miring naik = bulan berstok
   tebal cenderung bermargin lebih baik; menyebar tanpa arah = tidak ada
   hubungan.

Garis putus-putus tegak = batas 50% dan 80% safety; garis putus-putus mendatar
= margin rata-rata periode; garis tren = arah umum. **Pilih tahun** di bagian
atas untuk memeriksa apakah hubungannya sama seperti gabungan semua tahun —
pada data contoh, 2024–2025 kuat (0,88 dan 0,77) tetapi 2023 dan 2026 nyaris
tidak ada (0,07 dan 0,11), sehingga angka gabungan 0,42 **tidak boleh dipakai
sebagai aturan**. Halaman akan menuliskan peringatan itu sendiri.

Tabel di bawah grafik menjawab tiga hal dengan angka: margin rata-rata per
kelompok stok (tipis/sedang/tebal), jumlah bulan di tiap kelompok, dan korelasi
per tahun. **Ekspor Excel** menghasilkan dua sheet: Data bulanan dan Ringkasan.

## 3d. Membereskan alarm

Menu **Alarm** sekarang menunjukkan **ke mana harus pergi**. Tiap alarm punya
tombol **"Buka <halaman> →"** dan 2–3 langkah perbaikan.

| Kelompok | Contoh | Perbaikan ada di |
|---|---|---|
| Stok & operasional | stok di bawah safety | **Stok & Days** (atau perbarui stok lewat Unggah Data) |
| Data belum masuk | SICOM/kurs/stok/tiket terlambat | **Input Harian** (SICOM & kurs) · **Unggah Data** (stok & tiket) |
| Selisih angka | tiket vs pembelian / vs Excel lama | **Rekonsiliasi** |
| Harga beli | harga aktual di atas maksimum | **Aturan Harga** |
| Margin vs target | margin bulan berjalan di bawah target | **Margin Performance** (lalu Margin Bridge) |

Alarm **padam sendiri** setelah datanya benar dan evaluasi ulang dijalankan —
tidak ada tombol "hapus alarm". Kalau data memang belum tersedia (mis. terbitan
SICOM belum keluar), jangan mengisi angka kira-kira; pertimbangkan mengubah
**ambang** alarm di kartu "Pengaturan alarm (admin)".

## 3e. Mengisi stok & pembelian harian (tanpa Excel)

Menu **Input Harian** sekarang punya panel **"Kesegaran data hari ini"**:
5 kartu sumber (SICOM, Kurs, Stok, Tiket, Pembelian) berisi tanggal terakhir,
umur hari, dan tanda ⚠ bila lewat batas. Di bawahnya ada tombol tanggal yang
belum terisi — klik untuk langsung mengisi formulirnya.

**Stok harian** — satu angka per hari:
1. pilih tanggal,
2. pilih jenis: **Total (semua grade)** atau satu grade,
3. isi jumlah + pilih satuan **ton** atau **kg** (disimpan dalam kg),
4. simpan. Setelah itu langsung tampil stok, safety, rasio, dan days.

**Pembelian harian** — qty kering + amount:
1. pilih tanggal dan **tingkat**: *Total hari* / *per grade* / *per vendor* /
   *per tiket*,
2. isi qty kering (kg) dan amount (Rp),
3. simpan; harga Rp/kg, US¢/kg, dan margin harian dihitung otomatis memakai
   kurs & SICOM yang berlaku.

Aturan penting:
- **mengisi ulang tanggal yang sama = koreksi** (menimpa baris itu, nilai lama
  dilaporkan). Jadi salah ketik tidak perlu dihapus manual.
- **jangan mencampur** "Total hari" dengan "per grade/vendor/tiket" pada
  tanggal yang sama — sistem akan menolak supaya tidak terhitung dua kali.
- grade & vendor harus sudah ada di Master Grade / Master Vendor.
- setiap simpanan tercatat (siapa, kapan) dan langsung memperbarui OP Margin,
  Days of Cover, dan alarm.

## 3f. Mengunggah Excel: pratinjau dulu, baru disimpan

Tab **Unggah Data** sekarang bekerja dalam **tiga langkah**. Tidak ada satu
baris pun yang masuk database sebelum Anda menekan tombol konfirmasi.

1. **Pilih file** — tarik & lepas file .xlsx (atau klik untuk memilih). Bisa
   ekspor *Master Data* tiket, bisa juga file format template — boleh hanya
   sebagian sheet, mis. hanya `Stok_Harian`.
2. **Periksa pratinjau** — muncul dua angka: berapa baris **siap disimpan**
   dan berapa baris **bermasalah**. Di bawahnya ada tabel per sheet + nomor
   baris + alasannya.
   * Baris bermasalah dikumpulkan sebagai **data mismatch**. Tekan
     **⬇ Unduh Excel data mismatch** untuk mengunduhnya: isinya baris asli
     (utuh), ditambah tiga kolom di kanan — `KODE_MASALAH`,
     `ALASAN_DITOLAK`, `BARIS_DI_FILE_ASLI`. Perbaiki nilainya, hapus ketiga
     kolom itu, lalu unggah ulang file tersebut. Baris yang sudah benar tidak
     perlu diulang.
   * Ada juga bagian **catatan pemeriksaan** (mis. vendor tak dikenal, Dry
     tidak cocok) — baris seperti ini **tetap dimuat**, hanya perlu dicek.
3. **Konfirmasi simpan ke database** — baru di sini data ditulis, OP Margin /
   Days of Cover / alarm dihitung ulang, dan unggahan tercatat (siapa, kapan,
   file apa). Tombol **Batalkan, jangan simpan** membuang pratinjau tanpa
   mengubah apa pun.

**Progress bar.** Selama proses berjalan muncul bilah merah + tulisan tahap
(*Mengunggah file… 45%* → *Memeriksa isi file (validasi)…* → *Menyimpan ke
database…*). Biarkan halaman terbuka sampai bilah penuh.

Pratinjau berlaku **60 menit**. Kalau kedaluwarsa, cukup unggah ulang filenya
(tidak ada data yang perlu dibereskan). Mengonfirmasi pratinjau yang sama dua
kali ditolak — data tidak akan tergandakan.

## 3g. Memasang di PC tanpa internet (luring)

Aplikasi **tidak perlu internet saat dipakai** (tidak ada CDN, font luar, atau
telemetri). Internet hanya dibutuhkan sekali untuk mengunduh pustaka. Karena
itu pemasangan di PC luring dilakukan dua tahap dengan dua skrip.

### Tahap 1 — di PC yang ADA internet (sekali saja)

1. Pasang **Python 3.11.x (64-bit)** dan **Node.js LTS** di PC ini. Python 3.11.6 juga kompatibel; angka patch tidak harus sama.
2. Klik dua kali **`ambil-bahan-offline.bat`**. Skrip ini:
   - mengunduh semua pustaka Python sebagai berkas *wheel* ke
     `bahan-offline\wheelhouse` untuk Windows 64-bit dan versi Python yang
     dipakai PC itu (boleh dipaksa: `ambil-bahan-offline.bat 3.11`);
   - memasang pustaka tampilan lalu membangunnya (`npm install`,
     `npm run build`), hasilnya disalin ke `bahan-offline\dist`;
   - menulis `bahan-offline\BACA-SAYA.txt` dan menampilkan ukuran folder.
3. Unduh juga installer **Python 3.11.x “Windows installer (64-bit)”** dari
   python.org — yang dibawa berkas `.exe` ini, **bukan** *web installer*.
4. ZIP seluruh folder aplikasi (termasuk `bahan-offline`), lalu salin ke PC
   tujuan lewat USB atau jaringan lokal.

### Tahap 2 — di PC TANPA internet

1. Pasang Python dari berkas `.exe` tadi; centang **“Add python.exe to PATH”**.
   Versinya harus **sama** dengan yang dipakai saat membuat wheel.
2. Klik dua kali **`start-offline.bat`**. Skrip ini menyiapkan sendiri: ruang
   kerja Python, pustaka dari `bahan-offline\wheelhouse` (`pip install
   --no-index`), `backend\.env`, database + data awal, lalu menyalin
   `bahan-offline\dist` ke `frontend\dist`.
3. API dijalankan dengan `SAJIKAN_WEB=true`, jadi **satu alamat saja**:
   `http://localhost:8000` — tanpa Node.js, tanpa port 5173.
4. **Node.js tidak perlu dipasang** di PC ini.

### Yang perlu diketahui

| Hal | Cara |
|---|---|
| Bisa dibuka dari komputer lain di jaringan | Buat berkas kosong bernama `jaringan-lan.txt` di folder aplikasi, lalu jalankan ulang. Alamatnya `http://ALAMAT-IP-PC:8000`; izinkan port 8000 di Windows Firewall. |
| Login dimatikan sementara | Buat berkas `tanpa-login.txt` (sama seperti mode biasa); hapus untuk mengaktifkan lagi. |
| Memperbarui aplikasi | Ulangi Tahap 1 di PC berinternet, lalu salin lagi kode terbaru **beserta** `bahan-offline`. Jangan pakai `git pull` / `perbarui-kode.bat` di PC luring. |
| Data & cadangan | Sama seperti biasa: `backend\opmargin.db` (SQLite) + folder `unggahan\`. Tidak berubah karena mode luring. |
| Versi Python yang cocok | Paket yang sudah diuji memakai **Python 3.11, 64-bit**. Python 3.11.6 cocok; yang penting angka mayor.minor `3.11` dan arsitektur 64-bit. |
| Mengganti versi Python | Wheel terikat versi mayor.minor dan arsitektur. Buat ulang bahan dengan versi tujuan, mis. `ambil-bahan-offline.bat 3.11`, lalu salin lagi. |

### Kalau ada yang gagal

| Pesan | Artinya | Perbaikan |
|---|---|---|
| `folder bahan-offline\wheelhouse tidak ada` | Folder bahan belum ikut tersalin | Salin seluruh folder aplikasi termasuk `bahan-offline` |
| `GAGAL: Python yang dipilih tidak cocok dengan bahan offline` | Launcher memilih versi/arsitektur lain, atau lingkungan lama dibuat dengan Python berbeda | Pastikan Python 3.11 64-bit terpasang. Skrip terbaru memilih `py -3.11` dan membuat ulang `backend\.venv` yang salah; database tidak dihapus. |
| `GAGAL memasang pustaka dari bahan-offline\wheelhouse` | Versi Python/arsitektur beda dengan wheel, atau folder wheel tidak lengkap | Buat ulang bahan dengan `ambil-bahan-offline.bat 3.11` di PC berinternet lalu salin folder `bahan-offline` lengkap |
| `GAGAL: tampilan web belum ada` | `bahan-offline\dist` tidak ada | Jalankan `ambil-bahan-offline.bat` di PC berinternet |
| `PERINGATAN: API belum menjawab` | Port 8000 dipakai program lain, atau API error | Baca jendela “OP Margin - API”; lihat juga `diagnosa.bat` |
| `PERINGATAN: API menjawab, tetapi versinya bukan ...` | Proses lain menjawab di port 8000 | Tutup program itu, jalankan `start-offline.bat` lagi |

### Bila ingin melakukannya manual (tanpa skrip)

```powershell
# di PC berinternet
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip download -r requirements.txt -d ..\bahan-offline\wheelhouse --only-binary=:all: --platform win_amd64 --python-version 3.11
cd ..\frontend
npm install
npm run build

# di PC tanpa internet (setelah Python dan wheel disalin)
cd backend
py -3.11 -m venv .venv
.venv\Scripts\pip install --no-index --find-links ..\bahan-offline\wheelhouse -r requirements.txt
.venv\Scripts\python -m app.cli init-db
.venv\Scripts\python -m app.cli import-template "..\sample_data\Template_dan_Data_Awal_OP_Margin_v3.xlsx"
set SAJIKAN_WEB=true
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 3h. Memutuskan selisih di Rekonsiliasi

Pada kedua kartu **Rekonsiliasi**, baris yang berselisih memiliki dropdown
**"Data mana yang benar?"**:

- kartu **Selisih yang sudah diketahui**: pilih **Tiket** atau **Excel lama**
  untuk Jul/Agu 2026;
- kartu **Pemeriksaan harian**: pilih **Dry tiket** atau **Qty pembelian**
  untuk tanggal yang berselisih lebih dari 1 kg.

Isi **Alasan revisi** bila perlu, lalu tekan **Simpan revisi**. Setelah
tersimpan, baris **tidak lagi menampilkan form besar**: formatnya kembali
ringkas seperti baris lain, kolom **Selisih** memakai nilai efektif (`0`) dengan
tanda kecil **Direvisi**, dan kolom **Status/Keputusan** memakai badge hijau
**✓ Direvisi · Histori** plus nilai yang dipakai, pembuat, dan waktu. Selisih
asli tetap menjadi histori di tooltip, ekspor Excel, dan audit log, bukan lagi
angka besar yang dicoret di sel utama.

**Data tiket/pembelian/Excel asli tidak diubah**; yang tersimpan adalah
keputusan pada tabel `rekonsiliasi_koreksi` plus jejak di audit log. Karena itu
keputusan tetap bisa diganti lewat tombol kecil **Revisi** (form hanya muncul
saat tombol itu ditekan, lalu bisa ditutup) atau dikembalikan ke kondisi semula
lewat tombol kecil **Batal**. Hanya **admin** yang bisa menyimpan/membatalkan;
pengguna lain tetap bisa membaca statusnya tanpa tombol aksi.

Efek keputusan:

1. Baris Rekonsiliasi dianggap cocok dan alarm `SELISIH_REKONSILIASI` untuk
   baris itu padam.
2. Ekspor Excel `rekonsiliasi.xlsx` memuat kolom sumber dipakai, selisih
   setelah revisi, pembuat, waktu, dan alasan.
3. Untuk Jul/Agu 2026, sumber yang dipilih juga menjadi **referensi intake**
   pada kartu **RM Stock – Intake vs Pricing**. Memilih Excel lama mengubah
   angka intake bulanan itu ke nilai Excel; memilih Tiket memakai angka
   referensi tiket. Modul lain tidak diubah.

## 3i. Kepatuhan vendor sampling

Menu **Pengawasan & Kontrol → Kepatuhan vendor sampling** membaca workbook
`Laporan_Monitoring_Vendor_RM_Purchasing (1).xlsx` yang disalin dari GitHub ke
akar repo. Delapan sheet di dalamnya dipasangkan otomatis menjadi empat
periode: **Agustus, September, Oktober, November 2026**; setiap periode punya
satu sheet `Log Monitoring ...` dan satu sheet `Summary ...`.

Halaman menyediakan:

- pilihan periode, pencarian vendor/catatan, tombol **Refresh**, dan
  **Ekspor Excel** untuk periode aktif (sheet `Summary` + `Log Monitoring`);
- kartu angka kunci: Total kunjungan, Tepat waktu, Terlambat, Tanpa data waktu,
  dan % Tepat waktu;
- tabel perbandingan empat bulan, tabel `Summary` per vendor, serta tabel log
  detail mengikuti jumlah kolom aslinya (16 kolom untuk Agu/Sep, 19 kolom
  untuk Okt/Nov).

Data **ditampilkan apa adanya** dari workbook melalui
`GET /api/kepatuhan-vendor-sampling`. Tidak ada tabel database, unggahan,
perhitungan ulang, atau koreksi otomatis. Perlu diperhatikan: header log
menulis *"Min. 30 menit"*, tetapi formula yang tersimpan memakai ambang
**40 menit** dengan arah yang berbeda — Agu/Sep `selisih ≥ 40 = Tepat Waktu`,
Okt/Nov `selisih ≥ 40 = Terlambat`. Perbedaan itu sengaja dijelaskan di layar
dan tidak diam-diam diseragamkan.

## 3j. Quick-fill koreksi intake (sejak 07/11/2026)

Di menu **Data Intake Details — Penerimaan Karet**, setelah filter diterapkan,
centang beberapa baris pada kolom paling kiri. Tombol **Pilih semua baris di
halaman ini** memilih 50 baris yang sedang tampil; pilihan tetap tersimpan saat
berpindah halaman, tetapi dibersihkan bila filter atau pencarian diubah. Panel
**Quick-fill koreksi intake** lalu muncul.

Isi **satu kolom** yang sama untuk semua baris terpilih — 17 kolom operasional
yang sama dengan modal Edit, termasuk tanggal, kode/nama supplier, kendaraan,
grade, berat/DRC, wilayah, Bin, dan Location. Kolom opsional bisa dikosongkan
lewat checkbox **Kosongkan nilai**; `Tanggal tiket` dan `Kode supplier` wajib
diisi sehingga tidak bisa dikosongkan. Untuk kolom wilayah, ketik nama persis
sesuai referensi **SCDF** karena validasi dilakukan per baris terhadap induk
wilayah yang sudah tersimpan.

Tekan **Pratinjau** dulu. Endpoint `POST /api/intake/quick-fill/pratinjau`
menghitung diff `sebelumnya → sesudah` per baris dan menolak baris yang tidak
valid tanpa menyimpan apa pun. Bila semua valid, di **bagian bawah kartu hasil
pratinjau** muncul blok hijau **Konfirmasi pratinjau** berisi tombol
**Konfirmasi & terapkan X perubahan** dan **Batalkan pratinjau**. Klik tombol
konfirmasi, lalu pilih **OK** pada dialog browser. Token pratinjau berlaku 15
menit. `POST /api/intake/quick-fill/terapkan` menyimpan **semua baris atau tidak
ada** dalam satu transaksi; token sekali pakai dan pendaftaran ditolak bila ada
baris yang berubah sejak pratinjau. Endpoint ini **admin-only** bila login lokal
aktif. Bila status pratinjau `ada_galat`, blok konfirmasi tidak muncul: perbaiki
baris yang ditolak lalu pratinjau ulang.

Setiap baris dicatat di audit log dengan aksi `ubah_massal` dan diff
`sebelumnya`/`sesudah`; mart dan alarm disegarkan sekali di akhir. Yang sengaja
tidak berubah: `ticket_no`, `line_seq`, `asal_getah`, `source_fingerprint`,
`unggahan_id`, `peringatan`, `Pembelian`, `RawUnggahan`, dan `RawBaris`. Tidak
ada tabel database baru. Quick-fill ditujukan untuk nilai yang seragam;
koreksi yang berbeda-beda per baris kini memakai alur **Excel diff
pratinjau + konfirmasi** di §3l.

## 3k. Bar intake pada peta provinsi (sejak 08/11/2026)

Buka **Intake Analisis**, lalu kartu **Sebaran Intake per Provinsi Indonesia**
dan pilih lapisan **Intake tercatat**. **Opsi centang `Pakai grafik bar`**
(bawaan: dicentang) memilih **pakai grafik bar atau tidak**. Centang aktif
berarti bar dipakai; centang kosong berarti tanpa grafik bar. Label kecil di
bawah checkbox menegaskan keadaan yang sedang dipilih. Saat dicentang,
setiap provinsi yang punya `kg_total > 0` dan namanya cocok dengan batas peta
mendapat satu **bar oranye vertikal** di titik tengah daratan terbesarnya. Titik
bar dihitung dari geometri `indonesia-provinsi.geojson`, bukan koordinat yang
diketik manual, sehingga bar tetap mengikuti bentuk peta bila berkas peta
diganti. Titik kecil putih di kaki bar menandai provinsi yang dimaksud.

Tinggi bar memakai **skala logaritmik** relatif terhadap intake terkecil dan
terbesar pada periode terpilih supaya provinsi bernilai kecil tidak hilang;
warna choropleth biru tetap memakai skala warna lamanya. Arahkan kursor ke
provinsi untuk membaca angka Dry yang pasti. Kosongkan centang **Pakai grafik
bar** bila ingin **tanpa grafik bar**, yaitu peta warna saja; legenda berubah
menjadi **Grafik bar dimatikan** dan catatan kaki menjelaskan cara
mengaktifkannya kembali. Bar **tidak** muncul pada lapisan **Sentra
produksi**, dan provinsi yang belum cocok dengan batas peta tetap tercantum di
panel **Belum terpetakan ke batas peta** tanpa bar. Tidak ada endpoint, tabel,
atau agregasi backend yang berubah.

## 3l. Excel diff pratinjau + konfirmasi di Data Intake Details (sejak 08/11/2026)

Di menu **Data Intake Details — Penerimaan Karet**, setelah filter aktif muncul
panel **Excel diff koreksi intake**. Alurnya:

1. Klik **Unduh Excel baris filter ini**. File `.xlsx` berisi sheet **Koreksi**
   dengan `ID`, `Ticket No`, `Baris`, dan **17 kolom operasional** yang sudah
   terisi nilai lama sesuai database (maksimal 500 baris). Tombol **Unduh
   template kosong** hanya untuk melihat format; jangan langsung dipakai
   karena sel kosong diartikan menghapus nilai opsional.
2. Ubah sel yang perlu pada Excel. **Biarkan nilai lama** bila tidak berubah;
   **kosongkan sel** untuk menghapus nilai opsional. Jangan mengosongkan
   `Tanggal tiket` atau `Kode supplier`. Jangan mengubah `ID`, `Ticket No`,
   dan `Baris`.
3. Unggah file itu lewat **File koreksi .xlsx**, lalu tekan **Pratinjau**.
   `POST /api/intake/excel-diff/pratinjau` membaca sheet **Koreksi**,
   mencocokkan header (nama label Indonesia maupun kode kolom), memeriksa
   identitas tiket, memvalidasi `IntakeUbah` dan referensi **SCDF** per baris,
   lalu menampilkan diff **sebelumnya → sesudah** per sel. Baris yang ditolak
   ditampilkan dengan alasannya; **belum ada data tersimpan** dan token tidak
   dibuat bila ada galat. Bila tidak ada nilai berubah, statusnya **kosong**.
4. Bila status **siap**, scroll ke blok hijau **Konfirmasi pratinjau** di bawah
   tabel diff. Klik **Konfirmasi & terapkan X perubahan**, lalu pilih **OK** pada
   dialog browser. `POST /api/intake/excel-diff/terapkan` menyimpan **semua
   perubahan atau tidak ada** dalam satu transaksi, mencatat audit
   `ubah_massal` per baris dengan penanda `sumber: excel` dan `nama_file`, lalu
   menyegarkan mart dan alarm sekali di akhir.
5. **Batalkan pratinjau** memakai `DELETE /api/intake/excel-diff/pratinjau/{token}`.
   Token di memori proses, berlaku **15 menit**, sekali pakai, dan hangus bila
   data berubah sejak pratinjau sehingga permintaan ditolak `409`.

`ticket_no`, `line_seq`, `asal_getah`, `source_fingerprint`, `unggahan_id`,
`peringatan`, `Pembelian`, `RawUnggahan`, dan `RawBaris` tetap tidak diubah.
Tidak ada tabel database baru. Endpoint lama `/api/unggah/pratinjau` tidak
dipakai; Quick-fill, Edit/Hapus per baris, filter wajib, dan 50 baris per
halaman tetap berjalan seperti sebelumnya. Hanya **admin** yang dapat
membuat pratinjau, menerapkan, atau membatalkannya.

## 3m. Deteksi salah ketik SCDF di Supplier Actor Details (sejak 08/11/2026)

Pada menu **Traceability → Supplier Actors**, klik nama supplier, lalu di kartu
**Sourcing locations from Asal Getah** tekan **Edit**. Di dalam mode Edit ada
dua panel yang berbeda: **Rekomendasi dari intake tahun sebelumnya** (pola
pembelian terdahulu) dan **Deteksi potensi salah ketik dari SCDF**. Panel
kedua memanggil `GET /api/traceability/actors/{kode}/origin-typo-check` dan
hanya membandingkan ejaan **District** serta **Sub-district** sumber dengan
nama resmi pada referensi SCDF. Kabupaten/Kota sumber tidak ditebak salah
ketik; nilainya tetap dipakai sebagai induk perbandingan.

Perbandingan membakukan huruf, spasi, underscore, tanda baca, dan awalan umum
seperti `Gampong`, `Keuchik`, `Desa`, serta `Kecamatan`. Jadi `D U M A I`,
`GAM[PONG REUSAK`, atau `KEUCHIK BINTAH` dapat dibandingkan dengan ejaan SCDF
yang lebih ringkas. Nama pendek memakai ambang kemiripan lebih tinggi supaya
tidak banyak peringatan kebetulan. Bila pasangan District + Sub-district sudah
persis ada pada SCDF untuk induk sumber, statusnya **`cocok`** dan tidak ada
peringatan. Bila ditemukan ejaan mirip, panel menampilkan kandidat
`Kabupaten/Kota · District · Sub-district`, skor kemiripan, dan rincian skor
per level.

Tombol **Pakai** hanya mengisi dropdown District/Sub-district; data **belum
tersimpan** sampai tombol **Simpan** diklik. Skor kemiripan bukan probabilitas
dan bukan vonis bahwa lokasi itu pasti benar. Bila kandidat berada di
Kabupaten/Kota SCDF lain, UI menandai **Induk SCDF berbeda** dan menyediakan
**Kembali ke induk sumber**. Pemetaan lintas induk tetap koreksi terkontrol:
`PUT /api/traceability/actors/{kode}/origin-correction` menerima
`target_kabupaten_norm`, mencatat audit, berlaku untuk semua tiket dengan
kombinasi lokasi sumber yang sama, dan **tidak mengubah intake asli**. Status
`tidak_ada_kandidat`, `referensi_kosong`, dan `sumber_tidak_lengkap` juga
dijelaskan di panel, bukan diubah menjadi tebakan otomatis.

Endpoint rekomendasi historis, dropdown District/Sub-district SCDF, **Hapus
pemetaan**, ekspor, dan impor workbook belum termapping tetap berjalan seperti
sebelumnya. Tidak ada tabel database baru. Health menambah fitur
`traceability-scdf-typo`.

## 4. Mengimpor data (tiket, stok, pembelian, dll.)

Selain lewat tab **Unggah Data**, impor bisa dijalankan dari terminal
(langsung masuk database, tanpa pratinjau):

```powershell
python -m app.cli import-tiket "C:\folder\Master Data 2026.xlsx" --pengunggah nama_anda
```

Importer otomatis mengenali format ekspor (header di baris 7) maupun format
template (header di baris 1), membuang baris subtotal, dan menampilkan
peringatan (vendor tak dikenal, Dry tidak cocok, wilayah kosong, dst.).

### Membaca tren & musiman di menu Intake Analisis

Di kartu **Penerimaan karet (kg) — biasa vs EUDR** ada tombol **📈 Analisis
tren & musiman** (letaknya rata kanan di baris filter, sama seperti tombol
Margin Bridge di halaman Margin Performance). Tombol itu membuka panel berisi
grafik total dengan garis **MA3** (rata-rata 3 bulan),
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

Di kartu yang sama ada tombol kedua, **📊 Analisis deskriptif & komposisi**.
Dipakai kalau ingin tahu: wilayah/vendor mana yang paling besar porsinya,
siapa saja yang bersama-sama menyumbang 80% volume (kelas A/B/C), dan berapa
porsi karet EUDR — total maupun per bulan, untuk memantau target kepatuhan.
Dimensinya bisa diganti di dalam panel (provinsi, vendor, grade, kabupaten).

### Menambah / mengubah vendor tanpa Excel

Buka tab **Master Vendor**. Di sana bisa menambah vendor baru, mengubah nama,
kategori, dan status, serta menghapus vendor yang belum dipakai. Kolom **Tiket**
dan **Ton kering** pada daftar menunjukkan vendor mana yang benar-benar dipakai,
jadi salah ketik kode langsung kelihatan.

**Profil pemasok (sejak v0.10.0).** Selain kode, nama, kategori, dan status,
tiap vendor menyimpan tiga informasi tambahan — semuanya **boleh kosong**:

| Isian | Keterangan |
|---|---|
| **Alamat** | alamat lengkap vendor (boleh dua baris) |
| **Contact person** | nama orang yang dihubungi; nomor HP boleh ditulis di situ, mis. `Budi — 0812-1111-2222` |
| **Klasifikasi** | **Small holder**, **Small estate**, atau **Rubber trader** |

Klasifikasi dipilih dari daftar (tidak diketik bebas) di layar. Saat impor
Excel, ejaan lain yang lazim tetap diterima — `Smallholder`, `small-holder`,
`Kebun Rakyat`, `trader`, `Pedagang` — tetapi ejaan yang tidak dikenal
**ditolak per baris** dengan alasan yang menyebut tiga pilihan itu, dan baris
lain tetap masuk. Klasifikasi sengaja tidak ditebak: angka komposisi pemasok
(kebun rakyat vs kebun besar vs pedagang) hanya berguna kalau isinya benar.

Di atas daftar ada baris **Komposisi** (jumlah tiap klasifikasi + yang belum
diisi) dan saringan **Klasifikasi**, sehingga bisa langsung dilihat berapa
banyak pemasok tiap jenis. Kotak **Cari** sekarang juga menelusuri alamat,
contact person, dan klasifikasi.

**Sourcing type di Supplier Actors (sejak v0.11.2).** Kolom **Sourcing types**
pada tab Supplier Actors (menu Traceability) diisi langsung lewat dropdown di
setiap baris: **Direct Smallholder**, **Indirect Smallholder**, atau **Own
Plantation**. Pilihan tersimpan begitu dipilih, tercatat di audit log, dan
muncul di detail supplier serta sheet `Supplier Actors` pada ekspor Excel.
Ini **field terpisah** dari Klasifikasi Master Vendor di atas — mengisi
sourcing type tidak mengubah Small holder / Small estate / Rubber trader, dan
bila sourcing type dikosongkan, kolom kembali memakai klasifikasi lama sebagai
fallback. Nilai di luar ketiga pilihan ditolak dengan pesan yang menyebut
pilihan yang sah.

**Supplier class berbasis intake (sejak v0.11.2).** Kotak **Supplier class** di
detail Supplier Actors bukan lagi berasal dari master: kelasnya dihitung dari
**Dry (MT) per supplier per bulan** dengan batas **≥ 1.500 = SS, ≥ 1.000 = S,
≥ 500 = A, ≥ 250 = B, ≥ 100 = C, < 100 = D**. Kotak Kpi menampilkan **kelas
tertinggi** yang dicapai pada periode terpilih (tanpa tabel kelas tiap
bulan). Ringkasan jumlah *supplier-bulan* per kelas **tidak ditampilkan di
Traceability**, melainkan sebagai kartu paling atas pada menu **Master
Vendor**; kartu itu otomatis memakai tahun intake terbaru. Ringkasan hanya
menghitung kode yang terdaftar di Master Vendor —
kode yang hanya muncul di tiket intake tetap punya kelas pada detailnya, dan
jumlahnya ditampilkan terpisah agar tidak hilang. Kelas dihitung dari nilai
sebelum dibulatkan, tidak disimpan, dan tidak bisa diisi manual.

**Tree node view (sejak v0.11.2, data asli sejak 07/11/2026).** Di menu
**Traceability**, tepat di sebelah tab **Supplier Actors**, ada tab **Tree node
view**. Diagramnya kini memakai **data asli** dari endpoint
`GET /api/traceability/tree`: `tiket_baris` + **Master Vendor** + **Master
Collector**, mengikuti filter tahun/periode/supplier/EUDR/LATEX pada halaman.
Bentuknya tetap **Pabrik → T1 vendor → T2 kolektor** dengan node lingkaran,
garis lengkung, dan warna per tier: pabrik hijau tua, T1 biru, T2 oranye.
Bawaannya vertikal dari atas ke bawah; tombol **Arah** mengubahnya menjadi
horizontal kiri → kanan. Label tiap node memuat kode/nama dan volume **Dry
(kg)**, sedangkan ketebalan garis mengikuti volume jalur.

**Kode tier tidak ditukar: T1 = vendor, T2 = kolektor.** Pabrik hanya simpul
akar visual. Klik node **T1** untuk menyorot semua **T2** di bawahnya; klik
lagi atau tekan **Reset sorotan** untuk kembali. Dropdown **T1** membatasi
jumlah vendor terbesar yang ditampilkan (4/8/12/semua) supaya pohon tetap
terbaca; sisa vendor dilaporkan di layar. Volume T2 berasal dari lintasan
`_supply_chain_lanes`, jadi tidak digandakan ketika beberapa kolektor cocok.
Sebagian volume T1 dapat langsung masuk tanpa kolektor tercatat; jumlahnya
ditampilkan sebagai catatan. Data ini tidak mengubah tabel Supplier Actors,
lane detail, SCDF, atau perhitungan modul lain.

Di Excel, tiga kolom baru ada di kanan: `Alamat`, `Kontak_Person`,
`Klasifikasi`. Mengosongkan selnya berarti **tidak diubah** (bukan dihapus) —
sama seperti Kategori — supaya file yang hanya berisi kode + nama tidak
menghapus profil yang sudah diisi lewat layar. Untuk benar-benar mengosongkan,
pakai tombol **ubah** di layar lalu kosongkan isiannya.

Untuk banyak vendor sekaligus: klik **Unduh template** di kartu *Bulk import*,
isi di Excel, lalu unggah kembali di kartu yang sama. Kode yang sudah ada akan
**diperbarui**, bukan digandakan.

Vendor yang sudah dipakai tiket **tidak bisa dihapus** — aplikasi menolak dan
menyarankan mengubah statusnya menjadi `nonaktif`. Ini disengaja: menghapus
kode akan membuat tonase historis kehilangan pemiliknya di laporan.

### Master Collector (sejak v0.11.0)

Menu **Master Collector** ada di grup **Master Data**. Collector adalah
perorangan yang harus terafiliasi ke satu vendor yang sudah terdaftar. Data
meliputi **Kode kolektor**, **Nama kolektor**, **NIK**, **No HP**, **Afiliasi
Vendor**, serta wilayah operasional berupa **Provinsi → Kabupaten/Kota → Desa**.
Wilayah diisi pada tiga kotak terpisah agar mudah dicari dan difilter.

Kode kolektor dan nama wajib diisi; afiliasi vendor wajib dipilih. NIK boleh
kosong, tetapi bila diisi harus tepat 16 angka dan tidak boleh sama dengan NIK
collector lain. NIK disimpan sebagai teks agar tidak berubah format. Vendor
yang masih memiliki collector terafiliasi tidak dapat dihapus; pindahkan
afiliasi atau hapus collector lebih dulu.

Formulir **Tambah/Ubah/Hapus** dan pencarian ada di kartu Daftar Collector.
Untuk Excel, gunakan **Unduh template** pada kartu Bulk import Collector.
Header sheet `Master_Collector`: `Kode_Kolektor`, `Nama_Kolektor`, `NIK`,
`No_HP`, `Afiliasi_Vendor`, `Provinsi`, `Kabupaten_Kota`, `Desa`. Afiliasi
memakai kode vendor yang sudah ada. Kode collector yang sudah terdaftar akan
diperbarui; sel opsional yang kosong tidak menghapus data tersimpan. Baris
salah (mis. NIK tidak 16 angka atau kode vendor tidak ada) ditolak sendiri,
sedangkan baris lain yang benar tetap diproses.

### Perbaikan pemasangan offline Python (v0.11.1)

Versi Python untuk bahan offline adalah **3.11, Windows 64-bit**. Patch seperti
3.11.6 tidak perlu sama persis dengan PC pembuat bahan: wheel CPython dipilih
berdasarkan mayor.minor (`3.11`) dan arsitektur (`win_amd64`). `ambil-bahan-offline.bat`
versi baru menulis target itu ke `bahan-offline\python-version.txt`.

`start-offline.bat` versi baru memakai launcher **`py -3.11`** (bukan `py -3`,
yang bisa memilih Python paling baru yang terpasang), mengecek versi dan
arsitektur 64-bit, serta membuat ulang `backend\.venv` jika sebelumnya
terbentuk dengan versi yang salah. Yang dibuat ulang hanya lingkungan Python;
`backend\opmargin.db` dan folder unggahan tidak dihapus. Untuk paket lama tanpa
`python-version.txt`, skrip memakai target 3.11 (sesuai paket cp311 yang
sudah diuji). Setelah pembaruan skrip, salin versi aplikasi terbaru ke PC
luring; wheelhouse lama boleh dipakai bila memang dibuat untuk Python 3.11
Windows 64-bit.

### Perbaikan unggah dari pratinjau pada Windows (v0.11.2)

Jika setelah menekan **Konfirmasi simpan** keluar `WinError 32` atau pesan
`file sedang digunakan`, tutup Excel/file manager bila file pratinjau sedang
terbuka, lalu pasang versi aplikasi **0.11.2**. Penyebab yang diperbaiki ada
di aplikasi: workbook Excel yang dibaca saat pratinjau belum ditutup, sehingga
Windows masih mengunci file ketika aplikasi hendak memindahkannya ke arsip
unggahan.

Versi 0.11.2 menutup semua workbook setelah pemeriksaan selesai (termasuk
jalur unggah tiket) dan menampilkan pesan yang dapat dibaca jika Windows masih
mengunci file. Setelah memperbarui kode, buka ulang aplikasi dan unggah ulang
file bila pratinjau lama sudah kedaluwarsa. Database tidak perlu dihapus atau
dibangun ulang.

## 5. Menjalankan pengujian (memastikan rumus persis Excel lama)

```powershell
python -m pytest
```

Harus tertulis `416 passed`. Pengujian mencakup semua kasus uji emas:
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
  pemeriksaan harian tiket vs pembelian; tiap baris selisih kini bisa
  diputuskan sumber mana yang benar (lihat bagian 3h).
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

## Kalau panel analisa terbuka tetapi datanya tidak muncul

Gejala lama: **RCA · 5 Why**, **Margin Bridge**, **Days of Cover**, **Analisis
tren & musiman**, dan **Analisis deskriptif & komposisi** terbuka, tetapi isinya
kosong / hanya "Menghitung…". Bukan karena endpoint rusak: `/api/ringkasan-
elemen/rca`, `/api/margin-bridge`, `/api/days-of-cover`,
`/api/kartu/penerimaan/tren`, dan `/api/kartu/penerimaan/komposisi` semuanya
menjawab 200. Penyebabnya panel-panel itu dulu memakai `useQueryKartu`, yang
**menahan permintaan jaringan sampai tombol Refresh kartu ditekan**. Karena
panel baru dipasang saat tombol analisa diklik, Refresh kartu tidak sempat
mendaftarkan query panel itu. Sekarang panel analisa memakai `useQuery` biasa:
saat panel dibuka, query langsung aktif dan memuat data. **5W1H** dan **Analisa
semua data** memakai `Panel5W1H` yang memang sudah `useQuery` biasa; URL 5W1H
pada kartu elemen juga dirapikan agar tidak menggabungkan dua `?`.

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
sejak versi 0.9.3. Kalau pesan itu masih muncul, yang menjawab di port 8000
pasti kode lama. Cara membuktikannya dari folder aplikasi:

```powershell
findstr /c:"Cloudflare Access" backend\app\main.py
```

- **Ada hasilnya** → folder ini masih kode lama (belum diperbarui). Jalankan
  `perbarui-kode.bat`.
- **Tidak ada hasil** → folder sudah 0.9.3; berarti ada proses lama di port
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
| `mode login : lokal (username-sandi)` dan API menjawab `0.11.2` + `lokal` | sudah benar | login dengan akun Anda (Ctrl+F5 dulu) |
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
   `VERSI.txt`-nya berisi `0.11.2`. Tunggu tulisan **`API siap: kode 0.11.2`**.
3. Buka `http://localhost:5173`, tekan **Ctrl+F5**.

Cek cepat kapan saja: `http://localhost:8000/api/health` — nilai `versi` dan
`kode` harus `0.11.2`, dan `folder` harus menunjuk folder aplikasi Anda.

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

1. **Otomatis** — klik dua kali **`perbarui-kode.bat`**. Secara bawaan skrip
   mengunduh seluruh isi branch `main` (kode serta file data/referensi yang
   disimpan di repository) ke folder baru di sebelah folder lama, lalu membuka
   foldernya. Folder lama tidak ditimpa atau dihapus. Database lokal
   `backend\opmargin.db` dicadangkan otomatis ke folder baru; `backend\.env`
   sengaja tidak disalin. Jalankan `start-web.bat` dari folder baru.

   Untuk mengunduh branch lain, jalankan dari Command Prompt, misalnya:

   ```bat
   perbarui-kode.bat arena/399dd64e-rubber-intelligence
   ```

2. **Manual** — unduh ZIP branch resmi di browser, lalu ekstrak:

   ```
   https://codeload.github.com/boldcraftcode-ops/rubber-intelligence/zip/refs/heads/main
   ```
3. **Paling rapi (butuh Git)** — di folder tujuan:

   ```powershell
   git clone -b main https://github.com/boldcraftcode-ops/rubber-intelligence.git
   ```

   Setelah itu pembaruan berikutnya cukup `git pull`.

**Data intake lokal tetap aman:** updater menggunakan SQLite online backup untuk
menyalin `backend\opmargin.db` tanpa mengubah database di folder lama. Berkas
`.env` tidak disalin agar setelan lama tidak mengganggu; aplikasi baru akan
menyiapkan setelan lokalnya sendiri. Tutup aplikasi sebelum menjalankan updater
agar hasil cadangan mencakup perubahan terakhir.

Cara memastikan folder baru benar-benar versi terbaru: lihat **`VERSI.txt`** di
akar folder (versi terbaru saat dokumen ini ditulis: **0.11.2**), atau buka
`http://localhost:8000/api/health` dan periksa `"versi"` serta `"kode"`.

## Login berhasil tetapi kembali ke form login lagi

Gejalanya: form login terisi, tombol ditekan, tidak ada pesan galat, tetapi
kembali ke form login. Di log API terlihat `POST /api/auth/login 200` lalu
`GET /api/auth/saya 401`.

Sebabnya **cookie sesi tidak terkirim**, dan itu terjadi bila:

- aplikasi dibuka **di dalam iframe** (halaman preview/embed), atau
- halaman web dan API berada di **situs berbeda**, atau
- browser memblokir cookie pihak ketiga.

Sejak versi 0.9.3 hal ini ditangani otomatis: saat login, API mengirim `token`
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
