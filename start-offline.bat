@echo off
rem ============================================================
rem  OP Margin - start-offline.bat
rem
rem  Untuk PC yang TIDAK ada internet.
rem  Menyiapkan sendiri apa pun yang belum ada, memakai bahan
rem  yang dibawa dari PC berinternet (ambil-bahan-offline.bat):
rem
rem    1. Ruang kerja Python (backend\.venv)
rem    2. Pustaka Python dari bahan-offline\wheelhouse  (tanpa internet)
rem    3. Berkas setelan login (backend\.env)
rem    4. Database + data awal
rem    5. Tampilan web dari bahan-offline\dist  (tanpa Node.js)
rem    6. Menjalankan API yang sekaligus menyajikan tampilan web:
rem       http://localhost:8000
rem
rem  Berkas penanda (letakkan di folder ini bila perlu):
rem    tanpa-login.txt     login dimatikan sementara
rem    jaringan-lan.txt    bisa dibuka dari komputer lain di jaringan
rem
rem  ASCII saja, tanpa blok "( ... )" berlapis, tanpa "for /f".
rem ============================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

set "VPY=%~dp0backend\.venv\Scripts\python.exe"
set "WHEEL=%~dp0bahan-offline\wheelhouse"
set "DISTBAHAN=%~dp0bahan-offline\dist"
set "DIST=%~dp0frontend\dist"
set "TMPH=%TEMP%\opmargin_health.json"
set "PUNDUH=curl"
set "HOST=127.0.0.1"
set "VERSI_KODE="

where curl >nul 2>nul
if not errorlevel 1 goto :punya_curl
set "PUNDUH=powershell"
:punya_curl

echo ============================================================
echo  OP MARGIN - MODE TANPA INTERNET
echo  Folder: %~dp0
if not exist "VERSI.txt" goto :lewat_versi
set /p VERSI_KODE=<"VERSI.txt"
echo  Versi kode: %VERSI_KODE%
goto :lewat_versi2
:lewat_versi
echo  Versi kode: VERSI.txt tidak ada
:lewat_versi2
echo ============================================================
echo.

rem ------------------------------------------------------------
echo [1/6] Memeriksa ruang kerja Python
rem ------------------------------------------------------------
if exist "%VPY%" goto :punya_venv
echo     belum ada, menyiapkan backend\.venv...
where py >nul 2>nul
if errorlevel 1 goto :cari_python
set "PY=py -3"
goto :buat_venv

:cari_python
where python >nul 2>nul
if errorlevel 1 goto :tanpa_python
set "PY=python"

:buat_venv
%PY% -m venv "%~dp0backend\.venv"
if errorlevel 1 goto :venv_gagal
echo     ruang kerja siap.

:punya_venv

rem ------------------------------------------------------------
echo.
echo [2/6] Memeriksa pustaka Python
rem ------------------------------------------------------------
"%VPY%" -c "import fastapi, openpyxl, sqlalchemy, uvicorn, multipart, jwt, dotenv" >nul 2>nul
if not errorlevel 1 goto :punya_pustaka
echo     belum lengkap, memasang dari bahan-offline\wheelhouse...
if not exist "%WHEEL%" goto :tanpa_bahan
pushd backend
".venv\Scripts\python.exe" -m pip install --no-index --find-links "%WHEEL%" --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :pip_gagal
popd
echo     pustaka siap.

:punya_pustaka

rem ------------------------------------------------------------
echo.
echo [3/6] Memeriksa berkas setelan login (backend\.env)
rem ------------------------------------------------------------
if exist "backend\.env" goto :punya_env
echo     belum ada, membuat sekarang...
pushd backend
".venv\Scripts\python.exe" -m app.cli atur-login-lokal
if errorlevel 1 goto :env_gagal
popd

:punya_env

rem ------------------------------------------------------------
echo.
echo [4/6] Memeriksa database dan data awal
rem ------------------------------------------------------------
if exist "backend\opmargin.db" goto :punya_db
echo     belum ada, membuat database + memuat data awal dari template...
pushd backend
".venv\Scripts\python.exe" -m app.cli init-db
if errorlevel 1 goto :db_gagal
".venv\Scripts\python.exe" -m app.cli import-template "..\sample_data\Template_dan_Data_Awal_OP_Margin_v3.xlsx" --pengunggah "%USERNAME%"
if errorlevel 1 goto :db_gagal
popd

:punya_db

rem ------------------------------------------------------------
echo.
echo [5/6] Memeriksa tampilan web siap pakai
rem ------------------------------------------------------------
rem  Selalu disalin bila bahan tersedia: tampilan lama yang tertinggal
rem  akan tampil sebagai "beda versi" dan membingungkan.
if not exist "%DISTBAHAN%\index.html" goto :cek_dist_lokal
echo     menyalin tampilan web dari bahan-offline\dist...
xcopy "%DISTBAHAN%" "%DIST%" /E /I /Y >nul
if errorlevel 1 goto :dist_gagal
goto :punya_dist

:cek_dist_lokal
if exist "frontend\dist\index.html" goto :punya_dist
goto :tanpa_dist

:punya_dist

rem ------------------------------------------------------------
echo.
echo [6/6] Menjalankan aplikasi
rem ------------------------------------------------------------
call :hentikan_service
call :bersihkan_port 8000 "API" "app.main:app"

set "SAJIKAN_WEB=true"
set "SAJIKAN_WEB_FOLDER=%DIST%"
if exist "%~dp0tanpa-login.txt" goto :mode_tanpa_login
set "AUTH_DISABLED="
goto :cek_lan

:mode_tanpa_login
set "AUTH_DISABLED=true"
echo     PERHATIAN: tanpa-login.txt ditemukan -> LOGIN DIMATIKAN sementara.
echo     Semua orang yang bisa membuka alamat ini bisa memakai aplikasi.

:cek_lan
if not exist "%~dp0jaringan-lan.txt" goto :jalan
set "HOST=0.0.0.0"
echo     jaringan-lan.txt ditemukan -> bisa dibuka dari komputer lain.

:jalan
start "OP Margin - API" /D "%~dp0backend" cmd /k ".venv\Scripts\python -m uvicorn app.main:app --host %HOST% --port 8000"

echo.
echo Menunggu API siap (maksimal 40 detik).
set /a NCOBA=0

:menu_health
set /a NCOBA+=1
timeout /t 1 >nul 2>nul
call :ambil_health
if not errorlevel 1 goto :health_ok
if %NCOBA% GEQ 40 goto :health_lambat
goto :menu_health

:health_lambat
echo.
echo PERINGATAN: API belum menjawab di http://127.0.0.1:8000
echo Buka jendela "OP Margin - API" dan baca pesan errornya (paling bawah).
goto :buka

:health_ok
if not defined VERSI_KODE goto :buka
findstr /c:"%VERSI_KODE%" "%TMPH%" >nul 2>nul
if errorlevel 1 goto :versi_lain
echo API siap: kode %VERSI_KODE%.
goto :buka

:versi_lain
echo PERINGATAN: API menjawab, tetapi versinya bukan %VERSI_KODE%.
echo Kemungkinan ada program lain di port 8000, atau folder ini kode lama.

:buka
echo.
echo ============================================================
echo  Buka browser ke: http://localhost:8000
if /i "%HOST%"=="0.0.0.0" echo  Dari komputer lain: http://ALAMAT-IP-PC-INI:8000
echo  Satu alamat saja: API sekaligus menyajikan tampilan web.
echo  Untuk berhenti: tutup jendela "OP Margin - API".
echo  Data Anda: backend\opmargin.db  +  folder unggahan\
echo ============================================================
timeout /t 3 >nul 2>nul
start http://localhost:8000
endlocal
exit /b 0

rem ============================================================
rem  Penanganan kegagalan
rem ============================================================
:tanpa_python
echo.
echo GAGAL: Python tidak ditemukan di PC ini.
echo Pasang Python 3.11 "Windows installer 64-bit" dari PC berinternet
echo (berkas .exe yang dibawa), centang "Add python.exe to PATH",
echo lalu tutup jendela ini dan jalankan start-offline.bat lagi.
goto :berhenti

:tanpa_bahan
echo.
echo GAGAL: folder bahan-offline\wheelhouse tidak ada.
echo Folder itu dibawa dari PC berinternet:
echo   1. Di PC berinternet: jalankan ambil-bahan-offline.bat
echo   2. Salin SELURUH folder aplikasi termasuk bahan-offline ke sini
goto :berhenti

:venv_gagal
echo.
echo GAGAL membuat backend\.venv. Periksa pesan di atas.
echo Pastikan Python terpasang lengkap dan folder aplikasi bisa ditulis.
goto :berhenti

:pip_gagal
popd >nul 2>nul
echo.
echo GAGAL memasang pustaka dari bahan-offline\wheelhouse.
echo Kemungkinan versi Python di PC ini beda dengan versi wheel.
echo Python di PC ini:
"%VPY%" --version
echo Jalankan ambil-bahan-offline.bat di PC berinternet dengan versi
echo Python yang sama, misalnya: ambil-bahan-offline.bat 3.11
goto :berhenti

:env_gagal
popd >nul 2>nul
echo.
echo GAGAL membuat backend\.env. Periksa pesan di atas.
goto :berhenti

:db_gagal
popd >nul 2>nul
echo.
echo GAGAL membuat database atau memuat data awal. Periksa pesan di atas.
goto :berhenti

:tanpa_dist
echo.
echo GAGAL: tampilan web belum ada.
echo Folder bahan-offline\dist belum ikut tersalin.
echo Di PC berinternet: jalankan ambil-bahan-offline.bat, lalu salin
echo lagi SELURUH folder aplikasi termasuk bahan-offline ke PC ini.
goto :berhenti

:dist_gagal
echo.
echo GAGAL menyalin bahan-offline\dist ke frontend\dist.
echo Pastikan folder tujuan bisa ditulis.
goto :berhenti

:berhenti
echo.
pause
endlocal
exit /b 1

rem ============================================================
rem  :hentikan_service
rem  Aplikasi bisa terpasang sebagai service Windows (lihat
rem  deploy/install-windows.md). Service yang hidup akan langsung
rem  menghidupkan lagi API lama setelah ditutup.
rem ============================================================
:hentikan_service
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=@(); try { $s = Get-Service -Name 'OPMargin*' -ErrorAction Stop } catch {}; if (-not $s) { Write-Host '   tidak ada service OPMargin*' } else { foreach ($x in $s) { Write-Host ('   service ' + $x.Name + ' (' + $x.Status + ') dihentikan'); try { Stop-Service -Name $x.Name -Force -ErrorAction Stop } catch { Write-Host ('   GAGAL menghentikan service ' + $x.Name + ': ' + $_.Exception.Message); Write-Host '   -> jalankan start-offline.bat sebagai Administrator, atau hentikan lewat services.msc' } } }"
goto :eof

rem ============================================================
rem  :bersihkan_port PORT NAMA POLA
rem  Menutup paksa proses aplikasi lama yang masih memegang port.
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
