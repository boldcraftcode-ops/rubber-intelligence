"""Tes tindak lanjut alarm (v0.9.6).

Permintaan pemilik: alarm tidak boleh hanya berbunyi — tiap alarm harus
menunjukkan **ke halaman mana** dan **langkah apa** untuk membereskannya.

Yang dijaga di sini:
- setiap kode alarm yang dikenal punya `halaman` + minimal 2 langkah;
- `halaman` hanya berisi id menu yang benar-benar ada di tampilan web
  (kalau salah, tombol di layar tidak berbuat apa-apa);
- alarm selisih rekonsiliasi membedakan dua kasus: selisih periode yang
  menunggu persetujuan vs temuan harian;
- kode yang belum punya panduan tetap diberi arah aman (tidak 500/None);
- endpoint /api/alarm ikut mengirim `kategori` dan `tindakan`.
"""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.core.tindakan_alarm import HALAMAN_DIKENAL, URUTAN_KATEGORI, tindakan_untuk
from app.main import buat_app

KODE_DIKENAL = [
    "STOK_DI_BAWAH_SAFETY",
    "MARGIN_DI_BAWAH_TARGET",
    "SICOM_TERLAMBAT",
    "KURS_TERLAMBAT",
    "STOK_TERLAMBAT",
    "TIKET_TERLAMBAT",
    "SELISIH_REKONSILIASI",
    "HARGA_DI_ATAS_MAKS",
]


@pytest.fixture(scope="module")
def klien(engine):
    return TestClient(buat_app(engine))


@pytest.mark.parametrize("kode", KODE_DIKENAL)
def test_setiap_alarm_punya_halaman_dan_langkah(kode):
    t = tindakan_untuk(kode, dt.date(2026, 9, 8))
    assert t["halaman"] in HALAMAN_DIKENAL
    assert t["halaman_label"]
    assert t["judul"]
    assert len(t["langkah"]) >= 2
    assert all(len(l) > 20 for l in t["langkah"]), "langkah harus konkret, bukan 1-2 kata"
    assert t["kategori"] in URUTAN_KATEGORI


def test_halaman_sesuai_masalahnya():
    """Arah tombol harus masuk akal: data terlambat -> isi/unggah, bukan laporan."""
    assert tindakan_untuk("SICOM_TERLAMBAT")["halaman"] == "input"
    assert tindakan_untuk("KURS_TERLAMBAT")["halaman"] == "input"
    assert tindakan_untuk("STOK_TERLAMBAT")["halaman"] == "unggah"
    assert tindakan_untuk("TIKET_TERLAMBAT")["halaman"] == "unggah"
    assert tindakan_untuk("STOK_DI_BAWAH_SAFETY")["halaman"] == "stok"
    assert tindakan_untuk("SELISIH_REKONSILIASI")["halaman"] == "rekonsiliasi"
    assert tindakan_untuk("HARGA_DI_ATAS_MAKS")["halaman"] == "aturan"
    assert tindakan_untuk("MARGIN_DI_BAWAH_TARGET")["halaman"] == "ringkasan"


def test_selisih_periode_beda_dari_selisih_harian():
    periode = tindakan_untuk("SELISIH_REKONSILIASI", dt.date(2026, 7, 1))
    harian = tindakan_untuk("SELISIH_REKONSILIASI", None)
    assert periode["judul"] != harian["judul"]
    assert any("persetujuan" in l or "keputusan" in l for l in periode["langkah"])
    assert any("tanggal" in l.lower() for l in harian["langkah"])


def test_alarm_tanggal_masuk_ke_langkah():
    t = tindakan_untuk("STOK_DI_BAWAH_SAFETY", dt.date(2026, 9, 8))
    assert any("08/09/2026" in l for l in t["langkah"])


def test_kode_tak_dikenal_tetap_aman():
    t = tindakan_untuk("ALARM_BARU_YANG_BELUM_ADA")
    assert t["halaman"] in HALAMAN_DIKENAL
    assert t["langkah"]


def test_health_menyebut_fitur_alarm_tindakan(klien):
    fitur = klien.get("/api/health").json()["fitur"]
    assert "alarm-tindakan" in fitur
    assert "stok-margin-panduan" in fitur


def test_endpoint_alarm_mengirim_tindakan(klien):
    d = klien.get("/api/alarm").json()
    assert d["alarm"], "data contoh harus memunculkan minimal satu alarm"
    for a in d["alarm"]:
        assert a["kategori"] in URUTAN_KATEGORI
        t = a["tindakan"]
        assert t["kategori"] == a["kategori"]
        assert t["halaman"] in HALAMAN_DIKENAL
        assert t["langkah"]
