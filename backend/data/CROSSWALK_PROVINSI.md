# Crosswalk Provinsi → Kabupaten/Kota untuk ID_AUX

## Sumber resmi

- Dataset: **Kode dan Data Wilayah Administrasi Indonesia**, repositori
  `dikisiswanto/wilayah-administrasi-indonesia` pada commit `e6b51084d8f8dfed2a3325d72e8a9aa4bf1be4ee`.
- Dasar data: **Keputusan Mendagri No. 100.1.1-6117 Tahun 2022**, sebagaimana
  dicantumkan README sumber; tautan: <https://github.com/dikisiswanto/wilayah-administrasi-indonesia/tree/e6b51084d8f8dfed2a3325d72e8a9aa4bf1be4ee/csv>.
- Lisensi: MIT. Salinan `LICENSE.txt`, `provinces.csv`, dan `regencies.csv`
  ada di `backend/data/sumber_crosswalk/` untuk audit offline.
- Diakses: 2026-11-05.

## Isi berkas

`crosswalk_provinsi_id_aux.csv` memetakan `kabupaten_norm` pada tabel
`traceability_wilayah` (hasil `ID_AUX.xlsx`) ke:

| Kolom | Arti |
|---|---|
| `kabupaten_norm` | Kunci hasil normalisasi `ID_AUX` |
| `provinsi` | Nama provinsi resmi |
| `kode_provinsi`, `kode_kabupaten` | Kode Kemendagri dari sumber |
| `nama_referensi` | Nama Kabupaten/Kota pada sumber |
| `dasar` | `exact`, `alias_ejaan`, `alias_nama_lama`, atau `alias_kecamatan` |
| `sumber` | Penanda versi/commit sumber |

## Cara pemetaan

1. Nama Kabupaten/Kota pada `regencies.csv` dinormalisasi dengan
   `normalisasi_kabupaten()` yang sama dengan aplikasi, lalu dihubungkan ke
   `province_id` → `provinces.csv`.
2. `kabupaten_norm` dari seluruh 81.909 baris SCDF dicocokkan ke peta itu.
   Cocok langsung → `dasar=exact`.
3. Variasi ejaan, awalan `ADM.`/`KEP.`, dan nama lama dicocokkan ke nama resmi
   lewat daftar alias yang eksplisit. Alias nama lama/penyingkatan hanya
   dipakai bila kecamatan pada ID_AUX cocok dengan kecamatan pada kabupaten
   tujuan: BARU → KOTABARU 20/21 kecamatan, MALUKU TENGGARA BARAT → KEPULAUAN TANIMBAR 7/10 kecamatan, MAMUJU UTARA → PASANGKAYU 12/12 kecamatan, TOBA SAMOSIR → TOBA 16/16 kecamatan.
4. `BANJAR` sengaja **tidak** dipetakan: nama itu dipakai dua provinsi pada
   sumber resmi. Kecamatan ID_AUX cocok 18/23 dengan
   `KALIMANTAN SELATAN` dan 4/23 dengan `JAWA BARAT`;
   memilih satu secara otomatis akan salah untuk sebagian baris.
5. Selain `BANJAR`, kunci yang bukan satuan administrasi — `DANAU`,
   `DANAU TOBA`, `HUTAN`, `UNKNOWN`, `WADUK CIRATA`, `WADUNG KEDUNGOMBO` —
   dibiarkan tanpa provinsi. Ini fitur danau/hutan/waduk atau label kosong pada
   sumber geometri, bukan Kabupaten/Kota. Semua kunci tanpa pemetaan pasti
   tercantum di bagian **Cakupan** dan tetap `provinsi_norm = NULL`.

## Cakupan

- Kabupaten/Kota unik pada ID_AUX: **494**
- Termapping: **487** (98.6%)
- Tidak termapping: **7** — `BANJAR`, `DANAU`, `DANAU TOBA`, `HUTAN`, `UNKNOWN`, `WADUK CIRATA`, `WADUNG KEDUNGOMBO`
- Provinsi pada crosswalk: **37**

## Aturan pakai

- Crosswalk **hanya mengisi** `traceability_wilayah.provinsi` dan
  `provinsi_norm`; baris intake, koreksi, audit, dan `code` tidak diubah.
- Nilai Provinsi pada data intake **tidak pernah** dipakai sebagai sumber
  opsi edit. Filter Provinsi tetap boleh memakai nilai intake yang sudah ada,
  tetapi koreksi wajib memakai nama dari crosswalk.
- Baris yang tidak termapping tetap `provinsi_norm = NULL`. Validator
  Kabupaten/Kota/Kecamatan/Desa tidak memaksakan filter provinsi pada baris
  itu, tetapi tetap menolak Provinsi yang tidak ada di crosswalk.
- Untuk memperbarui: ganti snapshot sumber, perbarui commit SHA di `sumber`,
  jalankan ulang pembuatan CSV, lalu panggil
  `terapkan_crosswalk_provinsi()`; baris yang sudah terisi tidak ditimpa.
