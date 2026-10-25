"""Tes keamanan & login: satu-satunya cara masuk adalah username + sandi.

Dulu aplikasi mendukung login Cloudflare Access. Fitur itu SUDAH DIHAPUS,
sehingga tes di sini memastikan:

- halaman terproteksi menolak permintaan tanpa sesi;
- login berhasil dengan sandi benar dan ditolak dengan sandi salah;
- header/cookie sisa Cloudflare (Cf-Access-Jwt-Assertion, CF_Authorization)
  TIDAK lagi bisa dipakai untuk masuk;
- /api/health terbuka tanpa login dan tanpa data bisnis;
- konfigurasi produksi yang salah membuat aplikasi menolak start;
- prosedur backup/restore tetap utuh.
"""
import sqlite3

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import buat_app


def _klien(base_url: str = "http://testserver"):
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    return TestClient(buat_app(eng), base_url=base_url)


@pytest.fixture()
def tanpa_auth(monkeypatch):
    """Mode pengembangan: login dimatikan, seperti fixture conftest."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.delenv("CF_ACCESS_AUD", raising=False)
    return monkeypatch


@pytest.fixture()
def dengan_auth(monkeypatch):
    """Login username+sandi aktif."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("CF_ACCESS_AUD", raising=False)
    return monkeypatch


# ---------------------------------------------------------------- halaman API
def test_tanpa_sesi_ditolak(dengan_auth):
    r = _klien().get("/api/tahun")
    assert r.status_code == 401
    assert "Belum login" in r.json()["detail"]
    assert "username dan sandi" in r.json()["detail"]


def test_login_berhasil_dan_sesi_dipakai(dengan_auth):
    k = _klien()
    r = k.post("/api/auth/login", json={"username": "admin", "sandi": "admin123"})
    assert r.status_code == 200
    assert r.json()["peran"] == "admin"
    assert k.get("/api/alarm").status_code == 200
    assert k.get("/api/auth/saya").json()["mode"] == "lokal"


def test_sandi_salah_ditolak(dengan_auth):
    r = _klien().post("/api/auth/login",
                      json={"username": "admin", "sandi": "salah-sekali"})
    assert r.status_code == 401
    assert "Username atau sandi salah" in r.json()["detail"]


def test_logout_menghapus_sesi(dengan_auth):
    k = _klien()
    k.post("/api/auth/login", json={"username": "admin", "sandi": "admin123"})
    assert k.get("/api/alarm").status_code == 200
    k.post("/api/auth/logout")
    assert k.get("/api/alarm").status_code == 401


# ------------------------------------- sisa Cloudflare tidak lagi berpengaruh
def test_header_cloudflare_tidak_lagi_dipakai(dengan_auth):
    """Dulu header ini cukup untuk masuk. Sekarang harus 401."""
    r = _klien().get("/api/alarm",
                     headers={"Cf-Access-Jwt-Assertion": "token-apa-saja"})
    assert r.status_code == 401


def test_cookie_cloudflare_tidak_lagi_dipakai(dengan_auth):
    k = _klien()
    k.cookies.set("CF_Authorization", "token-apa-saja")
    assert k.get("/api/alarm").status_code == 401


def test_setelan_access_di_env_diabaikan(monkeypatch):
    """CF_ACCESS_* sisa deploy lama tidak boleh mengubah cara login."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.setenv("CF_ACCESS_AUD", "aud-lama")
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", "lama.cloudflareaccess.com")
    k = _klien()
    assert k.get("/api/auth/mode").json()["cara"] == "username-sandi"
    assert k.post("/api/auth/login",
                  json={"username": "admin", "sandi": "admin123"}
                  ).status_code == 200


# --------------------------------------------------------------------- health
def test_health_terbuka_tanpa_login(dengan_auth):
    """/api/health boleh diakses monitoring tanpa login, tanpa data sensitif."""
    r = _klien().get("/api/health")
    assert r.status_code == 200
    isi = r.json()
    assert isi["status"] == "ok"
    # "fitur"/"login"/"kode" = identitas proses (bukan data bisnis), dipakai
    # untuk mendiagnosis "API masih versi lama".
    assert set(isi) <= {"status", "app", "versi", "waktu", "fitur",
                        "login", "kode"}
    assert all(isinstance(x, str) and "/" not in x for x in isi.get("fitur", []))
    assert isi["login"]["cara"] == "username-sandi"


# --------------------------------------------- menolak start bila salah setelan
def test_produksi_auth_disabled_menolak_start(monkeypatch):
    monkeypatch.setenv("APP_ENV", "produksi")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    with pytest.raises(RuntimeError, match="DILARANG"):
        buat_app(create_engine("sqlite://", future=True))


def test_produksi_tanpa_secret_key_menolak_start(monkeypatch):
    monkeypatch.setenv("APP_ENV", "produksi")
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        buat_app(create_engine("sqlite://", future=True))


def test_development_tetap_jalan(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("CF_ACCESS_AUD", raising=False)
    assert _klien().get("/api/health").status_code == 200


# ------------------------------------------------------------ backup & restore
def test_backup_dan_restore(tmp_path, engine):
    """Salin database dengan sqlite backup API (seperti backup.ps1), lalu
    restore ke folder uji dan pastikan datanya utuh."""
    sumber_path = engine.url.database
    cadangan = tmp_path / "backup" / "opmargin.db"
    cadangan.parent.mkdir()
    src = sqlite3.connect(sumber_path)
    dst = sqlite3.connect(cadangan)
    src.backup(dst)  # snapshot konsisten walau sedang dipakai
    dst.close()
    src.close()

    uji = tmp_path / "uji-restore" / "opmargin.db"
    uji.parent.mkdir()
    uji.write_bytes(cadangan.read_bytes())

    con = sqlite3.connect(uji)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    jumlah = con.execute("SELECT COUNT(*) FROM pembelian").fetchone()[0]
    margin = con.execute(
        "SELECT op_margin_usc FROM mart_bulanan WHERE tahun=2026 AND bulan=1"
    ).fetchone()[0]
    con.close()
    assert jumlah == 2179                 # data lengkap
    assert round(margin, 4) == 10.5725    # angka emas tetap benar
