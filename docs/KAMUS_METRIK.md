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
| E (harga beli Rp tertimbang) | ΣAmount / Σqty | Rp/kg | Dipakai margin bridge; dasar dekomposisi |
| K (kurs efektif tertimbang) | ΣAmount / Σ(Amount/kurs) | Rp/USD | OP Price = 100 × E / K **persis** (identitas) |
| efek harga Rp (bridge) | 100 × (E_B − E_A) / K_A | US¢/kg | Kontribusi ke margin = −efek ini |
| efek kurs (bridge) | 100 × E_B × (1/K_B − 1/K_A) | US¢/kg | Kontribusi ke margin = −efek ini |
| penutupan bridge | awal + ΔSICOM − efek harga − efek kurs − akhir | US¢/kg | Harus ~0: bridge tertutup persis |
| days of cover | stok_ton / kapasitas_ton_per_hari | hari | Sama dengan `days`; kapasitas & safety ikut parameter yang berlaku pada tanggal itu |
| safety (hari) | safety_ton / kapasitas_ton_per_hari | hari | Pembanding days of cover (bukan ambang konstan) |

**Margin Bridge** (`/api/margin-bridge`) — tombol analisa pada kartu RM Stock –
Intake vs Pricing: OP Margin periode A → B diurai menjadi ΔSICOM, efek harga
beli Rp/kg, dan efek kurs. Periode mengikuti filter kartu (`dari`/`sampai`,
format YYYY-MM): A = bulan `dari`, B = bulan `sampai`; bila satu bulan dipilih,
A = bulan sebelumnya. Tanpa filter: default bulan terakhir vs sebelumnya
(atau `basis=tahunan` untuk tahun vs tahun, hanya bulan berdata di kedua tahun).
SICOM/OP Price/margin memakai rumus resmi di atas, sehingga ujung bridge =
angka ringkasan resmi.

**Days of Cover** (`/api/days-of-cover`) — tombol analisa pada kartu yang sama:
cadangan hari olah dari stok, dengan tren harian, safety stock dalam hari,
rerata 30 data terakhir, dan hitungan hari di bawah safety. `dari`/`sampai`
menerima YYYY-MM (periode kartu; `sampai` = akhir bulan) atau YYYY-MM-DD;
bawaannya 180 hari data terakhir. Bisa diekspor ke Excel (`format=xlsx`).

Catatan hubungan stok–margin (halaman analisis, fase berikutnya): korelasi
historis ±0,43 adalah **asosiasi, bukan bukti sebab-akibat** — wajib ditulis
demikian di layar.
