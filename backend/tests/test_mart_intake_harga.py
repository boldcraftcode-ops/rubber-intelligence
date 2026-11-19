import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.mart import bangun_mart
from app.models import Base, HargaGrade, MartHarian, Pembelian, TiketBaris


@pytest.fixture()
def sesi_harga(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'harga-intake.db'}", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def tiket(ticket_no, date, grade, dry):
    return TiketBaris(ticket_no=ticket_no, line_seq=1, ticket_date=date,
                      kode_vendor="V1", item_code=grade, dry_kg=Decimal(dry))


def test_amount_pembelian_dari_intake_menggantikan_data_manual(sesi_harga):
    tanggal = dt.date(2026, 5, 10)
    sesi_harga.add_all([
        tiket("T1", tanggal, "SLAB1", "10.000"),
        tiket("T2", tanggal, "SLAB2", "5.000"),
        HargaGrade(tanggal=dt.date(2026, 5, 1), item_code="SLAB1",
                   harga_rp_per_kg=Decimal("20000")),
        HargaGrade(tanggal=dt.date(2026, 5, 1), item_code="SLAB2",
                   harga_rp_per_kg=Decimal("30000")),
        Pembelian(tanggal=tanggal, item_code="ALL", kode_vendor="", ticket_no="",
                  qty_kering_kg=Decimal("999"), amount_rp=Decimal("999999999")),
    ])
    sesi_harga.flush()

    bangun_mart(sesi_harga)
    hasil = sesi_harga.get(MartHarian, tanggal)
    assert hasil.qty_kering_kg == pytest.approx(15)
    assert float(hasil.amount_rp) == pytest.approx(350_000)
    assert hasil.harga_rp_per_kg == pytest.approx(350_000 / 15)
    baris_beli = list(sesi_harga.scalars(select(Pembelian).where(Pembelian.tanggal == tanggal)))
    assert {(b.item_code, float(b.qty_kering_kg), float(b.amount_rp)) for b in baris_beli} == {
        ("SLAB1", 10, 200_000), ("SLAB2", 5, 150_000)}


def test_sicom_rebuild_tidak_mengubah_baris_pembelian(sesi_harga):
    tanggal = dt.date(2026, 5, 10)
    lama = Pembelian(tanggal=tanggal, item_code="ALL", kode_vendor="", ticket_no="",
                     qty_kering_kg=Decimal("99"), amount_rp=Decimal("123456"))
    sesi_harga.add_all([
        tiket("T1", tanggal, "SLAB1", "10.000"),
        HargaGrade(tanggal=dt.date(2026, 5, 1), item_code="SLAB1",
                   harga_rp_per_kg=Decimal("20000")),
        lama,
    ])
    sesi_harga.flush()
    bangun_mart(sesi_harga, sinkronkan_pembelian=False)
    baris = list(sesi_harga.scalars(select(Pembelian).where(Pembelian.tanggal == tanggal)))
    assert len(baris) == 1
    assert baris[0].item_code == "ALL"
    assert float(baris[0].amount_rp) == pytest.approx(123456)


def test_harga_yang_sudah_kedaluwarsa_tidak_dipakai(sesi_harga):
    tanggal = dt.date(2026, 5, 10)
    sesi_harga.add_all([
        tiket("T1", tanggal, "SLAB1", "10.000"),
        HargaGrade(tanggal=dt.date(2026, 5, 1), berlaku_sampai=dt.date(2026, 5, 9),
                   item_code="SLAB1", harga_rp_per_kg=Decimal("20000")),
    ])
    sesi_harga.flush()
    bangun_mart(sesi_harga)
    hasil = sesi_harga.get(MartHarian, tanggal)
    assert hasil is not None and hasil.amount_rp is None


def test_tanggal_tanpa_harga_satu_grade_dikecualikan(sesi_harga):
    tanggal = dt.date(2026, 5, 10)
    sesi_harga.add_all([
        tiket("T1", tanggal, "SLAB1", "10.000"),
        tiket("T2", tanggal, "SLAB2", "5.000"),
        HargaGrade(tanggal=dt.date(2026, 5, 1), item_code="SLAB1",
                   harga_rp_per_kg=Decimal("20000")),
        Pembelian(tanggal=tanggal, item_code="ALL", kode_vendor="", ticket_no="",
                  qty_kering_kg=Decimal("15"), amount_rp=Decimal("500000")),
    ])
    sesi_harga.flush()

    bangun_mart(sesi_harga)
    hasil = sesi_harga.get(MartHarian, tanggal)
    assert hasil is not None
    assert hasil.qty_kering_kg is None
    assert hasil.amount_rp is None
    assert list(sesi_harga.scalars(select(Pembelian).where(Pembelian.tanggal == tanggal))) == []
