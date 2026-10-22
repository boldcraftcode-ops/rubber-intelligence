"""API modul Database: info isi, kosongkan, ekspor, dan impor database.

- Hanya untuk admin/pemelihara data; semua aksi tercatat di audit log.
- Ekspor/impor bekerja pada berkas SQLite (default). Bila DATABASE_URL
  menunjuk ke PostgreSQL, gunakan alat backup bawaan server tersebut.
- Impor & kosongkan selalu membuat cadangan otomatis dulu di folder
  `cadangan/` sehingga langkah keliru bisa dipulihkan.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import sqlite3
import tempfile

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .auth_lokal import wajib_admin
from .core.alarm import catat_audit, evaluasi_alarm
from .mart import bangun_mart
from .models import Base

KATA_KONFIRMASI = "KOSONGKAN"
_SQLITE_MAGIC = b"SQLite format 3\x00"

# Tabel yang minimal harus ada agar file .db dianggap database OP Margin
_TABEL_WAJIB = {"raw_unggahan", "raw_baris"}


class KosongkanMasuk(BaseModel):
    konfirmasi: str
    pengisi: str = "?"


def _path_sqlite(engine: Engine) -> str | None:
    """Path file .db bila memakai SQLite; None untuk database lain."""
    if engine.url.get_backend_name() != "sqlite":
        return None
    path = engine.url.database
    if not path or path == ":memory:":
        return None
    return os.path.abspath(path)


def _folder_cadangan() -> pathlib.Path:
    folder = pathlib.Path(os.environ.get("CADANGAN_DIR", "cadangan"))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _buat_cadangan(path_db: str, alasan: str) -> str:
    """Salin database saat ini ke folder cadangan (pakai API backup SQLite
    supaya aman walau database sedang dipakai)."""
    stempel = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    tujuan = _folder_cadangan() / f"{stempel}_{alasan}_opmargin.db"
    sumber = sqlite3.connect(path_db)
    try:
        target = sqlite3.connect(str(tujuan))
        try:
            sumber.backup(target)
        finally:
            target.close()
    finally:
        sumber.close()
    return str(tujuan)


def pasang_router_database(app, ambil_session, engine: Engine):
    router = APIRouter(prefix="/api/database")
    dep = Depends(ambil_session)
    SessionBaru = sessionmaker(bind=engine, future=True, expire_on_commit=False)

    # ------------------------------------------------------------ info isi
    @router.get("/info")
    def info(session: Session = dep):
        jumlah: dict[str, int] = {}
        for tabel in Base.metadata.sorted_tables:
            jumlah[tabel.name] = session.scalar(
                select(func.count()).select_from(tabel)) or 0
        path = _path_sqlite(engine)
        ukuran = (os.path.getsize(path)
                  if path and os.path.exists(path) else None)
        return {
            "jenis": engine.url.get_backend_name(),
            "sqlite": path is not None,
            "ukuran_kb": round(ukuran / 1024, 1) if ukuran is not None else None,
            "jumlah": jumlah,
            "total_baris": sum(jumlah.values()),
            "kosong": sum(jumlah.values()) == 0,
        }

    # ------------------------------------------------------------ kosongkan
    @router.post("/kosongkan")
    def kosongkan(data: KosongkanMasuk, request: Request, session: Session = dep):
        wajib_admin(request)  # hanya admin (saat login lokal aktif)
        if data.konfirmasi.strip().upper() != KATA_KONFIRMASI:
            raise HTTPException(422, "Konfirmasi tidak cocok. Ketik kata "
                                     f"'{KATA_KONFIRMASI}' persis untuk melanjutkan.")
        # Cadangan otomatis dulu (bila SQLite) supaya bisa dipulihkan.
        path = _path_sqlite(engine)
        file_cadangan = _buat_cadangan(path, "sebelum-kosongkan") if path else None

        total = 0
        for tabel in reversed(Base.metadata.sorted_tables):
            hasil = session.execute(delete(tabel))
            total += hasil.rowcount or 0
        # Catat jejak SETELAH pengosongan supaya catatannya ikut tersimpan.
        catat_audit(session, data.pengisi, "hapus", "database", {
            "aksi": "kosongkan semua tabel",
            "baris_terhapus": total,
            "cadangan": file_cadangan,
        })
        session.commit()
        return {"status": "selesai", "baris_terhapus": total,
                "cadangan": file_cadangan,
                "pesan": ("Semua data dihapus. " +
                          (f"Cadangan otomatis tersimpan di {file_cadangan}. "
                           if file_cadangan else "") +
                          "Mulai isi ulang lewat tab Unggah Data / Input Harian.")}

    # ------------------------------------------------------------ ekspor
    @router.get("/ekspor")
    def ekspor():
        path = _path_sqlite(engine)
        if path is None or not os.path.exists(path):
            raise HTTPException(422, "Ekspor file hanya tersedia untuk database "
                                     "SQLite. Untuk PostgreSQL gunakan pg_dump.")
        # Salin dengan API backup agar konsisten walau sedang dipakai.
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        sumber = sqlite3.connect(path)
        try:
            target = sqlite3.connect(tmp)
            try:
                sumber.backup(target)
            finally:
                target.close()
        finally:
            sumber.close()
        nama = f"opmargin_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        from starlette.background import BackgroundTask
        return FileResponse(tmp, filename=nama,
                            media_type="application/octet-stream",
                            background=BackgroundTask(os.remove, tmp))

    # ------------------------------------------------------------ impor
    @router.post("/impor")
    async def impor(request: Request, file: UploadFile = File(...),
                    pengisi: str = Form("?")):
        wajib_admin(request)  # hanya admin (saat login lokal aktif)
        path = _path_sqlite(engine)
        if path is None:
            raise HTTPException(422, "Impor file hanya tersedia untuk database "
                                     "SQLite. Untuk PostgreSQL gunakan pg_restore.")
        isi = await file.read()
        if not isi.startswith(_SQLITE_MAGIC):
            raise HTTPException(422, f"File '{file.filename}' bukan database "
                                     "SQLite. Pilih file .db hasil Ekspor "
                                     "Database dari aplikasi ini.")
        # Tulis ke file sementara lalu periksa isinya dulu.
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            pathlib.Path(tmp).write_bytes(isi)
            try:
                con = sqlite3.connect(tmp)
                try:
                    tabel = {r[0] for r in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'")}
                finally:
                    con.close()
            except sqlite3.Error:
                raise HTTPException(422, "File database rusak / tidak bisa dibaca.")
            if not _TABEL_WAJIB <= tabel:
                hilang = ", ".join(sorted(_TABEL_WAJIB - tabel))
                raise HTTPException(422, "File ini bukan database OP Margin "
                                         f"(tabel {hilang} tidak ada). Pilih file "
                                         "hasil Ekspor Database dari aplikasi ini.")

            # Cadangkan database lama, tutup semua koneksi, lalu ganti filenya.
            file_cadangan = (_buat_cadangan(path, "sebelum-impor")
                             if os.path.exists(path) else None)
            engine.dispose()
            shutil.copyfile(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

        # Lengkapi tabel yang mungkin belum ada (file dari versi lama),
        # lalu hitung ulang mart & alarm dan catat jejaknya.
        Base.metadata.create_all(engine)
        with SessionBaru() as session:
            bangun_mart(session)
            evaluasi_alarm(session)
            catat_audit(session, pengisi, "impor", "database", {
                "nama_file": file.filename,
                "ukuran_kb": round(len(isi) / 1024, 1),
                "cadangan": file_cadangan,
            })
            session.commit()
            total = 0
            for t in Base.metadata.sorted_tables:
                total += session.scalar(select(func.count()).select_from(t)) or 0

        return {"status": "selesai", "total_baris": total,
                "cadangan": file_cadangan,
                "pesan": ("Database berhasil diganti dengan file yang diimpor; "
                          "mart & alarm sudah dihitung ulang. " +
                          (f"Database lama dicadangkan di {file_cadangan}."
                           if file_cadangan else ""))}

    app.include_router(router)
