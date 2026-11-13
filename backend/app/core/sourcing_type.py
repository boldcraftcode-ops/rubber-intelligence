"""Sourcing type Supplier Actors (diisi langsung dari form pada tabel).

Tiga pilihan yang diminta pemilik:

    Direct Smallholder  -> direct_smallholder
    Indirect Smallholder -> indirect_smallholder
    Own Plantation      -> own_plantation

Ini **berbeda** dengan `core/klasifikasi_vendor.py` (Small holder /
Small estate / Rubber trader) yang dipakai Master Vendor, impor Excel, dan
filter komposisi pemasok. Field ini disimpan terpisah pada `vendor.sourcing_type`
agar aturan lama tidak berubah. Kode disimpan stabil, label yang tampil di
layar; ejaan yang tidak dikenal ditolak, bukan disimpan diam-diam.
"""
from __future__ import annotations

#: kode -> label yang dilihat pengguna
SOURCING_TYPE: dict[str, str] = {
    "direct_smallholder": "Direct Smallholder",
    "indirect_smallholder": "Indirect Smallholder",
    "own_plantation": "Own Plantation",
}

PESAN_PILIHAN = "Direct Smallholder, Indirect Smallholder, atau Own Plantation"


def kunci(nilai) -> str:
    """Normalkan: huruf kecil, underscore/hyphen jadi spasi, spasi tunggal."""
    return " ".join(str(nilai or "").strip().lower()
                    .replace("_", " ").replace("-", " ").split())


#: teks ternormalisasi (kode maupun label) -> kode baku
KODE_DARI_TEKS: dict[str, str] = {
    kunci(nama): kode for kode, nama in SOURCING_TYPE.items()
}
KODE_DARI_TEKS.update({
    "direct small holder": "direct_smallholder",
    "indirect small holder": "indirect_smallholder",
    "own estate": "own_plantation",
    "kebun sendiri": "own_plantation",
})


def bakukan(nilai) -> str | None:
    """Teks bebas -> kode. Kosong -> None; tak dikenal -> ValueError."""
    teks = kunci(nilai)
    if not teks:
        return None
    kode = KODE_DARI_TEKS.get(teks)
    if not kode:
        raise ValueError(f"Sourcing type '{str(nilai).strip()}' tidak dikenal. "
                         f"Pilih salah satu: {PESAN_PILIHAN}.")
    return kode


def label(nilai) -> str | None:
    """Kode/label -> label tampilan (None bila kosong atau tak dikenal)."""
    kode = KODE_DARI_TEKS.get(kunci(nilai))
    return SOURCING_TYPE.get(kode) if kode else None


def daftar_untuk_layar() -> list[dict]:
    """Pilihan dropdown: [{kode, label}]."""
    return [{"kode": k, "label": v} for k, v in SOURCING_TYPE.items()]
