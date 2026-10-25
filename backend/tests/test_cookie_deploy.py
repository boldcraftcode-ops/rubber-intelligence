"""Tes SameSite cookie sesi — jalur deploy lewat Cloudflare Tunnel.

Latar belakang: login memakai cookie `op_sesi`. Bila tampilan web dan API
berada di SITUS berbeda (mis. <proyek>.pages.dev + api.domain-anda.com),
browser TIDAK mengirim cookie SameSite=lax, sehingga login tampak berhasil
tetapi permintaan berikutnya 401 (kembali ke form login). Setelan
COOKIE_SAMESITE=none menyelesaikannya, dan Secure wajib ikut menyala.

Yang diuji di sini: nilai bawaan tidak berubah (lax), nilai "none" bekerja,
Secure selalu menyala saat none, dan salah tulis tidak membuat aplikasi mati.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import buat_app


def _engine():
    return create_engine("sqlite://", future=True,
                         connect_args={"check_same_thread": False},
                         poolclass=StaticPool)


def _klien():
    return TestClient(buat_app(_engine()))


@pytest.fixture()
def siap_login(monkeypatch):
    """Login username+sandi aktif, tanpa CAPTCHA/akses lain."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)


def _cookie_sesi(klien) -> str:
    r = klien.post("/api/auth/login",
                   json={"username": "admin", "sandi": "admin123"})
    assert r.status_code == 200, r.text
    return r.headers["set-cookie"]


def test_bawaan_tetap_lax(siap_login, monkeypatch):
    """Tanpa setelan baru: perilaku lama tidak berubah."""
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
    cookie = _cookie_sesi(_klien())
    assert "SameSite=lax" in cookie
    assert "HttpOnly" in cookie


def test_none_untuk_deploy_lintas_situs(siap_login, monkeypatch):
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    cookie = _cookie_sesi(_klien())
    assert "SameSite=none" in cookie
    # Browser membuang SameSite=None tanpa Secure -> Secure wajib menyala.
    assert "Secure" in cookie


def test_none_membuat_secure_menyala_di_luar_produksi(siap_login, monkeypatch):
    """Tanpa APP_ENV=produksi pun, none harus disertai Secure."""
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    monkeypatch.setenv("APP_ENV", "development")
    cookie = _cookie_sesi(_klien())
    assert "SameSite=none" in cookie and "Secure" in cookie


def test_strict_dihormati(siap_login, monkeypatch):
    monkeypatch.setenv("COOKIE_SAMESITE", "strict")
    assert "SameSite=strict" in _cookie_sesi(_klien())


def test_salah_tulis_tidak_mengunci_pengguna(siap_login, monkeypatch):
    """Nilai kacau -> jatuh ke lax + dilaporkan, bukan aplikasi gagal start."""
    monkeypatch.setenv("COOKIE_SAMESITE", "non")   # maksudnya "none"
    klien = _klien()
    assert "SameSite=lax" in _cookie_sesi(klien)
    info = klien.get("/api/auth/mode").json()
    assert info["cookie_samesite"] == "lax"
    assert info["cookie_samesite_salah_tulis"] is True


def test_health_melaporkan_setelan_cookie(siap_login, monkeypatch):
    """Supaya diagnosa/deploy bisa dicek tanpa membuka browser."""
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    isi = _klien().get("/api/health").json()
    assert isi["login"]["cookie_samesite"] == "none"
    assert isi["login"]["cookie_samesite_salah_tulis"] is False
