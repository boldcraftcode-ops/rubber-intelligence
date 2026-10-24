# OP Margin

Aplikasi web internal pengganti Excel "Details OP Margin" & "Analisa OP Margin"
untuk perusahaan pengolah karet (OP = out purchase; margin = SICOM − harga beli,
US¢/kg, basis berat kering).

- Cara menjalankan: `docs/CARA_MENJALANKAN.md`
- Asumsi & pertanyaan terbuka: `docs/ASUMSI.md`
- Definisi metrik: `docs/KAMUS_METRIK.md`

Status: **Fase 7** — menu master grade & halaman harga per grade (form harian +
bulk import dengan template unduhan, margin indikatif). Sudah ada API (FastAPI)
dan aplikasi web (React + Vite): ringkasan, input harian SICOM/kurs, unggah data,
rekonsiliasi, perencanaan, alarm, pengguna, dll. **100 unit test** — termasuk 19
kasus uji emas yang dicocokkan persis dengan perhitungan Excel lama.

Struktur: `backend/` = API, rumus inti, importer, pengujian; `frontend/` =
aplikasi web; `docs/` = panduan & asumsi; `deploy/` = panduan deployment;
`sample_data/` = template Excel (data awal).

Catatan: `sample_data/` berisi template & data awal; jangan memasukkan data
rahasia asli ke repositori publik.
