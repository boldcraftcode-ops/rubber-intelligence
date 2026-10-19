"""Model database OP Margin.

Tiga lapisan:
- raw   : salinan apa adanya tiap unggahan (tidak pernah diubah/dihapus)
- clean : data tervalidasi (tiket_baris, pembelian, sicom, kurs, stok, dst.)
- mart  : tabel siap pakai (mart_harian, mart_bulanan), dibangun ulang tiap unggahan

Semua nilai Rupiah memakai Numeric (tepat), bukan float.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ----------------------------------------------------------------------------
# Lapisan RAW
# ----------------------------------------------------------------------------
class RawUnggahan(Base):
    """Catatan satu kali unggah file. Tidak pernah diubah atau dihapus."""

    __tablename__ = "raw_unggahan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nama_file: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    waktu: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    pengunggah: Mapped[str] = mapped_column(String(100), default="?")
    catatan: Mapped[str | None] = mapped_column(Text, nullable=True)


class RawBaris(Base):
    """Salinan apa adanya setiap baris dari file yang diunggah (JSON)."""

    __tablename__ = "raw_baris"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unggahan_id: Mapped[int] = mapped_column(ForeignKey("raw_unggahan.id"), index=True)
    sheet: Mapped[str] = mapped_column(String(100))
    baris_ke: Mapped[int] = mapped_column(Integer)  # nomor baris di file (1-based)
    isi: Mapped[str] = mapped_column(Text)  # JSON list nilai sel


# ----------------------------------------------------------------------------
# Lapisan CLEAN
# ----------------------------------------------------------------------------
class Vendor(Base):
    __tablename__ = "vendor"

    kode: Mapped[str] = mapped_column(String(20), primary_key=True)
    nama_baku: Mapped[str] = mapped_column(String(200))
    varian_nama: Mapped[str | None] = mapped_column(Text, nullable=True)  # dipisah |
    kategori: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)


class Grade(Base):
    __tablename__ = "grade"

    item_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    kelompok: Mapped[str | None] = mapped_column(String(100), nullable=True)
    eudr: Mapped[bool] = mapped_column(Boolean, default=False)  # kode TTSR
    keterangan: Mapped[str | None] = mapped_column(Text, nullable=True)


class TiketBaris(Base):
    """Satu baris tiket intake. Kunci = (ticket_no, line_seq)."""

    __tablename__ = "tiket_baris"
    __table_args__ = (UniqueConstraint("ticket_no", "line_seq", name="uq_tiket_line"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(50), index=True)
    line_seq: Mapped[int] = mapped_column(Integer)
    ticket_date: Mapped[dt.date] = mapped_column(Date, index=True)
    kode_vendor: Mapped[str] = mapped_column(String(20), index=True)
    nama_vendor_asli: Mapped[str | None] = mapped_column(String(200), nullable=True)
    vehicle_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    item_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    drc_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    wet_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    sample_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    reject_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    drc_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dry_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    asal_getah: Mapped[str | None] = mapped_column(Text, nullable=True)
    provinsi: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kabupaten: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kecamatan: Mapped[str | None] = mapped_column(String(100), nullable=True)
    desa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tiket_nol: Mapped[bool] = mapped_column(Boolean, default=False)  # Wet = 0
    peringatan: Mapped[str | None] = mapped_column(Text, nullable=True)
    unggahan_id: Mapped[int | None] = mapped_column(ForeignKey("raw_unggahan.id"), nullable=True)


class Pembelian(Base):
    """Amount pembelian. Granularitas fleksibel: total/hari (item_code='ALL'),
    per grade, per vendor, atau per tiket. Kolom kunci kosong disimpan ''."""

    __tablename__ = "pembelian"
    __table_args__ = (
        UniqueConstraint("tanggal", "item_code", "kode_vendor", "ticket_no", name="uq_pembelian"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tanggal: Mapped[dt.date] = mapped_column(Date, index=True)
    item_code: Mapped[str] = mapped_column(String(50), default="ALL")
    kode_vendor: Mapped[str] = mapped_column(String(20), default="")
    ticket_no: Mapped[str] = mapped_column(String(50), default="")
    qty_kering_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3))
    amount_rp: Mapped[Decimal] = mapped_column(Numeric(20, 2))  # Rupiah penuh, tepat
    unggahan_id: Mapped[int | None] = mapped_column(ForeignKey("raw_unggahan.id"), nullable=True)


class Sicom(Base):
    __tablename__ = "sicom"

    tanggal: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    usc_per_kg: Mapped[float] = mapped_column(Float)
    kontrak: Mapped[str | None] = mapped_column(String(50), nullable=True)  # [TERBUKA]
    sumber: Mapped[str | None] = mapped_column(String(200), nullable=True)
    catatan: Mapped[str | None] = mapped_column(Text, nullable=True)
    unggahan_id: Mapped[int | None] = mapped_column(ForeignKey("raw_unggahan.id"), nullable=True)


class Kurs(Base):
    """Kurs USD/IDR, berlaku sejak tanggal tertentu (bisa berubah tengah bulan)."""

    __tablename__ = "kurs"

    berlaku_dari: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    idr_per_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    sumber: Mapped[str | None] = mapped_column(String(200), nullable=True)
    catatan: Mapped[str | None] = mapped_column(Text, nullable=True)
    unggahan_id: Mapped[int | None] = mapped_column(ForeignKey("raw_unggahan.id"), nullable=True)


class Stok(Base):
    __tablename__ = "stok"
    __table_args__ = (UniqueConstraint("tanggal", "item_code", name="uq_stok"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tanggal: Mapped[dt.date] = mapped_column(Date, index=True)
    item_code: Mapped[str] = mapped_column(String(50), default="")  # '' = total
    stok_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3))
    catatan: Mapped[str | None] = mapped_column(Text, nullable=True)
    unggahan_id: Mapped[int | None] = mapped_column(ForeignKey("raw_unggahan.id"), nullable=True)


class ParameterPabrik(Base):
    __tablename__ = "parameter_pabrik"

    berlaku_dari: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    kapasitas_ton_per_hari: Mapped[float] = mapped_column(Float)
    safety_stock_ton: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_stock_hari: Mapped[float | None] = mapped_column(Float, nullable=True)
    catatan: Mapped[str | None] = mapped_column(Text, nullable=True)
    unggahan_id: Mapped[int | None] = mapped_column(ForeignKey("raw_unggahan.id"), nullable=True)


class AturanStokHarga(Base):
    """Mesin aturan: rentang rasio_stok -> penyesuaian target margin (US¢/kg).
    Berversi tanggal berlaku; baris lama tidak dihapus (riwayat)."""

    __tablename__ = "aturan_stok_harga"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    berlaku_dari: Mapped[dt.date] = mapped_column(Date, index=True)
    urutan: Mapped[int] = mapped_column(Integer)
    ukuran: Mapped[str] = mapped_column(String(100), default="Stok / Safety Stock")
    batas_bawah: Mapped[float | None] = mapped_column(Float, nullable=True)  # >=
    batas_atas: Mapped[float | None] = mapped_column(Float, nullable=True)  # <
    penyesuaian_usc: Mapped[float] = mapped_column(Float)
    keterangan: Mapped[str | None] = mapped_column(Text, nullable=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    dibuat_pada: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    dibuat_oleh: Mapped[str] = mapped_column(String(100), default="?")


class TargetMargin(Base):
    __tablename__ = "target_margin"
    __table_args__ = (UniqueConstraint("tahun", "bulan", name="uq_target"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tahun: Mapped[int] = mapped_column(Integer, index=True)
    bulan: Mapped[int] = mapped_column(Integer)
    versi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_usc_per_kg: Mapped[float] = mapped_column(Float)
    unggahan_id: Mapped[int | None] = mapped_column(ForeignKey("raw_unggahan.id"), nullable=True)


class Perencanaan(Base):
    """Penyesuaian manual & Effort untuk perencanaan tahun depan (pengganti Y27)."""

    __tablename__ = "perencanaan"
    __table_args__ = (UniqueConstraint("tahun_target", "bulan", name="uq_rencana"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tahun_target: Mapped[int] = mapped_column(Integer, index=True)
    bulan: Mapped[int] = mapped_column(Integer)
    penyesuaian_manual_usc: Mapped[float] = mapped_column(Float, default=0.0)
    effort_usc: Mapped[float] = mapped_column(Float, default=0.0)
    alasan: Mapped[str | None] = mapped_column(Text, nullable=True)
    unggahan_id: Mapped[int | None] = mapped_column(ForeignKey("raw_unggahan.id"), nullable=True)


class PeringatanData(Base):
    """Peringatan hasil validasi impor (vendor tak dikenal, Dry tidak cocok, dll.)."""

    __tablename__ = "peringatan_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unggahan_id: Mapped[int | None] = mapped_column(ForeignKey("raw_unggahan.id"), nullable=True)
    sheet: Mapped[str | None] = mapped_column(String(100), nullable=True)
    baris_ke: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kode: Mapped[str] = mapped_column(String(50))
    pesan: Mapped[str] = mapped_column(Text)
    waktu: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class HargaGrade(Base):
    """Daftar harga beli per grade (Rp/kg), berlaku sejak tanggal tertentu.
    Dipakai sebagai INFORMASI/indikatif; Amount resmi tetap total per hari
    (hasil kalkulasi pembayaran intake). Lihat docs/ASUMSI.md."""

    __tablename__ = "harga_grade"
    __table_args__ = (UniqueConstraint("tanggal", "item_code", name="uq_harga_grade"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tanggal: Mapped[dt.date] = mapped_column(Date, index=True)
    item_code: Mapped[str] = mapped_column(String(50), index=True)
    harga_rp_per_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    catatan: Mapped[str | None] = mapped_column(Text, nullable=True)
    diisi_oleh: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unggahan_id: Mapped[int | None] = mapped_column(ForeignKey("raw_unggahan.id"), nullable=True)


class AuditLog(Base):
    """Jejak perubahan: siapa mengubah aturan/parameter/perencanaan, kapan,
    dan apa isinya. Tidak pernah dihapus."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    waktu: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    siapa: Mapped[str] = mapped_column(String(100), default="?")
    aksi: Mapped[str] = mapped_column(String(50))  # tambah/ubah
    objek: Mapped[str] = mapped_column(String(100), index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON


class PengaturanAlarm(Base):
    """Pengaturan alarm yang bisa diubah admin (aktif/nonaktif + ambang)."""

    __tablename__ = "pengaturan_alarm"

    kode: Mapped[str] = mapped_column(String(50), primary_key=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    ambang: Mapped[float | None] = mapped_column(Float, nullable=True)
    satuan: Mapped[str | None] = mapped_column(String(30), nullable=True)
    keterangan: Mapped[str | None] = mapped_column(Text, nullable=True)


class Alarm(Base):
    """Alarm aktif hasil evaluasi (dibangun ulang setiap evaluasi,
    setelah tiap unggahan/perubahan data)."""

    __tablename__ = "alarm"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kode: Mapped[str] = mapped_column(String(50), index=True)
    tanggal_data: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    pesan: Mapped[str] = mapped_column(Text)
    nilai: Mapped[float | None] = mapped_column(Float, nullable=True)
    dievaluasi_pada: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow)


# ----------------------------------------------------------------------------
# Lapisan MART (dibangun ulang setelah tiap unggahan)
# ----------------------------------------------------------------------------
class MartHarian(Base):
    __tablename__ = "mart_harian"

    tanggal: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    qty_kering_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_rp: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    harga_rp_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    kurs: Mapped[float | None] = mapped_column(Float, nullable=True)
    sicom_usc: Mapped[float | None] = mapped_column(Float, nullable=True)
    harga_usc_per_kg: Mapped[float] = mapped_column(Float, default=0.0)  # 0 bila tanpa pembelian
    margin_usc: Mapped[float] = mapped_column(Float, default=0.0)  # 0 bila tanpa pembelian
    granularitas: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stok_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    stok_ton: Mapped[float | None] = mapped_column(Float, nullable=True)
    kapasitas_ton: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_ton: Mapped[float | None] = mapped_column(Float, nullable=True)
    days: Mapped[float | None] = mapped_column(Float, nullable=True)
    rasio_stok: Mapped[float | None] = mapped_column(Float, nullable=True)


class MartBulanan(Base):
    __tablename__ = "mart_bulanan"
    __table_args__ = (UniqueConstraint("tahun", "bulan", name="uq_mart_bulanan"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tahun: Mapped[int] = mapped_column(Integer, index=True)
    bulan: Mapped[int] = mapped_column(Integer)
    qty_ton: Mapped[float] = mapped_column(Float)
    sicom_usc: Mapped[float | None] = mapped_column(Float, nullable=True)
    harga_beli_usc: Mapped[float | None] = mapped_column(Float, nullable=True)
    op_margin_usc: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_usc: Mapped[float | None] = mapped_column(Float, nullable=True)
    pencapaian: Mapped[float | None] = mapped_column(Float, nullable=True)  # margin / target
    selisih_vs_target: Mapped[float | None] = mapped_column(Float, nullable=True)
    hari_pembelian: Mapped[int] = mapped_column(Integer, default=0)
