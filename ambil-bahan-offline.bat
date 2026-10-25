@echo off
rem ============================================================
rem  OP Margin - ambil-bahan-offline.bat
rem
rem  DIJALANKAN DI PC YANG ADA INTERNET (sekali saja, sebelum
rem  memasang aplikasi di PC tanpa internet).
rem
rem  Yang disiapkan:
rem    1. Semua pustaka Python sebagai berkas wheel, di
rem       bahan-offline\wheelhouse  (tanpa perlu internet di tujuan)
rem    2. Tampilan web siap pakai, di bahan-offline\dist
rem       (jadi Node.js TIDAK perlu dipasang di PC tujuan)
rem    3. bahan-offline\BACA-SAYA.txt - petunjuk singkat
rem
rem  Setelah selesai: salin SELURUH folder aplikasi ini, termasuk
rem  folder bahan-offline, ke PC tanpa internet. Di sana cukup
rem  klik dua kali start-offline.bat.
rem
rem  Boleh diberi argumen versi Python, misalnya:
rem      ambil-bahan-offline.bat 3.11
rem  Pakai versi yang SAMA dengan Python di PC tanpa internet.
rem
rem  Catatan teknis: ASCII saja, tanpa blok "( ... )" berlapis,
rem  tanpa "for /f", akhir baris CRLF. Pertahankan gaya itu bila
rem  mengedit berkas ini.
rem ============================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

set "BAHAN=%~dp0bahan-offline"
set "WHEEL=%BAHAN%\wheelhouse"
set "DIST=%BAHAN%\dist"
set "TMPV=%TEMP%\opmargin_pyver.txt"
set "TMPT=%TEMP%\opmargin_tanggal.txt"
set "PY="
set "PYVER=%~1"
set "VERSI_KODE=tidak diketahui"

echo ============================================================
echo  MENYIAPKAN BAHAN UNTUK PC TANPA INTERNET
echo  Folder aplikasi : %~dp0
echo  Folder bahan    : %BAHAN%
echo ============================================================
echo.

if not exist "VERSI.txt" goto :lewat_versi
set /p VERSI_KODE=<"VERSI.txt"
echo  Versi kode: %VERSI_KODE%
:lewat_versi
echo.

rem ------------------------------------------------------------
echo [1/5] Mencari Python di PC ini
rem ------------------------------------------------------------
where py >nul 2>nul
if errorlevel 1 goto :cari_python
set "PY=py -3"
goto :ada_python

:cari_python
where python >nul 2>nul
if errorlevel 1 goto :tanpa_python
set "PY=python"

:ada_python
echo     Python: %PY%
%PY% -m pip --version >nul 2>nul
if errorlevel 1 goto :siapkan_pip
goto :punya_pip

:siapkan_pip
echo     pip belum tersedia, menyiapkan sekarang...
%PY% -m ensurepip --upgrade
if errorlevel 1 goto :pip_tidak_ada

:punya_pip
if defined PYVER goto :punya_ver
%PY% -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))" > "%TMPV%"
set /p PYVER=<"%TMPV%"
:punya_ver
if not defined PYVER goto :tanpa_python
echo     Wheel dibuat untuk Python %PYVER%, Windows 64-bit.
echo     PC tanpa internet harus memakai Python %PYVER% juga.

rem ------------------------------------------------------------
echo.
echo [2/5] Mengunduh pustaka Python ke bahan-offline\wheelhouse
rem ------------------------------------------------------------
if exist "%WHEEL%" goto :punya_wheel
mkdir "%WHEEL%" >nul 2>nul
:punya_wheel
%PY% -m pip download --dest "%WHEEL%" --only-binary=:all: --platform win_amd64 --python-version %PYVER% --disable-pip-version-check --requirement "backend\requirements.txt"
if errorlevel 1 goto :unduh_gagal
echo     selesai: pustaka Python sudah ada di bahan-offline\wheelhouse

rem ------------------------------------------------------------
echo.
echo [3/5] Memeriksa Node.js (dipakai hanya di PC ini, bukan di PC tujuan)
rem ------------------------------------------------------------
where node >nul 2>nul
if errorlevel 1 goto :tanpa_node
where npm >nul 2>nul
if errorlevel 1 goto :tanpa_node
echo     Node.js siap.

rem ------------------------------------------------------------
echo.
echo [4/5] Membangun tampilan web (npm install + npm run build)
rem ------------------------------------------------------------
pushd frontend
if exist "node_modules" goto :bangun_dist
echo     memasang pustaka tampilan web, mohon tunggu (sekali saja)...
call npm install
if errorlevel 1 goto :npm_gagal

:bangun_dist
echo     membangun tampilan web...
call npm run build
if errorlevel 1 goto :bangun_gagal
popd

if exist "frontend\dist\index.html" goto :salin_dist
echo     GAGAL: hasil build tidak ditemukan di frontend\dist.
goto :bangun_gagal

:salin_dist
if not exist "%DIST%" goto :buat_dist
echo     membuang hasil build lama di bahan-offline\dist...
rmdir /s /q "%DIST%"
:buat_dist
xcopy "frontend\dist" "%DIST%" /E /I /Y >nul
if errorlevel 1 goto :dist_gagal
echo     selesai: tampilan web siap di bahan-offline\dist

rem ------------------------------------------------------------
echo.
echo [5/5] Menulis petunjuk di bahan-offline\BACA-SAYA.txt
rem ------------------------------------------------------------
%PY% -c "import datetime; print(datetime.date.today().strftime('%d/%m/%Y'))" > "%TMPT%"
set /p HARIINI=<"%TMPT%"
if exist "%BAHAN%\BACA-SAYA.txt" del "%BAHAN%\BACA-SAYA.txt" >nul 2>nul
> "%BAHAN%\BACA-SAYA.txt" echo BAHAN OFFLINE - OP MARGIN
>> "%BAHAN%\BACA-SAYA.txt" echo.
>> "%BAHAN%\BACA-SAYA.txt" echo Tanggal dibuat : %HARIINI%
>> "%BAHAN%\BACA-SAYA.txt" echo Versi kode     : %VERSI_KODE%
>> "%BAHAN%\BACA-SAYA.txt" echo Wheel Python   : Python %PYVER%, Windows 64-bit
>> "%BAHAN%\BACA-SAYA.txt" echo.
>> "%BAHAN%\BACA-SAYA.txt" echo ISI FOLDER INI
>> "%BAHAN%\BACA-SAYA.txt" echo   wheelhouse   pustaka Python untuk pemasangan tanpa internet
>> "%BAHAN%\BACA-SAYA.txt" echo   dist         tampilan web yang sudah jadi, siap dipakai
>> "%BAHAN%\BACA-SAYA.txt" echo.
>> "%BAHAN%\BACA-SAYA.txt" echo YANG MASIH PERLU DIUNDUH SENDIRI
>> "%BAHAN%\BACA-SAYA.txt" echo   Python %PYVER% - Windows installer 64-bit dari python.org
>> "%BAHAN%\BACA-SAYA.txt" echo   Pilih "Windows installer 64-bit", BUKAN "web installer".
>> "%BAHAN%\BACA-SAYA.txt" echo   Saat memasang, centang "Add python.exe to PATH".
>> "%BAHAN%\BACA-SAYA.txt" echo.
>> "%BAHAN%\BACA-SAYA.txt" echo CARA MEMAKAI DI PC TANPA INTERNET
>> "%BAHAN%\BACA-SAYA.txt" echo   1. Salin seluruh folder aplikasi termasuk folder bahan-offline ini.
>> "%BAHAN%\BACA-SAYA.txt" echo   2. Pasang Python tadi.
>> "%BAHAN%\BACA-SAYA.txt" echo   3. Klik dua kali start-offline.bat di folder aplikasi.
>> "%BAHAN%\BACA-SAYA.txt" echo   4. Browser terbuka ke http://localhost:8000
>> "%BAHAN%\BACA-SAYA.txt" echo.
>> "%BAHAN%\BACA-SAYA.txt" echo CATATAN
>> "%BAHAN%\BACA-SAYA.txt" echo   - Node.js TIDAK perlu dipasang di PC tanpa internet.
>> "%BAHAN%\BACA-SAYA.txt" echo   - Jangan jalankan git pull atau perbarui-kode.bat di PC tanpa internet.
>> "%BAHAN%\BACA-SAYA.txt" echo   - Untuk memperbarui aplikasi: ulangi skrip ini di PC berinternet,
>> "%BAHAN%\BACA-SAYA.txt" echo     lalu salin lagi kode terbaru beserta folder bahan-offline.
echo     selesai.

echo.
echo ============================================================
echo SELESAI. Bahan offline siap di:
echo   %BAHAN%
echo.
echo Langkah berikutnya:
echo   1. Unduh Python %PYVER% "Windows installer 64-bit" dari:
echo      https://www.python.org/downloads/windows/
echo   2. Salin SELURUH folder aplikasi ini, termasuk bahan-offline,
echo      ke PC tanpa internet. Paling aman: ZIP dulu foldernya.
echo   3. Di PC itu: pasang Python, lalu klik dua kali start-offline.bat.
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%BAHAN%'; $s=(Get-ChildItem -LiteralPath $p -Recurse -File | Measure-Object -Property Length -Sum).Sum; Write-Host ('   ukuran bahan-offline: ' + [math]::Round($s/1MB,1) + ' MB')"
echo.
pause
endlocal
exit /b 0

rem ============================================================
rem  Penanganan kegagalan
rem ============================================================
:tanpa_python
echo.
echo GAGAL: Python tidak ditemukan di PC ini.
echo Skrip ini butuh Python di PC yang ADA internet, untuk mengunduh pustaka.
echo Pasang dari https://www.python.org/downloads/ lalu centang
echo "Add python.exe to PATH", tutup jendela ini, buka lagi, ulangi.
goto :berhenti

:pip_tidak_ada
echo.
echo GAGAL: pip tidak bisa disiapkan.
echo Coba jalankan perintah ini di jendela Command Prompt:
echo    py -3 -m ensurepip --upgrade
goto :berhenti

:unduh_gagal
echo.
echo GAGAL: pustaka Python tidak berhasil diunduh.
echo Periksa: (1) koneksi internet PC ini, (2) versi Python %PYVER%
echo masih didukung pustaka yang dipakai. Bila ragu, pakai Python 3.11:
echo    ambil-bahan-offline.bat 3.11
goto :berhenti

:tanpa_node
echo.
echo GAGAL: Node.js tidak ditemukan di PC ini.
echo Node.js hanya dipakai DI PC INI untuk membangun tampilan web.
echo Pasang versi LTS dari https://nodejs.org, tutup jendela ini,
echo buka lagi, lalu ulangi skrip ini.
goto :berhenti

:npm_gagal
popd >nul 2>nul
echo.
echo GAGAL saat "npm install". Periksa pesan di atas, lalu coba lagi.
goto :berhenti

:bangun_gagal
popd >nul 2>nul
echo.
echo GAGAL saat "npm run build". Periksa pesan di atas, lalu coba lagi.
goto :berhenti

:dist_gagal
echo.
echo GAGAL menyalin hasil build ke bahan-offline\dist.
echo Pastikan folder aplikasi tidak sedang dibuka program lain.
goto :berhenti

:berhenti
echo.
pause
endlocal
exit /b 1
