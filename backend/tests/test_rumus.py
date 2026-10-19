"""Kasus uji emas untuk rumus murni (tanpa database)."""
from decimal import Decimal

from app.core import rumus


def test_harian_3_jan_2026():
    """SICOM 181,7; qty 194.806 kg; Amount Rp 5.556.209.500; kurs 16.644
    -> harga 28.521,76 Rp/kg; 171,3636 US¢/kg; margin 10,3364."""
    harga_rp = rumus.harga_rp_per_kg(Decimal("5556209500"), Decimal("194806"))
    assert round(harga_rp, 2) == 28521.76
    harga_usc = rumus.rp_ke_usc(harga_rp, 16644)
    assert round(harga_usc, 4) == 171.3636
    assert round(rumus.margin_harian(181.7, harga_usc), 4) == 10.3364


def test_hari_tanpa_pembelian_nol():
    assert rumus.harga_rp_per_kg(0, 0) == 0.0
    assert rumus.rp_ke_usc(0, 16644) == 0.0


def test_days_31_jan_2023():
    """Stok 4.313,93 ton, kapasitas 275 -> Days 15,687."""
    ton = rumus.stok_ton(4313930)
    assert round(ton, 2) == 4313.93
    assert round(rumus.hitung_days(ton, 275), 3) == 15.687


def test_days_dan_rasio_31_agu_2026():
    """Stok 551,947 ton, kapasitas 186,34, safety 2.795,1
    -> Days 2,962; rasio 0,1975."""
    ton = rumus.stok_ton(551947)
    assert round(rumus.hitung_days(ton, 186.34), 3) == 2.962
    assert round(rumus.rasio_stok(ton, 2795.1), 4) == 0.1975


def test_safety_dari_hari():
    """Bila Safety_Stock_Ton kosong: safety = hari x kapasitas."""
    assert rumus.hitung_safety_ton(None, 15, 186.34) == 15 * 186.34
    assert rumus.hitung_safety_ton(2795.1, 15, 186.34) == 2795.1


def test_aturan_stok():
    aturan = [
        rumus.BarisAturan(0.0, 0.5, -2),
        rumus.BarisAturan(0.5, 0.8, -1),
        rumus.BarisAturan(0.8, 1.2, 0),
        rumus.BarisAturan(1.2, None, 1),
    ]
    assert rumus.cari_aturan(aturan, 0.1975).penyesuaian_usc == -2
    assert rumus.cari_aturan(aturan, 0.5).penyesuaian_usc == -1  # batas bawah <=
    assert rumus.cari_aturan(aturan, 0.8).penyesuaian_usc == 0
    assert rumus.cari_aturan(aturan, 5.0).penyesuaian_usc == 1
    assert rumus.cari_aturan([], 1.0) is None  # tabel kosong -> ATURAN BELUM DIISI


def test_harga_beli_maks():
    target_ef = rumus.target_efektif(10, -2)
    assert target_ef == 8
    maks_usc = rumus.harga_beli_maks_usc(181.7, target_ef)
    assert round(maks_usc, 4) == 173.7
    assert round(rumus.usc_ke_rp(maks_usc, 16644), 2) == round(173.7 * 16644 / 100, 2)


def test_rencana_jan_2027():
    """(16,3364 + 4,7719 + 15,0003 + 10,5725)/4 = 11,6703;
    - 2 = 9,6703; + 2,09 = 11,7603."""
    margin = [16.3364, 4.7719, 15.0003, 10.5725]
    dasar = rumus.rata_rata_sederhana(margin)
    assert round(dasar, 4) == 11.6703
    assert round(dasar + (-2), 4) == 9.6703
    assert round(rumus.rencana_net_margin(margin, -2, 2.09), 4) == 11.7603
