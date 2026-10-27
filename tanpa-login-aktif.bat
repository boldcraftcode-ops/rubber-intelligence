@echo off
rem ============================================================
rem  tanpa-login-aktif.bat
rem  Membuat penanda tanpa-login.txt supaya start-web.bat
rem  menjalankan aplikasi TANPA form login (sementara).
rem  Jalankan tanpa-login-mati.bat untuk mengaktifkan login lagi.
rem ============================================================
setlocal
cd /d "%~dp0"
echo Login akan DIMATIKAN (sementara).
echo.
echo 1^) Membuat berkas tanpa-login.txt
> "tanpa-login.txt" echo MODE TANPA LOGIN SEMENTARA - hapus berkas ini untuk mengaktifkan login kembali.
if not exist "tanpa-login.txt" goto gagal
echo    selesai.
echo.
echo 2^) Menjalankan start-web.bat ...
echo    Tutup dua jendela OP Margin lebih dulu bila masih terbuka.
echo.
call "%~dp0start-web.bat"
goto selesai

:gagal
echo GAGAL membuat tanpa-login.txt. Pastikan folder ini bisa ditulis.
echo Coba jalankan berkas ini dengan klik kanan - Run as administrator.
pause

:selesai
endlocal
