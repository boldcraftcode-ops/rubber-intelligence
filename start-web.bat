@echo off
rem ============================================================
rem  OP Margin - start-web.bat (Fase 2+)
rem  Menjalankan API + tampilan web.
rem  Syarat: sudah pernah menjalankan start.bat (untuk Python + data),
rem  dan Node.js terpasang (https://nodejs.org, versi LTS).
rem
rem  PENTING: skrip ini memeriksa apakah port 8000/5173 masih dipakai
rem  proses lama. Bila ya, skrip menawarkan menutupnya — karena proses
rem  API lama akan membuat fitur baru (Margin Bridge, Days of Cover,
rem  Jelaskan ke saya) tampak "tidak jalan" (404) walau kodenya sudah baru.
rem ============================================================
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
    echo GAGAL: jalankan dulu start.bat untuk menyiapkan Python dan data.
    pause & exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
    echo GAGAL: Node.js tidak ditemukan. Pasang dulu dari https://nodejs.org
    echo (pilih versi LTS, cukup klik Next sampai selesai), lalu jalankan lagi.
    pause & exit /b 1
)

rem ---------- 1. Periksa port yang mungkin masih dipakai sesi sebelumnya ----
call :cek_port 8000 "API"
call :cek_port 5173 "tampilan web"

if exist "frontend\node_modules" goto :lanjut
echo Memasang pustaka tampilan web (hanya pertama kali, mohon tunggu)...
pushd frontend
call npm install || (echo GAGAL saat npm install & pause & exit /b 1)
popd

:lanjut
echo Menjalankan backend (API) di jendela terpisah -- dengan auto-reload...
start "OP Margin - API" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo Menjalankan tampilan web di jendela terpisah...
start "OP Margin - Web" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Menunggu API siap...
set "SIAP="
for /l %%i in (1,1,20) do (
    if not defined SIAP (
        timeout /t 1 >nul
        curl -s -o "%TEMP%\opmargin_health.json" http://127.0.0.1:8000/api/health >nul 2>nul
        if not errorlevel 1 set "SIAP=1"
    )
)

if not defined SIAP (
    echo PERINGATAN: API belum merespons di http://127.0.0.1:8000
    echo Buka jendela "OP Margin - API" dan lihat pesan errornya.
    goto :buka
)

rem ---------- 2. Verifikasi proses API yang menjawab adalah kode TERBARU ----
findstr /c:"margin-bridge" "%TEMP%\opmargin_health.json" >nul 2>nul
if errorlevel 1 (
    echo.
    echo ============================================================
    echo PERINGATAN: API yang menjawab di port 8000 adalah VERSI LAMA.
    echo Fitur "Margin Bridge" dan "Days of Cover" tidak dikenali proses itu,
    echo jadi tombolnya akan gagal walau kode di folder ini sudah baru.
    echo.
    echo Perbaikan: tutup jendela "OP Margin - API" yang lama
    echo ^(atau matikan semua proses python/uvicorn^), lalu jalankan lagi
    echo start-web.bat ini.
    echo ============================================================
) else (
    echo API siap dan sudah memuat fitur terbaru ^(margin-bridge, days-of-cover^).
)

:buka
echo.
echo Tunggu beberapa detik, lalu buka browser ke:  http://localhost:5173
echo Untuk berhenti: tutup kedua jendela "OP Margin - API" dan "OP Margin - Web".
timeout /t 4 >nul
start http://localhost:5173
endlocal
exit /b 0

rem ============================================================
rem  :cek_port PORT NAMA
rem  Bila port dipakai, tanyakan apakah proses lama ditutup.
rem ============================================================
:cek_port
set "PORT=%~1"
set "NAMA=%~2"
netstat -ano | findstr /r /c:"LISTENING" | findstr /c:":%PORT% " >nul 2>nul
if errorlevel 1 goto :eof
echo.
echo Port %PORT% (%NAMA%) masih dipakai proses lain — kemungkinan jendela
echo "%NAMA%" dari sesi sebelumnya yang belum ditutup.
echo Proses lama itu memakai KODE LAMA, sehingga fitur baru tidak akan muncul.
choice /c YN /n /m "Tutup proses lama itu sekarang? [Y/T]=Ya  [N]=Biarkan: "
if errorlevel 2 (
    echo Dibiarkan. Fitur baru bisa gagal selama proses lama masih hidup.
    goto :eof
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"LISTENING" ^| findstr /c:":%PORT% "') do (
    taskkill /f /pid %%p >nul 2>nul
)
echo Proses lama di port %PORT% sudah ditutup.
timeout /t 1 >nul
goto :eof
