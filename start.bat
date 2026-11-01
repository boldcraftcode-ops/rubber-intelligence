@echo off
rem ============================================================
rem  OP Margin - start.bat (Fase 1, untuk testing)
rem  Jalankan dengan klik dua kali, atau dari terminal: start.bat
rem  Skrip ini otomatis:
rem    1. Menyiapkan Python (ruang kerja .venv) + pustaka
rem    2. Membuat database dan memuat data awal dari template
rem    3. Menjalankan 19 unit test kasus emas
rem    4. Menampilkan contoh hasil (ringkasan 2026, rekomendasi, rencana 2027)
rem ============================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0backend"

echo.
echo ===== [1/5] Mencari Python =====
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo GAGAL: Python tidak ditemukan.
    echo Silakan pasang dulu dari https://www.python.org/downloads/
    echo Saat memasang, centang "Add Python to PATH".
    goto :selesai
)
echo Python ditemukan: %PY%

echo.
echo ===== [2/5] Menyiapkan ruang kerja (.venv) dan pustaka =====
if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv || goto :gagal
)
set "VPY=.venv\Scripts\python.exe"
"%VPY%" -m pip install --quiet --disable-pip-version-check -r requirements.txt || goto :gagal
echo Pustaka siap.

echo.
echo ===== [3/5] Membuat database dan memuat data awal =====
"%VPY%" -m app.cli init-db || goto :gagal
"%VPY%" -m app.cli import-template "..\sample_data\Template_dan_Data_Awal_OP_Margin_v3.xlsx" --pengunggah "%USERNAME%" || goto :gagal

echo.
echo ===== [4/5] Menjalankan unit test (kasus uji emas) =====
"%VPY%" -m pytest -q
if errorlevel 1 (
    echo.
    echo PERHATIAN: ada test yang GAGAL. Lihat pesan di atas.
    goto :selesai
)
echo Semua test lulus.

echo.
echo ===== [5/5] Contoh hasil =====
"%VPY%" -m app.cli ringkasan 2026
echo.
"%VPY%" -m app.cli rekomendasi
echo.
"%VPY%" -m app.cli rencana 2027

echo.
echo ============================================================
echo SELESAI. Database: backend\opmargin.db
echo Perintah lain yang bisa dicoba (dari folder backend):
echo   .venv\Scripts\python -m app.cli ringkasan 2023
echo   .venv\Scripts\python -m app.cli rekomendasi --tanggal 31/08/2026
echo   .venv\Scripts\python -m app.cli import-tiket "C:\folder\Master Data.xlsx"
echo ============================================================
goto :selesai

:gagal
echo.
echo GAGAL: ada langkah yang error. Lihat pesan di atas, lalu coba lagi.

:selesai
echo.
pause
endlocal
