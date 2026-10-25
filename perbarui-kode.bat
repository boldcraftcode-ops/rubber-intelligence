@echo off
rem ============================================================
rem  OP Margin - perbarui-kode.bat
rem
rem  Mengunduh kode TERBARU dari branch resmi, lalu menaruhnya di
rem  folder baru di sebelah folder ini. Dipakai bila folder Anda
rem  adalah hasil UNDUHAN ZIP (bukan git clone) sehingga tidak bisa
rem  "git pull".
rem
rem  Tidak menghapus folder lama: database dan .env di folder lama
rem  tetap aman. Setelah selesai, jalankan start-web.bat di folder
rem  baru (skrip itu menyiapkan Python/library sendiri).
rem
rem  ASCII saja, tanpa blok "( ... )" berlapis, tanpa "for /f".
rem ============================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

set "CABANG=arena/18670644-rubber-intelligence"
set "URL=https://github.com/boldcraftcode-ops/rubber-intelligence/archive/refs/heads/%CABANG%.zip"
set "ZIP=%TEMP%\opmargin-terbaru.zip"
set "TUJUAN=%~dp0..\rubber-intelligence-terbaru"

echo ============================================================
echo  Memperbarui kode OP Margin
echo ============================================================
echo  Sumber : %URL%
echo  Hasil  : %TUJUAN%
echo.

rem ------------------------------------------------------------
echo [1/3] Mengunduh berkas kode terbaru
if exist "%ZIP%" del "%ZIP%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -Uri '%URL%' -OutFile '%ZIP%'; exit 0 } catch { Write-Host ('GAGAL mengunduh: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 goto :gagal_unduh

rem ------------------------------------------------------------
echo [2/3] Membuka isi berkas
if not exist "%TUJUAN%" goto :buat_tujuan
echo  Folder tujuan sudah ada. Memakai nama baru agar folder lama tidak tertimpa.
set "TUJUAN=%~dp0..\rubber-intelligence-terbaru-%RANDOM%"

:buat_tujuan
mkdir "%TUJUAN%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%TUJUAN%' -Force; exit 0 } catch { Write-Host ('GAGAL membuka ZIP: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 goto :gagal_buka

rem  Isi ZIP berada di satu subfolder; pindahkan isinya ke folder tujuan.
echo [3/3] Merapikan folder
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $sub = Get-ChildItem -LiteralPath '%TUJUAN%' -Directory | Select-Object -First 1; if ($sub) { Get-ChildItem -LiteralPath $sub.FullName -Force | Move-Item -Destination '%TUJUAN%' -Force; Remove-Item -LiteralPath $sub.FullName -Recurse -Force }"

echo.
echo ============================================================
echo  SELESAI. Kode terbaru ada di:
echo  %TUJUAN%
echo ============================================================
if exist "%TUJUAN%\VERSI.txt" goto :cetak_versi
goto :lanjut

:cetak_versi
echo  Versi kode: 
type "%TUJUAN%\VERSI.txt"

:lanjut
echo.
echo  Langkah berikutnya:
echo   1. Buka folder di atas (Windows Explorer akan dibuka).
echo   2. Klik dua kali start-web.bat di folder itu.
echo      (Pertama kali agak lama: skrip memasang Python/library sendiri.)
echo   3. Bila ingin memakai DATA lama, salin file berikut dari folder
echo      lama ke folder baru SEBELUM menjalankan start-web.bat:
echo        backend\opmargin.db      (database)
echo        backend\.env             (setelan login) - opsional
echo   4. Setelah aplikasi terbuka, Ctrl+F5 di browser.
echo.
echo  Folder lama tidak diubah/dihapus. Anda bisa menghapusnya nanti
echo  setelah folder baru berjalan normal.
echo ============================================================
start "" "%TUJUAN%"
goto :selesai

:gagal_unduh
echo.
echo GAGAL mengunduh. Periksa koneksi internet, lalu coba lagi.
echo Alternatif: buka alamat berikut di browser, lalu ekstrak manual:
echo   %URL%
goto :selesai

:gagal_buka
echo.
echo GAGAL membuka berkas ZIP. Unduh manual lewat browser:
echo   %URL%
goto :selesai

:selesai
echo.
pause
endlocal
exit /b 0
