"""Utilitas kecil: menyiapkan backend/.env untuk pemakaian di komputer sendiri.

Login Cloudflare Access sudah DIHAPUS: satu-satunya cara masuk adalah
username + sandi. Fungsi di sini memastikan `.env` siap untuk itu:

- AUTH_MODE=lokal (bila masih ada sisa setelan lama),
- AUTH_DISABLED dibuang (kalau ada, login mati),
- SECRET_KEY acak minimal 32 karakter,
- sisa setelan CF_ACCESS_* dibuang agar tidak mengganggu.

Dipakai oleh:
  python -m app.cli atur-login-lokal      (manual)
  start-web.bat                            (otomatis, saat .env belum ada)
"""
from __future__ import annotations

import pathlib
import secrets

JALUR_ENV_BAKU = pathlib.Path(__file__).resolve().parents[1] / ".env"
CONTOH_ENV = pathlib.Path(__file__).resolve().parents[1] / ".env.example"
PANJANG_SECRET_MINIMAL = 32


def _nilai(baris: list[str], kunci: str) -> str | None:
    for b in baris:
        if b.strip().startswith("#"):
            continue
        if "=" in b and b.split("=", 1)[0].strip() == kunci:
            return b.split("=", 1)[1].strip()
    return None


def _setel(baris: list[str], kunci: str, nilai: str,
           diubah: dict[str, str]) -> None:
    for i, b in enumerate(baris):
        if b.strip().startswith("#"):
            continue
        if "=" in b and b.split("=", 1)[0].strip() == kunci:
            lama = b.split("=", 1)[1].strip()
            if lama != nilai:
                diubah[kunci] = nilai
            baris[i] = f"{kunci}={nilai}"
            return
    baris.append(f"{kunci}={nilai}")
    diubah[kunci] = nilai


def _hapus(baris: list[str], kunci: str, diubah: dict[str, str]) -> None:
    """Buang baris aktif (bukan komentar) untuk kunci tertentu."""
    sisa = []
    for b in baris:
        aktif = not b.strip().startswith("#")
        if aktif and "=" in b and b.split("=", 1)[0].strip() == kunci:
            diubah[kunci] = "(dihapus)"
            continue
        sisa.append(b)
    baris[:] = sisa


def atur_login_lokal(jalur: pathlib.Path | None = None) -> dict:
    """Pastikan `.env` memakai login lokal dan punya SECRET_KEY yang layak.

    Tidak menimpa APP_ENV yang sudah ada (produksi tetap produksi), tidak
    menghapus setelan lain (DATABASE_URL, FRONTEND_ORIGIN, dst).

    Mengembalikan ringkasan: {"jalur", "dibuat", "diubah"}.
    """
    jalur = pathlib.Path(jalur) if jalur is not None else JALUR_ENV_BAKU
    dibuat = not jalur.exists()
    if dibuat and CONTOH_ENV.exists():
        isi = CONTOH_ENV.read_text(encoding="utf-8")
    elif dibuat:
        isi = ""
    else:
        isi = jalur.read_text(encoding="utf-8")

    baris = isi.splitlines()
    diubah: dict[str, str] = {}

    # Sisa setelan Cloudflare Access tidak dipakai lagi -> dibuang.
    for sisa in ("AUTH_MODE", "CF_ACCESS_TEAM_DOMAIN", "CF_ACCESS_AUD",
                 "CF_ACCESS_CERTS_URL"):
        if _nilai(baris, sisa) is not None:
            _hapus(baris, sisa, diubah)

    if _nilai(baris, "APP_ENV") is None:
        _setel(baris, "APP_ENV", "development", diubah)
    # AUTH_DISABLED=true mematikan login lokal, jadi tidak boleh ada.
    _hapus(baris, "AUTH_DISABLED", diubah)

    secret = _nilai(baris, "SECRET_KEY") or ""
    if len(secret) < PANJANG_SECRET_MINIMAL or secret.startswith("ganti-dengan"):
        _setel(baris, "SECRET_KEY", secrets.token_hex(32), diubah)

    jalur.parent.mkdir(parents=True, exist_ok=True)
    jalur.write_text("\n".join(baris).rstrip("\n") + "\n", encoding="utf-8")
    return {"jalur": str(jalur), "dibuat": dibuat, "diubah": diubah}
