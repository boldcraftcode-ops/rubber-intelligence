"""Kasus uji emas memakai data awal dari template (lewat importer + mart)."""
import datetime as dt

import pytest
from sqlalchemy import func, select

from app.core.perencanaan import hitung_rencana
from app.core.rekomendasi import rekomendasi_harga
from app.importer.template import impor_template
from app.models import MartBulanan, MartHarian, Pembelian, RawBaris

from tests.conftest import TEMPLATE


def ambil_bulan(session, tahun, bulan) -> MartBulanan:
    m = session.scalar(select(MartBulanan).where(
        MartBulanan.tahun == tahun, MartBulanan.bulan == bulan))
    assert m is not None, f"mart_bulanan {bulan}/{tahun} tidak ada"
    return m


# Kasus emas bulanan: (tahun, bulan, sicom, harga_beli, op_margin, ton)
KASUS_BULANAN = [
    (2026, 1, 184.2498, 173.6773, 10.5725, 3885.166),
    (2026, 2, 193.1812, 178.5348, 14.6463, 4169.011),
    (2023, 1, 138.6176, 122.2813, 16.3364, 7894.320),
    # Mar 2020: kurs berubah di tengah bulan (14.234 / 15.055 / 16.342 / 16.263)
    (2020, 3, 123.3930, 116.3440, 7.0490, 6728.055),
    # Apr 2022: Excel lama salah ketik (menampilkan 5,5232); nilai benar 4,3391
    (2022, 4, 171.4991, 167.1599, 4.3391, 4551.324),
]


@pytest.mark.parametrize("tahun,bulan,sicom,harga,margin,ton", KASUS_BULANAN)
def test_bulanan_emas(session, tahun, bulan, sicom, harga, margin, ton):
    m = ambil_bulan(session, tahun, bulan)
    assert round(m.sicom_usc, 4) == sicom
    assert round(m.harga_beli_usc, 4) == harga
    assert round(m.op_margin_usc, 4) == margin
    assert round(m.qty_ton, 3) == ton


def test_harian_3_jan_2026(session):
    h = session.get(MartHarian, dt.date(2026, 1, 3))
    assert h is not None
    assert round(h.harga_rp_per_kg, 2) == 28521.76
    assert h.kurs == 16644
    assert round(h.harga_usc_per_kg, 4) == 171.3636
    assert round(h.margin_usc, 4) == 10.3364


def test_days_31_jan_2023(session):
    h = session.get(MartHarian, dt.date(2023, 1, 31))
    assert h is not None
    assert round(h.stok_ton, 2) == 4313.93
    assert h.kapasitas_ton == 275
    assert round(h.days, 3) == 15.687


def test_days_rasio_31_agu_2026(session):
    h = session.get(MartHarian, dt.date(2026, 8, 31))
    assert h is not None
    assert round(h.days, 3) == 2.962
    assert round(h.rasio_stok, 4) == 0.1975


def test_rencana_jan_2027(session):
    """Dasar dari mart (4 tahun terakhir): 11,6703; net 11,7603."""
    hasil = hitung_rencana(session, 2027)
    jan = hasil[0]
    assert jan.tahun_dipakai == [2023, 2024, 2025, 2026]
    assert round(jan.rata_rata_dasar, 4) == 11.6703
    assert jan.penyesuaian_manual == -2
    assert jan.effort == 2.09
    assert round(jan.net_margin, 4) == 11.7603


def test_rekomendasi_memberi_alasan(session):
    h = rekomendasi_harga(session, dt.date(2026, 8, 31))
    assert h.status == "OK"
    assert h.aturan_contoh  # aturan dari template masih CONTOH
    assert h.rasio_stok is not None and round(h.rasio_stok, 4) == 0.1975
    assert h.penyesuaian_usc == -2  # rasio < 0,5
    assert h.alasan  # alasan selalu ditampilkan
    assert h.harga_beli_maks_usc is not None
    assert h.harga_beli_maks_rp_kg == pytest.approx(
        h.harga_beli_maks_usc * h.kurs / 100)


def test_impor_idempoten(engine):
    """Unggah file yang sama dua kali tidak menggandakan data clean,
    tetapi raw tetap menyimpan salinan tiap unggahan."""
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine, future=True)
    with Session() as s:
        jumlah_sebelum = s.scalar(select(func.count()).select_from(Pembelian))
        raw_sebelum = s.scalar(select(func.count()).select_from(RawBaris))
        hasil = impor_template(str(TEMPLATE), s, pengunggah="pytest-2")
        assert hasil.duplikat_file
        jumlah_sesudah = s.scalar(select(func.count()).select_from(Pembelian))
        raw_sesudah = s.scalar(select(func.count()).select_from(RawBaris))
    assert jumlah_sebelum == jumlah_sesudah  # clean tidak berganda
    assert raw_sesudah > raw_sebelum  # raw selalu bertambah (jejak unggahan)
