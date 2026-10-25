"""Tes cara login yang berlaku: /api/auth/mode, pesan 401 yang menjelaskan
kasus localhost pada mode Cloudflare Access, dan alat `atur-login-lokal`.

Latar belakang kasus nyata: `.env` masih berisi setelan Cloudflare Access
(CF_ACCESS_AUD) sehingga di localhost semua halaman menampilkan "Belum login
... Cloudflare Access" dan form username+sandi tidak pernah berhasil.
"""
import json

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import buat_app
from app.setup_env import atur_login_lokal, _nilai

AUD = "aud-uji-op-margin"


def _engine():
    return create_engine("sqlite://", future=True,
                         connect_args={"check_same_thread": False},
                         poolclass=StaticPool)


def _klien(lokal=False):
    """base_url localhost = meniru browser di komputer yang sama."""
    alamat = "http://localhost" if lokal else "http://testserver"
    return TestClient(buat_app(_engine()), base_url=alamat)


@pytest.fixture()
def mode_access(tmp_path, monkeypatch):
    kunci = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(kunci.public_key()))
    jwk.update({"kid": "kid-uji", "alg": "RS256", "use": "sig"})
    jwks = tmp_path / "jwks.json"
    jwks.write_text(json.dumps({"keys": [jwk]}))
    monkeypatch.setenv("CF_ACCESS_CERTS_URL", f"file://{jwks}")
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "access")
    monkeypatch.delenv("AUTH_DISABLED", raising=False)


@pytest.fixture()
def mode_lokal(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "lokal")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("CF_ACCESS_AUD", raising=False)
    monkeypatch.delenv("CF_ACCESS_CERTS_URL", raising=False)
    return tmp_path


# --------------------------------------------------------------- mode publik
def test_mode_access_terbaca_tanpa_login(mode_access):
    k = _klien()
    r = k.get("/api/auth/mode")
    assert r.status_code == 200
    isi = r.json()
    assert isi["mode"] == "access" and isi["cara"] == "cloudflare-access"
    assert isi["perlu_login"] is True
    assert isi["produksi"] is False


def test_mode_lokal_terbaca_tanpa_login(mode_lokal):
    k = _klien()
    r = k.get("/api/auth/mode")
    assert r.status_code == 200
    assert r.json()["cara"] == "username-sandi"


def test_mode_tanpa_auth(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("CF_ACCESS_AUD", raising=False)
    monkeypatch.setenv("AUTH_DISABLED", "true")
    r = _klien().get("/api/auth/mode")
    assert r.status_code == 200
    isi = r.json()
    assert isi["mode"] == "nonaktif" and isi["cara"] == "tanpa-login"
    assert isi["perlu_login"] is False and isi["produksi"] is False


def test_health_melaporkan_cara_login(mode_access):
    isi = _klien().get("/api/health").json()
    assert isi["login"]["cara"] == "cloudflare-access"


# ------------------------------------------------- pesan yang menjelaskan
def test_pesan_access_di_localhost_memberi_petunjuk(mode_access):
    r = _klien(lokal=True).get("/api/alarm")
    assert r.status_code == 401
    detail = r.json()["detail"]
    assert "Cloudflare Access" in detail
    assert "AUTH_MODE=lokal" in detail          # petunjuk yang bisa ditindak
    assert "localhost" in detail


def test_login_form_ditolak_dengan_jelas_pada_mode_access(mode_access):
    """Form username+sandi memang tidak berlaku; jangan balas 404/500."""
    r = _klien().post("/api/auth/login",
                      json={"username": "admin", "sandi": "admin123"})
    assert r.status_code == 422
    pesan = r.json()["detail"]
    assert "Cloudflare Access" in pesan and "AUTH_MODE=lokal" in pesan


def test_login_lokal_berhasil(mode_lokal):
    k = _klien()
    r = k.post("/api/auth/login", json={"username": "admin",
                                        "sandi": "admin123"})
    assert r.status_code == 200, r.text
    assert r.json()["peran"] == "admin"
    assert k.get("/api/auth/saya").json()["mode"] == "lokal"


def test_halaman_terlindungi_tanpa_sesi(mode_lokal):
    r = _klien().get("/api/alarm")
    assert r.status_code == 401
    assert "username dan sandi" in r.json()["detail"]


# ------------------------------------------------------- alat atur-login-lokal
def test_atur_login_lokal_membuat_env_baru(tmp_path):
    env = tmp_path / ".env"
    hasil = atur_login_lokal(env)
    assert hasil["dibuat"] is True
    baris = env.read_text().splitlines()
    assert _nilai(baris, "AUTH_MODE") == "lokal"
    assert len(_nilai(baris, "SECRET_KEY") or "") >= 32


def test_atur_login_lokal_mengalahkan_setelan_access(tmp_path):
    env = tmp_path / ".env"
    env.write_text("APP_ENV=development\nAUTH_MODE=access\n"
                   "CF_ACCESS_AUD=rahasia\nSECRET_KEY=pendek\n"
                   "DATABASE_URL=sqlite:///lain.db\n")
    atur_login_lokal(env)
    baris = env.read_text().splitlines()
    assert _nilai(baris, "AUTH_MODE") == "lokal"
    assert len(_nilai(baris, "SECRET_KEY")) >= 32
    # setelan lain tidak boleh hilang / berubah
    assert _nilai(baris, "CF_ACCESS_AUD") == "rahasia"
    assert _nilai(baris, "DATABASE_URL") == "sqlite:///lain.db"
    assert _nilai(baris, "APP_ENV") == "development"


def test_atur_login_lokal_tidak_menimpa_secret_yang_kuat(tmp_path):
    env = tmp_path / ".env"
    env.write_text("AUTH_MODE=lokal\nSECRET_KEY=" + "x" * 64 + "\n")
    hasil = atur_login_lokal(env)
    assert "SECRET_KEY" not in hasil["diubah"]
    assert _nilai(env.read_text().splitlines(), "SECRET_KEY") == "x" * 64


def test_atur_login_lokal_mematikan_auth_disabled(tmp_path):
    env = tmp_path / ".env"
    env.write_text("AUTH_DISABLED=true\n")
    atur_login_lokal(env)
    baris = env.read_text().splitlines()
    assert _nilai(baris, "AUTH_DISABLED") is None
    assert _nilai(baris, "AUTH_MODE") == "lokal"


# -------------------------------------- mode otomatis saat AUTH_MODE kosong
def test_akses_di_luar_produksi_otomatis_jadi_lokal(monkeypatch):
    """Kasus nyata: .env lama berisi setelan Access TANPA AUTH_MODE.

    Di luar produksi (localhost) aplikasi tidak boleh terjebak di mode Access
    yang mustahil dipakai — mode otomatis jadi lokal.
    """
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    isi = _klien().get("/api/auth/mode").json()
    assert isi["cara"] == "username-sandi"
    assert isi["mode_otomatis"] is True


def test_produksi_tanpa_auth_mode_tetap_access(monkeypatch):
    """Produksi tidak boleh ikut-ikutan jadi lokal (gagal-tertutup)."""
    from app.auth import KonfigurasiAuth
    monkeypatch.setenv("APP_ENV", "produksi")
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", "contoh.cloudflareaccess.com")
    assert KonfigurasiAuth().mode == "access"


def test_login_lokal_tetap_bisa_tanpa_secret_key(mode_lokal, monkeypatch):
    """SECRET_KEY kosong dulu membuat login gagal 500; sekarang kunci
    sementara dibuat otomatis sehingga login tetap bisa dipakai."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    k = _klien()
    r = k.post("/api/auth/login", json={"username": "admin",
                                        "sandi": "admin123"})
    assert r.status_code == 200, r.text
    assert k.get("/api/auth/saya").json()["username"] == "admin"


def test_diagnosa_dan_tanya_api_bisa_dijalankan():
    """Alat bantu pengguna tidak boleh error saat dijalankan."""
    from app import tanya_api
    from app.cli import _cetak_diagnosa

    _cetak_diagnosa()          # hanya mencetak; tidak boleh melempar
    assert callable(tanya_api.main)
