"""Impor file template "Template_dan_Data_Awal_OP_Margin" (.xlsx).

Idempoten: unggah dua kali tidak menggandakan data (clean memakai kunci
alami dan di-update bila sudah ada). Lapisan raw selalu menyimpan salinan
apa adanya setiap unggahan dan tidak pernah dihapus.

Aturan validasi: baris dengan tanggal/angka yang salah DITOLAK dengan pesan
yang menyebut sheet, baris, kolom, dan cara memperbaiki. Baris catatan
(hanya teks di satu kolom) dilewati tanpa error.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.alarm import evaluasi_alarm
from ..mart import bangun_mart
from ..models import (
    AturanStokHarga,
    Grade,
    HargaGrade,
    Kurs,
    ParameterPabrik,
    Pembelian,
    Perencanaan,
    PeringatanData,
    RawBaris,
    RawUnggahan,
    Sicom,
    Stok,
    TargetMargin,
    TiketBaris,
    Vendor,
)
from .tiket import impor_sheet_tiket
from .util import baris_kosong, ke_desimal, ke_float, ke_tanggal, ke_teks, kunci_header


@dataclass
class HasilImpor:
    unggahan_id: int = 0
    jumlah: dict[str, int] = field(default_factory=dict)
    ditolak: dict[str, int] = field(default_factory=dict)
    peringatan: list[str] = field(default_factory=list)
    duplikat_file: bool = False


def _peta_header(baris) -> dict[str, int]:
    return {kunci_header(v): i for i, v in enumerate(baris) if v is not None}


def _json_default(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return str(v)


def _baris_catatan(baris) -> bool:
    """Baris catatan: hanya kolom pertama terisi dan isinya teks panjang."""
    isi = [v for v in baris if v is not None and str(v).strip() != ""]
    return len(isi) == 1 and isinstance(baris[0], str) and len(str(baris[0])) > 30


def _simpan_raw(wb, session: Session, unggahan_id: int) -> None:
    for nama in wb.sheetnames:
        for i, baris in enumerate(wb[nama].iter_rows(values_only=True), start=1):
            if baris_kosong(baris):
                continue
            session.add(RawBaris(unggahan_id=unggahan_id, sheet=nama, baris_ke=i,
                                 isi=json.dumps(baris, default=_json_default,
                                                ensure_ascii=False)))


def _buat_unggahan(path: str, session: Session, pengunggah: str,
                   hasil: HasilImpor) -> RawUnggahan:
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    sudah_ada = session.scalar(select(RawUnggahan).where(RawUnggahan.sha256 == sha))
    hasil.duplikat_file = sudah_ada is not None
    unggahan = RawUnggahan(
        nama_file=path.replace("\\", "/").split("/")[-1], sha256=sha,
        pengunggah=pengunggah,
        catatan=f"duplikat dari unggahan #{sudah_ada.id}" if sudah_ada else None)
    session.add(unggahan)
    session.flush()
    hasil.unggahan_id = unggahan.id
    return unggahan


def impor_template(path: str, session: Session, pengunggah: str = "?") -> HasilImpor:
    hasil = HasilImpor()
    unggahan = _buat_unggahan(path, session, pengunggah, hasil)

    wb_raw = openpyxl.load_workbook(path, read_only=True, data_only=True)
    _simpan_raw(wb_raw, session, unggahan.id)
    wb = wb_raw

    def catat(sheet: str, baris_ke: int | None, kode: str, pesan: str):
        lokasi = f"[{sheet}" + (f" baris {baris_ke}" if baris_ke else "") + "]"
        hasil.peringatan.append(f"{lokasi} {pesan}")
        session.add(PeringatanData(unggahan_id=unggahan.id, sheet=sheet,
                                   baris_ke=baris_ke, kode=kode, pesan=pesan))

    def tolak(sheet: str, baris_ke: int, kode: str, pesan: str):
        hasil.ditolak[sheet] = hasil.ditolak.get(sheet, 0) + 1
        catat(sheet, baris_ke, kode, pesan + " Baris DITOLAK (tidak dimuat); "
              "perbaiki lalu unggah ulang.")

    def baca(nama_sheet: str):
        """Generator (nomor_baris, ambil, baris_mentah) untuk sheet berheader baris 1."""
        if nama_sheet not in wb.sheetnames:
            return
        ws = wb[nama_sheet]
        peta: dict[str, int] = {}
        for i, baris in enumerate(ws.iter_rows(values_only=True), start=1):
            if i == 1:
                peta = _peta_header(baris)
                continue
            if baris_kosong(baris) or _baris_catatan(baris):
                continue

            def ambil(nama, _baris=baris, _peta=peta):
                idx = _peta.get(nama)
                return _baris[idx] if idx is not None and idx < len(_baris) else None

            yield i, ambil

    def wajib_tanggal(sheet, i, ambil, kolom_kunci, label_kolom) -> dt.date | None:
        """Baca tanggal wajib; tolak dengan pesan jelas bila salah/kosong."""
        mentah = ambil(kolom_kunci)
        tanggal = ke_tanggal(mentah)
        if tanggal is None:
            if mentah in (None, ""):
                tolak(sheet, i, "TANGGAL_KOSONG",
                      f"Kolom {label_kolom} kosong.")
            else:
                tolak(sheet, i, "TANGGAL_SALAH",
                      f"Kolom {label_kolom} berisi '{mentah}' yang tidak terbaca "
                      "sebagai tanggal. Pakai format dd/mm/yyyy.")
        return tanggal

    def wajib_angka(sheet, i, ambil, kolom_kunci, label_kolom,
                    boleh_nol=False, konversi=ke_desimal):
        """Baca angka wajib (> 0, atau >= 0 bila boleh_nol). None bila ditolak."""
        mentah = ambil(kolom_kunci)
        nilai = konversi(mentah)
        if nilai is None:
            if mentah in (None, ""):
                tolak(sheet, i, "ANGKA_KOSONG", f"Kolom {label_kolom} kosong.")
            else:
                tolak(sheet, i, "ANGKA_SALAH",
                      f"Kolom {label_kolom} berisi '{mentah}' yang tidak terbaca "
                      "sebagai angka. Tulis angka polos tanpa satuan, contoh: 9500.")
            return None
        if nilai < 0 or (nilai == 0 and not boleh_nol):
            tolak(sheet, i, "ANGKA_DI_LUAR_BATAS",
                  f"Kolom {label_kolom} berisi {mentah}; nilainya harus lebih dari 0.")
            return None
        return nilai

    # ------------------------------------------------------------ master
    n = 0
    for i, ambil in baca("Master_Vendor") or []:
        kode = (ke_teks(ambil("kode_vendor")) or "").upper()
        if not kode:
            tolak("Master_Vendor", i, "KODE_KOSONG", "Kolom Kode_Vendor kosong.")
            continue
        v = session.get(Vendor, kode) or Vendor(kode=kode, nama_baku="")
        v.nama_baku = ke_teks(ambil("nama_baku")) or kode
        v.varian_nama = ke_teks(ambil("varian_nama"))
        v.kategori = ke_teks(ambil("kategori"))
        v.status = ke_teks(ambil("status"))
        session.merge(v)
        n += 1
    hasil.jumlah["vendor"] = n

    n = 0
    for i, ambil in baca("Master_Grade") or []:
        kode = ke_teks(ambil("item_code"))
        if not kode:
            tolak("Master_Grade", i, "KODE_KOSONG", "Kolom Item_Code kosong.")
            continue
        g = session.get(Grade, kode) or Grade(item_code=kode)
        g.kelompok = ke_teks(ambil("kelompok"))
        eudr_teks = (ke_teks(ambil("eudr (ttsr)")) or "").lower()
        g.eudr = eudr_teks in ("ya", "yes", "true", "1") or "TTSR" in kode.upper()
        g.keterangan = ke_teks(ambil("keterangan"))
        session.merge(g)
        n += 1
    hasil.jumlah["grade"] = n
    session.flush()

    # ------------------------------------------------------------ tiket intake
    # Diimpor SEBELUM pembelian supaya Qty_Kering_Kg yang kosong bisa
    # dihitung dari jumlah Dry tiket pada tanggal itu.
    if "Intake_Tiket" in wb_raw.sheetnames:
        wb2 = openpyxl.load_workbook(path, data_only=True)
        hasil.jumlah["tiket_baris"] = impor_sheet_tiket(
            wb2["Intake_Tiket"], session, unggahan.id, hasil.peringatan)
        session.flush()

    # Jumlah Dry tiket per tanggal (tanpa tiket nol), untuk mengisi Qty kosong.
    dry_per_kunci: dict[tuple, Decimal] = defaultdict(Decimal)
    for t in session.scalars(select(TiketBaris).where(TiketBaris.tiket_nol == False)):  # noqa: E712
        if t.dry_kg is None:
            continue
        dry_per_kunci[(t.ticket_date, None, None, None)] += t.dry_kg
        dry_per_kunci[(t.ticket_date, t.item_code, None, None)] += t.dry_kg
        dry_per_kunci[(t.ticket_date, None, t.kode_vendor, None)] += t.dry_kg
        dry_per_kunci[(t.ticket_date, None, None, t.ticket_no)] += t.dry_kg

    # ------------------------------------------------------------ pembelian
    # Granularitas fleksibel: total/hari (ALL), per grade, per vendor, per tiket.
    # Disimpan pada tingkat terhalus yang tersedia di file.
    n = 0
    for i, ambil in baca("Pembelian_Harian") or []:
        tanggal = wajib_tanggal("Pembelian_Harian", i, ambil, "tanggal", "Tanggal")
        if tanggal is None:
            continue
        amount = wajib_angka("Pembelian_Harian", i, ambil, "amount_rp",
                             "Amount_Rp", boleh_nol=True)
        if amount is None:
            continue
        item = ke_teks(ambil("item_code")) or "ALL"
        vendor = (ke_teks(ambil("kode_vendor")) or "").upper()
        tiket = ke_teks(ambil("ticket_no")) or ""

        mentah_qty = ambil("qty_kering_kg")
        qty = ke_desimal(mentah_qty)
        if qty is None and mentah_qty not in (None, ""):
            tolak("Pembelian_Harian", i, "ANGKA_SALAH",
                  f"Kolom Qty_Kering_Kg berisi '{mentah_qty}' yang tidak terbaca "
                  "sebagai angka.")
            continue
        if qty is None:
            # Qty kosong: hitung dari jumlah Dry tiket pada lingkup yang sama.
            if tiket:
                kunci = (tanggal, None, None, tiket)
                lingkup = f"tiket {tiket}"
            elif vendor:
                kunci = (tanggal, None, vendor, None)
                lingkup = f"vendor {vendor}"
            elif item != "ALL":
                kunci = (tanggal, item, None, None)
                lingkup = f"grade {item}"
            else:
                kunci = (tanggal, None, None, None)
                lingkup = "semua tiket hari itu"
            qty = dry_per_kunci.get(kunci)
            if qty is None or qty == 0:
                tolak("Pembelian_Harian", i, "QTY_TAK_BISA_DIHITUNG",
                      f"Qty_Kering_Kg kosong dan tidak ada tiket ({lingkup}) "
                      f"pada {tanggal.strftime('%d/%m/%Y')} untuk menghitungnya. "
                      "Isi Qty_Kering_Kg atau unggah tiketnya dahulu.")
                continue
            catat("Pembelian_Harian", i, "QTY_DARI_TIKET",
                  f"Qty_Kering_Kg kosong; dipakai jumlah Dry tiket ({lingkup}) "
                  f"pada {tanggal.strftime('%d/%m/%Y')} = {qty} kg.")
        elif qty <= 0:
            tolak("Pembelian_Harian", i, "ANGKA_DI_LUAR_BATAS",
                  f"Kolom Qty_Kering_Kg berisi {mentah_qty}; harus lebih dari 0.")
            continue

        p = session.scalar(select(Pembelian).where(
            Pembelian.tanggal == tanggal, Pembelian.item_code == item,
            Pembelian.kode_vendor == vendor, Pembelian.ticket_no == tiket))
        if p is None:
            p = Pembelian(tanggal=tanggal, item_code=item, kode_vendor=vendor,
                          ticket_no=tiket, qty_kering_kg=qty, amount_rp=amount)
            session.add(p)
        p.qty_kering_kg = qty
        p.amount_rp = amount
        p.unggahan_id = unggahan.id
        n += 1
    hasil.jumlah["pembelian"] = n

    # ------------------------------------------------------------ harga per grade
    # Daftar harga beli per grade (Rp/kg), berlaku sejak tanggal baris.
    n = 0
    kode_grade = {g.item_code for g in session.scalars(select(Grade))}
    for i, ambil in baca("Harga_Grade") or []:
        tanggal = wajib_tanggal("Harga_Grade", i, ambil, "tanggal", "Tanggal")
        if tanggal is None:
            continue
        item = ke_teks(ambil("item_code"))
        if not item:
            tolak("Harga_Grade", i, "KODE_KOSONG", "Kolom Item_Code kosong.")
            continue
        harga = wajib_angka("Harga_Grade", i, ambil, "harga_rp_per_kg",
                            "Harga_Rp_per_Kg")
        if harga is None:
            continue
        if kode_grade and item not in kode_grade:
            catat("Harga_Grade", i, "GRADE_TAK_DIKENAL",
                  f"Item Code '{item}' tidak ada di master grade. Tambahkan dulu "
                  "di menu Grade & Harga bila memang grade baru.")
        hg = session.scalar(select(HargaGrade).where(
            HargaGrade.tanggal == tanggal, HargaGrade.item_code == item))
        if hg is None:
            hg = HargaGrade(tanggal=tanggal, item_code=item, harga_rp_per_kg=harga)
            session.add(hg)
        hg.harga_rp_per_kg = harga
        hg.catatan = ke_teks(ambil("catatan"))
        hg.diisi_oleh = pengunggah
        hg.unggahan_id = unggahan.id
        n += 1
    hasil.jumlah["harga_grade"] = n

    # ------------------------------------------------------------ sicom
    n = 0
    for i, ambil in baca("SICOM_Harian") or []:
        tanggal = wajib_tanggal("SICOM_Harian", i, ambil, "tanggal", "Tanggal")
        if tanggal is None:
            continue
        harga = wajib_angka("SICOM_Harian", i, ambil, "sicom_usc_per_kg",
                            "SICOM_USc_per_kg", konversi=ke_float)
        if harga is None:
            continue
        s = session.get(Sicom, tanggal) or Sicom(tanggal=tanggal, usc_per_kg=harga)
        s.usc_per_kg = harga
        s.kontrak = ke_teks(ambil("kontrak"))  # [TERBUKA] kontrak boleh kosong
        s.sumber = ke_teks(ambil("sumber"))
        s.catatan = ke_teks(ambil("catatan"))
        s.unggahan_id = unggahan.id
        session.merge(s)
        n += 1
    hasil.jumlah["sicom"] = n

    # ------------------------------------------------------------ kurs
    n = 0
    for i, ambil in baca("Kurs") or []:
        tanggal = wajib_tanggal("Kurs", i, ambil, "berlaku_dari", "Berlaku_Dari")
        if tanggal is None:
            continue
        nilai = wajib_angka("Kurs", i, ambil, "kurs_idr_per_usd", "Kurs_IDR_per_USD")
        if nilai is None:
            continue
        k = session.get(Kurs, tanggal) or Kurs(berlaku_dari=tanggal, idr_per_usd=nilai)
        k.idr_per_usd = nilai
        k.sumber = ke_teks(ambil("sumber"))
        k.catatan = ke_teks(ambil("catatan"))
        k.unggahan_id = unggahan.id
        session.merge(k)
        n += 1
    hasil.jumlah["kurs"] = n

    # ------------------------------------------------------------ stok
    n = 0
    for i, ambil in baca("Stok_Harian") or []:
        tanggal = wajib_tanggal("Stok_Harian", i, ambil, "tanggal", "Tanggal")
        if tanggal is None:
            continue
        stok_kg = wajib_angka("Stok_Harian", i, ambil, "stok_kg", "Stok_Kg",
                              boleh_nol=True)
        if stok_kg is None:
            continue
        item = ke_teks(ambil("item_code")) or ""
        st = session.scalar(select(Stok).where(Stok.tanggal == tanggal,
                                               Stok.item_code == item))
        if st is None:
            st = Stok(tanggal=tanggal, item_code=item, stok_kg=stok_kg)
            session.add(st)
        st.stok_kg = stok_kg
        st.catatan = ke_teks(ambil("catatan"))
        st.unggahan_id = unggahan.id
        n += 1
    hasil.jumlah["stok"] = n

    # ------------------------------------------------------------ parameter pabrik
    n = 0
    for i, ambil in baca("Parameter_Pabrik") or []:
        tanggal = wajib_tanggal("Parameter_Pabrik", i, ambil, "berlaku_dari",
                                "Berlaku_Dari")
        if tanggal is None:
            continue
        kapasitas = wajib_angka("Parameter_Pabrik", i, ambil, "kapasitas_olah",
                                "Kapasitas_Olah", konversi=ke_float)
        if kapasitas is None:
            continue
        p = session.get(ParameterPabrik, tanggal) or ParameterPabrik(
            berlaku_dari=tanggal, kapasitas_ton_per_hari=kapasitas)
        p.kapasitas_ton_per_hari = kapasitas
        p.safety_stock_ton = ke_float(ambil("safety_stock_ton"))
        p.safety_stock_hari = ke_float(ambil("safety_stock_hari"))
        if p.safety_stock_ton is None and p.safety_stock_hari is None:
            catat("Parameter_Pabrik", i, "SAFETY_KOSONG",
                  "Safety_Stock_Ton dan Safety_Stock_Hari dua-duanya kosong; "
                  "rasio stok tidak bisa dihitung untuk periode ini.")
        p.catatan = ke_teks(ambil("catatan"))
        p.unggahan_id = unggahan.id
        session.merge(p)
        n += 1
    hasil.jumlah["parameter_pabrik"] = n

    # ------------------------------------------------------------ aturan stok->harga
    # Isi awal template hanyalah CONTOH bentuk [TERBUKA]; tetap dimuat tetapi
    # ditandai, dan hanya dimuat sekali (tidak menggandakan riwayat).
    n = 0
    if session.scalar(select(AturanStokHarga)) is None:
        for i, ambil in baca("Aturan_Stok_Harga") or []:
            penyesuaian = ke_float(ambil("penyesuaian_target_margin"))
            if penyesuaian is None:
                continue
            session.add(AturanStokHarga(
                berlaku_dari=dt.date(2000, 1, 1),
                urutan=int(ke_float(ambil("urutan")) or 0),
                ukuran=ke_teks(ambil("ukuran")) or "Stok / Safety Stock",
                batas_bawah=ke_float(ambil("batas_bawah")),
                batas_atas=ke_float(ambil("batas_atas")),
                penyesuaian_usc=penyesuaian,
                keterangan=ke_teks(ambil("keterangan")),
                dibuat_oleh=pengunggah))
            n += 1
        if n:
            catat("Aturan_Stok_Harga", None, "ATURAN_CONTOH",
                  "Aturan stok->harga yang dimuat adalah CONTOH dari template dan "
                  "harus diganti sesuai kebijakan resmi perusahaan.")
    hasil.jumlah["aturan_stok_harga"] = n

    # ------------------------------------------------------------ target margin
    n = 0
    for i, ambil in baca("Target_Margin") or []:
        tahun = ke_float(ambil("tahun"))
        bulan = ke_float(ambil("bulan"))
        target = ke_float(ambil("target_usc_per_kg"))
        if tahun is None or bulan is None or target is None:
            tolak("Target_Margin", i, "BARIS_TAK_LENGKAP",
                  "Kolom Tahun/Bulan/Target_USc_per_kg kosong atau bukan angka.")
            continue
        if not (1 <= int(bulan) <= 12):
            tolak("Target_Margin", i, "BULAN_SALAH",
                  f"Kolom Bulan berisi {bulan}; harus 1 sampai 12.")
            continue
        t = session.scalar(select(TargetMargin).where(
            TargetMargin.tahun == int(tahun), TargetMargin.bulan == int(bulan)))
        if t is None:
            t = TargetMargin(tahun=int(tahun), bulan=int(bulan), target_usc_per_kg=target)
            session.add(t)
        t.versi = ke_teks(ambil("versi"))
        t.target_usc_per_kg = target
        t.unggahan_id = unggahan.id
        n += 1
    hasil.jumlah["target_margin"] = n

    # ------------------------------------------------------------ perencanaan
    n = 0
    for i, ambil in baca("Perencanaan") or []:
        tahun = ke_float(ambil("tahun_target"))
        bulan = ke_float(ambil("bulan"))
        if tahun is None or bulan is None:
            tolak("Perencanaan", i, "BARIS_TAK_LENGKAP",
                  "Kolom Tahun_Target/Bulan kosong atau bukan angka.")
            continue
        if not (1 <= int(bulan) <= 12):
            tolak("Perencanaan", i, "BULAN_SALAH",
                  f"Kolom Bulan berisi {bulan}; harus 1 sampai 12.")
            continue
        r = session.scalar(select(Perencanaan).where(
            Perencanaan.tahun_target == int(tahun), Perencanaan.bulan == int(bulan)))
        if r is None:
            r = Perencanaan(tahun_target=int(tahun), bulan=int(bulan))
            session.add(r)
        r.penyesuaian_manual_usc = ke_float(ambil("penyesuaian_manual")) or 0.0
        r.effort_usc = ke_float(ambil("effort")) or 0.0
        r.alasan = ke_teks(ambil("alasan / dasar"))
        r.unggahan_id = unggahan.id
        n += 1
    hasil.jumlah["perencanaan"] = n

    session.flush()
    bangun_mart(session)
    evaluasi_alarm(session)  # alarm dievaluasi setelah tiap unggahan
    session.commit()
    return hasil


def impor_master_data(path: str, session: Session, pengunggah: str = "?") -> HasilImpor:
    """Impor file ekspor 'Master Data' (bisa beberapa sheet tiket dalam satu file)."""
    hasil = HasilImpor()
    unggahan = _buat_unggahan(path, session, pengunggah, hasil)

    wb_raw = openpyxl.load_workbook(path, read_only=True, data_only=True)
    _simpan_raw(wb_raw, session, unggahan.id)

    wb = openpyxl.load_workbook(path, data_only=True)
    total = 0
    for nama in wb.sheetnames:
        total += impor_sheet_tiket(wb[nama], session, unggahan.id, hasil.peringatan)
    hasil.jumlah["tiket_baris"] = total

    session.flush()
    bangun_mart(session)
    evaluasi_alarm(session)  # alarm dievaluasi setelah tiap unggahan
    session.commit()
    return hasil
