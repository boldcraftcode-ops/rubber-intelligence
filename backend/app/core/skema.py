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
        ("is_direct_producer", "BOOLEAN NOT NULL DEFAULT false"),
    ],
    "traceability_wilayah": [
        ("provinsi_norm", "VARCHAR(120)"),
        ("provinsi", "VARCHAR(120)"),
    ],
    "pengguna": [
        ("foto_profil", "TEXT"),
    ],
    "tiket_baris": [
        ("kabupaten_norm", "VARCHAR(120)"),
        ("kecamatan_norm", "VARCHAR(120)"),
        ("desa_norm", "VARCHAR(120)"),
        ("asal_getah_valid", "BOOLEAN"),
        ("source_fingerprint", "VARCHAR(64)"),
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


def isi_kunci_traceability(engine: Engine) -> int:
    """Backfill kunci wilayah ternormalisasi untuk tiket yang sudah ada.

    Asal Getah menjadi sumber utama karena kolom pecahannya merupakan turunan.
    Baris dengan format asal tidak sah tetap dicatat dengan flag False agar
    tidak diam-diam masuk pembilang traceability.
    """
    from sqlalchemy import or_, select
    from sqlalchemy.orm import Session

    from ..core.traceability import (normalisasi_kabupaten,
                                     normalisasi_teks_wilayah, parse_asal_getah)
    from ..models import TiketBaris

    jumlah = 0
    with Session(engine) as session:
        q = select(TiketBaris).where(or_(
            TiketBaris.kabupaten_norm.is_(None),
            TiketBaris.kecamatan_norm.is_(None),
            TiketBaris.desa_norm.is_(None),
            TiketBaris.asal_getah_valid.is_(None),
        ))
        for row in session.scalars(q):
            bagian = parse_asal_getah(row.asal_getah)
            if bagian:
                _, kabupaten, kecamatan, desa = bagian
                row.asal_getah_valid = True
            else:
                kabupaten, kecamatan, desa = row.kabupaten, row.kecamatan, row.desa
                row.asal_getah_valid = False
            row.kabupaten_norm = normalisasi_kabupaten(kabupaten)
            row.kecamatan_norm = normalisasi_teks_wilayah(kecamatan)
            row.desa_norm = normalisasi_teks_wilayah(desa)
            jumlah += 1
        if jumlah:
            session.commit()
    return jumlah
