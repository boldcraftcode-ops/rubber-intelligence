@echo off
rem ============================================================
rem  OP Margin - start-web.bat (Fase 2)
rem  Membuka halaman input cepat harian (SICOM & kurs).
rem  Syarat: sudah pernah menjalankan start.bat (untuk Python + data),
rem  dan Node.js terpasang (https://nodejs.org, versi LTS).
rem ============================================================
setlocal
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

if not exist "frontend\node_modules" (
    echo Memasang pustaka tampilan web (hanya pertama kali, mohon tunggu)...
    pushd frontend
    call npm install || (echo GAGAL saat npm install & pause & exit /b 1)
    popd
)

echo Menjalankan backend (API) di jendela terpisah...
start "OP Margin - API" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo Menjalankan tampilan web di jendela terpisah...
start "OP Margin - Web" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Tunggu beberapa detik, lalu buka browser ke:  http://localhost:5173
echo Untuk berhenti: tutup kedua jendela "OP Margin - API" dan "OP Margin - Web".
timeout /t 6 >nul
start http://localhost:5173
endlocal
