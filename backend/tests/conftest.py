"""Fixture bersama: database SQLite berisi data awal dari template.

Impor template hanya dilakukan sekali per sesi tes (lumayan lambat),
lalu dipakai bersama oleh semua tes baca-saja.
"""
from __future__ import annotations

import os
import pathlib

# Tes selalu berjalan mode development TANPA login, apa pun isi .env lokal.
# (load_dotenv tidak menimpa variabel yang sudah ada, jadi ini aman.)
os.environ["APP_ENV"] = "development"
os.environ["AUTH_DISABLED"] = "true"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.importer.template import impor_template
from app.models import Base

TEMPLATE = pathlib.Path(__file__).resolve().parents[2] / "sample_data" / \
    "Template_dan_Data_Awal_OP_Margin_v3.xlsx"


@pytest.fixture(scope="session")
def engine(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "tes.db"
    eng = create_engine(f"sqlite:///{db}", future=True)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, future=True)
    with Session() as session:
        impor_template(str(TEMPLATE), session, pengunggah="pytest")
    return eng


@pytest.fixture()
def session(engine):
    Session = sessionmaker(bind=engine, future=True)
    with Session() as s:
        yield s
