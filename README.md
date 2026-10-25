# OP Margin

Aplikasi web internal pengganti Excel "Details OP Margin" & "Analisa OP Margin"
untuk perusahaan pengolah karet (OP = out purchase; margin = SICOM − harga beli,
US¢/kg, basis berat kering).

- Cara menjalankan: `docs/CARA_MENJALANKAN.md`
- Asumsi & pertanyaan terbuka: `docs/ASUMSI.md`
- Definisi metrik: `docs/KAMUS_METRIK.md`
- Tema & identitas visual (palet, logo, aturan): `docs/TEMA.md`
- **Serah terima proyek** (untuk pengganti): `docs/SERAH_TERIMA.md`

Status: **v0.7.7** — halaman depan **Margin Performance**: strip angka kunci
(OP Margin vs target, SICOM, Days of Cover, intake) + panel "perlu perhatian
hari ini". Di menu **Analisis**, kartu **Penerimaan karet** punya
**rincian per bulan** (bulan × vendor/provinsi/kabupaten/kecamatan/desa) bila
filter periode lebih dari satu bulan, lengkap dengan tabel angka yang sama.
Kartu **RM Stock – Intake vs Pricing**
punya tiga tombol analisa dengan periode mengikuti filter kartu:
**5W1H**, **Margin Bridge** (ΔM = ΔSICOM − ΔOP Price, dua penyebab: pasar vs
keputusan, + bridge per bulan), dan **Days of Cover** (pemakaian implisit dari
neraca stok, safety dibandingkan dalam hari). Sudah ada API (FastAPI)
dan aplikasi web (React + Vite): ringkasan, input harian SICOM/kurs, unggah
data, rekonsiliasi, perencanaan, alarm, pengguna, dll. **172 unit test** —
termasuk 19 kasus uji emas yang dicocokkan persis dengan perhitungan Excel lama.

Struktur: `backend/` = API, rumus inti, importer, pengujian; `frontend/` =
aplikasi web; `docs/` = panduan & asumsi; `deploy/` = panduan deployment;
`sample_data/` = template Excel (data awal).

Catatan: `sample_data/` berisi template & data awal; jangan memasukkan data
rahasia asli ke repositori publik.
