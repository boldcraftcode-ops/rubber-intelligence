"""Setelan login aplikasi.

Login yang dipakai HANYA satu cara: **username + sandi** (login lokal) yang
tersimpan di tabel `pengguna`. Sesi disimpan sebagai cookie HttpOnly berisi
JWT yang ditandatangani SECRET_KEY.

Catatan: login Cloudflare Access sudah DIHAPUS atas permintaan pemilik
aplikasi (dulu dipakai untuk deploy lewat Cloudflare). Variabel CF_ACCESS_*
di .env sekarang diabaikan dan boleh dihapus.

Variabel .env yang masih dipakai:
  APP_ENV        = development | produksi
  SECRET_KEY     = kunci penanda tangan sesi, minimal 32 karakter
  AUTH_DISABLED  = "true" hanya untuk pengembangan; DILARANG di produksi
"""
from __future__ import annotations

import os
import secrets
import sys

# Jalur yang boleh diakses TANPA login:
#   /api/health      -> pemeriksaan hidup + identitas versi proses
#   /api/sehat       -> pemeriksaan sederhana
#   /api/auth/mode   -> frontend tahu cara login yang berlaku
#   /api/auth/login  -> tempat masuk
JALUR_BEBAS = ("/api/health", "/api/sehat", "/api/auth/mode", "/api/auth/login")


class KonfigurasiAuth:
    def __init__(self) -> None:
        self.app_env = os.environ.get("APP_ENV", "development").strip().lower()
        self.auth_disabled = os.environ.get("AUTH_DISABLED", "").strip().lower() == "true"
        # Hanya ada satu mode login sekarang. "nonaktif" berarti login
        # dimatikan lewat AUTH_DISABLED=true (khusus pengembangan).
        self.mode = "nonaktif" if self.auth_disabled else "lokal"

        self.secret = os.environ.get("SECRET_KEY", "").strip()
        # Sesi ditandatangani SECRET_KEY; kunci kosong membuat proses login
        # gagal. Di luar produksi kunci acak dibuat otomatis supaya aplikasi
        # tetap bisa dipakai (sesi berakhir saat API dijalankan ulang).
        self.secret_otomatis = False
        if len(self.secret) < 32 and not self.produksi:
            self.secret = secrets.token_hex(32)
            self.secret_otomatis = True
            sys.stderr.write(
                "CATATAN: SECRET_KEY belum diisi (minimal 32 karakter). "
                "Kunci sementara dibuat otomatis agar login bisa dipakai; "
                "tulis SECRET_KEY di backend/.env agar sesi tidak berakhir "
                "saat API dijalankan ulang.\n")

    @property
    def produksi(self) -> bool:
        return self.app_env.startswith("prod")

    @property
    def lokal_aktif(self) -> bool:
        """Login username+sandi dipasang bila login tidak dimatikan."""
        return not self.auth_disabled

    def validasi_start(self) -> None:
        """Dipanggil saat aplikasi start. Gagal-tertutup di produksi."""
        if not self.produksi:
            return
        if self.auth_disabled:
            raise RuntimeError(
                "APP_ENV=produksi tetapi AUTH_DISABLED=true. Ini DILARANG: "
                "aplikasi menolak start. Hapus AUTH_DISABLED dari .env produksi.")
        if len(self.secret) < 32:
            raise RuntimeError(
                "APP_ENV=produksi membutuhkan SECRET_KEY minimal 32 karakter "
                "di .env (untuk menandatangani sesi login). Buat dengan: "
                "python -c \"import secrets; print(secrets.token_hex(32))\"")
        # Sisa setelan lama Cloudflare Access tidak lagi berpengaruh, tetapi
        # lebih baik diberitahukan supaya .env produksi bisa dibersihkan.
        if os.environ.get("CF_ACCESS_AUD", "").strip():
            sys.stderr.write(
                "CATATAN: CF_ACCESS_* masih ada di .env tetapi TIDAK dipakai "
                "lagi (login Cloudflare Access sudah dihapus). Boleh dihapus.\n")


def info_mode(cfg: KonfigurasiAuth) -> dict:
    """Ringkasan cara login yang berlaku — dipakai /api/health dan
    /api/auth/mode. TANPA data sensitif (tanpa SECRET_KEY)."""
    if cfg.lokal_aktif:
        mode, cara = "lokal", "username-sandi"
    else:
        mode, cara = "nonaktif", "tanpa-login"
    return {"mode": mode, "cara": cara,
            "perlu_login": mode != "nonaktif",
            "produksi": cfg.produksi,
            "mode_otomatis": False}
