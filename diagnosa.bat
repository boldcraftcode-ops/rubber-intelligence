@echo off
rem ============================================================
rem  OP Margin - diagnosa.bat
rem  Menampilkan semua yang menentukan "bisa login atau tidak".
rem
rem  Skrip ini sengaja TIDAK bergantung pada perintah baru di dalam
rem  aplikasi: bila kode di folder ini versi lama, skrip tetap jalan
rem  dan memberi cara lain. ASCII saja, tanpa blok "( ... )"
rem  berlapis dan tanpa "for /f", agar tidak salah dibaca cmd.exe.
rem ============================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

echo ============================================================
echo  DIAGNOSA OP MARGIN
echo  Folder: %~dp0
echo ============================================================
echo.

rem ------------------------------------------------------------
echo [0] Versi kode di folder ini
if exist "VERSI.txt" goto :ada_versi
echo   VERSI.txt tidak ada  ^-^>  kode di folder ini LEBIH LAMA dari 0.7.6
goto :cek_git

:ada_versi
echo   VERSI.txt : 
type "VERSI.txt"

:cek_git
rem  Penanda paling pasti: kode 0.7.6 TIDAK memuat login Cloudflare Access.
if not exist "backend\app\main.py" goto :cek_git2
findstr /c:"Cloudflare Access" "backend\app\main.py" >nul 2>nul
if errorlevel 1 goto :cek_git2
echo.
echo   *** KODE LAMA: backend\app\main.py masih memuat login Cloudflare
echo       Access. Versi 0.7.6 sudah menghapusnya, jadi folder ini BELUM
echo       diperbarui. Jalankan perbarui-kode.bat. ***

:cek_git2
if exist ".git" goto :pakai_git
echo.
echo   *** Folder ini BUKAN hasil "git clone" (tidak ada folder .git) ***
echo   Kemungkinan besar ini hasil UNDUHAN ZIP. Unduhan ZIP TIDAK ikut
echo   diperbarui: kode di dalamnya tetap seperti saat diunduh. Inilah
echo   sebabnya perbaikan terbaru tidak terpakai walau Anda sudah
echo   mengunduh berkas lain.
echo.
echo   Cara mendapatkan kode terbaru: jalankan perbarui-kode.bat
echo   (ada di folder ini), ATAU unduh manual:
echo   https://github.com/boldcraftcode-ops/rubber-intelligence/archive/refs/heads/arena/18670644-rubber-intelligence.zip
goto :lanjut_git

:pakai_git
echo.
echo   Riwayat Git terakhir:
git --no-pager log -1 --oneline
git --no-pager status --short

:lanjut_git
echo.

rem ------------------------------------------------------------
echo [1] Berkas setelan backend\.env
if exist "backend\.env" goto :ada_env
echo   backend\.env TIDAK ADA (dibuat sekarang: login lokal)
pushd backend
if not exist ".venv\Scripts\python.exe" goto :keluar_buat
".venv\Scripts\python.exe" -m app.cli atur-login-lokal
:keluar_buat
popd
goto :lanjut_env

:ada_env
echo   baris aktif (tanpa komentar):
findstr /v /b "#" "backend\.env"

:lanjut_env
echo.

rem ------------------------------------------------------------
echo [2] Periksa setelan + database memakai kode di folder ini
pushd backend
if not exist ".venv\Scripts\python.exe" goto :tanpa_venv
findstr /c:"diagnosa" app\cli.py >nul 2>nul
if errorlevel 1 goto :diag_lama
".venv\Scripts\python.exe" -m app.cli diagnosa
goto :keluar_diag

:diag_lama
echo   KODE LAMA: perintah "diagnosa" belum ada di folder ini.
echo   Artinya kode yang dipakai BUKAN versi terbaru, sehingga
echo   perbaikan login terbaru juga belum ikut. Jalankan
echo   perbarui-kode.bat, lalu start-web.bat dari folder baru.
goto :keluar_diag

:tanpa_venv
echo   backend\.venv belum ada. Jalankan start-web.bat sekali dulu.

:keluar_diag
popd
echo.

rem ------------------------------------------------------------
echo [3] Jawaban API yang SEDANG berjalan di port 8000
pushd backend
if not exist ".venv\Scripts\python.exe" goto :probe_ps
if not exist "app\tanya_api.py" goto :probe_ps
".venv\Scripts\python.exe" -m app.tanya_api
goto :keluar_probe

:probe_ps
echo   (memakai PowerShell, tanpa perlu perintah baru di aplikasi)
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { '  /api/health   : ' + (Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 http://127.0.0.1:8000/api/health).Content } catch { '  /api/health   : TIDAK ADA JAWABAN di port 8000' }"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { '  /api/auth/mode: ' + (Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 http://127.0.0.1:8000/api/auth/mode).Content } catch { '  /api/auth/mode: TIDAK ADA (proses di port 8000 memakai kode lama)' }"

:keluar_probe
popd

echo.
echo ============================================================
echo  CARA MEMBACA HASIL
echo ============================================================
echo  [1]+[2] harus menyebut: mode login : lokal (username-sandi)
echo  [3] harus memuat versi 0.7.6 dan "cara":"username-sandi"
echo.
echo  Bila [2] menulis "KODE LAMA"  -^>  jalankan perbarui-kode.bat
echo  Bila [3] memuat "nonaktif"   -^>  hapus AUTH_DISABLED di backend\.env,
echo                                    lalu jalankan start-web.bat lagi
echo  Bila [3] "TIDAK ADA JAWABAN" -^>  API belum jalan: start-web.bat
echo  Bila sandi lupa              -^>  di folder backend jalankan:
echo     .venv\Scripts\python -m app.cli reset-sandi admin
echo ============================================================
echo.
pause
endlocal
exit /b 0
