# ASUMSI — keputusan default yang saya ambil (Fase 1)

Setiap hal bertanda **[TERBUKA]** di spesifikasi TIDAK saya putuskan sendiri;
daftar pertanyaannya ada di bagian bawah. Yang di bawah ini adalah default
teknis yang saya pilih dan bisa diubah kapan saja.

## Default teknis Fase 1
1. **Database**: SQLite (file `backend/opmargin.db`). Pindah ke PostgreSQL cukup
   mengganti `DATABASE_URL` di `.env`, tanpa mengubah kode. Alembic (migrasi
   skema) menyusul di fase berikutnya; sementara tabel dibuat lewat `init-db`.
2. **Granularitas pembelian**: importer menerima total/hari (`ALL`), per grade,
   per vendor, atau per tiket. Saat membangun mart, bila satu tanggal punya
   baris rinci (bukan `ALL`), baris `ALL` pada tanggal itu diabaikan supaya
   tidak hitung ganda.
3. **SICOM hari libur**: dipakai harga terakhir yang tersedia (baris terbaru
   dengan tanggal <= hari itu). Kolom `kontrak` disimpan dan boleh kosong.
4. **Kurs**: baris terbaru dengan `berlaku_dari <= tanggal` (bisa berubah di
   tengah bulan — diuji dengan kasus Mar 2020).
5. **Hari tanpa pembelian**: margin = 0 dan harga = 0 di mart harian; bulan
   hanya menghitung hari pembelian (sesuai spesifikasi).
6. **Aturan stok→harga dari template**: dimuat sekali sebagai **CONTOH**
   (berlaku_dari diset 01/01/2000) dan setiap rekomendasi harga menampilkan
   peringatan "masih CONTOH". Harus diganti aturan resmi.
7. **Baris contoh di Intake_Tiket template** (vendor V999/V998) ikut terimpor
   dan otomatis memunculkan peringatan "vendor tak dikenal". Hapus baris kuning
   contoh sebelum mengunggah data sungguhan.
8. **Apr 2022**: sistem menghitung nilai benar **4,3391** (Excel lama salah
   ketik di sel T147 menampilkan 5,5232 — sudah dikonfirmasi pengguna).
   Dicatat sebagai koreksi, tidak direplikasi.
9. **Idempoten**: file dengan isi persis sama (SHA-256 sama) boleh diunggah
   ulang; lapisan `raw` selalu mencatat unggahan baru (jejak), lapisan `clean`
   memakai kunci alami sehingga tidak pernah berganda.
10. **line_seq tiket** = urutan kemunculan baris dalam tiket di file yang
    diunggah. Mengunggah ulang file yang sama meng-update baris yang sama,
    tidak menggandakan.
11. **Reject** belum dikurangkan dari Wet/Dry (mengikuti data sumber).
    Lihat [TERBUKA] di bawah — berpotensi membuat margin tampak 2–3 US¢/kg
    lebih tinggi bila Amount dibayar atas berat bersih.
12. **Rata-rata tahun berjalan**: rata-rata sederhana 12 bulan = angka resmi
    (seperti Excel); rata-rata tertimbang tonase ditampilkan sebagai informasi.

## Default teknis Fase 2
13. **Qty_Kering_Kg kosong di Pembelian_Harian** dihitung dari jumlah Dry
    tiket pada lingkup yang sama (per tiket / vendor / grade / total hari),
    **tanpa tiket nol**. Bila tiketnya belum ada, baris DITOLAK dengan pesan
    jelas (bukan ditebak).
14. **Input manual SICOM/kurs** lewat halaman web dicatat sebagai "unggahan"
    di lapisan raw (siapa, kapan, nilai apa) supaya tetap bisa ditelusuri;
    menyimpan tanggal yang sama = menimpa dengan pemberitahuan nilai lama,
    tidak menggandakan. Mart dibangun ulang otomatis setiap simpan.
15. **Baris catatan** di sheet template (hanya teks panjang di kolom pertama,
    mis. baris 10 Parameter_Pabrik) dilewati tanpa error.
16. **Keamanan**: halaman input Fase 2 belum memakai login/peran (menyusul di
    fase keamanan dengan Cloudflare Access). Backend hanya mendengarkan
    127.0.0.1; browser memanggil lewat proxy satu-origin (URL relatif /api).

## Default teknis Fase 3
17. **Apr 2022** ditampilkan 4,3391 dengan label catatan koreksi di layar dan
    di ekspor Excel (Excel lama salah ketik di sel T147 menampilkan 5,5232).
18. **Rekonsiliasi**: selisih yang sudah diketahui (Jul 2026 = 19,453 ton;
    Agu 2026 = 6,878 ton; tiket berhenti 19 Sep 2026) ditanam sebagai data
    referensi dan selalu tampil di halaman Rekonsiliasi. Pemeriksaan harian
    tiket-vs-pembelian memakai toleransi 1 kg. Tidak ada koreksi otomatis —
    menunggu persetujuan pengguna [TERBUKA].
19. **Margin per grade/vendor** hanya dihitung bila Amount tersedia pada
    tingkat itu; kalau tidak, layar menampilkan "data harga belum tersedia".
    Tidak ada alokasi harga diam-diam.
20. **Kartu query**: semua kartu adalah query terdefinisi di backend dengan
    filter berdaftar-putih (tanggal, bulan, vendor, grade, EUDR, provinsi,
    kabupaten, kecamatan, desa). Tidak ada SQL dari klien. Teks "Cara
    dihitung" bersumber dari `semantic/metrics.yaml`.
21. **Telusur**: klik angka OP Margin bulanan → hari penyusun → baris
    pembelian/tiket + unggahan asal (nomor unggahan, nama file, pengunggah,
    waktu). Jejak menunjuk unggahan TERAKHIR yang menyentuh baris itu;
    riwayat penuh tetap tersimpan di lapisan raw.
22. **Lonjakan harga harian** dihitung terhadap median bulan yang sama,
    ambang 10% sesuai spesifikasi; "data terlambat" memakai ambang 3 hari
    (kurs dikecualikan karena hanya diisi saat berubah).

## Default teknis Fase 4
23. **Versi aturan & parameter tidak bisa ditimpa**: tanggal berlaku yang sama
    ditolak; buat tanggal baru. Versi lama tetap dipakai untuk tanggal lama,
    sehingga hasil historis tidak pernah berubah. Semua perubahan (aturan,
    parameter, perencanaan, pengaturan alarm) tercatat di `audit_log`.
24. **Ambang alarm bawaan** (semua bisa diubah admin, bukan kode):
    stok < 100% safety; SICOM > 1 hari; stok/tiket > 3 hari; kurs > 60 hari
    (karena hanya diisi saat berubah); selisih rekonsiliasi harian > 100 kg;
    margin bulan terakhir < target; harga aktual > harga maks aturan.
25. **Simulasi** memakai aturan/parameter/target yang berlaku pada tanggal
    simulasi (default hari ini) dan tidak menyimpan apa pun.
26. **Analisis stok vs margin** dihitung dari data (bukan angka tetap):
    korelasi Pearson bulan-bulan yang punya data stok; label "asosiasi,
    bukan sebab-akibat" selalu tampil.
27. **Status stok harian**: "di bawah safety" bila rasio < 1; "tanpa safety"
    bila safety stock tidak terdefinisi pada tanggal itu.

## Default teknis Fase 5
28. **Verifikasi Access di backend** memakai pustaka PyJWT + cryptography
    (standar industri untuk RS256/JWKS); kunci publik di-cache 1 jam dan
    diambil ulang otomatis saat Cloudflare merotasi kunci.
29. **Gagal-tertutup di produksi**: `APP_ENV=produksi` + `AUTH_DISABLED=true`
    → aplikasi menolak start; konfigurasi Access kosong di produksi → juga
    menolak start. Halaman /docs dan /openapi.json otomatis mati di produksi.
30. **/api/health** terbuka tanpa login untuk monitoring, hanya berisi
    status/versi/waktu (tanpa data bisnis).
31. **Backup**: snapshot SQLite lewat backup API (aman saat server menulis),
    verifikasi `integrity_check` otomatis, retensi 30 hari; logika restore
    diuji di unit test setiap kali pytest dijalankan.
32. **Peran rinci (admin/manajer/intake/viewer)** belum diberlakukan di
    endpoint — semua email yang lolos Access punya akses sama. Pemetaan
    email→peran menyusul (butuh daftar email per peran dari Anda).

## Default teknis Fase 6
33. **Unggah lewat web** (tab Unggah Data): hanya .xlsx, batas 20 MB
    (UNGGAH_MAKS_MB di .env), jenis file dideteksi otomatis (ekspor Master
    Data vs format template), file asli disimpan di `backend/unggahan/`
    (ikut backup harian, tidak pernah dihapus), setiap unggahan tercatat di
    audit log, dan mart + alarm dihitung ulang otomatis.
34. **Amount pembelian** dicatat sebagai total per hari (jawaban pengguna:
    hasil kalkulasi total pembayaran getah intake per hari). Karena Amount
    diturunkan dari pembayaran intake, aturan rekonsiliasi "Dry tiket per
    tanggal = Quantity pembelian" adalah pemeriksaan konsistensi yang sah.

## Default teknis Fase 7
35. **Harga per grade = daftar harga (price list)**, berlaku sejak tanggal
    isian sampai ada harga baru. Diisi lewat form (bulk per tanggal) atau
    bulk import sheet 'Harga_Grade' (template unduhan tersedia). Grade harus
    ada di master (form menolak; import memberi peringatan). Tercatat di
    audit log; menimpa tanggal sama tidak menggandakan.
36. **Margin per grade dari daftar harga berlabel INDIKATIF** — bukan dari
    Amount pembayaran aktual (Amount resmi = total/hari). Apakah daftar harga
    ini akan dipakai untuk alokasi Amount per grade secara resmi masih
    [TERBUKA] (lihat #4) — sistem tidak memutuskan sendiri.
37. **Master grade** dikelola lewat menu (tambah/ubah; kode TTSR otomatis
    EUDR). Grade tidak pernah dihapus dari sistem, hanya ditambah/diubah,
    agar data historis tetap tertaut.

## Pertanyaan [TERBUKA] — menunggu jawaban Anda
| # | Topik | Pertanyaan |
|---|-------|-----------|
| 1 | ~~Granularitas Amount~~ | **TERJAWAB (18/10/2026)**: Amount pembelian/hari = hasil kalkulasi TOTAL pembayaran getah intake per hari → granularitas resmi = total per hari. Rincian per grade/vendor belum ada (lihat #4). |
| 2 | Kontrak SICOM | Kontrak TSR20 bulan ke berapa yang dipakai sebagai acuan? Kolom sudah ada, masih kosong. |
| 3 | Aturan stok→harga | Apa rentang rasio dan penyesuaian resmi? Isi template hanyalah contoh bentuk. |
| 4 | Selisih harga antar grade | Berapa selisih harga beli antar grade? Rekomendasi harga saat ini dihitung di rata-rata semua grade. |
| 5 | Reject | Apakah Amount dibayar atas berat bersih (setelah reject)? Bila ya, Quantity perlu disesuaikan agar harga/kg tidak terlihat terlalu rendah. |
| 6 | Selisih rekonsiliasi | Jul 2026 (5.269,319 vs 5.249,866) dan Agu 2026 (4.759,827 vs 4.752,949): tiket dianggap sumber resmi — perlu persetujuan Anda sebelum angka lama dikoreksi. |
| 7 | Dasar angka Y27 | Dasar Penyesuaian Manual dan Effort di Perencanaan belum diketahui; nilai template dimuat apa adanya. |
