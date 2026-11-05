@echo off
rem ============================================================
rem  Rubber Intelligence - perbarui-kode.bat
rem
rem  Mengunduh seluruh isi repository (kode + file data/referensi)
rem  dari branch GitHub lalu menaruhnya di folder baru. Aman untuk
rem  folder hasil ZIP; folder lama tidak dihapus atau ditimpa.
rem
rem  Pemakaian:
rem    perbarui-kode.bat                         (branch main)
rem    perbarui-kode.bat nama-branch             (branch pilihan)
rem
rem  Database lokal backend\opmargin.db dicadangkan ke folder baru
rem  menggunakan SQLite backup API, sehingga data lama tetap tersedia.
rem  backend\.env tidak disalin.
rem ============================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

set "PEMILIK=boldcraftcode-ops"
set "REPO=rubber-intelligence"
set "CABANG=%~1"
if not defined CABANG set "CABANG=main"
set "URL=https://codeload.github.com/%PEMILIK%/%REPO%/zip/refs/heads/%CABANG%"
set "ZIP=%TEMP%\rubber-intelligence-%RANDOM%-%RANDOM%.zip"
set "TUJUAN=%~dp0..\rubber-intelligence-terbaru"
set "KODE_KELUAR=0"
set "PY="

echo ============================================================
echo  Memperbarui Rubber Intelligence
echo ============================================================
echo  Branch : %CABANG%
echo  Sumber : %URL%
echo  Tujuan : %TUJUAN%
echo.
echo  File kode dan file data/referensi dari branch akan diunduh.
echo  Database lokal akan dicadangkan ke folder baru bila tersedia.
echo  Tutup aplikasi sebelum menjalankan agar salinan data paling baru.
echo.

rem ------------------------------------------------------------
echo [1/4] Mengunduh paket lengkap dari GitHub
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $ErrorActionPreference='Stop'; try { Invoke-WebRequest -UseBasicParsing -Uri '%URL%' -OutFile '%ZIP%'; if ((Get-Item -LiteralPath '%ZIP%').Length -lt 1024) { throw 'Berkas unduhan terlalu kecil atau bukan ZIP branch.' }; exit 0 } catch { Write-Host ('GAGAL mengunduh: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 goto :gagal_unduh

rem ------------------------------------------------------------
echo [2/4] Mengekstrak ke folder baru
if not exist "%TUJUAN%" goto :buat_tujuan
echo  Folder tujuan sudah ada; memilih nama baru agar tidak tertimpa.
set "TUJUAN=%~dp0..\rubber-intelligence-terbaru-%RANDOM%"

:buat_tujuan
mkdir "%TUJUAN%" >nul 2>nul
if errorlevel 1 goto :gagal_folder
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $ErrorActionPreference='Stop'; try { Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%TUJUAN%' -Force; $sub = Get-ChildItem -LiteralPath '%TUJUAN%' -Directory | Select-Object -First 1; if (-not $sub) { throw 'Struktur ZIP tidak dikenal.' }; Get-ChildItem -LiteralPath $sub.FullName -Force | Move-Item -Destination '%TUJUAN%' -Force; Remove-Item -LiteralPath $sub.FullName -Recurse -Force; exit 0 } catch { Write-Host ('GAGAL mengekstrak: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 goto :gagal_buka

rem ------------------------------------------------------------
echo [3/4] Memindahkan database lokal (jika ada)
if not exist "backend\opmargin.db" goto :tanpa_db
if not exist "%TUJUAN%\backend" mkdir "%TUJUAN%\backend" >nul 2>nul
set "OPMARGIN_DB_SRC=%~dp0backend\opmargin.db"
set "OPMARGIN_DB_DST=%TUJUAN%\backend\opmargin.db"
if exist "backend\.venv\Scripts\python.exe" goto :pakai_venv
where py >nul 2>nul
if not errorlevel 1 goto :pakai_py
where python >nul 2>nul
if errorlevel 1 goto :tanpa_python_db
set "PY=python"
goto :cadangkan_db

:pakai_venv
set "PY=backend\.venv\Scripts\python.exe"
goto :cadangkan_db

:pakai_py
set "PY=py -3"

:cadangkan_db
%PY% -c "import os,sqlite3; src=sqlite3.connect(os.environ['OPMARGIN_DB_SRC'],timeout=30); dst=sqlite3.connect(os.environ['OPMARGIN_DB_DST'],timeout=30); src.backup(dst); dst.close(); src.close()"
if errorlevel 1 goto :gagal_db
echo  Database lokal berhasil dicadangkan ke folder baru.
goto :lanjut_db

:tanpa_db
echo  Tidak ada database lokal; folder baru siap memakai database aplikasi.
goto :lanjut_db

:tanpa_python_db
echo  Python tidak ditemukan untuk mencadangkan database.
echo  Database lama tidak diubah. Salin backend\opmargin.db secara manual
set "KODE_KELUAR=1"
goto :akhir

:gagal_db
echo  GAGAL mencadangkan database. Pastikan file tidak rusak, lalu coba lagi.
echo  Folder lama tetap aman; database lama tidak diubah.
set "KODE_KELUAR=1"
goto :akhir

:lanjut_db
echo.
echo [4/4] Pemeriksaan versi dan langkah berikutnya
if not exist "%TUJUAN%\VERSI.txt" goto :tanpa_versi
echo  Versi kode yang diunduh:
type "%TUJUAN%\VERSI.txt"
goto :tampil_langkah

:tanpa_versi
echo  Peringatan: VERSI.txt tidak ditemukan di hasil unduhan.

:tampil_langkah
echo.
echo  Seluruh file dari branch, termasuk file data/referensi yang ada di
echo  repository, sudah tersedia di folder baru:
echo   %TUJUAN%
echo.
echo  Berikutnya:
echo   1. Buka folder baru dan jalankan start-web.bat.
echo   2. Muat ulang halaman aplikasi dengan Ctrl+F5.
echo   3. Database lokal disalin otomatis; backend\.env tidak disalin.
echo  Folder lama tidak dihapus. Jangan hapus sebelum aplikasi baru normal.
echo.
start "" "%TUJUAN%"
if exist "%ZIP%" del "%ZIP%" >nul 2>nul
goto :akhir

:gagal_unduh
echo.
echo GAGAL mengunduh branch "%CABANG%". Periksa koneksi internet dan nama branch.
echo Unduh manual melalui alamat berikut, lalu ekstrak ZIP:
echo   %URL%
set "KODE_KELUAR=1"
goto :akhir

:gagal_folder
echo.
echo GAGAL membuat folder tujuan:
echo   %TUJUAN%
set "KODE_KELUAR=1"
goto :akhir

:gagal_buka
echo.
echo GAGAL membuka ZIP. Unduh manual melalui browser:
echo   %URL%
set "KODE_KELUAR=1"

:akhir
echo.
if exist "%ZIP%" del "%ZIP%" >nul 2>nul
pause
endlocal & exit /b %KODE_KELUAR%
