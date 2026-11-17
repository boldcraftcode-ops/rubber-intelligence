import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import buat_app


@pytest.fixture()
def klien(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "p" * 40)
    monkeypatch.setenv("AUTH_DISABLED", "true")  # Setelan lama harus diabaikan.
    engine = create_engine("sqlite://", future=True,
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    client = TestClient(buat_app(engine))
    assert client.post("/api/auth/login", json={
        "username": "admin", "sandi": "admin123"}).status_code == 200
    return client


def test_preferensi_login_dan_nilai_baku(klien):
    response = klien.get("/api/preferensi")
    assert response.status_code == 200
    assert response.json()["efektif"] == {
        "desimal_angka": 3, "desimal_persen": 1, "satuan_berat": "otomatis"}


def test_preferensi_pribadi_dan_reset_per_kunci(klien):
    response = klien.put("/api/preferensi", json={"desimal_angka": 2})
    assert response.status_code == 200
    assert response.json()["efektif"]["desimal_angka"] == 2
    assert response.json()["efektif"]["desimal_persen"] == 1

    reset = klien.put("/api/preferensi", json={"desimal_angka": None})
    assert reset.status_code == 200
    assert reset.json()["efektif"]["desimal_angka"] == 3
    assert reset.json()["pribadi"] == {}


@pytest.mark.parametrize("patch", [
    {"desimal_angka": -1}, {"desimal_angka": 5},
    {"desimal_persen": 3}, {"satuan_berat": "kilogram"},
    {"unknown": 2}, {"desimal_angka": 1.5},
])
def test_preferensi_menolak_nilai_di_luar_rentang(klien, patch):
    assert klien.put("/api/preferensi", json=patch).status_code == 422


def test_admin_bisa_mengunci_bawaan_dan_pribadi_tidak_bisa_menimpa(klien):
    response = klien.put("/api/preferensi/bawaan", json={
        "nilai": {"desimal_angka": 2},
        "terkunci": {"desimal_angka": True},
    })
    assert response.status_code == 200
    effective = klien.put("/api/preferensi", json={"desimal_angka": 4}).json()
    assert effective["efektif"]["desimal_angka"] == 2
    assert effective["pribadi"] == {}


def test_perlu_login_untuk_membaca_preferensi(klien):
    klien.cookies.clear()
    assert klien.get("/api/preferensi").status_code == 401
    assert klien.get("/api/preferensi/bawaan").status_code == 401


def test_pengguna_biasa_tidak_bisa_mengubah_bawaan_perusahaan(klien):
    assert klien.post("/api/auth/pengguna", json={
        "username": "operator", "nama": "Operator", "sandi": "sandi-uji-123",
        "peran": "pengguna",
    }).status_code == 200
    klien.post("/api/auth/logout")
    assert klien.post("/api/auth/login", json={
        "username": "operator", "sandi": "sandi-uji-123",
    }).status_code == 200
    assert klien.put("/api/preferensi/bawaan", json={
        "nilai": {"desimal_angka": 2},
    }).status_code == 403
    assert klien.put("/api/preferensi", json={"desimal_angka": 2}).status_code == 200
