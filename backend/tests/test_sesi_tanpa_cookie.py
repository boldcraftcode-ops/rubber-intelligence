"""Tes sesi tanpa cookie: header Authorization: Bearer.

Latar belakang nyata: bila aplikasi dibuka di dalam iframe (halaman preview /
embed) atau browser memblokir cookie lintas situs, cookie `op_sesi` tidak
pernah dikirim. Akibatnya login berhasil (200) tetapi permintaan berikutnya
401, dan pengguna kembali ke form login tanpa pesan apa pun.

Karena itu login mengirim `token` di badan respons, dan API menerimanya lewat
header `Authorization: Bearer <token>` sebagai cadangan. Cookie tetap cara
utama dan tidak berubah.
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


@pytest.fixture()
def klien(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
    return TestClient(buat_app(_engine()))


def _login(klien):
    r = klien.post("/api/auth/login",
                   json={"username": "admin", "sandi": "admin123"})
    assert r.status_code == 200, r.text
    return r.json()


def test_login_mengirim_token(klien):
    """Token harus ada di respons supaya tampilan web bisa menyimpannya."""
    isi = _login(klien)
    assert isi["status"] == "ok"
    assert isinstance(isi["token"], str) and isi["token"].count(".") == 2


def test_token_bekerja_tanpa_cookie(klien):
    """Inti perbaikan: tanpa cookie sama sekali, header Bearer dilayani."""
    token = _login(klien)["token"]
    klien.cookies.clear()          # meniru browser yang memblokir cookie

    r = klien.get("/api/auth/saya", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "admin"

    # Endpoint data juga harus terbuka, bukan hanya /auth/saya.
    assert klien.get("/api/tahun", headers={
        "Authorization": f"Bearer {token}"}).status_code == 200


def test_tanpa_cookie_dan_tanpa_token_tetap_401(klien):
    """Cadangan tidak boleh melonggarkan keamanan."""
    _login(klien)
    klien.cookies.clear()
    assert klien.get("/api/auth/saya").status_code == 401
    assert klien.get("/api/tahun").status_code == 401


def test_token_palsu_ditolak(klien):
    klien.cookies.clear()
    r = klien.get("/api/auth/saya", headers={"Authorization": "Bearer palsu.palsu.palsu"})
    assert r.status_code == 401
    assert "tidak sah" in r.json()["detail"].lower()


def test_skema_authorization_lain_diabaikan(klien):
    """Hanya "Bearer"; skema lain tidak boleh lolos."""
    token = _login(klien)["token"]
    klien.cookies.clear()
    r = klien.get("/api/auth/saya", headers={"Authorization": f"Basic {token}"})
    assert r.status_code == 401


def test_cookie_masih_jadi_cara_utama(klien):
    """Tanpa header apa pun, cookie dari login tetap dipakai (perilaku lama)."""
    _login(klien)
    r = klien.get("/api/auth/saya")     # TestClient menyimpan & mengirim cookie
    assert r.status_code == 200


def test_logout_tidak_memengaruhi_token(klien):
    """Logout menghapus cookie; tampilan web juga menghapus token tersimpan.

    API sengaja tidak menyimpan daftar token (stateless), jadi yang diuji di
    sini: setelah logout, cookie hilang tetapi permintaan tanpa kredensial 401.
    """
    token = _login(klien)["token"]
    klien.post("/api/auth/logout")
    klien.cookies.clear()
    assert klien.get("/api/auth/saya").status_code == 401
    # Token masih sah sampai kedaluwarsa — itu sifat JWT, bukan bug.
    assert klien.get("/api/auth/saya", headers={
        "Authorization": f"Bearer {token}"}).status_code == 200
