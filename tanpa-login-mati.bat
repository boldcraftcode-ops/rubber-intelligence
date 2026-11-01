@echo off
rem ============================================================
rem  tanpa-login-mati.bat
rem  Menghapus penanda tanpa-login.txt supaya form login AKTIF lagi.
rem ============================================================
setlocal
cd /d "%~dp0"
if not exist "tanpa-login.txt" goto sudah_aktif
del /q "tanpa-login.txt"
echo Penanda dihapus. Login username+sandi AKTIF lagi.
echo Jalankan start-web.bat untuk menerapkan.
pause
goto selesai

:sudah_aktif
echo Penanda tidak ada: login memang sudah aktif. Tidak ada yang diubah.
pause

:selesai
endlocal
