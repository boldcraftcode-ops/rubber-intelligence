# Prosedur restore backup + uji restore

Backup harian tersimpan di `C:\op-margin-backup\YYYY-MM-DD_HHmm\opmargin.db`
(30 hari terakhir). Log di `C:\op-margin-backup\backup-log.txt`.

## A. Uji restore di folder uji (lakukan berkala, minimal tiap 3 bulan)

Tujuan: memastikan file backup benar-benar bisa dipakai, TANPA menyentuh
database produksi.

```powershell
# 1. Siapkan folder uji
mkdir C:\op-margin-uji-restore

# 2. Salin backup terbaru ke folder uji
$terbaru = Get-ChildItem C:\op-margin-backup -Directory | Sort-Object Name | Select-Object -Last 1
copy "$($terbaru.FullName)\opmargin.db" C:\op-margin-uji-restore\opmargin.db

# 3. Periksa keutuhan dan isi datanya memakai Python aplikasi
cd C:\op-margin\backend
.venv\Scripts\python -c "import sqlite3; c=sqlite3.connect(r'C:\op-margin-uji-restore\opmargin.db'); print('integrity:', c.execute('PRAGMA integrity_check').fetchone()[0]); print('baris pembelian:', c.execute('select count(*) from pembelian').fetchone()[0]); print('OP Margin Jan 2026:', c.execute('select round(op_margin_usc,4) from mart_bulanan where tahun=2026 and bulan=1').fetchone()[0])"
```

Hasil yang benar: `integrity: ok`, jumlah baris masuk akal (ribuan), dan
OP Margin Jan 2026 = 10.5725. Bila ketiganya benar → **uji restore BERHASIL**;
catat tanggal uji di buku catatan operasional. Hapus folder uji bila selesai:
`rmdir /s C:\op-margin-uji-restore`.

(Logika uji yang sama dijalankan otomatis di unit test
`backend/tests/test_fase5.py::test_backup_dan_restore` setiap kali
`pytest` dijalankan.)

## B. Restore sungguhan (musibah: db rusak/terhapus)

```powershell
# 1. Hentikan service API
C:\nssm\nssm.exe stop OPMarginAPI

# 2. Amankan file lama (jangan langsung menimpa)
cd C:\op-margin\backend
rename opmargin.db opmargin-rusak-$(Get-Date -Format yyyyMMdd).db

# 3. Salin backup yang dipilih
copy C:\op-margin-backup\[PILIH-TANGGAL]\opmargin.db opmargin.db

# 4. Nyalakan lagi dan periksa
C:\nssm\nssm.exe start OPMarginAPI
# buka http://127.0.0.1:8000/api/health lalu cek halaman Ringkasan
```

Setelah restore: data yang masuk SETELAH waktu backup harus diunggah/diisi
ulang (lihat tanggal di halaman Kualitas Data → Kesegaran data).
