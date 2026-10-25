"""Tes Fase 5: verifikasi JWT Cloudflare Access, penolakan start di produksi,
/api/health tanpa data sensitif, dan prosedur restore backup."""
import datetime as dt
import json
import sqlite3

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import buat_app
from app.models import Base

AUD = "aud-uji-op-margin"


@pytest.fixture()
def kunci_rsa():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def lingkungan_access(tmp_path, monkeypatch, kunci_rsa):
    """Siapkan JWKS lokal + env sehingga auth AKTIF."""
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(kunci_rsa.public_key()))
    jwk.update({"kid": "kid-uji", "alg": "RS256", "use": "sig"})
    jwks_file = tmp_path / "jwks.json"
    jwks_file.write_text(json.dumps({"keys": [jwk]}))
    monkeypatch.setenv("CF_ACCESS_CERTS_URL", f"file://{jwks_file}")
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    monkeypatch.setenv("AUTH_MODE", "access")   # tegas: bukan login lokal
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.setenv("APP_ENV", "development")


def _klien():
    eng = create_engine("sqlite://", future=True,
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    return TestClient(buat_app(eng))


def _token(kunci, aud=AUD, email="budi@kantor.co.id", exp_detik=600, kid="kid-uji"):
    pem = kunci.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    klaim = {"aud": aud, "email": email,
             "iat": dt.datetime.utcnow(),
             "exp": dt.datetime.utcnow() + dt.timedelta(seconds=exp_detik)}
    return jwt.encode(klaim, pem, algorithm="RS256", headers={"kid": kid})


# ----------------------------------------------------------------------------
# Verifikasi JWT
# ----------------------------------------------------------------------------
def test_tanpa_token_ditolak(lingkungan_access):
    k = _klien()
    r = k.get("/api/tahun")
    assert r.status_code == 401
    assert "Belum login" in r.json()["detail"]


def test_token_sah_diterima(lingkungan_access, kunci_rsa):
    k = _klien()
    r = k.get("/api/alarm", headers={"Cf-Access-Jwt-Assertion": _token(kunci_rsa)})
    assert r.status_code == 200


def test_audience_salah_ditolak(lingkungan_access, kunci_rsa):
    k = _klien()
    r = k.get("/api/alarm", headers={
        "Cf-Access-Jwt-Assertion": _token(kunci_rsa, aud="aplikasi-lain")})
    assert r.status_code == 401
    assert "tidak sah" in r.json()["detail"]


def test_token_kedaluwarsa_ditolak(lingkungan_access, kunci_rsa):
    k = _klien()
    r = k.get("/api/alarm", headers={
        "Cf-Access-Jwt-Assertion": _token(kunci_rsa, exp_detik=-60)})
    assert r.status_code == 401
    assert "kedaluwarsa" in r.json()["detail"]


def test_tanda_tangan_palsu_ditolak(lingkungan_access):
    """Token ditandatangani kunci LAIN (penyerang) -> ditolak."""
    kunci_palsu = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    k = _klien()
    r = k.get("/api/alarm", headers={
        "Cf-Access-Jwt-Assertion": _token(kunci_palsu, kid="kid-uji")})
    assert r.status_code == 401


def test_health_terbuka_tanpa_login(lingkungan_access):
    """/api/health boleh diakses monitoring tanpa token, tanpa data sensitif."""
    k = _klien()
    r = k.get("/api/health")
    assert r.status_code == 200
    isi = r.json()
    assert isi["status"] == "ok"
    # "fitur" = daftar nama endpoint (bukan data bisnis); dipakai untuk
    # memastikan proses API yang berjalan memang versi terbaru.
    assert set(isi) <= {"status", "app", "versi", "waktu", "fitur", "login"}
    assert all(isinstance(x, str) and "/" not in x for x in isi.get("fitur", []))


# ----------------------------------------------------------------------------
# Menolak start bila produksi salah konfigurasi
# ----------------------------------------------------------------------------
def test_produksi_auth_disabled_menolak_start(monkeypatch):
    monkeypatch.setenv("APP_ENV", "produksi")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    with pytest.raises(RuntimeError, match="DILARANG"):
        buat_app(create_engine("sqlite://", future=True))


def test_produksi_tanpa_access_menolak_start(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "access")
    monkeypatch.setenv("APP_ENV", "produksi")
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("CF_ACCESS_TEAM_DOMAIN", raising=False)
    monkeypatch.delenv("CF_ACCESS_AUD", raising=False)
    monkeypatch.delenv("CF_ACCESS_CERTS_URL", raising=False)
    with pytest.raises(RuntimeError, match="Cloudflare Access"):
        buat_app(create_engine("sqlite://", future=True))


def test_development_tanpa_access_tetap_jalan(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("CF_ACCESS_AUD", raising=False)
    monkeypatch.delenv("CF_ACCESS_CERTS_URL", raising=False)
    k = _klien()
    assert k.get("/api/health").status_code == 200


# ----------------------------------------------------------------------------
# Backup & restore (logika yang sama dengan deploy/backup.ps1)
# ----------------------------------------------------------------------------
def test_backup_dan_restore(tmp_path, engine):
    """Salin database dengan sqlite backup API (seperti backup.ps1), lalu
    restore ke folder uji dan pastikan datanya utuh."""
    # 'server' = db hasil impor template pada fixture engine
    sumber_path = engine.url.database
    cadangan = tmp_path / "backup" / "opmargin.db"
    cadangan.parent.mkdir()
    src = sqlite3.connect(sumber_path)
    dst = sqlite3.connect(cadangan)
    src.backup(dst)  # snapshot konsisten walau sedang dipakai
    dst.close(); src.close()

    # restore ke folder uji
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
