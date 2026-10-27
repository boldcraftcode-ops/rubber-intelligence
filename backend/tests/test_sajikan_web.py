"""Tes mode satu-origin: API sekaligus menyajikan tampilan web (SAJIKAN_WEB).

Dipakai untuk deploy lewat Cloudflare Tunnel dengan SATU hostname, tanpa
Cloudflare Pages. Tujuannya menghindari masalah cookie lintas situs: bila
tampilan web dan API satu alamat, cookie sesi selalu terkirim.

Yang dijaga di sini:
- bawaan (tanpa SAJIKAN_WEB) tidak berubah: akar aplikasi tetap 404;
- bila aktif, "/" menyajikan index.html dan aset ikut tersaji;
- rute /api TIDAK tertutup oleh berkas statis;
- bila foldernya belum ada, aplikasi tetap hidup (API tidak boleh mati).
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
def tanpa_login(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.delenv("SAJIKAN_WEB", raising=False)
    monkeypatch.delenv("SAJIKAN_WEB_FOLDER", raising=False)
    return monkeypatch


def _buat_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><title>Rubber Intelligence</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "logo.svg").write_text("<svg/>", encoding="utf-8")
    return dist


def test_bawaan_akar_tetap_404(tanpa_login):
    klien = TestClient(buat_app(_engine()))
    assert klien.get("/").status_code == 404
    assert klien.get("/api/health").json()["web_statistik"] is None


def test_satu_origin_menyajikan_index_dan_aset(tanpa_login, tmp_path):
    dist = _buat_dist(tmp_path)
    tanpa_login.setenv("SAJIKAN_WEB", "true")
    tanpa_login.setenv("SAJIKAN_WEB_FOLDER", str(dist))
    klien = TestClient(buat_app(_engine()))

    r = klien.get("/")
    assert r.status_code == 200
    assert "Rubber Intelligence" in r.text
    assert klien.get("/assets/app.js").status_code == 200
    assert klien.get("/logo.svg").status_code == 200


def test_rute_api_tidak_tertutup_berkas_statis(tanpa_login, tmp_path):
    """Kesalahan klasik: mount "/" menelan /api. Harus tetap hidup."""
    dist = _buat_dist(tmp_path)
    tanpa_login.setenv("SAJIKAN_WEB", "1")
    tanpa_login.setenv("SAJIKAN_WEB_FOLDER", str(dist))
    klien = TestClient(buat_app(_engine()))

    assert klien.get("/api/health").status_code == 200
    assert klien.get("/api/health").json()["status"] == "ok"
    # Ekspor Excel juga lewat /api, bukan berkas statis.
    assert klien.get("/api/auth/mode").status_code == 200


def test_folder_belum_dibangun_aplikasi_tetap_hidup(tanpa_login, tmp_path):
    """Pengguna sering menyalakan SAJIKAN_WEB sebelum `npm run build`."""
    tanpa_login.setenv("SAJIKAN_WEB", "true")
    tanpa_login.setenv("SAJIKAN_WEB_FOLDER", str(tmp_path / "belum-ada"))
    klien = TestClient(buat_app(_engine()))

    assert klien.get("/api/health").status_code == 200
    assert klien.get("/").status_code == 404
    assert klien.get("/api/health").json()["web_statistik"] is None


def test_health_melaporkan_folder_web(tanpa_login, tmp_path):
    dist = _buat_dist(tmp_path)
    tanpa_login.setenv("SAJIKAN_WEB", "ya")
    tanpa_login.setenv("SAJIKAN_WEB_FOLDER", str(dist))
    isi = TestClient(buat_app(_engine())).get("/api/health").json()
    assert isi["web_statistik"] == str(dist)
