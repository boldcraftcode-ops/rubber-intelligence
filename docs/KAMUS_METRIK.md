# KAMUS METRIK — OP Margin

Semua tonase dan harga analisis memakai **berat kering** (Dry, kg).
Definisi mesin ada di `backend/semantic/metrics.yaml`; file ini versi
yang mudah dibaca manusia.

| Metrik | Rumus | Satuan | Catatan |
|--------|-------|--------|---------|
| Dry | Wet × DRC / 100 | kg | Dipakai nilai dari ekspor; divalidasi selisih ≤ 1,5 kg |
| harga_rp_kg (harian) | amount_rp / qty_kering_kg | Rp/kg | Hari tanpa pembelian = 0 |
| harga_usc_kg (harian) | harga_rp_kg / kurs × 100 | US¢/kg | Kurs = baris terbaru dengan berlaku_dari ≤ tanggal |
| margin_harian | SICOM − harga_usc_kg | US¢/kg | Hari tanpa pembelian = 0 |
| sicom_bulan | Σ(qty×SICOM) / Σ(qty) | US¢/kg | Bobot tonase kering, hanya hari pembelian |
| harga_beli_bulan_usc | 100 × Σ(amount/kurs) / Σ(qty) | US¢/kg | Setara rata-rata harian tertimbang tonase |
| op_margin_bulan | sicom_bulan − harga_beli_bulan_usc | US¢/kg | Angka utama (pengganti Excel Details) |
| pencapaian | op_margin_bulan / target_bulan | rasio | Di Excel lama berlabel "%" |
| Avg YTD (resmi) | rata-rata sederhana bulan berdata | US¢/kg | Seperti Excel lama |
| Avg YTD tertimbang | Σ(margin×ton)/Σ(ton) | US¢/kg | Informasi saja |
| stok_ton | stok_kg / 1000 | ton | |
| days | stok_ton / kapasitas | hari | Kapasitas olah dari parameter_pabrik yang berlaku |
| safety_ton | Safety_Stock_Ton, atau Safety_Stock_Hari × kapasitas | ton | |
| rasio_stok | stok_ton / safety_ton | rasio | Masukan mesin aturan |
| target_efektif | target_bulan + penyesuaian aturan stok | US¢/kg | Aturan: batas bawah ≤ rasio < batas atas |
| harga_beli_maks_usc | SICOM hari ini − target_efektif | US¢/kg | Ditampilkan beserta alasannya |
| harga_beli_maks_rp | harga_beli_maks_usc × kurs / 100 | Rp/kg | |
| net_margin rencana | rata-rata margin bulan sama (tahun terpilih) + penyesuaian manual + effort | US¢/kg | Pengganti sheet Y27; default 4 tahun terakhir |
| Δ SICOM (bridge) | SICOM_B − SICOM_A | US¢/kg | Kontribusi = +Δ SICOM (pasar) |
| Δ OP Price (bridge) | OP Price_B − OP Price_A | US¢/kg | Kontribusi = −Δ OP Price (keputusan) |
| Δ Margin (bridge) | Δ SICOM − Δ OP Price | US¢/kg | Sama dengan selisih margin resmi; tertutup persis |
| Pass-through | Δ OP Price / Δ SICOM | rasio | Porsi penurunan SICOM yang diikuti harga beli; sisanya ditanggung margin |
| E (harga beli Rp tertimbang) | ΣAmount / Σqty | Rp/kg | Hanya untuk rincian Δ OP Price |
| K (kurs efektif tertimbang) | ΣAmount / Σ(Amount/kurs) | Rp/USD | OP Price = 100 × E / K persis |
| efek harga Rp (rincian) | 100 × (E_B − E_A) / K_A | US¢/kg | Kontribusi ke margin = −efek ini |
| efek kurs (rincian) | 100 × E_B × (1/K_B − 1/K_A) | US¢/kg | Kontribusi ke margin = −efek ini |
| pemakaian (DoC) | stok awal + intake − stok akhir | ton | Pemakaian implisit dari neraca stok |
| pemakaian harian | pemakaian / jumlah hari bulan | ton/hari | |
| days of cover | stok akhir / pemakaian harian | hari | Lebih adil daripada tonase karena menyesuaikan pemakaian |
| safety (hari) | safety ton / pemakaian harian | hari | 2.795 ton ≈ 21,5 hari pada 130 ton/hari |
| safety dinamis | 21,5 hari × pemakaian harian | ton | Pengganti safety tetap yang tidak responsif |

**Satuan tonase kartu RM Stock – Intake vs Pricing**: RM Stock, Intake, dan
Safety Level tersedia dalam **MT (metric ton)** maupun **kg**, dengan
`1 MT = 1.000 kg`. API `GET /api/ringkasan-elemen` mengirim `*_ton` dan `*_kg`
sekaligus; tombol **MT / kg** di kartu mengubah sumbu, grafik, dan angka utama
tabel, sementara angka kecil di bawahnya selalu menampilkan satuan pasangan.
Ekspor Excel memuat kolom untuk kedua satuan. SICOM, OP Price, dan OP Margin
tetap **US¢/kg** (harga, bukan berat); panel 5W1H, RCA, Margin Bridge, dan Days
of Cover tetap memakai ton sesuai rumusnya.

**Margin Bridge** (`/api/margin-bridge`) — tombol analisa pada kartu RM Stock –
Intake vs Pricing. Dua penyebab: ΔM = ΔSICOM − ΔOP Price. SICOM = harga acuan
pasar (di luar kendali), OP Price = harga beli (keputusan). Bridge per bulan
menandai penyebab *dipicu pasar* vs *dipicu keputusan*; rincian opsional
memecah Δ OP Price menjadi efek harga Rp dan efek kurs. Periode = pilihan
periode awal & akhir (bawaan mengikuti filter kartu). Contoh terverifikasi 2025:
Jan 15,00 → Des 8,77 (−6,23) = SICOM −18,39 (menekan) + OP Price +12,16
(menolong), pass-through 66%; April dipicu pasar (−8,28), Oktober dipicu
keputusan (−3,77).

**Days of Cover** (`/api/days-of-cover`) — tombol analisa pada kartu yang sama.
Pemakaian tidak ada di data, jadi dihitung dari neraca stok: pemakaian = stok
awal + intake − stok akhir; DoC = stok akhir ÷ (pemakaian ÷ hari). Safety
dibandingkan dalam hari, dan tersedia safety dinamis (21,5 hari × pemakaian
harian). Catatan: susut/transfer/penyesuaian stok terhitung sebagai pemakaian,
dan bulan pertama tidak bisa dihitung tanpa stok akhir bulan sebelumnya.

Catatan hubungan stok–margin (halaman analisis, fase berikutnya): korelasi
historis ±0,43 adalah **asosiasi, bukan bukti sebab-akibat** — wajib ditulis
demikian di layar.

## Tombol "Jelaskan ke saya"

Setiap kartu punya tombol **Jelaskan ke saya** (`GET /api/jelaskan/{kartu}`) yang
menjelaskan angka dengan urutan **jawaban dulu, bukti kemudian**:

| Bagian | Isi |
|--------|-----|
| `angka_utama` | **satu** angka saja (mis. "3 bulan berturut-turut di bawah target") |
| `what` | kesimpulan: apa yang terjadi |
| `so_what` | penyebab: harga acuan vs harga beli, tanpa istilah teknis |
| `now_what` | tindakan: tahan harga beli / cari pemasok lebih murah / tinjau target |
| `analogi` | warung beli Rp 9.000 jual Rp 10.000 = untung Rp 1.000/kg |
| `cara_baca` | satu kalimat membaca grafik |
| `detail` + `rumus` | **lapisan kedua**, hanya dibuka bila ditanyakan |

Aturan: angka dibulatkan ("sekitar 2 sen"), tidak ada empat desimal, tanpa kata
*variance*, *bridge*, atau *MoM*. Bila target berubah di tengah periode, narasi
menyebutkannya beserta sumbernya (tabel target margin), supaya pertanyaan
"kenapa target bulan itu X?" tidak menggantung.

## Supplier class berbasis intake (Traceability)

Kelas supplier **bukan** klasifikasi master (Small holder / Small estate /
Rubber trader) dan **bukan** sourcing type (Direct/Indirect Smallholder, Own
Plantation). Kelas dihitung murni dari volume intake, tidak disimpan dan tidak
bisa diisi manual.

| Kelas | Dry per supplier per bulan | Catatan |
|-------|---------------------------|---------|
| SS | ≥ 1.500 MT | batas tertinggi |
| S | ≥ 1.000 MT | |
| A | ≥ 500 MT | |
| B | ≥ 250 MT | |
| C | ≥ 100 MT | |
| D | < 100 MT | termasuk bulan tanpa intake bila tidak ada baris |

Rumus: `Dry (MT) = Σ dry_kg / 1.000` untuk satu `kode_vendor` pada satu
`YYYY-MM`, memakai baris intake yang lolos `_filter_base` (tiket valid, Wet/DRC
konsisten, bukan LATEX OP, mengikuti filter tahun/periode/EUDR). Perbandingan
memakai nilai **sebelum dibulatkan** supaya 1.499,9996 MT tidak naik menjadi
SS hanya karena tampil sebagai 1.500,000 MT. Detail Supplier Actors hanya
menampilkan **satu nilai kelas tertinggi** dalam periode, tanpa tabel bulanan;
ringkasan jumlah *supplier-bulan* per kelas berada di menu **Master Vendor**
(dengan tahun terbaru otomatis) dan hanya menghitung kode yang punya baris
Master Vendor.

## Rekonsiliasi: selisih asli vs selisih efektif

| Istilah | Arti |
|---------|------|
| `selisih_ton` / `selisih_kg` | Selisih **asli** antara dua sumber. Nilai ini tidak pernah diubah keputusan, supaya riwayat dan ekspor lama tetap dapat diaudit. |
| `selisih_efektif_ton` / `selisih_efektif_kg` | Selisih yang dipakai status & alarm: `0` bila sudah ada keputusan sumber benar,jika belum ada keputusan, sama dengan selisih asli. |
| `nilai_dipakai_ton` / `nilai_dipakai_kg` | Angka dari sumber yang dipilih (Tiket, Excel lama, atau Qty pembelian). |
| `sumber_dipakai` | Kode sumber yang disetujui: `tiket`, `excel`, atau `pembelian`. |
| `direvisi` / `koreksi` | Penanda keputusan beserta alasan, pembuat, dan waktu; keputusan dapat dibatalkan. |

Keputusan **tidak menimpa** `tiket_baris`, `pembelian`, atau angka Excel lama.
Untuk selisih bulanan Jul/Agu 2026, sumber yang dipilih juga menjadi
`sumber_intake` pada `GET /api/ringkasan-elemen`; bulan tanpa keputusan tetap
memakai urutan lama: tiket (bila wajar) → referensi rekonsiliasi → pembelian.
