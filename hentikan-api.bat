@echo off
rem ============================================================
rem  OP Margin - hentikan-api.bat
rem
rem  Menutup SEMUA proses API/tampilan web aplikasi ini di komputer,
rem  apa pun foldernya. Dipakai bila aplikasi masih menampilkan
rem  "Aplikasi dan servernya beda versi" (API lama masih menjawab).
rem
rem  Bila ada yang TIDAK bisa ditutup, skrip ini mengatakannya dengan
rem  jujur (biasanya proses dijalankan sebagai Administrator atau
rem  sebagai service Windows). Solusinya: klik kanan berkas ini ->
rem  "Run as administrator".
rem
rem  ASCII saja, tanpa blok "( ... )" berlapis, tanpa "for /f".
rem ============================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

echo ============================================================
echo  MENGHENTIKAN PROSES APLIKASI OP MARGIN
echo  Folder skrip ini: %~dp0
echo ============================================================
echo.

echo [1/3] Service Windows (bila aplikasi dipasang sebagai service)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = @(); try { $s = Get-Service -Name 'OPMargin*' -ErrorAction Stop } catch {}; if (-not $s) { Write-Host '   tidak ada service bernama OPMargin*' } else { foreach ($x in $s) { Write-Host ('   service ' + $x.Name + ' status ' + $x.Status + ' -> dihentikan'); try { Stop-Service -Name $x.Name -Force -ErrorAction Stop } catch { Write-Host ('   GAGAL menghentikan service ' + $x.Name + ': ' + $_.Exception.Message + ' (buka skrip ini sebagai Administrator)') } } }"
echo.

echo [2/3] Proses uvicorn / npm run dev / vite (semua folder)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$saya=$PID; $induk=0; try { $induk=(Get-CimInstance Win32_Process -Filter ('ProcessId=' + $saya)).ParentProcessId } catch {}; $pola='app.main:app|uvicorn|npm run dev|node_modules\\\.bin\\vite'; $daftar=@(); try { $daftar = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { $_.CommandLine -and ($_.CommandLine -match $pola) }) } catch { $daftar = @() }; if (-not $daftar) { Write-Host '   tidak ada proses aplikasi yang berjalan' } else { foreach ($p in $daftar) { if ($p.ProcessId -ne $saya -and $p.ProcessId -ne $induk) { Write-Host ('   PID ' + $p.ProcessId + ' ditutup'); try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch { Write-Host ('   GAGAL menutup PID ' + $p.ProcessId + ' (' + $p.Name + '): ' + $_.Exception.Message + ' -> jalankan skrip ini sebagai Administrator') } } } }"
echo.

echo [3/3] Pemegang port 8000 dan 5173 - diperiksa ulang
powershell -NoProfile -ExecutionPolicy Bypass -Command "$saya=$PID; Start-Sleep -Milliseconds 800; $bebas=$true; foreach ($p in @(8000,5173)) { $pid2 = @(); try { $pid2 = (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop).OwningProcess } catch {}; $pid2 = $pid2 | Where-Object { $_ -and $_ -ne $saya } | Sort-Object -Unique; if (-not $pid2) { Write-Host ('   port ' + $p + ' : BEBAS') } else { $bebas=$false; foreach ($id in $pid2) { $info = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $id) -ErrorAction SilentlyContinue; $cmd = ''; if ($info) { $cmd = $info.CommandLine }; Write-Host ('   port ' + $p + ' : MASIH DIPAKAI PID ' + $id); Write-Host ('      ' + $cmd); try { Stop-Process -Id $id -Force -ErrorAction Stop; Write-Host '      -> dicoba ditutup sekali lagi' } catch { Write-Host ('      -> TIDAK BISA ditutup: ' + $_.Exception.Message) ; Write-Host '      -> jalankan hentikan-api.bat sebagai Administrator' } } } }; if (-not $bebas) { Write-Host ''; Write-Host '   CATATAN: bila proses di atas adalah service Windows, ia akan hidup lagi' ; Write-Host '   setelah ditutup. Hentikan service-nya dulu (langkah [1]).' ; Write-Host '   Bila perlu: matikan lewat Task Manager (Details), atau restart komputer.' }"
echo.
echo ============================================================
echo  SELESAI. Bila kedua port sudah BEBAS:
echo    1. Jalankan start-web.bat DARI FOLDER APLIKASI YANG BARU
echo       (folder yang ada VERSI.txt berisi 0.7.3).
echo    2. Tunggu tulisan "API siap: kode 0.7.3".
echo    3. Buka http://localhost:5173 dan tekan Ctrl+F5.
echo ============================================================
echo.
pause
endlocal
exit /b 0
