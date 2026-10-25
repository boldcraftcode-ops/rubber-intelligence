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
rem  Baris pertama VERSI.txt = nomor versi kode di folder ini.
set "VERSI_KODE="
set /p VERSI_KODE=<"VERSI.txt"
echo  Versi kode: %VERSI_KODE%

:lewat_versi
echo ============================================================
echo.

rem ------------------------------------------------------------
rem  1. Ruang kerja Python (.venv)
rem ------------------------------------------------------------
if exist "%VPY%" goto :cek_env

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
goto :cek_env

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

:cek_env
rem ------------------------------------------------------------
rem  1b. Berkas backend\.env - setelan login
rem      Login hanya username + sandi. Bila .env belum ada, dibuat
rem      otomatis supaya akun admin tersedia dan sesi bisa
rem      ditandatangani (SECRET_KEY).
rem ------------------------------------------------------------
if not exist "backend\.env" goto :buat_env
goto :punya_env

:buat_env
echo Membuat backend\.env (login username + sandi) - sekali saja.
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
echo.
echo [4] Menutup proses lama di port 8000 dan 5173 (bila ada).
echo     Proses lama = kode lama = login & fitur baru gagal.
call :hentikan_service
call :bersihkan_port 8000 "API" "app.main:app"
call :bersihkan_port 5173 "tampilan web" "vite"

rem ------------------------------------------------------------
rem  5. Jalankan API + web di jendela terpisah
rem ------------------------------------------------------------
echo.
echo Menjalankan API di jendela "OP Margin - API" (dengan auto-reload).
rem  AUTH_DISABLED dibuang untuk jendela ini supaya login BENAR-BENAR aktif,
rem  apa pun sisa setelan di backend\.env (variabel lingkungan menang atas
rem  isi .env karena load_dotenv tidak menimpa).
set "AUTH_DISABLED="
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
rem  Pastikan proses yang menjawab memang kode TERBARU di folder ini.
if not defined VERSI_KODE goto :versi_tak_dikenal
findstr /c:"%VERSI_KODE%" "%TMPH%" >nul 2>nul
if errorlevel 1 goto :versi_lama
echo API siap: kode %VERSI_KODE% (login username + sandi).
goto :buka

:versi_tak_dikenal
findstr /c:"margin-bridge" "%TMPH%" >nul 2>nul
if errorlevel 1 goto :versi_lama
echo API siap (VERSI.txt tidak ada, jadi versi tidak bisa dipastikan).
goto :buka

:versi_lama
if defined SUDAH_ULANG goto :versi_tetap_lama
set "SUDAH_ULANG=1"
echo.
echo API yang menjawab BUKAN kode di folder ini. Menutup paksa port 8000
echo lalu menjalankan API sekali lagi (otomatis).
call :bersihkan_port 8000 "API" "app.main:app"
start "OP Margin - API" /D "%~dp0backend" cmd /k ".venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
set /a NCOBA=0
goto :menu_health

:versi_tetap_lama
echo.
echo ============================================================
echo GAGAL: API di port 8000 tetap VERSI LAIN walau sudah diulang.
echo Aplikasi ini butuh kode %VERSI_KODE%.
echo.
echo Kemungkinan penyebab:
echo  1. Ada program lain yang memakai port 8000 (bukan aplikasi ini).
echo     Cek: netstat -ano ^| findstr :8000
echo  2. Folder ini masih kode lama: jalankan perbarui-kode.bat
echo  3. Windows menahan proses lama: restart komputer, lalu ulangi.
echo.
echo Jendela "OP Margin - API" sekarang menampilkan pesan errornya.
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
rem  :hentikan_service
rem  Aplikasi bisa dipasang sebagai service Windows (lihat
rem  deploy/install-windows.md). Service yang hidup akan LANGSUNG
rem  menghidupkan lagi API lama setelah ditutup, jadi harus dimatikan.
rem ============================================================
:hentikan_service
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=@(); try { $s = Get-Service -Name 'OPMargin*' -ErrorAction Stop } catch {}; if (-not $s) { Write-Host '   tidak ada service OPMargin*' } else { foreach ($x in $s) { Write-Host ('   service ' + $x.Name + ' (' + $x.Status + ') dihentikan'); try { Stop-Service -Name $x.Name -Force -ErrorAction Stop } catch { Write-Host ('   GAGAL menghentikan service ' + $x.Name + ': ' + $_.Exception.Message); Write-Host '   -> jalankan start-web.bat sebagai Administrator, atau hentikan lewat services.msc' } } }"
goto :eof

rem ============================================================
rem  :bersihkan_port PORT NAMA POLA
rem  Menutup paksa proses aplikasi lama:
rem   - pemegang port itu, dan
rem   - proses yang baris perintahnya cocok dengan POLA (perlu, karena
rem     "uvicorn --reload" punya proses induk yang menghidupkan ulang
rem     anaknya, sehingga mematikan anaknya saja tidak cukup).
rem  Tidak bertanya: proses lama itulah penyebab login & fitur gagal.
rem ============================================================
:bersihkan_port
set "PORT=%~1"
set "NAMA=%~2"
set "POLA=%~3"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=%PORT%; $nama='%NAMA%'; $pola='%POLA%'; $saya=$PID; $induk=0; try { $induk=(Get-CimInstance Win32_Process -Filter ('ProcessId=' + $saya)).ParentProcessId } catch {}; $pernah=$false; for ($i=0; $i -lt 5; $i++) { $kandidat=@(); try { $kandidat += (Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { $_.CommandLine -and ($_.CommandLine -match $pola) } | ForEach-Object { $_.ProcessId }) } catch {}; try { $kandidat += (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop).OwningProcess } catch { $kandidat += @(netstat -ano | Select-String 'LISTENING\s*$' | Select-String (':' + $p + '\s') | ForEach-Object { ($_.ToString().Trim() -split '\s+')[-1] }) }; $kandidat = $kandidat | Where-Object { $_ -and $_ -ne 0 -and $_ -ne $saya -and $_ -ne $induk } | Sort-Object -Unique; if (-not $kandidat) { break }; foreach ($id in $kandidat) { $pernah=$true; try { Stop-Process -Id $id -Force -ErrorAction Stop; Write-Host ('   port ' + $p + ' (' + $nama + '): PID ' + $id + ' ditutup') } catch { Write-Host ('   GAGAL menutup PID ' + $id + ' (butuh Administrator): ' + $_.Exception.Message) } }; Start-Sleep -Milliseconds 900 }; if (-not $pernah) { Write-Host ('   port ' + $p + ' (' + $nama + ') sudah bebas') } else { Write-Host ('   port ' + $p + ' (' + $nama + ') dibersihkan') }"
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
