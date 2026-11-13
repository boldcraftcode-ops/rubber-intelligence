"""Kartu angka kunci auto-tampil + panel analisa tidak lagi tertahan Refresh.

Penyebab lama: `useQueryKartu` memaksa `enabled:false` bila ada konteks
`KartuMuatSaatDiminta`. Panel analisa baru dipasang saat tombol diklik, sehingga
Refresh kartu tidak pernah mendaftarkan query panel itu. Endpoint backend tetap
200; perbaikannya ada di frontend.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import buat_app

AKAR = Path(__file__).resolve().parents[2]


def _teks(rel: str) -> str:
    return (AKAR / rel).read_text(encoding="utf-8")


@pytest.fixture()
def klien(engine):
    return TestClient(buat_app(engine))


def test_angka_kunci_margin_performance_otomatis_tanpa_refresh():
    bersama = _teks("frontend/src/bersama.tsx")
    assert "otomatis?: boolean" in bersama
    assert "konteks.otomatis" in bersama
    assert '!otomatis && letakRefresh === "header"' in bersama
    assert 't("Data dimuat otomatis")' in bersama
    assert '"Data dimuat otomatis": "Loaded automatically"' in _teks(
        "frontend/src/i18n.tsx")

    ringkasan = _teks("frontend/src/pages/Ringkasan.tsx")
    awal = ringkasan.index('<KartuMuatSaatDiminta\n        otomatis')
    akhir = ringkasan.index("<KartuMuatSaatDiminta", awal + 10)
    blok = ringkasan[awal:akhir]
    assert 'judul="Angka kunci Margin Performance"' in blok
    assert "ringkasOtomatis.data" in blok
    assert "setelahDiminta" not in blok
    assert "kunciRefreshTambahan" not in blok
    assert "TombolRefreshKartu" not in blok
    assert 'queryKey: ["ringkasan-angka-kunci", thn]' in ringkasan
    assert "enabled: thn !== null" in ringkasan
    # Kartu "OP Margin bulanan" dan kawan-kawan tetap on-demand.
    assert "enabled: ringkasanDiminta && thn !== null" in ringkasan
    assert ringkasan.count('letakRefresh="filter"') == 3


def test_panel_analisa_memakai_query_biasa_bukan_use_query_kartu():
    ringkasan = _teks("frontend/src/pages/Ringkasan.tsx")
    for kunci in ("rca-rm-stock-intake-pricing", "margin-bridge",
                  "days-of-cover"):
        assert f'useQuery({{ queryKey: ["{kunci}", url]' in ringkasan
        assert f'useQueryKartu({{ queryKey: ["{kunci}", url]' not in ringkasan
    # 5W1H tidak boleh menggabungkan dua query string.
    assert "url={`/api/ringkasan-elemen/analisa${qsPeriode}`}" in ringkasan
    assert "url={urlAnalisa + qsPeriode}" not in ringkasan
    assert "useQueryKartu" in ringkasan  # kartu grafik tetap on-demand

    analisis = _teks("frontend/src/pages/Analisis.tsx")
    assert 'import { useQuery } from "@tanstack/react-query";' in analisis
    assert 'const q = useQuery({\n    queryKey: ["tren-penerimaan", url]' in analisis
    assert 'const q = useQuery({\n    queryKey: ["komposisi-penerimaan", url]' in analisis
    assert 'useQueryKartu({\n    queryKey: ["tren-penerimaan", url]' not in analisis
    assert 'useQueryKartu({\n    queryKey: ["komposisi-penerimaan", url]' not in analisis
    assert "useQueryKartu" in analisis  # kartu utama tetap on-demand

    bersama = _teks("frontend/src/bersama.tsx")
    assert "export function Panel5W1H" in bersama
    assert 'const q = useQuery({ queryKey: ["analisa-5w1h", url]' in bersama


def test_endpoint_analisa_menjawab_200(klien):
    """Backend bukan penyebab panel kosong; semua endpoint analisa tersedia."""
    for url in (
        "/api/ringkasan-elemen/analisa",
        "/api/ringkasan-elemen/rca",
        "/api/margin-bridge",
        "/api/days-of-cover",
        "/api/kartu/penerimaan/tren",
        "/api/kartu/penerimaan/komposisi?dimensi=provinsi",
        "/api/analisis/analisa",
        "/api/ringkasan/2026",
    ):
        r = klien.get(url)
        assert r.status_code == 200, f"{url}: {r.status_code} {r.text[:200]}"
