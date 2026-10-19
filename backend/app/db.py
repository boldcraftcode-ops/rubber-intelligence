"""Koneksi database.

Default memakai SQLite (file lokal). Untuk pindah ke PostgreSQL cukup
mengganti DATABASE_URL di file .env / variabel lingkungan, tanpa mengubah kode.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_URL = "sqlite:///opmargin.db"


def buat_engine(url: str | None = None) -> Engine:
    url = url or os.environ.get("DATABASE_URL", DEFAULT_URL)
    return create_engine(url, future=True)


def buat_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)
