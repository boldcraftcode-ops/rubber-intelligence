"""Tes skrip pemasangan tanpa internet (v0.9.9).

Dua berkas yang dijaga:
  - ``ambil-bahan-offline.bat`` dijalankan di PC berinternet: mengunduh
    wheel Python + membangun ``frontend/dist`` ke folder ``bahan-offline``.
  - ``start-offline.bat`` dijalankan di PC tanpa internet: memasang dari
    wheelhouse lokal lalu menyajikan API + web satu alamat.

Aturan proyek untuk berkas .bat (docs/SERAH_TERIMA.md bagian 7):
ASCII saja, akhir baris CRLF, tanpa blok "( ... )" berlapis, tanpa "for /f".
Tes ini menjaga aturan itu sekaligus isi pentingnya, supaya skrip tidak
diam-diam rusak saat ada perubahan lain.
"""
from __future__ import annotations

import pathlib
import re

import pytest

AKAR = pathlib.Path(__file__).resolve().parents[2]
AMBIL = AKAR / "ambil-bahan-offline.bat"
JALAN = AKAR / "start-offline.bat"

SEMUA = [AMBIL, JALAN]


def _teks(berkas: pathlib.Path) -> str:
    return berkas.read_bytes().decode("ascii")


@pytest.mark.parametrize("berkas", SEMUA)
def test_berkas_ada(berkas):
    assert berkas.is_file(), f"{berkas.name} hilang"


@pytest.mark.parametrize("berkas", SEMUA)
def test_ascii_dan_crlf(berkas):
    isi = berkas.read_bytes()
    assert all(b < 128 for b in isi), f"{berkas.name} memuat karakter non-ASCII"
    assert isi.count(b"\r\n") == isi.count(b"\n"), f"{berkas.name} tidak CRLF"
    assert b"\n" not in isi.replace(b"\r\n", b""), "ada LF tanpa CR"


@pytest.mark.parametrize("berkas", SEMUA)
def test_tanpa_for_f_dan_blok_berlapis(berkas):
    """Komentar (rem) boleh menyebut aturannya; perintahnya tidak boleh memakai."""
    teks = _teks(berkas)
    for nomor, baris in enumerate(teks.splitlines(), start=1):
        inti = baris.strip().lower()
        if not inti or inti.startswith("rem"):
            continue
        assert "for /f" not in inti, f"{berkas.name}:{nomor} memakai for /f"
        assert inti != "(", f"{berkas.name}:{nomor} membuka blok bersyarat"
    assert "%~dp0" in teks  # selalu bekerja dari folder skrip


@pytest.mark.parametrize("berkas", SEMUA)
def test_label_goto_call_lengkap(berkas):
    teks = _teks(berkas)
    label = set(re.findall(r"(?m)^:([A-Za-z0-9_]+)[ \t]*\r?$", teks))
    lompat = set(re.findall(r"(?i)\bgoto\s+:([A-Za-z0-9_]+)", teks))
    panggil = set(re.findall(r"(?i)\bcall\s+:([A-Za-z0-9_]+)", teks))
    assert label, "tidak ada label sama sekali"
    assert (lompat | panggil) <= label | {"eof"}, (
        f"label tidak ditemukan: {(lompat | panggil) - label - {'eof'}}")


@pytest.mark.parametrize("berkas", SEMUA)
def test_kutip_seimbang_per_baris(berkas):
    for nomor, baris in enumerate(_teks(berkas).splitlines(), start=1):
        assert baris.count('"') % 2 == 0, f"{berkas.name}:{nomor} kutip ganjil"


def test_ambil_mengunduh_wheel_dan_membangun_dist():
    teks = _teks(AMBIL)
    for potongan in ("pip download", "--only-binary=:all:", "win_amd64",
                     "--python-version", "wheelhouse", "--requirement"):
        assert potongan in teks, f"ambil-bahan-offline.bat tidak memuat {potongan}"
    for potongan in ("npm install", "npm run build", "bahan-offline\\dist",
                     "BACA-SAYA.txt", "xcopy"):
        assert potongan in teks, f"ambil-bahan-offline.bat tidak memuat {potongan}"
    # boleh memaksa versi Python lewat argumen pertama
    assert 'set "PYVER=%~1"' in teks
    assert "ensurepip" in teks  # pip belum ada -> disiapkan, bukan gagal


def test_start_memasang_tanpa_internet():
    teks = _teks(JALAN)
    for potongan in ("--no-index", "--find-links", "bahan-offline\\wheelhouse",
                     "-r requirements.txt", "atur-login-lokal", "init-db",
                     "import-template", "--port 8000"):
        assert potongan in teks, f"start-offline.bat tidak memuat {potongan}"


def test_ambil_mencatat_versi_python_target():
    teks = _teks(AMBIL)
    assert 'python-version.txt' in teks
    assert '> "%BAHAN%\\python-version.txt" echo %PYVER%' in teks


def test_start_memilih_minor_python_tepat_dan_membuat_ulang_venv_mismatch():
    teks = _teks(JALAN)
    assert 'set "PYVER=3.11"' in teks
    assert 'set "PY=py -%PYVER%"' in teks
    assert 'sys.version_info[0]' in teks and 'sys.version_info[1]' in teks
    assert 'struct.calcsize' in teks  # menolak Python 32-bit
    assert 'rmdir /s /q "%~dp0backend\\.venv"' in teks
    assert 'python-version.txt' in teks


def test_start_menyajikan_satu_alamat_tanpa_node():
    teks = _teks(JALAN)
    assert 'set "SAJIKAN_WEB=true"' in teks
    assert "SAJIKAN_WEB_FOLDER" in teks
    assert "http://localhost:8000" in teks
    # tanpa Node/Vite di PC tujuan: tidak ada perintah npm maupun port 5173
    # (kata "Node.js" boleh muncul di komentar penjelasan).
    for nomor, baris in enumerate(teks.splitlines(), start=1):
        inti = baris.strip()
        if not inti or inti.lower().startswith("rem"):
            continue
        assert "npm" not in inti.lower(), f"baris {nomor}: masih memakai npm"
        assert "5173" not in inti, f"baris {nomor}: masih memakai port 5173"


def test_start_menutup_proses_lama_dan_menunggu_api():
    teks = _teks(JALAN)
    assert "call :bersihkan_port 8000" in teks
    assert "call :hentikan_service" in teks
    assert ":ambil_health" in teks
    assert "findstr" in teks  # memastikan versi yang menjawab memang kode ini


def test_penanda_lan_dan_tanpa_login_didukung():
    teks = _teks(JALAN)
    assert "jaringan-lan.txt" in teks
    assert "0.0.0.0" in teks
    assert "tanpa-login.txt" in teks


def test_kedua_skrip_memakai_folder_bahan_yang_sama():
    assert "bahan-offline\\wheelhouse" in _teks(AMBIL)
    assert "bahan-offline\\wheelhouse" in _teks(JALAN)
    assert "bahan-offline\\dist" in _teks(AMBIL)
    assert "bahan-offline\\dist" in _teks(JALAN)


@pytest.mark.parametrize("berkas", SEMUA)
def test_versi_dibaca_dari_versi_txt(berkas):
    assert "VERSI.txt" in _teks(berkas)


def test_dokumentasi_menyebut_kedua_skrip():
    cara = (AKAR / "docs" / "CARA_MENJALANKAN.md").read_text(encoding="utf-8")
    serah = (AKAR / "docs" / "SERAH_TERIMA.md").read_text(encoding="utf-8")
    for nama in ("ambil-bahan-offline.bat", "start-offline.bat"):
        assert nama in cara, f"{nama} belum dijelaskan di CARA_MENJALANKAN.md"
        assert nama in serah, f"{nama} belum dijelaskan di SERAH_TERIMA.md"
