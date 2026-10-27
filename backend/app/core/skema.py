"""Penyesuaian skema ringan untuk database yang SUDAH ADA.

`Base.metadata.create_all()` hanya membuat tabel yang belum ada; tabel lama
tidak pernah ditambah kolomnya. Aplikasi ini dipakai di PC yang database-nya
sudah berisi data, jadi kolom baru (mis. alamat/kontak/klasifikasi vendor pada
v0.10.0) harus ditambahkan tanpa menghapus apa pun.

Cara kerjanya: periksa kolom yang benar-benar ada di database, lalu jalankan
`ALTER TABLE ... ADD COLUMN` hanya untuk kolom yang belum ada. Aman diulang
berkali-kali (idempoten) dan tidak pernah menghapus/mengubah data.

Catatan: karena ini bukan sistem migrasi penuh, perubahan yang mengubah tipe
atau menghapus kolom tetap harus dilakukan manual (lihat docs/CARA_MENJALANKAN.md).
"""
from __future__ import annotations

import sys

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

#: tabel -> daftar (nama kolom, tipe SQL). Tipe sengaja sederhana dan sama
#: untuk SQLite maupun PostgreSQL.
KOLOM_BARU: dict[str, list[tuple[str, str]]] = {
    "vendor": [
        ("alamat", "TEXT"),
        ("kontak_person", "VARCHAR(200)"),
        ("klasifikasi", "VARCHAR(30)"),
    ],
}


def kolom_hilang(engine: Engine) -> dict[str, list[tuple[str, str]]]:
    """Kolom yang ada di KOLOM_BARU tetapi belum ada di database."""
    pemeriksa = inspect(engine)
    tabel_ada = set(pemeriksa.get_table_names())
    hasil: dict[str, list[tuple[str, str]]] = {}
    for tabel, daftar in KOLOM_BARU.items():
        if tabel not in tabel_ada:
            continue  # tabel belum dibuat; create_all yang mengurus
        sudah = {k["name"] for k in pemeriksa.get_columns(tabel)}
        kurang = [(nama, tipe) for nama, tipe in daftar if nama not in sudah]
        if kurang:
            hasil[tabel] = kurang
    return hasil


def pastikan_kolom_baru(engine: Engine) -> list[str]:
    """Tambahkan kolom baru yang belum ada. Mengembalikan daftar tindakan."""
    tindakan: list[str] = []
    for tabel, daftar in kolom_hilang(engine).items():
        for nama, tipe in daftar:
            with engine.begin() as koneksi:
                koneksi.execute(text(
                    f'ALTER TABLE {tabel} ADD COLUMN {nama} {tipe}'))
            tindakan.append(f"{tabel}.{nama}")
    if tindakan:
        sys.stderr.write(
            "Skema disesuaikan (kolom baru ditambahkan): "
            + ", ".join(tindakan) + "\n")
    return tindakan
