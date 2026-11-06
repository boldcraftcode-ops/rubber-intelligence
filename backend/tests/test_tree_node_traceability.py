"""Tab Tree node view pada modul Traceability.

Tes sumber ini menjaga struktur diagram yang diminta pemilik: satu pabrik,
4 vendor T1, 10 kolektor T2, K5 menyuplai dua vendor, serta interaksi klik T1.
Tidak ada endpoint/table backend baru; diagram murni komponen React.
"""
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
SUMBER = (AKAR / "frontend/src/pages/Traceability.tsx").read_text(encoding="utf-8")


def test_tab_ketiga_ada_di_sebelah_supplier_actors():
    assert 'useState<"regions" | "actors" | "pohon">' in SUMBER
    assert 'onClick={() => setTab("actors")}' in SUMBER
    assert 'onClick={() => setTab("pohon")}' in SUMBER
    assert '>Tree node view</button>' in SUMBER
    assert '<PohonRantaiPasok />' in SUMBER
    assert 'tab === "actors" ? (' in SUMBER


def test_struktur_pabrik_t1_t2():
    assert 'const ID_T1 = ["V1", "V2", "V3", "V4"];' in SUMBER
    assert 'const ID_T2 = ["K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8", "K9", "K10"];' in SUMBER
    assert 'V1: ["K1", "K2", "K3", "K4"]' in SUMBER
    assert 'V2: ["K5"]' in SUMBER
    assert 'V3: ["K6", "K7", "K5"]' in SUMBER
    assert 'V4: ["K8", "K9", "K10"]' in SUMBER
    # K5 = satu kolektor, dua vendor: dua sambungan masuk ke node yang sama.
    assert SUMBER.count('ke: "K5"') == 2
    assert 'volume node K5' in SUMBER
    assert 'tidak dihitung' in SUMBER


def test_tampilan_sesuai_permintaan():
    assert 'pabrik: "#14532D"' in SUMBER
    assert 't1: "#175CD3"' in SUMBER
    assert 't2: "#F79009"' in SUMBER
    assert 'function jalurLengkung' in SUMBER
    assert 'C ${a.x}' in SUMBER or 'C ${a.x + dx' in SUMBER
    assert 'strokeWidth={lebarGaris(s.volumeKg)}' in SUMBER
    assert 'function lebarGaris' in SUMBER
    assert '<circle cx={p.x} cy={p.y} r={radius}' in SUMBER
    assert '{fmtAngka(s.volumeKg, 0)} kg' in SUMBER
    assert 'fontFamily="Arial, Helvetica, sans-serif"' in SUMBER
    assert 'bg-white' in SUMBER


def test_arah_dan_interaksi_klik_t1():
    assert 'useState<ArahPohon>("vertikal")' in SUMBER
    assert 'setArah("horizontal")' in SUMBER
    assert 'setArah("vertikal")' in SUMBER
    assert 'const pilihT1' in SUMBER
    assert 'onClick={bolehKlik ? () => pilihT1(s.id) : undefined}' in SUMBER
    assert 'const t2Sorot' in SUMBER
    assert 'const sambunganSorot' in SUMBER
    assert 'Klik node T1 untuk menyorot semua T2 di bawahnya' in SUMBER
