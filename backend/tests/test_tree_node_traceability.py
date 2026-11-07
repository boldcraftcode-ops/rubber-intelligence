"""Tab Tree node view pada modul Traceability.

Setelah koreksi pemilik, diagram **tidak lagi memakai contoh statis**.
Sumbernya endpoint data asli `/api/traceability/tree`; kode tier tetap
T1 = vendor dan T2 = kolektor.
"""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
SUMBER = (AKAR / "frontend/src/pages/Traceability.tsx").read_text(encoding="utf-8")


def test_tab_ketiga_dan_sumber_data_asli():
    assert 'useState<"regions" | "actors" | "pohon">' in SUMBER
    assert 'onClick={() => setTab("pohon")}' in SUMBER
    assert '>Tree node view</button>' in SUMBER
    assert '<PohonRantaiPasok query={query} aktif={tab === "pohon"} />' in SUMBER
    assert '/api/traceability/tree' in SUMBER
    assert 'traceability-tree' in SUMBER
    assert '<b>data asli</b>' in SUMBER
    assert 'data.sumber' in SUMBER


def test_contoh_statis_sudah_dihapus():
    assert 'const ID_T1 = ["V1", "V2", "V3", "V4"];' not in SUMBER
    assert 'const ID_T2 = ["K1", "K2", "K3", "K4", "K5"' not in SUMBER
    assert 'Ini diagram contoh statis' not in SUMBER
    assert 'volume node K5' not in SUMBER
    assert 'K5 juga menyuplai' not in SUMBER


def test_kode_tier_tidak_ditukar():
    assert 'type TierPohon = "PABRIK" | "T1" | "T2";' in SUMBER
    assert 'PABRIK: "#14532D"' in SUMBER
    assert 'T1: "#175CD3"' in SUMBER
    assert 'T2: "#F79009"' in SUMBER
    assert 'data.kode_tier[tier]' in SUMBER
    assert '<b>T1 = vendor</b>' in SUMBER
    assert '<b>T2 = kolektor</b>' in SUMBER
    assert 'T1 = vendor, T2 = kolektor' in SUMBER


def test_tampilan_dan_interaksi_tetap():
    assert 'function jalurLengkung' in SUMBER
    assert 'function lebarGaris' in SUMBER
    assert 'strokeWidth={lebarGaris(e.volume_kg, minVolume, maksVolume)}' in SUMBER
    assert '<circle cx={p.x} cy={p.y} r={radius}' in SUMBER
    assert '{fmtAngka(n.volume_kg, 0)} kg' in SUMBER
    assert 'fontFamily="Arial, Helvetica, sans-serif"' in SUMBER
    assert 'setArah("horizontal")' in SUMBER
    assert 'setArah("vertikal")' in SUMBER
    assert 'const t2Sorot' in SUMBER
    assert 'const sambunganSorot' in SUMBER
    assert 'Klik node <b>T1</b> untuk menyorot semua <b>T2</b>' in SUMBER
