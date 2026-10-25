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
