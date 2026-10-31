"""API master vendor (Fase 8): daftar, tambah, ubah, hapus, template bulk
import, dan impor massal langsung dari menu Master Vendor.

Alasan modul terpisah: kode vendor dipakai sebagai kunci di `tiket_baris` dan
`pembelian`. Salah ketik kode membuat tonase hilang dari laporan, jadi master
vendor harus bisa dirawat sendiri (bukan menunggu unggah template tahunan).

Aturan yang dijaga:
- kode vendor disimpan HURUF BESAR dan tanpa spasi tepi (kunci, tidak boleh
  berubah saat mengubah data lain — kode yang berubah = vendor baru);
- vendor yang sudah dipakai tiket/pembelian TIDAK boleh dihapus begitu saja
  (laporan akan kehilangan pemilik tonase). Bawaannya ditolak dengan pesan
  jelas; `paksa=true` tetap disediakan untuk kasus salah input yang harus
  dibersihkan, dan tetap dicatat di audit;
- impor massal bersifat upsert: kode yang sudah ada diperbarui, kode baru
  ditambahkan, baris rusak dilaporkan per baris (tidak membatalkan yang lain).

Sejak v0.10.0 master vendor juga menyimpan **alamat**, **contact person**, dan
**klasifikasi** (Small holder / Small estate / Rubber trader). Ejaan bebas
diterima saat impor; ejaan yang tidak dikenal ditolak per baris dengan pesan
yang menyebut tiga pilihan itu — bukan disimpan diam-diam sebagai nilai lain.
Mengosongkan sel di Excel berarti "jangan ubah", sama seperti Kategori.
"""
from __future__ import annotations

import io
import re

import openpyxl
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .core.alarm import catat_audit
from .core.klasifikasi_vendor import (bakukan as bakukan_klasifikasi,
                                      daftar_untuk_layar, label as label_klasifikasi)
from .models import Collector, Pembelian, TiketBaris, Vendor

SHEET = "Master_Vendor"
KOLOM = ["Kode_Vendor", "Nama_Baku", "Varian_Nama", "Kategori", "Status",
         "Alamat", "Kontak_Person", "Klasifikasi"]
STATUS_BAKU = ("aktif", "nonaktif", "diblokir")
POLA_KODE = re.compile(r"^[A-Z0-9][A-Z0-9._/-]{0,19}$")
BATAS_IMPOR = 5000
BATAS_LAPORAN = 200


class VendorMasuk(BaseModel):
    kode: str = Field(min_length=1, max_length=20)
    nama_baku: str = Field(min_length=1, max_length=200)
    varian_nama: str | None = None
    kategori: str | None = None
    status: str | None = None
    alamat: str | None = None
    kontak_person: str | None = None
    klasifikasi: str | None = None
    pengisi: str = "?"


class VendorUbah(BaseModel):
    nama_baku: str = Field(min_length=1, max_length=200)
    varian_nama: str | None = None
    kategori: str | None = None
    status: str | None = None
    alamat: str | None = None
    kontak_person: str | None = None
    klasifikasi: str | None = None
    pengisi: str = "?"


def _kode_baku(kode: str) -> str:
    return (kode or "").strip().upper()


def _bersih(teks: str | None) -> str | None:
    nilai = (teks or "").strip()
    return nilai or None


def _status_baku(status: str | None) -> str:
    nilai = (status or "").strip().lower()
    if not nilai:
        return "aktif"
    if nilai not in STATUS_BAKU:
        raise HTTPException(422, f"Status '{status}' tidak dikenal. Pilih salah "
                                 f"satu: {', '.join(STATUS_BAKU)}.")
    return nilai


def _klasifikasi_atau_tolak(nilai: str | None) -> str | None:
    """Kosong -> None; ejaan tak dikenal -> 422 dengan tiga pilihan."""
    try:
        return bakukan_klasifikasi(nilai)
    except ValueError as e:
        raise HTTPException(422, str(e))


def _periksa_kode(kode: str) -> str:
    kode = _kode_baku(kode)
    if not kode:
        raise HTTPException(422, "Kode vendor tidak boleh kosong.")
    if len(kode) > 20:
        raise HTTPException(422, f"Kode vendor '{kode}' lebih dari 20 karakter. "
                                 "Kode harus sama persis dengan yang dipakai di tiket.")
    if not POLA_KODE.match(kode):
        raise HTTPException(422, f"Kode vendor '{kode}' mengandung karakter yang "
                                 "tidak diizinkan. Pakai huruf, angka, dan "
                                 "tanda - . _ / saja (contoh: V001, SUPP-01).")
    return kode


def _pemakaian(session: Session, kode: str) -> dict:
    """Berapa banyak data historis memakai kode ini."""
    jumlah_tiket = session.scalar(
        select(func.count()).select_from(TiketBaris).where(
            TiketBaris.kode_vendor == kode)) or 0
    jenis_tiket = session.scalar(
        select(func.count(func.distinct(TiketBaris.ticket_no))).where(
            TiketBaris.kode_vendor == kode)) or 0
    ton = session.scalar(
        select(func.sum(TiketBaris.dry_kg)).where(
            TiketBaris.kode_vendor == kode)) or 0
    jumlah_pembelian = session.scalar(
        select(func.count()).select_from(Pembelian).where(
            Pembelian.kode_vendor == kode)) or 0
    terakhir = session.scalar(
        select(func.max(TiketBaris.ticket_date)).where(
            TiketBaris.kode_vendor == kode))
    return {
        "baris_tiket": int(jumlah_tiket),
        "jumlah_tiket": int(jenis_tiket),
        "ton_kering": round(float(ton) / 1000, 3),
        "baris_pembelian": int(jumlah_pembelian),
        "intake_terakhir": terakhir.isoformat() if terakhir else None,
        "terpakai": bool(jumlah_tiket or jumlah_pembelian),
    }


def _baris_vendor(session: Session, v: Vendor) -> dict:
    pakai = _pemakaian(session, v.kode)
    return {
        "kode": v.kode, "nama_baku": v.nama_baku,
        "varian_nama": v.varian_nama, "kategori": v.kategori,
        # Status lama di database bisa tertulis "Aktif"; dibakukan huruf kecil
        # supaya cocok dengan pilihan di layar dan warna penandanya.
        "status": (v.status or "").strip().lower() or "aktif",
        "alamat": v.alamat, "kontak_person": v.kontak_person,
        "klasifikasi": v.klasifikasi,
        "klasifikasi_label": label_klasifikasi(v.klasifikasi), **pakai,
    }


def pasang_router_vendor(app, ambil_session):
    router = APIRouter(prefix="/api")
    dep = Depends(ambil_session)

    # ------------------------------------------------------------------ daftar
    @router.get("/vendor")
    def daftar_vendor(q: str | None = None, status: str | None = None,
                      klasifikasi: str | None = None, session: Session = dep):
        """Daftar vendor + berapa banyak data historis yang memakainya.

        `q` mencari di kode, nama baku, varian nama, kategori, alamat, contact
        person, dan label klasifikasi (tidak peka huruf besar/kecil).
        `status` menyaring aktif/nonaktif/diblokir; `klasifikasi` menyaring
        small_holder/small_estate/rubber_trader.
        """
        baris = [_baris_vendor(session, v) for v in session.scalars(
            select(Vendor).order_by(Vendor.kode))]
        cari = (q or "").strip().lower()
        if cari:
            baris = [b for b in baris
                     if cari in b["kode"].lower()
                     or cari in b["nama_baku"].lower()
                     or cari in (b["varian_nama"] or "").lower()
                     or cari in (b["kategori"] or "").lower()
                     or cari in (b["alamat"] or "").lower()
                     or cari in (b["kontak_person"] or "").lower()
                     or cari in (b["klasifikasi_label"] or "").lower()]
        if status:
            ingin = status.strip().lower()
            baris = [b for b in baris if (b["status"] or "").lower() == ingin]
        if klasifikasi:
            ingin = klasifikasi.strip().lower()
            if ingin in ("-", "kosong", "belum diisi"):
                baris = [b for b in baris if not b["klasifikasi"]]
            else:
                try:
                    ingin = bakukan_klasifikasi(ingin) or ingin
                except ValueError:
                    raise HTTPException(422, str(
                        ValueError(f"Klasifikasi '{klasifikasi}' tidak dikenal. "
                                   "Pilih salah satu: Small holder, Small estate, "
                                   "atau Rubber trader.")))
                baris = [b for b in baris if b["klasifikasi"] == ingin]
        ringkas: dict[str, int] = {k: 0 for k in ("small_holder", "small_estate",
                                                  "rubber_trader", None)}
        for b in baris:
            ringkas[b["klasifikasi"] if b["klasifikasi"] in ringkas
                    else None] = ringkas.get(
                        b["klasifikasi"] if b["klasifikasi"] in ringkas
                        else None, 0) + 1
        return {
            "baris": baris,
            "jumlah": len(baris),
            "jumlah_total": session.scalar(
                select(func.count()).select_from(Vendor)) or 0,
            "status_baku": list(STATUS_BAKU),
            "klasifikasi_baku": daftar_untuk_layar(),
            "ringkasan_klasifikasi": {
                "small_holder": ringkas["small_holder"],
                "small_estate": ringkas["small_estate"],
                "rubber_trader": ringkas["rubber_trader"],
                "belum_diisi": ringkas[None],
            },
        }

    # ------------------------------------------------------------------ tambah
    @router.post("/vendor")
    def tambah_vendor(data: VendorMasuk, session: Session = dep):
        kode = _periksa_kode(data.kode)
        if session.get(Vendor, kode):
            raise HTTPException(409, f"Kode vendor '{kode}' sudah ada. Gunakan "
                                     "tombol Ubah pada baris tersebut, atau pakai "
                                     "kode lain.")
        v = Vendor(
            kode=kode,
            nama_baku=(data.nama_baku or "").strip() or kode,
            varian_nama=_bersih(data.varian_nama),
            kategori=_bersih(data.kategori),
            status=_status_baku(data.status),
            alamat=_bersih(data.alamat),
            kontak_person=_bersih(data.kontak_person),
            klasifikasi=_klasifikasi_atau_tolak(data.klasifikasi),
        )
        session.add(v)
        catat_audit(session, data.pengisi, "tambah", "vendor", {
            "kode": kode, "nama_baku": v.nama_baku, "kategori": v.kategori,
            "status": v.status, "klasifikasi": v.klasifikasi})
        session.commit()
        return {"status": "tersimpan",
                "pesan": f"Vendor {kode} — {v.nama_baku} ditambahkan.",
                "vendor": _baris_vendor(session, v)}

    # ------------------------------------------------------------------- ubah
    @router.put("/vendor/{kode}")
    def ubah_vendor(kode: str, data: VendorUbah, session: Session = dep):
        kode = _kode_baku(kode)
        v = session.get(Vendor, kode)
        if not v:
            raise HTTPException(404, f"Vendor '{kode}' tidak ada. Muat ulang "
                                     "halaman: mungkin sudah dihapus.")
        lama = {"nama_baku": v.nama_baku, "varian_nama": v.varian_nama,
                "kategori": v.kategori, "status": v.status,
                "alamat": v.alamat, "kontak_person": v.kontak_person,
                "klasifikasi": v.klasifikasi}
        v.nama_baku = (data.nama_baku or "").strip() or v.nama_baku
        v.varian_nama = _bersih(data.varian_nama)
        v.kategori = _bersih(data.kategori)
        v.status = _status_baku(data.status)
        v.alamat = _bersih(data.alamat)
        v.kontak_person = _bersih(data.kontak_person)
        v.klasifikasi = _klasifikasi_atau_tolak(data.klasifikasi)
        catat_audit(session, data.pengisi, "ubah", "vendor", {
            "kode": kode, "lama": lama,
            "baru": {"nama_baku": v.nama_baku, "varian_nama": v.varian_nama,
                     "kategori": v.kategori, "status": v.status,
                     "alamat": v.alamat, "kontak_person": v.kontak_person,
                     "klasifikasi": v.klasifikasi}})
        session.commit()
        return {"status": "tersimpan",
                "pesan": f"Vendor {kode} diperbarui. Riwayat tiket/pembelian "
                         "yang memakai kode ini tidak berubah.",
                "vendor": _baris_vendor(session, v)}

    # ------------------------------------------------------------------ hapus
    @router.delete("/vendor/{kode}")
    def hapus_vendor(kode: str, paksa: bool = False, pengisi: str = "?",
                     session: Session = dep):
        kode = _kode_baku(kode)
        v = session.get(Vendor, kode)
        if not v:
            raise HTTPException(404, f"Vendor '{kode}' tidak ada.")
        jumlah_collector = session.scalar(select(func.count()).select_from(Collector).where(
            Collector.kode_vendor == kode)) or 0
        if jumlah_collector:
            raise HTTPException(409, (
                f"Vendor {kode} masih menjadi afiliasi {jumlah_collector} collector. "
                "Pindahkan collector ke vendor lain atau hapus collector terlebih dahulu."
            ))
        pakai = _pemakaian(session, kode)
        if pakai["terpakai"] and not paksa:
            raise HTTPException(409, (
                f"Vendor {kode} masih dipakai {pakai['jumlah_tiket']} tiket "
                f"({pakai['ton_kering']:,.3f} ton kering) dan "
                f"{pakai['baris_pembelian']} baris pembelian. Menghapusnya "
                "membuat tonase itu kehilangan pemiliknya di laporan. "
                "Ubah statusnya menjadi 'nonaktif' (tombol Ubah) supaya tidak "
                "dipakai lagi tanpa merusak riwayat. Bila kode ini memang salah "
                "input dan belum dipakai, hapus bisa dipaksa dengan paksa=true "
                "(tetap tercatat di audit)."
            ).replace(",", "."))
        session.delete(v)
        catat_audit(session, pengisi, "hapus", "vendor",
                    {"kode": kode, "nama_baku": v.nama_baku,
                     "dipaksa": bool(pakai["terpakai"]), "pemakaian": pakai})
        session.commit()
        return {"status": "terhapus",
                "pesan": (f"Vendor {kode} dihapus."
                          + (" Data tiket/pembelian yang memakai kode ini tetap "
                             "tersimpan sebagai teks kode." if pakai["terpakai"]
                             else "")),
                "dipaksa": bool(pakai["terpakai"]), "pemakaian": pakai}

    # --------------------------------------------------------------- template
    @router.get("/vendor/template")
    def template_vendor(session: Session = dep):
        """Template .xlsx untuk bulk import (sheet `Master_Vendor`).

        Isinya: baris contoh yang sudah dikenal sistem, supaya pengguna bisa
        langsung mengubah/menambah di Excel lalu mengunggahnya kembali di menu
        Master Vendor (atau di tab Unggah Data — nama sheet-nya sama).
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = SHEET
        ws.append(KOLOM)
        for v in session.scalars(select(Vendor).order_by(Vendor.kode)):
            ws.append([v.kode, v.nama_baku, v.varian_nama, v.kategori,
                       v.status or "aktif", v.alamat, v.kontak_person,
                       v.klasifikasi or None])
        if ws.max_row == 1:      # belum ada data: beri satu baris contoh
            ws.append(["V001", "PT Contoh Karet Nusantara", "PT Contoh Karet|CV Contoh",
                       "nasional", "aktif", "Jl. Contoh No. 1, Medan",
                       "Budi — 0812-0000-0000", "small_holder"])
        for kolom, lebar in zip("ABCDEFGH", (16, 40, 40, 20, 14, 45, 30, 16)):
            ws.column_dimensions[kolom].width = lebar
        ws.freeze_panes = "A2"

        panduan = wb.create_sheet("Petunjuk")
        for teks in [
            ["PETUNJUK PENGISIAN MASTER VENDOR"],
            [""],
            ["1. Isi/ubah baris pada sheet Master_Vendor. Jangan ganti nama sheet."],
            ["2. Kode_Vendor wajib; disimpan HURUF BESAR. Contoh: V001, SUPP-01."],
            ["   Kode harus SAMA PERSIS dengan yang dipakai di tiket intake."],
            ["3. Nama_Baku wajib. Varian_Nama = nama lain vendor yang sering"],
            ["   muncul di tiket, dipisah tanda | (pipa). Contoh: PT A|CV A."],
            ["4. Kategori bebas (mis. nasional, lokal, koperasi)."],
            ["5. Status: aktif / nonaktif / diblokir. Kosong = aktif."],
            ["6. Alamat: alamat lengkap vendor (boleh lebih dari satu baris)."],
            ["7. Kontak_Person: nama orang yang dihubungi, boleh plus nomor HP."],
            ["8. Klasifikasi: Small holder / Small estate / Rubber trader."],
            ["   Ejaan lain yang lazim tetap diterima (mis. Smallholder, trader)."],
            ["   Kosongkan bila belum tahu; ejaan yang tidak dikenal akan DITOLAK"],
            ["   dengan alasan di laporan impor (baris lain tetap masuk)."],
            ["9. Mengosongkan sel Alamat/Kontak/Klasifikasi/Kategori = tidak diubah."],
            ["10. Unggah: menu Master Vendor > Bulk import, atau tab Unggah Data."],
            ["   Kode yang sudah ada akan DIPERBARUI (bukan digandakan)."],
            ["11. Menghapus vendor tidak dilakukan lewat Excel. Pakai tombol Hapus."],
        ]:
            panduan.append(teks)
        panduan.column_dimensions["A"].width = 78

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument"
                       ".spreadsheetml.sheet",
            headers={"Content-Disposition":
                     'attachment; filename="Master_Vendor_template.xlsx"'})

    # ------------------------------------------------------------ impor massal
    @router.post("/vendor/impor")
    async def impor_vendor(file: UploadFile = File(...), pengisi: str = Form("?"),
                           session: Session = dep):
        """Bulk import dari file .xlsx bersheet `Master_Vendor`.

        Upsert: kode yang sudah ada diperbarui, kode baru ditambahkan. Baris
        rusak dilaporkan per baris dan tidak membatalkan baris lain.
        """
        nama = (file.filename or "unggahan.xlsx")
        if not nama.lower().endswith(".xlsx"):
            raise HTTPException(422, f"File '{nama}' bukan .xlsx. Simpan ulang "
                                     "sebagai .xlsx lalu unggah lagi.")
        isi = await file.read()
        if not isi:
            raise HTTPException(422, "File kosong. Pilih file yang benar.")
        try:
            wb = openpyxl.load_workbook(io.BytesIO(isi), data_only=True,
                                        read_only=True)
        except Exception:
            raise HTTPException(422, f"File '{nama}' tidak bisa dibuka sebagai "
                                     "Excel. Pastikan tidak rusak/terkunci sandi.")
        if SHEET not in wb.sheetnames:
            wb.close()
            raise HTTPException(422, f"Sheet '{SHEET}' tidak ditemukan. File "
                                     f"berisi: {', '.join(wb.sheetnames) or '(kosong)'}. "
                                     "Unduh template dari menu ini supaya nama "
                                     "sheet-nya benar.")
        ws = wb[SHEET]
        baris_semua = list(ws.iter_rows(values_only=True))
        wb.close()
        if not baris_semua:
            raise HTTPException(422, "Sheet Master_Vendor kosong.")

        # Cari baris header (kolom 'kode_vendor'), lalu petakan nomor kolom.
        idx_header = None
        for i, r in enumerate(baris_semua[:10]):
            teks = [str(x or "").strip().lower() for x in r]
            if any("kode" in x and "vendor" in x for x in teks):
                idx_header = i
                break
        if idx_header is None:
            raise HTTPException(422, "Baris judul kolom tidak ditemukan. Kolom "
                                     "pertama seharusnya 'Kode_Vendor'.")
        kepala = [str(x or "").strip().lower() for x in baris_semua[idx_header]]
        peta: dict[str, int] = {}
        for pos, nama_kolom in enumerate(kepala):
            kunci = nama_kolom.replace(" ", "_")
            if kunci in ("kode_vendor", "kode"):
                peta["kode"] = pos
            elif kunci in ("nama_baku", "nama"):
                peta["nama"] = pos
            elif kunci in ("varian_nama", "varian"):
                peta["varian"] = pos
            elif kunci in ("kategori",):
                peta["kategori"] = pos
            elif kunci in ("status",):
                peta["status"] = pos
            elif kunci in ("alamat", "address", "alamat_lengkap"):
                peta["alamat"] = pos
            elif kunci in ("kontak_person", "kontak", "contact_person",
                           "contact", "cp"):
                peta["kontak"] = pos
            elif kunci in ("klasifikasi", "klasifikasi_vendor", "kategori_vendor",
                           "classification", "tipe_vendor"):
                peta["klasifikasi"] = pos
        if "kode" not in peta or "nama" not in peta:
            raise HTTPException(422, "Kolom Kode_Vendor dan Nama_Baku wajib ada "
                                     "di sheet Master_Vendor.")

        def ambil(r, kunci):
            pos = peta.get(kunci)
            if pos is None or pos >= len(r):
                return None
            nilai = r[pos]
            return None if nilai is None else str(nilai).strip()

        ditambah = diperbarui = 0
        tolak: list[dict] = []
        dilihat: dict[str, int] = {}
        data = [r for r in baris_semua[idx_header + 1:]
                if any(x not in (None, "") for x in r)]
        if len(data) > BATAS_IMPOR:
            raise HTTPException(422, f"File berisi {len(data)} baris, melebihi "
                                     f"batas {BATAS_IMPOR} baris sekali unggah. "
                                     "Pecah filenya lalu unggah bertahap.")

        for no, r in enumerate(data, start=idx_header + 2):
            kode = _kode_baku(ambil(r, "kode") or "")
            nama_baku = _bersih(ambil(r, "nama"))
            if not kode:
                tolak.append({"baris": no, "kode": None,
                              "alasan": "Kode_Vendor kosong."})
                continue
            if not POLA_KODE.match(kode):
                tolak.append({"baris": no, "kode": kode,
                              "alasan": "Kode mengandung karakter tidak "
                                        "diizinkan atau lebih dari 20 karakter."})
                continue
            if not nama_baku:
                tolak.append({"baris": no, "kode": kode,
                              "alasan": "Nama_Baku kosong."})
                continue
            if kode in dilihat:
                tolak.append({"baris": no, "kode": kode,
                              "alasan": f"Kode ganda di file (sudah dipakai baris "
                                        f"{dilihat[kode]}); baris ini diabaikan."})
                continue
            status_teks = (ambil(r, "status") or "").strip().lower()
            if status_teks and status_teks not in STATUS_BAKU:
                tolak.append({"baris": no, "kode": kode,
                              "alasan": f"Status '{status_teks}' tidak dikenal "
                                        f"(aktif/nonaktif/diblokir)."})
                continue
            try:
                klasifikasi = bakukan_klasifikasi(ambil(r, "klasifikasi"))
            except ValueError as e:
                tolak.append({"baris": no, "kode": kode, "alasan": str(e)})
                continue
            dilihat[kode] = no
            v = session.get(Vendor, kode)
            if v is None:
                v = Vendor(kode=kode)
                session.add(v)
                ditambah += 1
            else:
                diperbarui += 1
            v.nama_baku = nama_baku
            v.varian_nama = _bersih(ambil(r, "varian"))
            if peta.get("kategori") is not None:
                v.kategori = _bersih(ambil(r, "kategori"))
            # Alamat/kontak/klasifikasi: kosong = jangan ubah (sama seperti
            # Kategori), supaya file yang hanya berisi kode+nama tidak
            # menghapus profil yang sudah diisi lewat layar.
            if peta.get("alamat") is not None and _bersih(ambil(r, "alamat")):
                v.alamat = _bersih(ambil(r, "alamat"))
            if peta.get("kontak") is not None and _bersih(ambil(r, "kontak")):
                v.kontak_person = _bersih(ambil(r, "kontak"))
            if peta.get("klasifikasi") is not None and klasifikasi:
                v.klasifikasi = klasifikasi
            v.status = status_teks or (v.status or "aktif")
            session.flush()

        catat_audit(session, pengisi, "impor", "vendor", {
            "nama_file": nama, "ditambah": ditambah, "diperbarui": diperbarui,
            "ditolak": len(tolak), "kode": sorted(dilihat)})
        session.commit()
        return {
            "status": "selesai",
            "nama_file": nama,
            "ditambah": ditambah,
            "diperbarui": diperbarui,
            "ditolak": len(tolak),
            "jumlah_baris": len(data),
            "peringatan": tolak[:BATAS_LAPORAN],
            "pesan": (f"{ditambah} vendor baru, {diperbarui} diperbarui"
                      + (f", {len(tolak)} baris ditolak" if tolak else "")
                      + ". Kode yang sudah ada diperbarui, bukan digandakan."),
        }

    # Catatan urutan: route dengan path tetap (/vendor/template) HARUS
    # didaftarkan sebelum /vendor/{kode}; kalau tidak, "template" akan
    # dianggap kode vendor dan unduhan template menjawab 404.
    @router.get("/vendor/{kode}")
    def detail_vendor(kode: str, session: Session = dep):
        v = session.get(Vendor, _kode_baku(kode))
        if not v:
            raise HTTPException(404, f"Vendor '{_kode_baku(kode)}' tidak ada.")
        return _baris_vendor(session, v)

    app.include_router(router)
