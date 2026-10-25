@echo off
rem ============================================================
rem  OP Margin - perbaiki.bat
rem
rem  SATU berkas untuk membereskan semuanya. Jalankan dengan klik
rem  dua kali. Tidak perlu git, tidak perlu mengunduh berkas lain.
rem
rem  Yang dikerjakan:
rem   1. Menutup semua proses aplikasi lama (port 8000 & 5173).
rem      Proses lama = kode lama = login gagal.
rem   2. Mengunduh kode TERBARU dari branch resmi ke folder baru.
rem   3. Menyalin database lama (data Anda) ke folder baru.
rem   4. Menyiapkan Python + pustaka di folder baru.
rem   5. Menyetel ulang sandi admin -> MENAMPILKAN SANDI BARU.
rem   6. Menjalankan start-web.bat dari folder baru.
rem
rem  Folder lama TIDAK dihapus dan TIDAK diubah.
rem  ASCII saja, tanpa blok "( ... )" berlapis, tanpa "for /f".
rem ============================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

set "CABANG=arena/18670644-rubber-intelligence"
set "URL=https://github.com/boldcraftcode-ops/rubber-intelligence/archive/refs/heads/%CABANG%.zip"
set "ZIP=%TEMP%\opmargin-perbaiki.zip"
set "BARU=%~dp0..\rubber-intelligence-baru"

echo ============================================================
echo  MEMPERBAIKI OP MARGIN
echo  Folder lama : %~dp0
echo  Folder baru : %BARU%
echo ============================================================
echo.

rem ------------------------------------------------------------
echo [1/6] Menutup proses aplikasi lama
powershell -NoProfile -ExecutionPolicy Bypass -Command "$saya=$PID; $induk=0; try { $induk=(Get-CimInstance Win32_Process -Filter ('ProcessId=' + $saya)).ParentProcessId } catch {}; $pola='app.main:app|uvicorn|npm run dev|vite'; $kandidat=@(); try { $kandidat += (Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { $_.CommandLine -and ($_.CommandLine -match $pola) } | ForEach-Object { $_.ProcessId }) } catch {}; foreach ($p in @(8000,5173)) { try { $kandidat += (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop).OwningProcess } catch {} }; $kandidat = $kandidat | Where-Object { $_ -and $_ -ne 0 -and $_ -ne $saya -and $_ -ne $induk } | Sort-Object -Unique; if (-not $kandidat) { Write-Host '   tidak ada proses lama' } else { foreach ($id in $kandidat) { Write-Host ('   PID ' + $id + ' ditutup'); Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } } ; Start-Sleep -Milliseconds 1200"
echo.

rem ------------------------------------------------------------
echo [2/6] Mengunduh kode terbaru
if exist "%ZIP%" del "%ZIP%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -Uri '%URL%' -OutFile '%ZIP%'; exit 0 } catch { Write-Host ('   GAGAL mengunduh: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 goto :gagal_unduh
echo    selesai
echo.

rem ------------------------------------------------------------
echo [3/6] Menyiapkan folder baru
if not exist "%BARU%" goto :buat_folder
echo    folder tujuan sudah ada; memakai nama lain agar tidak tertimpa
set "BARU=%~dp0..\rubber-intelligence-baru-%RANDOM%"

:buat_folder
mkdir "%BARU%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%BARU%' -Force; exit 0 } catch { Write-Host ('   GAGAL membuka ZIP: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 goto :gagal_buka
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $sub = Get-ChildItem -LiteralPath '%BARU%' -Directory | Select-Object -First 1; if ($sub) { Get-ChildItem -LiteralPath $sub.FullName -Force | Move-Item -Destination '%BARU%' -Force; Remove-Item -LiteralPath $sub.FullName -Recurse -Force }"

if exist "%BARU%\VERSI.txt" goto :versi_baru
echo    versi kode baru: (VERSI.txt tidak ada - periksa folder baru)
goto :lanjut_versi

:versi_baru
echo    versi kode baru:
type "%BARU%\VERSI.txt"

:lanjut_versi
echo.

rem ------------------------------------------------------------
echo [4/6] Menyalin database lama (data Anda)
if not exist "backend\opmargin.db" goto :tanpa_db
copy /y "backend\opmargin.db" "%BARU%\backend\opmargin.db" >nul
echo    database disalin: backend\opmargin.db
goto :lanjut_db

:tanpa_db
echo    tidak ada backend\opmargin.db di folder lama
echo    (folder baru akan memuat data awal dari template)

:lanjut_db
echo    catatan: backend\.env TIDAK disalin. Folder baru membuat .env
echo    bersih (login username + sandi) supaya tidak ada sisa setelan lama.
echo.

rem ------------------------------------------------------------
echo [5/6] Menyiapkan Python + pustaka (pertama kali agak lama)
pushd "%BARU%\backend"
if exist ".venv\Scripts\python.exe" goto :punya_venv
where py >nul 2>nul
if not errorlevel 1 goto :pakai_py
where python >nul 2>nul
if errorlevel 1 goto :tanpa_python
set "PY=python"
goto :buat_venv

:pakai_py
set "PY=py -3"

:buat_venv
%PY% -m venv .venv
if errorlevel 1 goto :venv_gagal

:punya_venv
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :venv_gagal
".venv\Scripts\python.exe" -m app.cli init-db
".venv\Scripts\python.exe" -m app.cli atur-login-lokal
echo.
echo    --------------------------------------------------------
echo    SANDI ADMIN BARU (dicatat, dipakai untuk login):
".venv\Scripts\python.exe" -m app.cli reset-sandi admin
echo    --------------------------------------------------------
popd
echo.
goto :jalankan

:tanpa_python
popd
echo    GAGAL: Python tidak ditemukan. Pasang dari https://www.python.org/downloads/
echo    (centang "Add Python to PATH"), lalu jalankan perbaiki.bat lagi.
goto :selesai

:venv_gagal
popd
echo    GAGAL menyiapkan Python/pustaka di folder baru.
echo    Jalankan start-web.bat di folder baru untuk mencoba lagi.
goto :selesai

rem ------------------------------------------------------------
echo [6/6] Menjalankan aplikasi dari folder baru
:jalankan
echo    Jendela "OP Margin - API" dan "OP Margin - Web" akan terbuka.
echo    Tunggu sampai muncul "API siap: kode ..." lalu browser terbuka.
timeout /t 2 >nul 2>nul
start "OP Margin" /D "%BARU%" cmd /c start-web.bat
start "" "%BARU%"
echo.
echo ============================================================
echo  SELESAI
echo  Folder aplikasi yang dipakai sekarang:
echo  %BARU%
echo.
echo  Login: username "admin"
echo  Sandi: LIHAT BARIS "SANDI ADMIN BARU" DI ATAS
echo        (bila terlewat, jalankan di folder baru:
echo         backend\.venv\Scripts\python -m app.cli reset-sandi admin)
echo.
echo  Bila muncul layar "beda versi" atau pesan aneh: jalankan
echo  diagnosa.bat DI FOLDER BARU, lalu kirimkan hasilnya.
echo  Folder lama boleh dihapus setelah folder baru normal.
echo ============================================================
goto :selesai

:gagal_unduh
echo.
echo GAGAL mengunduh kode terbaru. Periksa koneksi internet.
echo Alternatif: buka alamat ini di browser, ekstrak, lalu jalankan
echo start-web.bat di folder hasil ekstrak:
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
