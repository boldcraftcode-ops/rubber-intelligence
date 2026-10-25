"""Tes cara login: /api/auth/mode, sesi username+sandi, dan alat bantu
`atur-login-lokal`.

Login Cloudflare Access sudah dihapus, jadi yang diuji di sini hanya jalur
username + sandi — termasuk memastikan sisa setelan CF_ACCESS_* tidak lagi
berpengaruh.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import buat_app
from app.setup_env import atur_login_lokal, _nilai


def _engine():
    return create_engine("sqlite://", future=True,
                         connect_args={"check_same_thread": False},
                         poolclass=StaticPool)


def _klien():
    return TestClient(buat_app(_engine()))


@pytest.fixture()
def mode_lokal(monkeypatch, tmp_path):
    """Login username+sandi aktif."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("CF_ACCESS_AUD", raising=False)
    return tmp_path


# --------------------------------------------------------------- mode publik
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


def test_health_melaporkan_cara_login(mode_lokal):
    isi = _klien().get("/api/health").json()
    assert isi["login"]["cara"] == "username-sandi"


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
    assert _nilai(baris, "AUTH_MODE") is None
    assert len(_nilai(baris, "SECRET_KEY") or "") >= 32


def test_atur_login_lokal_membersihkan_sisa_cloudflare(tmp_path):
    """Sisa setelan Cloudflare Access lama dibuang agar tidak membingungkan."""
    env = tmp_path / ".env"
    env.write_text("APP_ENV=development\nAUTH_MODE=access\n"
                   "CF_ACCESS_AUD=rahasia\n"
                   "CF_ACCESS_TEAM_DOMAIN=lama.cloudflareaccess.com\n"
                   "SECRET_KEY=pendek\n"
                   "DATABASE_URL=sqlite:///lain.db\n")
    atur_login_lokal(env)
    baris = env.read_text().splitlines()
    assert _nilai(baris, "AUTH_MODE") is None
    assert _nilai(baris, "CF_ACCESS_AUD") is None
    assert _nilai(baris, "CF_ACCESS_TEAM_DOMAIN") is None
    assert len(_nilai(baris, "SECRET_KEY")) >= 32
    # setelan lain tidak boleh hilang / berubah
    assert _nilai(baris, "DATABASE_URL") == "sqlite:///lain.db"
    assert _nilai(baris, "APP_ENV") == "development"


def test_atur_login_lokal_tidak_menimpa_secret_yang_kuat(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SECRET_KEY=" + "x" * 64 + "\n")
    hasil = atur_login_lokal(env)
    assert "SECRET_KEY" not in hasil["diubah"]
    assert _nilai(env.read_text().splitlines(), "SECRET_KEY") == "x" * 64


def test_atur_login_lokal_mematikan_auth_disabled(tmp_path):
    env = tmp_path / ".env"
    env.write_text("AUTH_DISABLED=true\n")
    atur_login_lokal(env)
    baris = env.read_text().splitlines()
    assert _nilai(baris, "AUTH_DISABLED") is None


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


# ------------------------------------------------- identitas versi kode
def test_health_memuat_identitas_versi(monkeypatch):
    """Versi kode dilaporkan supaya folder lama mudah dikenali."""
    from app.versi import VERSI, versi_folder

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    isi = _klien().get("/api/health").json()
    assert isi["versi"] == VERSI
    assert isi["kode"] == versi_folder()


def test_versi_tiga_sumber_harus_sama():
    """VERSI.txt, backend/app/versi.py, dan frontend/src/versi.ts harus sama.

    Bila berbeda, aplikasi akan menampilkan layar "beda versi" padahal
    sebenarnya tidak ada masalah — jadi ketiganya dijaga oleh tes ini.
    """
    import re

    from app.versi import AKAR, VERSI, versi_folder

    berkas = AKAR / "VERSI.txt"
    assert berkas.exists(), "VERSI.txt harus ada di akar repo"
    assert versi_folder() == VERSI

    ts = (AKAR / "frontend" / "src" / "versi.ts").read_text(encoding="utf-8")
    cocok = re.search(r'VERSI_UI\s*=\s*"([^"]+)"', ts)
    assert cocok, "frontend/src/versi.ts harus berisi VERSI_UI"
    assert cocok.group(1) == VERSI, (
        f"versi UI ({cocok.group(1)}) != versi backend ({VERSI})")


def test_reset_sandi_membuat_akun_bila_belum_ada(tmp_path, monkeypatch, capsys):
    """perbaiki.bat mengandalkan perintah ini untuk SELALU mencetak sandi.

    Pada database baru belum ada akun admin, jadi perintah ini harus membuatnya
    (bukan hanya mengeluh), supaya pemakai mendapat sandi yang pasti berlaku.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.auth_lokal import cek_sandi
    from app.cli import _reset_sandi
    from app.models import Base, Pengguna

    db = tmp_path / "baru.db"
    eng = create_engine(f"sqlite:///{db}", future=True)
    Base.metadata.create_all(eng)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")

    _reset_sandi("admin", "sandi-uji-123")
    keluaran = capsys.readouterr().out
    assert "sandi baru : sandi-uji-123" in keluaran
    assert "dibuat sebagai admin" in keluaran

    Session = sessionmaker(bind=eng, future=True)
    with Session() as s:
        p = s.get(Pengguna, "admin")
        assert p is not None and p.peran == "admin" and p.aktif
        assert cek_sandi("sandi-uji-123", p.hash_sandi)
