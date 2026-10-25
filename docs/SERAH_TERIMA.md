# SERAH TERIMA — Rubber Intelligence (OP Margin)

Dokumen ini ditulis untuk **orang yang menggantikan saya** mengurus proyek ini.
Isinya bukan promosi, tapi hal-hal yang kalau tidak diketahui akan memakan waktu:
apa yang sudah jadi, apa yang belum, aturan yang tidak boleh dilanggar, dan
jebakan yang sudah pernah menjatuhkan saya.

Kalau Anda hanya punya 15 menit, baca bagian **1 (Status)**, **3 (Cara
menjalankan)**, dan **7 (Aturan yang tidak boleh dilanggar)**. Selebihnya bisa
dibaca saat mengerjakan tugas pertama.

Terakhir diperbarui: **2026-10-25**, versi kode **0.9.4**.

---

## 1. Apa proyek ini

Aplikasi web internal pengganti dua berkas Excel lama: **"Details OP Margin"**
dan **"Analisa OP Margin"**, untuk perusahaan pengolah karet.

- **OP** = *out purchase* (harga beli bahan baku), bukan *operating profit*.
- **OP Margin** = `SICOM − harga beli`, satuan **US¢/kg**, basis **berat kering**.
- **SICOM** = harga acuan pasar (di luar kendali perusahaan).
- **Harga beli (OP Price)** = keputusan perusahaan.

Jadi yang diukur aplikasi ini sederhana: *berapa selisih antara harga pasar dan
harga yang kita bayar, dan siapa penyebab perubahannya* — pasar atau keputusan
kita sendiri. Semua fitur lain melayani pertanyaan itu.

Pengguna utama: bagian pembelian/pengadaan dan manajemen pabrik. Mereka memakai
ini setiap hari untuk memutuskan **harga beli maksimum** yang masih aman.

---

## 2. Status per 2026-10-25

| Hal | Nilai |
|---|---|
| Versi kode | **0.9.4** (`VERSI.txt`, `backend/app/versi.py`, `frontend/src/versi.ts`) |
| Branch kerja | `arena/18670644-rubber-intelligence` |
| Pull request | **#1 masih terbuka** — https://github.com/boldcraftcode-ops/rubber-intelligence/pull/1 |
| Branch `main` | belum memuat pekerjaan v0.7.x–v0.8.x |
| Unit test | **310 lulus** (`cd backend && .venv/bin/python -m pytest -q`) |
| Build frontend | bersih, ±3,3 detik (`cd frontend && npm run build`) |
| Database | SQLite `backend/opmargin.db` (tidak masuk Git) |

Sudah selesai (fase 1–8): fondasi data & rumus, input harian SICOM/kurs,
unggah Excel, rekonsiliasi, perencanaan tahun depan, alarm, kualitas data,
master grade & harga per grade, analisa (5W1H, Margin Bridge, Days of Cover),
tombol "Jelaskan ke saya", ekspor Excel, login username+sandi, tema korporat,
dan halaman depan **Margin Performance** (strip angka kunci + panel "perlu
perhatian").

Belum selesai: lihat **bagian 11**.

---

## 3. Cara menjalankan

### 3a. Untuk pengguna akhir (Windows)

Cukup klik dua kali **`start-web.bat`**. Skrip itu menyiapkan venv, database,
`.env`, dan `node_modules` sendiri, menutup proses lama di port 8000/5173,
menyalakan API + tampilan web, lalu membuka browser.

Berkas `.bat` lain yang ada dan fungsinya:

| Berkas | Fungsi |
|---|---|
| `start-web.bat` | jalan sehari-hari (API + web) |
| `hentikan-api.bat` | mematikan API yang masih memegang port 8000 |
| `perbaiki.bat` | satu klik: tarik kode terbaru, salin data, reset sandi admin |
| `perbarui-kode.bat` | untuk folder hasil unduhan ZIP (bukan `git clone`) |
| `diagnosa.bat` | memeriksa versi folder, proses di port, mode login |
| `start.bat` | skrip uji fase 1: siapkan venv + database, jalankan tes, cetak contoh hasil di terminal (tidak menyalakan web) |

### 3b. Untuk pengembang (Linux / sandbox / CI)

```bash
# API
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.cli init-db                 # buat tabel
.venv/bin/python -m app.cli import-template ../sample_data/Template_dan_Data_Awal_OP_Margin_v3.xlsx
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Tampilan web (terminal lain)
cd frontend
npm install
npm run dev      # http://localhost:5173, /api diproksi ke 127.0.0.1:8000
```

Login awal: **`admin` / `admin123`** (dari `ADMIN_SANDI_AWAL` di
`backend/.env`). Ganti setelah bisa masuk.

> Jalur di atas sudah saya uji dari database kosong (2026-10-25): `init-db` →
> `import-template` → `ringkasan 2026` menghasilkan tabel Jan–Okt 2026 yang
> masuk akal. Kalau di tempat Anda gagal, yang paling mungkin beda adalah
> Python (butuh 3.11+) atau versi pustaka di `requirements.txt`.

### 3c. Perintah yang sering dipakai

```bash
cd backend
.venv/bin/python -m pytest -q                                  # 310 tes
.venv/bin/python -m app.cli diagnosa                            # laporan kesehatan
.venv/bin/python -m app.cli reset-sandi admin                   # lupa sandi
.venv/bin/python -m app.cli atur-login-lokal                    # pastikan mode login benar
.venv/bin/python -m app.cli import-tiket <berkas.xlsx>          # impor ekspor tiket
.venv/bin/python -m app.cli ringkasan 2026                      # ringkasan di terminal
.venv/bin/python -m app.cli rekomendasi                         # harga beli maksimum
.venv/bin/python -m app.cli rencana 2027                        # perencanaan

cd frontend && npm run build     # tsc -b + vite build (WAJIB lulus sebelum commit)
```

---

## 4. Peta repo — di mana mengubah apa

```
rubber-intelligence/
├── start-web.bat, *.bat        skrip Windows (lihat tabel 3a)
├── VERSI.txt                   baris 1 = versi kode folder ini
├── docs/
│   ├── SERAH_TERIMA.md         ← dokumen ini
│   ├── CARA_MENJALANKAN.md     panduan pengguna + troubleshooting versi/login
│   ├── ASUMSI.md               keputusan default + pertanyaan TERBUKA (penting!)
│   ├── KAMUS_METRIK.md         definisi istilah & rumus
│   └── TEMA.md                 palet, logo, aturan tampilan
├── backend/
│   ├── app/
│   │   ├── main.py             rakitan FastAPI, /api/health, SICOM & kurs
│   │   ├── models.py           22 tabel: raw_*, mart_*, pengguna, alarm, dst.
│   │   ├── mart.py             pembentuk mart harian/bulanan dari data mentah
│   │   ├── api_analisis.py     analisa, kartu, bridge, DoC, kualitas, ekspor
│   │   ├── api_fase4.py        stok, aturan harga, simulasi, rencana, alarm
│   │   ├── api_grade.py        master grade & harga per grade
│   │   ├── api_vendor.py       master vendor: CRUD + template + impor massal
│   │   ├── api_unggah.py       unggah Excel lewat web
│   │   ├── api_database.py     info/kosongkan/ekspor/impor database
│   │   ├── api_jelaskan.py     penyusun teks "Jelaskan ke saya" (What/So what/Now what)
│   │   ├── auth_lokal.py       login username+sandi, sesi JWT di cookie
│   │   ├── cli.py              perintah terminal (lihat 3c)
│   │   ├── versi.py            VERSI + versi_folder()
│   │   ├── importer/           pembaca Excel (template.py, tiket.py)
│   │   └── core/               RUMUS — ini jantung aplikasi:
│   │       ├── rumus.py        margin, harga, agregasi
│   │       ├── analisa.py      analisa per dimensi, 5W1H
│   │       ├── stok_margin.py  analisa stok vs margin, Days of Cover
│   │       ├── rekomendasi.py  harga beli maksimum dari aturan stok→harga
│   │       ├── perencanaan.py  proyeksi tahun depan
│   │       ├── rekonsiliasi.py pembanding tiket vs Excel lama
│   │       ├── kualitas.py     deteksi data terlambat/aneh
│   │       └── alarm.py        evaluasi alarm + audit
│   ├── semantic/metrics.yaml   definisi metrik (rujukan, dibaca fase API)
│   ├── tests/                  310 tes, termasuk kasus emas Excel lama
│   ├── unggahan/               berkas Excel yang diunggah lewat web
│   └── .env.example            contoh setelan (JANGAN commit .env asli)
└── frontend/
    ├── src/App.tsx             kerangka: sidebar, header, daftar menu (TAB)
    ├── src/pages/*.tsx         17 halaman (termasuk MasterVendor.tsx)
    ├── src/bersama.tsx         gaya bersama: Kartu, tombol, input, modal, 5W1H
    ├── src/i18n.tsx            kamus ID→EN; teks di kode ditulis Bahasa Indonesia
    ├── src/index.css           tema (palet, .galaxy, .kartu-aksen, aturan Recharts)
    ├── public/logo-*.svg|png   logo Rubber Intelligence
    └── wrangler.jsonc          deploy statis Cloudflare (opsional)
```

**Urutan alur data** (hafalkan ini, 90% bug ada di sini):

```
Excel/unggahan → RawUnggahan + RawBaris (mentah, apa adanya)
   → importer + mart.py → MartHarian → MartBulanan
   → core/*.py (rumus) → api_*.py (JSON) → React
```

Angka di layar **tidak pernah** dihitung di frontend. Kalau angka salah,
periksa `mart.py` dan `core/*`, bukan `.tsx`.

---

## 5. Definisi bisnis yang mengikat

Ini bukan selera teknis — ini versi yang sudah dikonfirmasi pemilik proyek.
Mengubahnya berarti mengubah arti laporan ke manajemen.

- **OP Margin** = SICOM − OP Price, US¢/kg, **berat kering**.
- **Margin Bridge** punya **dua penyebab** saja: **Δ SICOM** (pasar, di luar
  kendali) dan **Δ OP Price** (keputusan kita). Keduanya harus menjumlah persis
  ke Δ margin — ini diuji.
- **Days of Cover** memakai **pemakaian implisit** dari neraca stok:
  `pemakaian = stok awal + intake − stok akhir`, lalu
  `DoC = stok akhir ÷ (pemakaian ÷ jumlah hari)`. Tidak ada data pemakaian
  langsung; jangan mengarang konsumsi dari kapasitas pabrik.
- **Safety** dibandingkan **dalam hari**, bukan ton.
- **Intake** memakai **kuantitas kering** dari pembelian/tiket.
- **Avg YTD** yang resmi = **rata-rata sederhana** bulan berdata (seperti Excel
  lama). Rata-rata **tertimbang tonase** hanya informasi tambahan — jangan
  menukar keduanya.
- Penurunan margin di Bridge ditampilkan **merah tegas** dan **selalu disertai
  angka + sebab**, bukan warna saja.
- Aksesibilitas: **jangan** menyampaikan arti hanya lewat hijau/merah. Warna
  harus disertai ikon (▲/▼) atau kata.

Detail lengkap: `docs/KAMUS_METRIK.md`.

---

## 6. Bentuk tampilan yang disepakati

Mengikuti materi identitas korporat yang dikirim pemilik proyek. Ringkasnya:

| Warna | Kode | Peran |
|---|---|---|
| Merah | `#FF1313` | aksen: tombol utama, garis aksen, eyebrow, penurunan |
| Navy | `#1D2434` | teks utama, panel identitas, seri grafik utama |
| Putih | `#FFFFFF` | kartu, modal, panel form |
| Abu terang | `#F8F8F8` | latar halaman, area sidebar, menu aktif |
| Abu | `#64676C` | teks sekunder, sumbu grafik |

Aturan turunannya (sudut `rounded-sm`, garis rambut `#E4E5E8`, kartu bergaris
merah di atas, pola titik sebagai aksen) ada di `docs/TEMA.md`.

Halaman depan bernama **Margin Performance** (dulu "Ringkasan"), dengan eyebrow
header **Rubber Intelligence** di semua halaman. Logo: daun karet tiga helai +
tetesan lateks merah + simpul data, dibuat manual sebagai SVG
(`frontend/public/logo-rubber-intelligence.svg`).

**Jangan memakai font/CDN/gambar eksternal.** Aplikasi harus jalan di jaringan
tertutup pabrik; semua aset lokal.

### Periode tampilan menu Stok (v0.8.0)

Menu **Stok** kini punya pemilih periode di bagian paling atas, dengan isi
bawaan **1 Januari tahun berjalan s.d. bulan berjalan** (dibuka Oktober 2026 →
Jan 2026 – Okt 2026). Tiga kartu di bawahnya mengikuti periode itu:

| Kendali | Arti |
|---|---|
| **Dari bulan** / **Sampai bulan** | batas periode; tanggal dipotong otomatis (awal bulan → hari terakhir bulan) |
| **tahun ini** | mengembalikan isian ke bawaan (awal tahun – bulan ini) |
| **seluruh data** | melepas batas periode; semua tanggal yang ada ikut dihitung |

Periode aktif selalu tertulis di bar atas (*"Menampilkan Jan 2026 – Okt 2026 ·
251 hari berdata"*) dan diulang di keterangan tiap kartu, supaya angka tidak
terbaca lepas dari rentangnya. Bila bulan awal melewati bulan akhir, aplikasi
menolak memuat data dan menampilkan pesan, bukan grafik kosong.

Kartu **Stok hari terakhir** menampilkan tanggal terakhir *di dalam periode*,
bukan tanggal terakhir di seluruh database — jadi mengubah periode ikut
mengubah baris ini.

Pemilih periode ini dipakai bersama oleh menu Stok dan Intake Analisis
(`PilihRentangBulan` di `frontend/src/bersama.tsx`), supaya bentuk, warna, dan
perilakunya tidak bercabang.

### Daftar intake terakhir & batas 12 bulan KPI Reject (v0.8.1)

**Kartu "Daftar intake terakhir"** (paling bawah halaman Intake Analisis, setelah
kartu margin) menjawab
pertanyaan *"kapan intake terakhir masuk?"* tanpa perlu membuka Excel:

| Bagian | Isi |
|---|---|
| Ringkasan atas | tanggal intake terakhir + penanda umur (*hari ini / kemarin / N hari lalu*, merah bila > 7 hari), nomor tiket, vendor, grade, ton kering, dan berapa tiket masuk hari itu |
| Tabel | 10/20/50/100 tiket terbaru: tanggal, no tiket, vendor, grade, wet ton, dry ton, reject ton, kabupaten–provinsi |
| Penutup | *"N dari M tiket (data sejak …)"* supaya jelas daftar ini terpotong atau tidak |

Satu baris tabel = **satu tiket** (satu kendaraan datang). Tiket dengan beberapa
baris `line_seq` (beberapa grade dalam satu kendaraan) digabung: ton dijumlahkan,
grade digabung dengan koma. **Tiket nol tidak ikut** daftar, sama seperti kartu
Penerimaan. Endpoint: `GET /api/kartu/intake-terakhir?limit=20` (juga `&format=xlsx`).

**Kartu KPI Reject %** kini dibatasi **12 bulan terakhir yang berdata**, bukan
seluruh riwayat 2020–2026:

- ada pilihan **6 / 12 / 24 bulan terakhir / Semua bulan** (bawaan **12**);
- ringkasan di atas tabel ikut dihitung dari bulan yang ditampilkan (bukan seluruh
  riwayat), sehingga *"Rata-rata 12 bulan terakhir: 0,01%"* selalu cocok dengan
  tabel di bawahnya;
- bila data lebih panjang dari batas, muncul catatan *"Menampilkan 12 bulan
  terakhir dari N bulan"*;
- endpoint `GET /api/kartu/reject?bulan=12` (`bulan=0` = semua bulan,
  `bulan` di luar 0–120 → 422). Filter tahun tetap jalan dan dihitung setelah
  filter itu.

### Master Vendor — CRUD & bulk import (v0.9.0)

Menu baru **Master Vendor** (sidebar, di atas Grade & Harga) merawat daftar
vendor: daftar + cari + saring status, tambah, ubah, hapus, dan impor massal
dari Excel. Sebelumnya vendor hanya bisa masuk lewat unggah template tahunan,
sehingga salah ketik kode baru terlihat setelah tonase hilang dari laporan.

| Kemampuan | Perilaku |
|---|---|
| **Daftar** | kode, nama baku, varian nama, kategori, status; plus **jumlah tiket, ton kering, dan tanggal intake terakhir** per vendor — jadi langsung kelihatan kode mana yang benar-benar dipakai |
| **Cari & saring** | mencari di kode/nama/varian/kategori; saring status aktif/nonaktif/diblokir |
| **Tambah** | kode dibakukan HURUF BESAR; hanya huruf, angka, dan `- . _ /` (maks 20) karena kode harus sama persis dengan di tiket |
| **Ubah** | nama, varian, kategori, status. **Kode tidak bisa diubah** — kode berbeda = vendor berbeda |
| **Hapus** | dua langkah (klik Hapus → “ya, hapus”) dan **ditolak server** bila vendor sudah dipakai tiket/pembelian, dengan pesan yang menyebut jumlah pemakaian; jalur yang disarankan: ubah status menjadi `nonaktif`. Hapus paksa tetap tersedia dan tercatat di audit |
| **Template** | `Master_Vendor_template.xlsx`: sheet `Master_Vendor` (kolom `Kode_Vendor, Nama_Baku, Varian_Nama, Kategori, Status`) berisi seluruh vendor yang ada + sheet `Petunjuk` |
| **Bulk import** | unggah `.xlsx` langsung dari menu ini (juga tetap bisa lewat tab Unggah Data): kode lama **diperbarui**, kode baru ditambah, baris rusak dilaporkan per baris tanpa membatalkan baris lain; kode ganda di dalam file ditolak baris keduanya |

Endpoint: `GET/POST /api/vendor`, `PUT/DELETE /api/vendor/{kode}`,
`GET /api/vendor/template`, `POST /api/vendor/impor`.
Hapus: `DELETE /api/vendor/{kode}?paksa=true`.

Catatan penting: status lama di database yang tertulis “Aktif” ditampilkan
sebagai `aktif` (dibakukan huruf kecil) supaya cocok dengan pilihan di layar.
CORS kini mengizinkan `PUT` dan `DELETE` — tanpa itu tombol ubah/hapus gagal
bila tampilan web dan API berada di domain berbeda (deploy tunnel).

### Analisis tren & musiman + normalisasi wilayah (v0.9.1)

Disematkan di kartu **Penerimaan karet (kg) — biasa vs EUDR** sebagai
**tombol `📈 Analisis tren & musiman`** yang rata kanan di baris filter —
bentuk dan perilakunya sama dengan tombol **🌉 Margin Bridge** / **📦 Days of
Cover** di Margin Performance: tombol navy (`kelasTombolAnalisa`) → **panel
modal** dengan kepala panel berisi periode, **Ekspor Excel**, dan **Tutup**;
klik latar gelap untuk menutup. Panelnya baru memuat data saat tombol ditekan.

Sumbernya `GET /api/kartu/penerimaan/tren` (ikut filter periode dan mode grade
kartu; ada ekspor `.xlsx`).

| Bagian | Isi |
|---|---|
| **Kepala panel** | judul, periode yang dianalisis, Ekspor Excel, Tutup |
| **Grafik** | total kg per bulan + **garis MA3** (rata-rata bergerak 3 bulan) + EUDR |
| **Tabel** | per bulan: total, biasa, EUDR, MA3, **MoM %**, **YoY %** |
| **Dekomposisi** | tren, musiman, residu + **indeks musiman 12 bulan kalender** |
| **Peringatan** | kotak kuning "periksa dulu sebelum dipakai untuk perkiraan" |

**Metode yang dipakai (jujur, bukan STL LOESS penuh):** dekomposisi aditif
klasik — tren = rata-rata bergerak 12 bulan terpusat (bobot ½ di ujung),
musiman = rata-rata sisa per bulan kalender lalu dinormalkan agar total 12 bulan
= 0, residu = sisa. Hasilnya dipakai untuk membaca pola musim gugur daun
(Feb–Apr) dan musim hujan. **Butuh minimal 24 bulan** (idealnya 36); di bawah
itu blok dekomposisi menampilkan pesan jumlah bulan yang kurang dan **tidak**
menampilkan angka tren/musiman — lebih baik kosong daripada menyesatkan.
MA3/MoM/YoY tetap bisa dipakai walau data masih pendek.

Catatan teknis:
- MA3/MoM/YoY/dekomposisi dihitung dari **seluruh deret** yang ada, lalu
  `dari`/`sampai` hanya memotong tampilan — supaya bulan pertama pada periode
  pilihan tetap punya pembanding.
- MoM/YoY **kosong (bukan 0%)** bila pembandingnya tidak ada atau nol.
- Bulan tanpa tiket tetap tampil sebagai bulan bernilai 0 (grafik tidak
  melompat), tetapi ikut dilaporkan sebagai peringatan.
- Bila ada bulan nol di dalam deret, catatan dekomposisi menyebut bahwa nol
  dihitung sebagai penerimaan nol sehingga hasil bisa bias bila sebenarnya
  data belum diunggah.

**Validasi otomatis sebelum angka dipakai untuk perkiraan:**
1. **Bulan nol** dan **rentetan nol di tengah** — ditandai sebagai "tiket
   kemungkinan belum diunggah", bukan penerimaan berhenti.
2. **Bulan terakhir belum lengkap** — dihitung dari tanggal tiket terakhir vs
   hari terakhir bulan itu.
3. **Pola datar tidak wajar** — deret ≥3 bulan berurutan dengan variasi <5%
   (CV) ditandai; penerimaan karet nyata tidak seseragam itu.
4. **Ejaan wilayah dobel** — lihat bagian berikut.

#### Normalisasi nama wilayah (provinsi → desa)

Masalah nyata yang dilaporkan pemilik: `"Sumatera Utara"` dan
`"SUMATERA UTARA"`, `"Riau"` dan `"RIAU"` muncul sebagai baris terpisah
(Okt-26: 7.100 kg dan 4.680 kg). Itu memang **masalah standardisasi data**,
bukan provinsi berbeda.

Perbaikannya (berlaku di kartu Penerimaan dan Tonase):
- **kunci** wilayah dibakukan: spasi dirapatkan + **HURUF BESAR**
  (`UPPER`/`TRIM`) → satu provinsi = satu baris;
- **label** memakai ejaan yang paling sering muncul (`Sumatera Utara`), supaya
  tampilan tetap enak dibaca;
- filter dan drill-down wilayah **tidak peka huruf besar/kecil** dan
  mengabaikan spasi berlebih;
- penggabungannya **dilaporkan**, bukan diam-diam: `wilayah.digabung` berisi
  daftar ejaan yang disatukan, ditampilkan di kartu dan di blok analisis.

> **Perubahan kontrak API:** untuk dimensi wilayah, `kunci` pada jawaban
> kartu kini berupa teks ter-normalisasi (`DELI SERDANG`), sedangkan `label`
> tetap ejaan asli (`Deli Serdang`). Kode yang memakai `kunci` sebagai teks
> tampilan perlu beralih ke `label`.

Kepala panel modal (`KepalaPanel`) dipindah ke `frontend/src/bersama.tsx` dan
dipakai ketiga tombol analisa (Margin Bridge, Days of Cover, Analisis tren &
musiman), supaya bentuk panel tidak bercabang lagi di kemudian hari.

Penyebabnya di sumber data, jadi normalisasi ini obat sementara: idealnya
ekspor/pengetikan dari aplikasi asal ikut dibakukan, atau dipakai master
wilayah. Hal itu belum dikerjakan.

### Analisis deskriptif & komposisi (v0.9.3)

Tombol kedua di kartu **Penerimaan karet (kg) — biasa vs EUDR** —
**📊 Analisis deskriptif & komposisi** — dengan pola yang sama seperti
**📈 Analisis tren & musiman** dan **🌉 Margin Bridge**: tombol navy → panel
modal + kepala panel (periode, Ekspor Excel, Tutup). Sumber:
`GET /api/kartu/penerimaan/komposisi` (ikut filter periode & mode grade kartu;
ada ekspor `.xlsx`).

Panelnya menjawab tiga hal yang bisa langsung dipakai:

| Bagian | Isi |
|---|---|
| **KPI** | total kg/ton, wilayah terbesar + porsinya, jumlah kategori untuk mencapai 80%, share EUDR |
| **Ketergantungan pasokan** | porsi terbesar, tiga terbesar, **HHI** (0 = menyebar, 1 = satu pihak) beserta artinya |
| **Tabel share** | kg, porsi %, kumulatif %, **kelas ABC**, EUDR % per kategori, jumlah tiket |
| **Grafik** | porsi (%) per kategori, batang horizontal |
| **EUDR vs biasa** | share total, grafik share per bulan, tabel per bulan + **perubahan** (▲/▼ poin) |

**Dimensi komposisi bisa diganti di dalam panel** (provinsi / vendor / grade /
kabupaten) tanpa mengubah dimensi kartu — jadi ketergantungan bisa dilihat per
wilayah maupun per pemasok. Bawaannya mengikuti dimensi kartu saat tombol
ditekan.

**Aturan Pareto/ABC yang dipakai:**
- urut menurun menurut volume, porsi dihitung dari total periode terpilih;
- **Kelas A** = kategori yang membuat kumulatif **mencapai 80%** (kategori
  yang melewati ambang tetap ikut A, tidak terbelah), **B** sampai 95%,
  **C** sisanya (ekor panjang);
- *"N dari M kategori diperlukan untuk mencapai 80%"* menghitung kategori yang
  membuat kumulatif mencapai 80% — jadi 50% + 25% + 25% menghasilkan N = 3,
  bukan 2.

**HHI** (Herfindahl–Hirschman) = jumlah kuadrat porsi: ≥0,25 tinggi
(pasokan bergantung pada sedikit pihak), 0,15–0,25 sedang, <0,15 menyebar.

Catatan pembacaan: contoh pada data sekarang — Sumatera Utara **50,2%**,
Riau 25,1%, Aceh 24,7%, HHI **0,376** (tinggi); share EUDR **13,19%** dengan
rentang per bulan 12,6–13,3% (Okt-26 39,7% karena bulan itu baru 3 tiket,
jangan dibandingkan langsung). Angka Sumatera Utara berbeda dari contoh di
permintaan (575.792 kg) karena sekarang ejaan `Sumatera Utara` dan
`SUMATERA UTARA` sudah digabung.

### Menu samping jadi pohon dua tingkat (v0.9.4)

Menu kiri yang tadinya **16 tombol datar** sekarang **6 grup + 16 halaman**
(semua halaman lama tetap ada, hanya dikelompokkan):

| Grup (ID / EN) | Isi |
|---|---|
| 📊 Analitik / *Analytics* | Margin Performance · Intake Analisis · Stok · Stok vs Margin |
| 💰 Harga & Perencanaan / *Pricing & Planning* | Aturan Harga · Simulasi · Perencanaan |
| 🛡️ Pengawasan & Kontrol / *Monitoring & Control* | Alarm · Rekonsiliasi · Kualitas Data |
| 🗂️ Master Data | Master Vendor · Grade & Harga |
| 📥 Input Data / *Data Entry* | Input Harian · Unggah Data |
| ⚙️ Administrasi / *Administration* | Database · Pengguna — **hanya admin**, grup ini
tidak dirender untuk peran lain |

Cara kerjanya:
- baris grup **bukan halaman**: diklik = buka/tutup, ditandai chevron `▶` yang
  berputar dan `aria-expanded` (pembaca layar tahu statusnya);
- **semua grup terbuka pada pemakaian pertama**, jadi tidak ada menu yang
  "hilang"; buka/tutup yang dipilih pengguna diingat di
  `localStorage` (`ri.menu.grup`);
- pindah halaman — termasuk lewat tombol di Margin Performance — otomatis
  **membuka grup** tempat halaman itu berada;
- halaman aktif tetap ditandai garis merah `#FF1313` + latar `#F8F8F8`, ditambah
  `aria-current="page"` (tidak bergantung warna saja);
- badge jumlah Alarm tetap menempel di halaman Alarm.

Nama grup ikut dwibahasa ID/EN seperti halaman lain. Urutan halaman di dalam
grup mengikuti struktur yang diminta pemilik.

Diuji lewat render server (`react-dom/server`): 6 grup tampil dengan urutan dan
nama di atas; peran **staf** tidak melihat grup Administrasi maupun Database/
Pengguna; keadaan "tertutup" dari `localStorage` benar-benar menyembunyikan
anak grup (`aria-expanded="false"`); versi EN keluar sebagai *Analytics,
Pricing & Planning, Monitoring & Control, Master Data, Data Entry,
Administration*.

---

## 6b. Deploy lewat Cloudflare Tunnel (masih hidup, penting)

**Yang dihapus hanya Cloudflare Access (gerbang login). Tunnel tidak.**
Tunnel = jalur koneksi dari Cloudflare ke PC; Access = halaman login Cloudflare.
Menghapus Access tidak memutus tunnel. Berkas `deploy/cloudflared-config.example.yml`
dan `deploy/install-windows.md` masih utuh dan masih dipakai.

Ada dua pola pemasangan:

| Pola | Cara kerja | Setelan wajib |
|---|---|---|
| **Satu-origin** (disarankan) | API menyajikan `frontend/dist`; satu hostname tunnel melayani halaman + API | `SAJIKAN_WEB=true` di `.env`, `npm run build` |
| Terpisah | halaman di Pages/Workers, API di `api.domain` | `VITE_API_URL` saat build, `FRONTEND_ORIGIN`, dan `COOKIE_SAMESITE=none` bila beda situs |

Sesi memakai dua jalur: **cookie HttpOnly `op_sesi`** (utama) dan **token di
`Authorization: Bearer`** (cadangan, dikirim API saat login dan disimpan
tampilan web di `localStorage`). Cadangan ini ada karena cookie tidak terkirim
di dalam iframe atau lintas situs — lihat jebakan di bagian 9.

Jebakan yang paling menipu: **cookie sesi**. `op_sesi` dipasang dengan
`SameSite=lax`. Bila halaman web dan API berada di **situs berbeda**
(`*.pages.dev` / `*.workers.dev` + domain lain), browser tidak mengirim cookie
itu untuk permintaan `fetch`, sehingga login *tampak* berhasil lalu langsung
kembali ke form — tanpa pesan galat apa pun. Perbaikannya `COOKIE_SAMESITE=none`
(Secure otomatis menyala). Cara memastikan tanpa browser:

```
GET /api/auth/mode   -> "cookie_samesite":"none"
GET /api/health      -> "web_statistik":"...frontend/dist"   (mode satu-origin)
```

Satu-origin menghilangkan seluruh masalah ini karena cookie selalu same-site.

## 6c. Mode login: kondisi sekarang & cara mengembalikannya

> Ditulis atas permintaan pemilik proyek. Sebelumnya bagian ini sengaja
> dikosongkan; sekarang justru **wajib** dibaca sebelum menyerahkan aplikasi
> ke orang lain.

### Kondisi saat dokumen ini dibuat

Login sedang **DIMATIKAN sementara** untuk keperluan pemecahan masalah, dengan
satu penanda berkas di akar repo:

```
tanpa-login.txt        <- ADA  = login dimatikan
                       <- TIDAK ADA = login username+sandi aktif
```

Berkas itu **tidak masuk Git** (ada di `.gitignore`), jadi penandanya hanya
hidup di komputer pemilik. Di mesin lain, login aktif secara bawaan.

Saat penanda ada, aplikasi menampilkan banner kuning di atas semua halaman:
**"MODE TANPA LOGIN (SEMENTARA)"**. Banner itu sengaja dibuat mencolok supaya
tidak lupa. Selama penanda ada, **siapa pun yang bisa membuka alamat aplikasi
masuk sebagai admin tanpa sandi** — jangan biarkan kondisi ini ada saat aplikasi
dipasang di internet.

### Cara mengembalikan (Windows, cara tercepat)

```
1. Klik dua kali  tanpa-login-mati.bat
   -> berkas tanpa-login.txt dihapus, muncul pesan "login AKTIF lagi"
2. Tutup jendela "OP Margin - API" dan "OP Margin - Web"
   (atau jalankan hentikan-api.bat)
3. Jalankan start-web.bat
4. Login dengan username + sandi
5. Muat ulang halaman dengan Ctrl+F5
```

### Cara memastikan sudah benar (tanpa menebak)

| Periksa | Hasil yang benar |
|---|---|
| `tanpa-login.txt` di folder aplikasi | **tidak ada** (`dir tanpa-login.txt` → File Not Found) |
| `http://localhost:8000/api/auth/mode` | `"cara":"username-sandi"` dan `"perlu_login":true` |
| `http://localhost:8000/api/health` → `login` | `cara` = `username-sandi` |
| Halaman aplikasi | banner kuning **hilang**, muncul form login |
| `diagnosa.bat` | melaporkan mode login lokal |

Kalau setelah langkah di atas masih terbuka tanpa login, berarti
**`AUTH_DISABLED=true` tertulis di `backend/.env`.** Hapus baris itu:

```
notepad backend\.env        # hapus baris AUTH_DISABLED=...
```

Lalu jalankan ulang `start-web.bat`. Perlu diketahui: `start-web.bat` sudah
membuang `AUTH_DISABLED` sendiri, jadi masalah ini hanya muncul bila API
dinyalakan dengan cara lain (mis. service Windows atau perintah manual).

### Di server / produksi

Di `APP_ENV=produksi`, aplikasi **menolak start** bila `AUTH_DISABLED=true`
(pengaman, lihat `auth.validasi_start`). Artinya salah setelan tidak bisa
diam-diam membuka aplikasi di internet — API langsung gagal hidup dan
alasannya tertulis di konsol.

### Hal yang harus dibereskan lebih dulu sebelum login dinyalakan lagi

1. Tentukan apakah masalah "login lalu kembali ke form" sudah selesai: versi
   0.7.6 menyimpan token di memori **juga**, bukan hanya `localStorage`, karena
   di dalam iframe keduanya diblokir. Uji dulu di **browser biasa**, bukan
   preview di dalam iframe.
2. Pastikan `SECRET_KEY` di `backend/.env` terisi (minimal 32 karakter) supaya
   sesi tidak berakhir setiap API dijalankan ulang.
3. Ganti sandi `admin` bawaan (`admin123`) setelah bisa masuk: menu kanan atas →
   Ganti sandi, lalu buat akun untuk setiap pemakai di menu **Pengguna**.

## 7. Aturan yang tidak boleh dilanggar

Semua ini lahir dari kegagalan nyata, bukan kehati-hatian berlebihan.

1. **Login hanya username + sandi.** Login Cloudflare Access sudah **dihapus
   permanen** atas permintaan pemilik. Jangan menawarkannya kembali, jangan
   membuatnya opsional, jangan menambah jalur lewat header/cookie Access.
2. **Berkas `.bat` wajib ASCII, CRLF, tanpa blok `( ... )` berlapis, tanpa
   `for /f`.** Setiap `goto` harus punya label. Pelanggaran menghasilkan pesan
   konyol seperti `'f' is not recognized`.
3. **Versi harus sinkron di 6 tempat** setiap rilis: `VERSI.txt`,
   `backend/app/versi.py`, `frontend/src/versi.ts`, `docs/CARA_MENJALANKAN.md`,
   `diagnosa.bat`, `hentikan-api.bat`. Aplikasi **menolak** login bila versi UI
   ≠ versi API (layar "beda versi") — ini disengaja untuk menangkap proses lama.
4. **Jangan mematikan pemeriksaan versi itu.** Ia menyelamatkan pengguna dari
   bug yang sebenarnya bukan bug (API lama masih hidup di port 8000).
5. **Jangan menambal gejala di lapisan API bila akarnya proses lama.** Pesan
   `"Cloudflare Access"` atau versi `0.5.0` berarti ada proses API lama, bukan
   kode salah. Perbaikannya: `hentikan-api.bat` lalu `start-web.bat`.
6. **Selalu jalankan `npm run build` (bukan hanya `vite build`)** — skrip npm
   memakai `tsc -b`, jadi error tipe ikut tertangkap.
7. **310 tes harus tetap lulus.** Tes "kasus emas"
   (`tests/test_data_awal.py`, `tests/test_bridge_doc.py`) mencocokkan hasil
   dengan Excel lama sampai beberapa desimal. Kalau tes emas gagal, hampir pasti rumus
   yang diubah, bukan tesnya.
8. **Jangan commit** `backend/.env`, `backend/opmargin.db`, `node_modules`,
   `frontend/dist`. Sudah ada di `.gitignore` — jangan dihapus dari sana.
9. **Jangan mengarang angka saat data kurang.** Pola yang dipakai di seluruh
   aplikasi: tampilkan status jujur (`"DATA KURANG"`, `"belum bisa dihitung"`)
   + alasan + apa yang harus diisi. Pemilik proyek sangat tidak menyukai
   tebakan.
10. **Jangan menyentuh setelan cookie tanpa alasan.** Bawaan `lax` sudah benar
    untuk satu domain. `none` hanya untuk halaman web & API di situs berbeda,
    dan wajib disertai `Secure` (sudah otomatis lewat `cookie_secure`).
11. **Bypass login hanya untuk sementara.** Penandanya `tanpa-login.txt`
    (dibuat `tanpa-login-aktif.bat`, dihapus `tanpa-login-mati.bat`). Kondisi
    ini HARUS dikembalikan sebelum aplikasi dipakai bersama atau dipasang di
    internet — lihat bagian 6c.
12. **Jangan bekerja di branch lain.** Semua pekerjaan di
    `arena/18670644-rubber-intelligence`; PR #1 dari branch itu.

---

## 8. Resep tugas yang sering muncul

### Menambah endpoint API
1. Taruh di `api_*.py` yang paling dekat domainnya (jangan bikin berkas baru
   kecuali benar-benar domain baru).
2. Rumus di `core/`, bukan di dalam handler.
3. Tambah tes di `backend/tests/`, minimal satu kasus normal + satu kasus data
   kosong.
4. Kalau menambah kemampuan baru yang perlu dikenali proses lama, tambahkan
   namanya ke daftar `fitur` di `/api/health`.

### Menambah kartu di halaman
1. Pakai komponen `Kartu` dari `bersama.tsx` (sudah membawa garis merah, tombol
   "Jelaskan ke saya", ekspor).
2. **Judul kartu = kesimpulan angkanya**, bukan nama grafik. Contoh:
   "Margin naik 2,4 ¢ karena SICOM, bukan karena harga beli kita".
3. Warna ambil dari palet di bagian 6; jangan mengarang warna baru.
4. Bila kartu butuh penjelasan "Jelaskan ke saya", tambahkan cabang di
   `api_jelaskan.py` dengan kerangka **What / So what / Now what**, satu angka
   utama dibulatkan, tanpa jargon.

### Rincian bulanan pada kartu Analisis
Tiga kartu punya rincian bulanan dengan aturan yang sama —
`/api/kartu/penerimaan`, `/api/kartu/tonase`, dan `/api/kartu/margin-per` —
saat filter periode mencakup **lebih dari satu bulan**. Parameternya `per=bulan`
dan `top` (jumlah dimensi terbesar yang dipertahankan).

- **penerimaan**: kg kering, dipisah grade biasa vs EUDR.
- **tonase**: ton kering per dimensi, mendukung drill-down wilayah.
- **margin-per**: margin US¢/kg **dan** ton per bulan. PENTING: margin adalah
  *tingkat*, bukan jumlah — total per bulan memakai agregat tertimbang tonase,
  **tidak** dijumlahkan antar dimensi.

Aturan yang disengaja:

- **Sumbu bulan mengikuti periode filter**, bukan data. Mengganti filter lain
  (mis. hanya EUDR) tidak boleh menggeser sumbu, karena perbandingan bulan akan
  menyesatkan. Bulan tanpa tiket tampil sebagai 0.
- Pengecualian: rentang > 24 bulan dipotong ke rentang bulan berdata agar grafik
  tidak penuh kolom kosong.
- `top` (1–40) dimensi terbesar dipertahankan; sisanya digabung menjadi satu
  baris `Lainnya (n vendor)` supaya grafik tetap terbaca.
- Tanpa `per=bulan`, bentuk jawaban **tidak berubah** — halaman/kartu lain dan
  ekspor lama tetap aman. Ini dijaga oleh tes.
- `/api/kartu/margin-per` kini menerima `dari`/`sampai` dan `tahun` menjadi
  opsional (tanpa tahun dipakai tahun terakhir yang ada datanya).
- Margin per grade/vendor **tidak pernah** dialokasikan diam-diam: bila Amount
  pembelian hanya tersedia sebagai total harian (`item_code='ALL'`), jawabannya
  `"data harga belum tersedia"`. Itu fitur, bukan bug.

Di layar, tabel di bawah grafik memuat angka yang sama persis dengan grafik
(bulan × dimensi + total + porsi), jadi angka bisa dibaca tanpa menebak dari
batang. Komponennya `RincianBulanan` di `frontend/src/pages/Analisis.tsx`.

### Menambah teks dwibahasa
Tulis dalam Bahasa Indonesia di kode, lalu tambahkan padanannya di
`frontend/src/i18n.tsx` (`KAMUS`). Kata yang tidak ada di kamus tampil apa
adanya dalam Bahasa Indonesia — tidak error, tapi tidak diterjemahkan.
**Hati-hati kunci ganda**: TypeScript menolak objek dengan properti kembar
(`TS1117`) dan itu pernah menggagalkan build.

### Menambah pilihan menu
`frontend/src/App.tsx` → array `TAB` (`id`, `label`, `ikon`, `hanyaAdmin`).
Ikon memakai glif teks sederhana (`◧ ◨ ▤ ▥ ▦ ▧ ▩ ▲ ≡ ◆ ◇ ↑ ✎ ▣ ●`), bukan
pustaka ikon. Jangan menulis ulang array ini dengan regex baris-per-baris —
pernah membuat label dan ikon tertukar; ganti blok utuhnya.

### Rilis versi baru (prosedur yang sudah terbukti)
```bash
# 1. pastikan bersih
cd backend && .venv/bin/python -m pytest -q          # 310 passed
cd ../frontend && npm run build                       # bersih

# 2. naikkan versi di 6 berkas (isi dua variabel, sisanya otomatis)
cd ..
LAMA=$(tr -d '\r\n' < VERSI.txt)     # versi yang masih terpakai
BARU=0.9.4                            # <- tulis versi baru di sini
for f in VERSI.txt backend/app/versi.py frontend/src/versi.ts \
         docs/CARA_MENJALANKAN.md diagnosa.bat hentikan-api.bat; do
  sed -i "s/$LAMA/$BARU/g" "$f"
done
echo "versi: $LAMA -> $BARU"
#    (Windows: ganti manual nilai versi di 6 berkas itu)
#    .bat: pastikan tetap ASCII + CRLF
grep -nP '[^\x00-\x7F]' diagnosa.bat hentikan-api.bat

# 3. build ulang (versi ikut ter-bundle ke UI)
cd frontend && npm run build && cd ..

# 4. commit + push (branch sesi, bukan main)
git add -A && git commit -m "..." && git push origin arena/18670644-rubber-intelligence
```
Setelah itu **restart API** agar `/api/health` melaporkan versi baru; kalau
tidak, pengguna akan melihat layar "beda versi" (yang memang tujuannya).

---

## 9. Jebakan yang sudah memakan waktu

| Gejala | Penyebab sebenarnya | Cara benar |
|---|---|---|
| `'f' is not recognized`, atau skrip berhenti tanpa pesan | `.bat` berisi blok `( )` berlapis / `for /f` / non-ASCII | tulis ulang gaya datar, ASCII, CRLF |
| Tombol analisa 404 "fitur tidak dikenali" | proses API lama masih memegang port 8000 | `hentikan-api.bat`, lalu `start-web.bat` |
| Login ditolak padahal sandi benar, pesan menyebut "Cloudflare Access" | API lama (v0.5.0) yang menjawab, bukan kode di folder | cek `/api/health` → bandingkan `versi` dengan `VERSI.txt` |
| Layar "Aplikasi dan servernya beda versi" | versi `versi.ts` ≠ `versi.py` atau API belum di-restart | samakan versi, restart API |
| Service Windows `OPMargin*` menghidupkan ulang API lama | API dipasang sebagai service | hentikan service-nya dulu (`install-windows.md`) |
| Tes gagal "no such table: pengguna" | `TestClient` + `sqlite://` tanpa `StaticPool` & `check_same_thread=False` | pakai pola fixture di `tests/conftest.py` |
| `create_engine("sqlite://")` hilang tabel antar koneksi | tiap koneksi dapat database in-memory baru | `StaticPool` |
| Build gagal `TS1117` properti ganda | dua kunci sama di `KAMUS` i18n | hapus duplikat |
| Label menu tertukar dengan ikon | `re.sub` per baris pada array `TAB` | ganti blok utuh |
| Tabel "Pengguna" menampilkan teks tak terlihat | kelas `bg` dan `text` bernilai warna sama | audit: cari baris dengan `bg-[#x]` dan `text-[#x]` sama |
| Logo tidak muncul di login | aset eksternal/CDN | taruh di `frontend/public/`, rujuk path relatif |
| Preview aplikasi kosong total | kode browser memanggil `localhost:8000` langsung | selalu pakai URL relatif `/api/...`; dev server memproksikan |
| Login "berhasil" tapi langsung kembali ke form (deploy) | cookie `SameSite=lax` tidak dikirim lintas situs | `COOKIE_SAMESITE=none`, atau pakai satu-origin (`SAJIKAN_WEB=true`) |
| Aplikasi terbuka tanpa form login | penanda `tanpa-login.txt` ada, atau `AUTH_DISABLED=true` di `backend/.env` | jalankan `tanpa-login-mati.bat`, hapus baris itu, jalankan ulang `start-web.bat` (bagian 6c) |
| Login 200 tetapi `/api/auth/saya` 401, kembali ke form | cookie sesi tidak terkirim (iframe / lintas situs / cookie pihak ketiga diblokir) | sejak 0.7.5 ada cadangan `Authorization: Bearer` — pastikan tampilan web versi baru; untuk deploy beda situs setel `COOKIE_SAMESITE=none` atau pakai satu-origin |
| `uvicorn: Attribute "app" not found in module "app.main"` | baris `app = buat_app()` di akhir `main.py` ikut terhapus saat menyunting | tambahkan kembali; **tes unit tidak menangkapnya** karena tes memanggil `buat_app()` |

Catatan lingkungan kerja saya (mungkin berguna, mungkin tidak):
- **Playwright tidak bisa dipakai** di sandbox ini — unduhan Chromium gagal.
  Verifikasi visual dilakukan lewat build + grep CSS hasil build, atau render
  SSR sementara dengan `vite build --ssr`. Jangan buang waktu memasang browser.
- `generate_image` pernah gagal `429`; logo akhirnya dibuat sebagai SVG manual
  dan dirender ke PNG memakai `resvg-py` di venv terpisah.
- `convert`/`cairosvg`/`inkscape` tidak tersedia untuk mengubah SVG → PNG.

---

## 10. Pertanyaan yang MASIH menunggu jawaban pemilik

Ini bukan pekerjaan teknis yang bisa diputuskan sendiri. Jangan mengarang
jawaban; tanyakan. Sumber: `docs/ASUMSI.md` (bagian "Pertanyaan [TERBUKA]").

1. **Kontrak SICOM**: kontrak TSR20 bulan ke berapa dipakai sebagai acuan?
   Kolomnya ada, masih kosong.
2. **Aturan stok → harga**: berapa rentang rasio stok dan penyesuaian resminya?
   Yang terpasang sekarang masih **CONTOH dari template** (ada alarm yang
   mengingatkan hal ini).
3. **Selisih harga antar grade**: berapa selisih resminya? Rekomendasi harga
   kini dihitung pada rata-rata semua grade.
4. **Reject**: apakah Amount dibayar atas berat bersih setelah reject? Bila ya,
   Quantity perlu disesuaikan agar harga/kg tidak terlihat terlalu rendah.
5. **Selisih rekonsiliasi** Jul 2026 (5.269,319 vs 5.249,866 ton) dan Agu 2026
   (4.759,827 vs 4.752,949 ton): tiket dianggap sumber resmi, tetapi koreksi
   angka lama **butuh persetujuan** pemilik.
6. **Dasar angka perencanaan (Y27)**: dasar Penyesuaian Manual dan Effort belum
   diketahui; nilai template dimuat apa adanya.

Skrip alarm yang aktif saat ini memberi 7 temuan, termasuk selisih rekonsiliasi
yang menunggu persetujuan dan SICOM yang tertinggal 15 hari. Itu **bukan bug**;
itu data yang memang belum diisi.

---

## 11. Yang belum dikerjakan / kandidat lanjutan

Berurutan dari yang paling masuk akal:

1. **Merge PR #1 ke `main`** setelah pemilik menerima hasilnya (lihat 12).
2. **Ganti aturan stok→harga contoh** dengan kebijakan resmi (menunggu #2 di
   bagian 10). Tanpa ini, "rekomendasi harga beli" tidak bisa dipercaya.
3. **Isi SICOM & stok terbaru** agar `rekomendasi` berhenti berstatus
   `"DATA KURANG"` dan DoC bisa dihitung untuk bulan berjalan.
4. **Notifikasi**: alarm saat ini hanya terlihat bila halaman dibuka. Kandidat:
   ringkasan harian ke email/WhatsApp. Belum ada fondasinya.
5. **Peran pengguna** masih dua tingkat (admin / biasa). Kalau perlu pemisahan
   pembelian vs manajemen, mulai dari tabel `pengguna` dan middleware
   `wajib_admin`.
6. **PostgreSQL** untuk pemakaian bersama: cukup set `DATABASE_URL`, kode tidak
   berubah. Belum diuji di PostgreSQL sungguhan.
7. **Selisih harga antar grade** (menunggu #3) agar rekomendasi per grade.

---

## 12. Keamanan & data

- Rahasia ada di `backend/.env` (tidak masuk Git). `SECRET_KEY` **wajib** ≥ 32
  karakter di produksi; `ADMIN_SANDI_AWAL` hanya dipakai saat tabel pengguna
  masih kosong.
- Sandi disimpan sebagai hash (lihat `auth_lokal.hash_sandi`), sesi = JWT HS256
  di cookie `op_sesi` (HttpOnly). Sejak 0.7.5 token yang sama juga boleh dikirim
  lewat `Authorization: Bearer` dan disimpan tampilan web di `localStorage`
  sebagai cadangan untuk lingkungan yang memblokir cookie. Konsekuensinya:
  token itu terbaca JavaScript, jadi **jangan menambahkan fitur yang
  menampilkan HTML mentah dari pengguna** (cegah XSS). Bila tidak butuh
  cadangan ini, hapus `token` dari respons login di `auth_lokal.py`.
- **Tanpa Cloudflare Access**, perlindungan sepenuhnya bergantung pada login
  aplikasi + HTTPS di depannya. Panduan: `deploy/checklist-keamanan.md`.
- Backup: `deploy/backup.ps1` (harian, retensi 30 hari) dan prosedur uji
  restore di `deploy/restore.md`. **Backup yang belum pernah diuji restore
  bukan backup.**
- Data asli perusahaan **jangan** dimasukkan ke repo publik. `sample_data/`
  hanya template + data awal.

---

## 13. Kalau Anda buntu

Urutan pemeriksaan yang paling cepat menemukan akar masalah:

1. **Versi**: `cat VERSI.txt` vs `curl http://localhost:8000/api/health`
   (`versi` dan `kode` harus sama dengan folder).
2. **Proses**: `netstat -ano | findstr :8000` → apakah PID yang menjawab itu
   proses yang baru dijalankan? (`health` juga melaporkan `folder`, `pid`,
   `mulai`).
3. **Login**: `curl http://localhost:8000/api/auth/mode` → harus
   `"cara":"username-sandi"`.
4. **Data**: apakah mart terisi? `python -m app.cli ringkasan <tahun>`.
5. **Rumus**: jalankan `pytest -q`. Kalau semua lulus, kesalahan ada di UI atau
   data, bukan perhitungan.
6. **Frontend**: `npm run build` — error tipe muncul di sini lebih awal daripada
   di browser.
7. Baru terakhir: baca log uvicorn dan konsol browser.

Untuk pengguna non-teknis, arahkan ke **`diagnosa.bat`** — skrip itu mencetak
semua hal di atas dalam bahasa manusia, termasuk folder dan PID proses yang
menjawab.

---

## 14. Riwayat keputusan penting

| Tanggal | Keputusan | Alasan |
|---|---|---|
| 2026-10 | Tiket = sumber resmi, Excel lama pembanding | tiket berasal dari transaksi nyata |
| 2026-10 | Bridge hanya dua penyebab (SICOM, OP Price) | agar jumlahnya menutup persis ke Δ margin |
| 2026-10 | DoC memakai pemakaian implisit neraca stok | tidak ada data pemakaian langsung; menolak mengarang |
| 2026-10 | Safety dibandingkan dalam hari | tonase menyesatkan saat laju olah berubah |
| 2026-10-18 | Amount = total pembayaran per hari (bukan per grade/vendor) | menyesuaikan sumber data yang ada |
| 2026-10-25 | **Login Cloudflare Access dihapus permanen** | pemilik tidak memakainya; satu jalur masuk lebih sederhana diaudit |
| 2026-10-25 | Tema korporat merah–navy + logo Rubber Intelligence | mengikuti materi identitas dari pemilik |
| 2026-10-25 | Halaman "Ringkasan" → **Margin Performance**; isi ditambah strip angka kunci + panel "perlu perhatian" | halaman depan harus menjawab "apa yang harus saya lakukan hari ini", bukan hanya "berapa angkanya" |

---

## 15. Ringkasan satu paragraf

Aplikasi ini menghitung selisih harga pasar dan harga beli karet, lalu
menjelaskan sebabnya. Angka dihitung di backend (`core/`), ditampilkan di React,
dan tidak boleh dikarang saat data kurang. Yang paling sering merusak pengalaman
pengguna bukan logika, melainkan **proses lama yang masih hidup** dan **versi
yang tidak sinkron** — periksa itu lebih dulu sebelum menyentuh kode. Jaga semua tes tetap hijau, jaga `.bat` tetap ASCII, dan jangan kembalikan Cloudflare
Access.
