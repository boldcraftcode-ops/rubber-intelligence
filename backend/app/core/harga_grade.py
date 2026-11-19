"""Aturan harga turunan untuk grade slab dan varian TTSR."""
from decimal import Decimal


def perluas_harga_slab(harga_input: dict[str, Decimal], kode_grade: set[str]) -> dict[str, Decimal]:
    """Kembangkan harga acuan SLAB ke grade rinci yang memang ada di master."""
    harga_input = {kode.strip().upper(): nilai for kode, nilai in harga_input.items()}
    hasil: dict[str, Decimal] = {}

    def pasang(kode: str, nilai: Decimal) -> None:
        if kode in kode_grade:
            hasil[kode] = nilai

    if "SLAB" in harga_input:
        slab1 = harga_input["SLAB"]
        slab2 = slab1 - Decimal("300")
        slab3 = slab2 - Decimal("2000")
        if slab2 < 0 or slab3 < 0:
            raise ValueError("Harga Slab terlalu rendah untuk pengurangan harga grade turunan.")
        for kode in ("SLAB", "SLAB1", "SLAB1 TTSR"):
            pasang(kode, slab1)
        for kode in ("SLAB2", "SLAB2 TTSR"):
            pasang(kode, slab2)
        for kode in ("SLAB3", "SLAB3 TTSR"):
            pasang(kode, slab3)
        return hasil

    if "SLAB1" in harga_input:
        for kode in ("SLAB1", "SLAB1 TTSR"):
            pasang(kode, harga_input["SLAB1"])
    if "SLAB2" in harga_input:
        slab3 = harga_input["SLAB2"] - Decimal("2000")
        if slab3 < 0:
            raise ValueError("Harga Slab 2 terlalu rendah untuk pengurangan harga Slab 3.")
        for kode in ("SLAB2", "SLAB2 TTSR"):
            pasang(kode, harga_input["SLAB2"])
        for kode in ("SLAB3", "SLAB3 TTSR"):
            pasang(kode, slab3)

    for kode, nilai in harga_input.items():
        if kode not in hasil and kode in kode_grade:
            hasil[kode] = nilai
    return hasil
