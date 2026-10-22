"""Verifikasi login Cloudflare Access (Fase 5).

Cara kerja di produksi:
- Semua permintaan ke /api (kecuali /api/health) harus membawa header
  Cf-Access-Jwt-Assertion (otomatis ditambahkan Cloudflare Access) atau
  cookie CF_Authorization.
- Token diverifikasi: tanda tangan (kunci publik JWKS dari team domain),
  audience (AUD aplikasi Access), dan masa berlaku.
- AUTH_DISABLED=true hanya untuk development lokal; aplikasi MENOLAK start
  bila dipakai saat APP_ENV=produksi. Di produksi, konfigurasi Access yang
  kosong juga membuat aplikasi menolak start (gagal-tertutup).

Variabel .env:
  APP_ENV                = development | produksi
  AUTH_DISABLED          = true/false
  CF_ACCESS_TEAM_DOMAIN  = contoh: perusahaanku.cloudflareaccess.com
  CF_ACCESS_AUD          = Application Audience (AUD) tag dari Access
  CF_ACCESS_CERTS_URL    = (opsional, untuk pengujian) ganti URL JWKS
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

import jwt

JALUR_BEBAS = ("/api/health", "/api/sehat")


class KonfigurasiAuth:
    def __init__(self) -> None:
        self.app_env = os.environ.get("APP_ENV", "development").strip().lower()
        self.auth_disabled = os.environ.get("AUTH_DISABLED", "").strip().lower() == "true"
        # Mode login: "lokal" (form username+sandi, data di tabel pengguna)
        # atau "access" (Cloudflare Access).
        self.mode = os.environ.get("AUTH_MODE", "access").strip().lower()
        self.secret = os.environ.get("SECRET_KEY", "").strip()
        self.team_domain = os.environ.get("CF_ACCESS_TEAM_DOMAIN", "").strip()
        self.aud = os.environ.get("CF_ACCESS_AUD", "").strip()
        self.certs_url = os.environ.get("CF_ACCESS_CERTS_URL", "").strip() or (
            f"https://{self.team_domain}/cdn-cgi/access/certs" if self.team_domain else "")

    @property
    def produksi(self) -> bool:
        return self.app_env.startswith("prod")

    @property
    def aktif(self) -> bool:
        """Auth Cloudflare Access dipasang bila mode access, tidak dimatikan,
        dan konfigurasi lengkap."""
        return (self.mode != "lokal" and not self.auth_disabled
                and bool(self.aud and self.certs_url))

    @property
    def lokal_aktif(self) -> bool:
        """Login lokal (form sendiri) dipasang bila mode lokal & tidak dimatikan."""
        return self.mode == "lokal" and not self.auth_disabled

    def validasi_start(self) -> None:
        """Dipanggil saat aplikasi start. Gagal-tertutup di produksi."""
        if not self.produksi:
            return
        if self.auth_disabled:
            raise RuntimeError(
                "APP_ENV=produksi tetapi AUTH_DISABLED=true. Ini DILARANG: "
                "aplikasi menolak start. Hapus AUTH_DISABLED dari .env produksi.")
        if self.mode == "lokal":
            if len(self.secret) < 32:
                raise RuntimeError(
                    "AUTH_MODE=lokal di produksi membutuhkan SECRET_KEY minimal "
                    "32 karakter di .env (untuk menandatangani sesi login). "
                    "Buat dengan: python -c \"import secrets; "
                    "print(secrets.token_hex(32))\"")
            return
        if not (self.aud and self.certs_url):
            raise RuntimeError(
                "APP_ENV=produksi tetapi CF_ACCESS_TEAM_DOMAIN / CF_ACCESS_AUD "
                "belum diisi di .env. Login Cloudflare Access wajib di produksi; "
                "lihat deploy/cloudflare-pages-access.md.")


class VerifikatorAccess:
    """Memverifikasi JWT Cloudflare Access memakai JWKS (cache kunci 1 jam)."""

    def __init__(self, cfg: KonfigurasiAuth) -> None:
        self.cfg = cfg
        self._kunci: dict[str, object] | None = None
        self._diambil_pada = 0.0

    def _jwks(self, paksa: bool = False) -> dict[str, object]:
        if paksa or self._kunci is None or time.time() - self._diambil_pada > 3600:
            with urllib.request.urlopen(self.cfg.certs_url, timeout=10) as r:
                data = json.load(r)
            self._kunci = {
                k["kid"]: jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(k))
                for k in data.get("keys", [])
                if k.get("kty") == "RSA" and k.get("kid")
            }
            self._diambil_pada = time.time()
        return self._kunci

    def verifikasi(self, token: str) -> dict:
        """Mengembalikan klaim bila sah; melempar jwt.PyJWTError bila tidak."""
        kid = jwt.get_unverified_header(token).get("kid")
        kunci = self._jwks().get(kid)
        if kunci is None:  # kunci mungkin baru dirotasi Cloudflare -> ambil ulang
            kunci = self._jwks(paksa=True).get(kid)
        if kunci is None:
            raise jwt.InvalidTokenError("kid tidak dikenal di JWKS")
        return jwt.decode(
            token, kunci, algorithms=["RS256"], audience=self.cfg.aud,
            options={"require": ["exp", "aud"]})
