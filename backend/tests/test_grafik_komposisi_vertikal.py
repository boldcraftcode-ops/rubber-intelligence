"""Grafik komposisi penerimaan karet: batang berdiri, Share EUDR tetap garis.

Istilah Recharts membingungkan: `layout="horizontal"` = kategori di X, angka
di Y, batang berdiri/vertikal. `layout="vertical"` = batang mendatar.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import buat_app

AKAR = Path(__file__).resolve().parents[2]


def _komposisi() -> str:
    """Bagian komponen tanpa komentar JSX, agar penjelasan tidak terbaca prop."""
    s = (AKAR / "frontend/src/pages/Analisis.tsx").read_text(encoding="utf-8")
    awal = s.index("export function AnalisisKomposisi(")
    akhir = s.index("\nfunction KartuPenerimaan()", awal)
    return re.sub(r"\{/\*.*?\*/\}", "", s[awal:akhir], flags=re.S)


@pytest.fixture()
def klien(engine):
    return TestClient(buat_app(engine))


def test_grafik_porsi_berdiri_vertikal():
    s = _komposisi()
    assert '<BarChart data={grafikPorsi} layout="horizontal"' in s
    assert 'layout="vertical"' not in s
    assert '<XAxis type="category" dataKey="nama"' in s
    assert '<YAxis type="number"' in s
    assert 'angle={-45}' in s and 'textAnchor="end"' in s
    assert '<Bar dataKey="Porsi (%)" fill="#1D2434" maxBarSize={48} />' in s
    # Label kategori dipendekkan agar 12 batang tidak saling menimpa; tooltip
    # memakai nama lengkap, tabel di bawahnya tetap memuat data asli.
    assert "namaLengkap: b.label" in s
    assert "labelFormatter={(label: any, payload: any)" in s
    assert s.count("<BarChart") == 1


def test_share_eudr_vs_biasa_tetap_grafik_garis():
    s = _komposisi()
    assert "Share EUDR vs biasa" in s
    assert "<LineChart data={grafikEudr}" in s
    assert '<Line type="monotone" dataKey="Share EUDR (%)"' in s
    assert s.count("<LineChart") == 1
    # Pengecualian: blok EUDR tidak ikut dipaksa memakai tata letak batang.
    eudr = s[s.index("Share EUDR vs biasa"):]
    assert 'layout="horizontal"' not in eudr
    assert 'layout="vertical"' not in eudr


def test_endpoint_komposisi_tetap_tersedia(klien):
    r = klien.get("/api/kartu/penerimaan/komposisi?dimensi=provinsi")
    assert r.status_code == 200
    assert "baris" in r.json()
