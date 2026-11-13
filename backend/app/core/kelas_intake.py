"""Kelas supplier berbasis Dry (MT) per supplier per bulan.

Batas yang diminta pemilik (tanda ≥ berlaku di setiap batas):

    SS  >= 1.500 MT
    S   >= 1.000 MT
    A   >=   500 MT
    B   >=   250 MT
    C   >=   100 MT
    D   <    100 MT

Satuan dasar tiket adalah `dry_kg`; pembagian 1.000 dilakukan sekali sebelum
membandingkan. Klasifikasi memakai nilai **tanpa pembulatan** agar 1.499,9996
MT tidak naik kelas hanya karena dibulatkan menjadi 1.500,000 MT di layar.

Ini berbeda dengan `klasifikasi_vendor.py` (Small holder / Small estate /
Rubber trader) dan `sourcing_type.py` (Direct/Indirect Smallholder, Own
Plantation): kelas di sini murni dihitung dari volume intake bulanan, tidak
disimpan dan tidak bisa diisi manual.
"""
from __future__ import annotations

#: (batas bawah Dry MT, kode kelas), urut dari yang terbesar
BATAS_KELAS: list[tuple[float, str]] = [
    (1500.0, "SS"),
    (1000.0, "S"),
    (500.0, "A"),
    (250.0, "B"),
    (100.0, "C"),
]

#: terbaik -> terendah; dipakai untuk "kelas tertinggi dalam periode"
KELAS_URUTAN: list[str] = ["SS", "S", "A", "B", "C", "D"]


def kelas(dry_mt) -> str:
    """Dry (MT) -> kode kelas. Nilai negatif/kosong masuk D."""
    nilai = float(dry_mt or 0)
    for batas, kode in BATAS_KELAS:
        if nilai >= batas:
            return kode
    return "D"


def kelas_tertinggi(daftar_kelas) -> str | None:
    """Kelas terbaik dari kumpulan kelas bulanan (None bila kosong)."""
    ada = [k for k in daftar_kelas if k in KELAS_URUTAN]
    if not ada:
        return None
    return min(ada, key=KELAS_URUTAN.index)


def batas_untuk_layar() -> list[dict]:
    """Legenda batas untuk UI: [{kelas, batas_mt, label}]."""
    # Ribuan memakai titik sesuai penulisan pemilik ("≥ 1.500 MT");
    # UI tetap memformat ulang dari `batas_mt` mengikuti bahasa aktif.
    hasil = [{"kelas": kode, "batas_mt": batas,
              "label": f"≥ {batas:,.0f} MT".replace(",", ".")}
             for batas, kode in BATAS_KELAS]
    hasil.append({"kelas": "D", "batas_mt": None, "label": "< 100 MT"})
    return hasil


def distribusi(daftar_kelas) -> list[dict]:
    """Hitung jumlah supplier-bulan per kelas, urut SS -> D."""
    from collections import Counter
    hitung = Counter(daftar_kelas)
    return [{"kelas": k, "jumlah": int(hitung.get(k, 0))}
            for k in KELAS_URUTAN]
