# TEMA & IDENTITAS VISUAL

Tema aplikasi mengikuti panduan identitas korporat: **latar terang, navy, aksen
merah**. Dokumen ini mencatat palet, berkas yang mengatur, dan aturan
pemakaiannya supaya perubahan berikutnya tetap konsisten.

## Palet

| Warna | Kode | Peran |
|---|---|---|
| Merah | `#FF1313` | Aksen: tombol utama, garis aksen, label kecil (eyebrow), garis merah di atas kartu |
| Navy | `#1D2434` | Warna utama: panel identitas, judul, teks utama, garis grafik |
| Putih | `#FFFFFF` | Permukaan: kartu, modal, panel form |
| Abu terang | `#F8F8F8` | Latar halaman, area sidebar bawah, latar item menu aktif |
| Abu | `#64676C` | Teks sekunder: keterangan, label kolom, sumbu grafik |

Warna status (aman / tipis / di bawah target) memakai biru–kuning–oranye
`#3B82F6`, `#EAB308`, `#F97316` **disertai ikon dan angka**, bukan hanya warna —
supaya tetap terbaca oleh pengguna buta warna.

## Berkas yang mengatur tampilan

- `frontend/src/index.css` — palet dasar, latar halaman (`.galaxy`), garis
  merah di atas kartu (`.kartu-aksen`), pola titik (`.pola-titik`), gaya
  scrollbar dan grafik Recharts.
- `frontend/src/bersama.tsx` — gaya bersama: `kelasInput`, `kelasLabel`,
  `kelasTombol`, `kelasTombolKecil`, `kelasTombolAnalisa`, dan komponen `Kartu`.
- `frontend/src/App.tsx` — kerangka: sidebar navy, menu dengan garis merah di
  kiri item aktif, kepala halaman (eyebrow merah + judul navy).
- `frontend/src/pages/*.tsx` — isi tiap halaman. Warna grafik didefinisikan di
  dekat grafiknya; palet seri ada di `Ringkasan.tsx` (`WARNA`) dan
  `WARNA_STATUS`.
- `frontend/public/logo-rubber-intelligence.svg` — logo utama (dipakai di
  halaman login, sidebar, dan favicon). Tersedia juga `logo-rubber-intelligence.png`
  (512 px) dan `logo-192.png`.

## Logo

Logo menggabungkan dua hal: **daun karet tiga helai** (bahan baku) dengan
**tetesan lateks merah** dan **dua simpul data** (analitik). Hanya dua warna —
navy `#1D2434` dan merah `#FF1313` — supaya tetap tajam saat dicetak maupun
dikecilkan menjadi favicon.

Berkas SVG dibuat manual (bukan hasil ekspor alat desain), jadi aman di-edit:
ubah `#1D2434`/`#FF1313` di dalam SVG bila identitas berubah.

## Aturan pemakaian

1. **Merah hemat.** Satu aksen merah per layar sudah cukup: tombol utama,
   eyebrow, atau garis aksen — jangan tiga-tiganya sekaligus.
2. **Sudut tajam.** Kartu, tombol, dan input memakai `rounded-sm`; hindari
   sudut bulat besar agar tetap terasa korporat.
3. **Garis rambut.** Pemisah memakai `#E4E5E8`, bukan bayangan tebal.
4. **Judul = kesimpulan.** Judul kartu menyebut kesimpulan angka, bukan nama
   grafik (aturan lama, tetap berlaku).
5. **Kontras.** Teks navy di atas putih/abu terang; jangan menaruh teks putih
   di atas permukaan putih.

## Mengubah tema

Semua warna aksen terkumpul di dua tempat: variabel di `bersama.tsx`
(`NAVY`, `MERAH`, `ABU`) dan kelas Tailwind dengan nilai langsung
(`bg-[#FF1313]`, `text-[#1D2434]`). Untuk mengganti warna aksen, ganti
`#FF1313` di `frontend/src` dan di `index.css`; tidak ada warna aksen yang
disimpan di backend.
