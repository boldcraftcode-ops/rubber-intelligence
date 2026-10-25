# SERAH TERIMA — Rubber Intelligence (OP Margin)

Dokumen ini ditulis untuk **orang yang menggantikan saya** mengurus proyek ini.
Isinya bukan promosi, tapi hal-hal yang kalau tidak diketahui akan memakan waktu:
apa yang sudah jadi, apa yang belum, aturan yang tidak boleh dilanggar, dan
jebakan yang sudah pernah menjatuhkan saya.

Kalau Anda hanya punya 15 menit, baca bagian **1 (Status)**, **3 (Cara
menjalankan)**, dan **7 (Aturan yang tidak boleh dilanggar)**. Selebihnya bisa
dibaca saat mengerjakan tugas pertama.

Terakhir diperbarui: **2026-10-25**, versi kode **0.7.7**.

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
| Versi kode | **0.7.7** (`VERSI.txt`, `backend/app/versi.py`, `frontend/src/versi.ts`) |
| Branch kerja | `arena/18670644-rubber-intelligence` |
| Pull request | **#1 masih terbuka** — https://github.com/boldcraftcode-ops/rubber-intelligence/pull/1 |
| Branch `main` | belum memuat pekerjaan v0.7.x |
| Unit test | **208 lulus** (`cd backend && .venv/bin/python -m pytest -q`) |
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
.venv/bin/python -m pytest -q                                  # 208 tes
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
│   ├── tests/                  208 tes, termasuk kasus emas Excel lama
│   ├── unggahan/               berkas Excel yang diunggah lewat web
│   └── .env.example            contoh setelan (JANGAN commit .env asli)
└── frontend/
    ├── src/App.tsx             kerangka: sidebar, header, daftar menu (TAB)
    ├── src/pages/*.tsx         16 halaman
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
7. **208 tes harus tetap lulus.** Tes "kasus emas"
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
11. **Jangan bekerja di branch lain.** Semua pekerjaan di
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

### Rincian bulanan pada kartu penerimaan
`GET /api/kartu/penerimaan?per=bulan` mengubah bentuk jawaban dari "satu baris
per dimensi" menjadi **bulan × dimensi** (dipakai saat filter periode lebih dari
satu bulan). Aturannya, dan ini disengaja:

- **Sumbu bulan mengikuti periode filter**, bukan data. Mengganti filter lain
  (mis. hanya EUDR) tidak boleh menggeser sumbu, karena perbandingan bulan akan
  menyesatkan. Bulan tanpa tiket tampil sebagai 0.
- Pengecualian: rentang > 24 bulan dipotong ke rentang bulan berdata agar grafik
  tidak penuh kolom kosong.
- `top` (1–40) dimensi terbesar dipertahankan; sisanya digabung menjadi satu
  baris `Lainnya (n vendor)` supaya grafik tetap terbaca.
- Tanpa `per=bulan`, bentuk jawaban **tidak berubah** — halaman/kartu lain dan
  ekspor lama tetap aman. Ini dijaga oleh tes.

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
cd backend && .venv/bin/python -m pytest -q          # 208 passed
cd ../frontend && npm run build                       # bersih

# 2. naikkan versi di 6 berkas (contoh 0.7.7 -> 0.7.8)
cd ..
for f in VERSI.txt backend/app/versi.py frontend/src/versi.ts \
         docs/CARA_MENJALANKAN.md diagnosa.bat hentikan-api.bat; do
  sed -i 's/0\.7\.7/0.7.8/g' "$f"
done
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
