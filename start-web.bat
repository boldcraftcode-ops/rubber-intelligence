@echo off
rem ============================================================
rem  OP Margin - start-web.bat (Fase 2+)
rem  Menjalankan API + tampilan web.
rem  Skrip ini MENYIAPKAN SENDIRI ruang kerja Python, database,
rem  dan pustaka web bila belum ada - jadi tidak akan berhenti
rem  dengan pesan "jalankan dulu start.bat".
rem
rem  Catatan teknis: berkas ini sengaja memakai ASCII saja, tanpa
rem  blok "( ... )" berlapis dan tanpa "for /f", agar tidak salah
rem  dibaca cmd.exe. Bila Anda mengeditnya, pertahankan gaya itu
rem  dan simpan dengan akhir baris CRLF (Windows).
rem ============================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

set "VPY=backend\.venv\Scripts\python.exe"
set "TMPH=%TEMP%\opmargin_health.json"
set "TMPP=%TEMP%\opmargin_port.txt"
set "PUNDUH=curl"
where curl >nul 2>nul
if not errorlevel 1 goto :punya_curl
set "PUNDUH=powershell"
:punya_curl

echo ============================================================
echo  OP Margin - menyiapkan dan menjalankan aplikasi
echo  Folder: %~dp0
if exist "VERSI.txt" goto :cetak_versi
echo  Versi kode: (VERSI.txt tidak ada - kemungkinan kode lama)
goto :lewat_versi

:cetak_versi
set /p VERSI_KODE=<"VERSI.txt"
echo  Versi kode: %VERSI_KODE%

:lewat_versi
echo ============================================================
echo.

rem ------------------------------------------------------------
rem  1. Ruang kerja Python (.venv)
rem ------------------------------------------------------------
if exist "%VPY%" goto :cek_mode_env

echo Ruang kerja Python belum ada. Menyiapkan sekarang (sekali saja).
where py >nul 2>nul
if not errorlevel 1 goto :pakai_py
where python >nul 2>nul
if errorlevel 1 goto :tanpa_python
set "PY=python"
goto :buat_venv

:pakai_py
set "PY=py -3"

:buat_venv
pushd backend
%PY% -m venv .venv
if errorlevel 1 goto :venv_gagal
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :venv_gagal
popd
goto :cek_mode_env

:venv_gagal
popd
echo.
echo GAGAL: tidak berhasil menyiapkan Python di folder backend\.venv
echo Coba jalankan start.bat sekali (klik dua kali), lalu ulangi start-web.bat.
goto :berhenti

:tanpa_python
echo.
echo GAGAL: Python tidak ditemukan di PATH komputer ini.
echo Pasang Python dari https://www.python.org/downloads/
echo Saat memasang, centang "Add Python to PATH", lalu jalankan lagi.
goto :berhenti

rem ------------------------------------------------------------
rem  1b. Berkas backend\.env - cara login untuk komputer ini
rem      Tanpa .env, aplikasi bisa masuk mode Cloudflare Access yang
rem      TIDAK bisa dipakai di localhost ("Belum login ... Cloudflare
rem      Access"). Jadi .env selalu disiapkan: mode login lokal.
rem ------------------------------------------------------------
if not exist "backend\.env" goto :buat_env
goto :cek_mode_env

:buat_env
echo Membuat backend\.env (login lokal: username + sandi) - sekali saja.
pushd backend
".venv\Scripts\python.exe" -m app.cli atur-login-lokal
popd
goto :cek_mode_env

:cek_mode_env
if not exist "backend\.env" goto :punya_env
findstr /i /c:"CF_ACCESS_AUD" "backend\.env" >nul 2>nul
if errorlevel 1 goto :punya_env
findstr /i /c:"AUTH_MODE=lokal" "backend\.env" >nul 2>nul
if not errorlevel 1 goto :punya_env
echo.
echo ============================================================
echo PERINGATAN: backend\.env memakai login Cloudflare Access.
echo Access hanya bekerja lewat domain yang dilindungi Cloudflare,
echo jadi di localhost SEMUA halaman akan berbunyi "Belum login ...
echo Cloudflare Access" dan form username+sandi tidak bisa dipakai.
echo ============================================================
set "JAWAB="
set /p "JAWAB=Ubah ke login lokal (username+sandi) sekarang? [Y] ya / [N] biarkan: "
if /i "%JAWAB%"=="Y" goto :perbaiki_env
if /i "%JAWAB%"=="T" goto :perbaiki_env
echo Dibiarkan. Login lokal tidak akan bisa dipakai selama AUTH_MODE
echo bukan lokal.
goto :punya_env

:perbaiki_env
pushd backend
".venv\Scripts\python.exe" -m app.cli atur-login-lokal
popd

:punya_env

rem ------------------------------------------------------------
rem  2. Database + data awal
rem ------------------------------------------------------------
if exist "backend\opmargin.db" goto :punya_db
echo Database belum ada. Membuat dan memuat data awal dari template.
pushd backend
".venv\Scripts\python.exe" -m app.cli init-db
if errorlevel 1 goto :db_gagal
".venv\Scripts\python.exe" -m app.cli import-template "..\sample_data\Template_dan_Data_Awal_OP_Margin_v3.xlsx" --pengunggah "%USERNAME%"
if errorlevel 1 goto :db_gagal
popd
goto :punya_db

:db_gagal
popd
echo.
echo GAGAL: database belum berhasil dibuat.
echo Jalankan start.bat sekali, lihat pesan errornya, lalu ulangi start-web.bat.
goto :berhenti

rem ------------------------------------------------------------
rem  3. Node.js + pustaka tampilan web
rem ------------------------------------------------------------
:punya_db
where node >nul 2>nul
if errorlevel 1 goto :tanpa_node

if exist "frontend\node_modules" goto :punya_web
echo Memasang pustaka tampilan web (hanya pertama kali, mohon tunggu).
pushd frontend
call npm install
if errorlevel 1 goto :npm_gagal
popd
goto :punya_web

:npm_gagal
popd
echo.
echo GAGAL saat "npm install". Periksa pesan di atas, lalu coba lagi.
goto :berhenti

:tanpa_node
echo.
echo GAGAL: Node.js tidak ditemukan.
echo Pasang dari https://nodejs.org (pilih versi LTS, klik Next sampai selesai),
echo tutup jendela ini, buka lagi, lalu jalankan start-web.bat.
goto :berhenti

rem ------------------------------------------------------------
rem  4. Port yang mungkin masih dipakai sesi sebelumnya
rem     (proses API lama = kode lama = fitur baru 404)
rem ------------------------------------------------------------
:punya_web
call :cek_port 8000 "API"
call :cek_port 5173 "tampilan web"

rem ------------------------------------------------------------
rem  5. Jalankan API + web di jendela terpisah
rem ------------------------------------------------------------
echo.
echo Menjalankan API di jendela "OP Margin - API" (dengan auto-reload).
rem  AUTH_MODE=lokal dipaksa untuk jendela ini: skrip ini selalu dipakai di
rem  komputer sendiri, tempat Cloudflare Access tidak mungkin bekerja.
rem  Variabel lingkungan menang atas isi backend\.env (load_dotenv tidak
rem  menimpa), jadi login lokal tetap berlaku walau .env masih setelan Access.
set "AUTH_MODE=lokal"
start "OP Margin - API" /D "%~dp0backend" cmd /k ".venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
echo Menjalankan tampilan web di jendela "OP Margin - Web".
start "OP Margin - Web" /D "%~dp0frontend" cmd /k "npm run dev"

echo.
echo Menunggu API siap (maksimal 30 detik).
set /a NCOBA=0

:menu_health
set /a NCOBA+=1
timeout /t 1 >nul 2>nul
call :ambil_health
if not errorlevel 1 goto :health_ok
if %NCOBA% GEQ 30 goto :health_lambat
goto :menu_health

:health_lambat
echo.
echo PERINGATAN: API belum menjawab di http://127.0.0.1:8000
echo Buka jendela "OP Margin - API" dan baca pesan errornya (paling bawah).
goto :buka

:health_ok
rem  Pastikan proses yang menjawab memang kode TERBARU.
findstr /c:"margin-bridge" "%TMPH%" >nul 2>nul
if errorlevel 1 goto :versi_lama
echo API siap: kode terbaru (margin-bridge, days-of-cover, jelaskan ada).
goto :buka

:versi_lama
echo.
echo ============================================================
echo PERINGATAN: API di port 8000 masih VERSI LAMA.
echo Fitur "Margin Bridge" dan "Days of Cover" tidak dikenali proses
echo itu, jadi tombolnya akan gagal walau kode di folder ini sudah baru.
echo.
echo Perbaikan: tutup jendela "OP Margin - API" yang lama, lalu
echo jalankan start-web.bat ini sekali lagi.
echo ============================================================
goto :buka

rem ------------------------------------------------------------
rem  6. Buka browser
rem ------------------------------------------------------------
:buka
echo.
echo Buka browser ke:  http://localhost:5173
echo Untuk berhenti: tutup jendela "OP Margin - API" dan "OP Margin - Web".
timeout /t 3 >nul 2>nul
start http://localhost:5173

:berhenti
echo.
pause
endlocal
exit /b 0

rem ============================================================
rem  :cek_port PORT NAMA
rem  Bila port sedang dipakai, tawarkan menutup proses lamanya.
rem ============================================================
:cek_port
set "PORT=%~1"
set "NAMA=%~2"
if exist "%TMPP%" del "%TMPP%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$x = netstat -ano | Select-String 'LISTENING' | Select-String ':%PORT% '; if ($x) { (($x[0].ToString().Trim() -split '\s+')[-1]) }" > "%TMPP%" 2>nul
set "PID="
if not exist "%TMPP%" goto :eof
< "%TMPP%" set /p PID=
if not defined PID goto :eof

echo.
echo Port %PORT% (%NAMA%) masih dipakai proses lain, PID %PID%.
echo Kemungkinan itu jendela "%NAMA%" dari sesi sebelumnya yang belum
echo ditutup. Proses lama memakai kode lama, jadi fitur baru bisa gagal.
set "JAWAB="
set /p "JAWAB=Tutup proses itu sekarang? [Y] ya / [N] biarkan (lalu Enter): "
if /i "%JAWAB%"=="Y" goto :tutup_port
if /i "%JAWAB%"=="T" goto :tutup_port
if /i "%JAWAB%"=="YA" goto :tutup_port
echo Dibiarkan. Fitur baru bisa gagal selama proses lama masih hidup.
goto :eof

:tutup_port
taskkill /f /pid %PID% >nul 2>nul
echo Proses lama di port %PORT% sudah ditutup.
timeout /t 1 >nul 2>nul
goto :eof

rem ============================================================
rem  :ambil_health  - ambil http://127.0.0.1:8000/api/health
rem ============================================================
:ambil_health
if /i "%PUNDUH%"=="curl" goto :ambil_curl
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://127.0.0.1:8000/api/health).Content | Out-File -Encoding ascii '%TMPH%'; exit 0 } catch { exit 1 }"
goto :eof

:ambil_curl
curl -s -f -o "%TMPH%" http://127.0.0.1:8000/api/health >nul 2>nul
goto :eof
