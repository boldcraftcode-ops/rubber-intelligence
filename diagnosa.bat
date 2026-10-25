@echo off
rem ============================================================
rem  OP Margin - diagnosa.bat
rem  Menampilkan semua yang menentukan "bisa login atau tidak":
rem  setelan .env, mode login, isi database, akun pengguna,
rem  dan jawaban API yang SEDANG berjalan.
rem
rem  Pakai: klik dua kali berkas ini, lalu salin seluruh isi jendela
rem  bila perlu bantuan.
rem
rem  Catatan teknis: ASCII saja, tanpa blok "( ... )" berlapis dan
rem  tanpa "for /f", agar tidak salah dibaca cmd.exe.
rem ============================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

echo ============================================================
echo  DIAGNOSA OP MARGIN
echo  Folder: %~dp0
echo ============================================================
echo.

if exist "backend\.venv\Scripts\python.exe" goto :punya_python
echo Ruang kerja Python belum ada. Menyiapkan lewat start-web.bat dulu.
echo Jalankan start-web.bat sekali, lalu jalankan diagnosa.bat lagi.
goto :selesai

:punya_python
echo [1] Versi kode yang ada di folder ini
if not exist ".git" goto :tanpa_git
git --no-pager log -1 --oneline
git --no-pager status --short
goto :lanjut1

:tanpa_git
echo  (bukan folder Git - tidak bisa memeriksa versi kode)

:lanjut1
echo.
echo [2] Setelan login dan database
pushd backend
".venv\Scripts\python.exe" -m app.cli diagnosa
popd

echo.
echo [3] Jawaban API yang SEDANG berjalan di port 8000
echo     (versi lama = jawaban tidak memuat "login"/"fitur" baru)
pushd backend
".venv\Scripts\python.exe" -m app.tanya_api
popd

echo.
echo ============================================================
echo  CARA MEMBACA HASIL
echo  - Bagian [2] harus menulis: mode login : lokal (username-sandi)
echo  - Bagian [3] harus memuat versi 0.6.1 dan mode "lokal"
echo  - Bila [3] kosong / gagal: API belum jalan (jalankan start-web.bat)
echo  - Bila [3] memuat mode "access": tutup jendela OP Margin - API,
echo    lalu jalankan start-web.bat lagi
echo ============================================================

:selesai
echo.
pause
endlocal
exit /b 0
