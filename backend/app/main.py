"""API OP Margin (Fase 2): input cepat harian SICOM & kurs + riwayat.

- Backend hanya mendengarkan 127.0.0.1 (lihat CARA_MENJALANKAN).
- Setiap input manual dicatat sebagai "unggahan" di lapisan raw supaya
  setiap angka tetap bisa ditelusuri asal-usulnya.
- Mart dibangun ulang otomatis setelah setiap perubahan.
- Login memakai username + sandi (tabel pengguna); pembatasan peran
  admin/pengguna ada di api_fase4/api_database.
"""
from __future__ import annotations

import pathlib

from dotenv import load_dotenv

# Baca backend/.env SEBELUM konfigurasi apa pun dibaca. Variabel yang sudah
# ada di lingkungan (mis. di-set service/OS) TIDAK ditimpa.
load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

import datetime as dt
import sys
import hashlib
import json
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from . import versi
from .auth import KonfigurasiAuth
from .core.alarm import evaluasi_alarm
from .core.kualitas import data_terlambat
from .core.lookup import kurs_pada, sicom_pada
from .core.skema import pastikan_kolom_baru
from .db import buat_engine, buat_session_factory
from .mart import bangun_mart
from .models import (Base, Grade, Kurs, MartHarian, Pembelian, RawBaris,
                     RawUnggahan, Sicom, Stok, Vendor)

import os


# ----------------------------------------------------------------------------
# Skema (Pydantic v2)
# ----------------------------------------------------------------------------
class SicomMasuk(BaseModel):
    tanggal: dt.date
    usc_per_kg: float = Field(gt=0, lt=10000,
                              description="Harga TSR20 dalam US¢/kg, contoh 181.7")
    kontrak: str | None = None  # [TERBUKA] kontrak boleh kosong
    catatan: str | None = None
    pengisi: str = "?"


class KursMasuk(BaseModel):
    berlaku_dari: dt.date
    idr_per_usd: float = Field(gt=0, lt=1_000_000,
                               description="Kurs IDR per USD, contoh 16644")
    catatan: str | None = None
    pengisi: str = "?"


class StokMasuk(BaseModel):
    """Satu angka stok untuk satu tanggal (total atau per grade)."""
    tanggal: dt.date
    item_code: str = ""          # "" = total; selain itu kode grade
    stok_kg: float = Field(gt=0, lt=10**12, description="Stok dalam kg")
    catatan: str | None = None
    pengisi: str = "?"


class PembelianMasuk(BaseModel):
    """Amount pembelian satu tanggal (total / per grade / per vendor / per tiket)."""
    tanggal: dt.date
    item_code: str = "ALL"
    kode_vendor: str = ""
    ticket_no: str = ""
    qty_kering_kg: float = Field(gt=0, lt=10**12)
    amount_rp: float = Field(ge=0, lt=10**15)
    catatan: str | None = None
    pengisi: str = "?"


def _info_proses() -> dict:
    """Folder kerja & PID proses API yang sedang menjawab.

    Dipakai layar "beda versi" di tampilan web: bila API yang menjawab
    ternyata dijalankan dari folder lain (proses lama), folder itulah yang
    harus ditutup. Aman: hanya untuk diagnosis di komputer sendiri.
    """
    import os

    from . import versi as _versi
    sekarang = dt.datetime.now(dt.timezone.utc)
    mulai = None
    try:  # waktu proses python ini dimulai
        import time as _time
        mulai = dt.datetime.fromtimestamp(
            _time.time() - _time.monotonic(), dt.timezone.utc
        ).isoformat(timespec="seconds")
    except Exception:
        mulai = sekarang.isoformat(timespec="seconds")
    return {"folder": str(_versi.AKAR), "pid": os.getpid(), "mulai": mulai}


def _catat_input_manual(session: Session, jenis: str, isi: dict, pengisi: str) -> int:
    """Catat input manual ke lapisan raw (jejak: siapa, kapan, apa)."""
    payload = json.dumps(isi, default=str, ensure_ascii=False, sort_keys=True)
    sha = hashlib.sha256(
        f"{jenis}|{payload}|{dt.datetime.utcnow().isoformat()}".encode()).hexdigest()
    unggahan = RawUnggahan(nama_file=f"input-manual:{jenis}", sha256=sha,
                           pengunggah=pengisi)
    session.add(unggahan)
    session.flush()
    session.add(RawBaris(unggahan_id=unggahan.id, sheet=jenis, baris_ke=1, isi=payload))
    return unggahan.id


# ----------------------------------------------------------------------------
# Aplikasi
# ----------------------------------------------------------------------------
def buat_app(engine: Engine | None = None) -> FastAPI:
    # --- keamanan: validasi konfigurasi SEBELUM aplikasi hidup -------------
    cfg_auth = KonfigurasiAuth()
    cfg_auth.validasi_start()  # menolak start bila produksi salah konfigurasi

    engine = engine or buat_engine()
    Base.metadata.create_all(engine)
    # Database yang sudah ada tidak ikut berubah lewat create_all: tambahkan
    # kolom baru (mis. profil vendor) tanpa menyentuh data lama.
    pastikan_kolom_baru(engine)
    SessionLocal = buat_session_factory(engine)

    # Di produksi, halaman dokumentasi otomatis dimatikan.
    app = FastAPI(title="OP Margin API", version=versi.VERSI,
                  docs_url=None if cfg_auth.produksi else "/docs",
                  redoc_url=None,
                  openapi_url=None if cfg_auth.produksi else "/openapi.json")

    # CORS ketat: hanya domain frontend dari .env (kosong = tanpa CORS,
    # karena frontend dev memakai proxy satu-origin).
    origins = [o for o in os.environ.get("FRONTEND_ORIGIN", "").split(",") if o]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins,
                           allow_credentials=True,
                           allow_methods=["GET", "POST", "PUT", "DELETE"],
                           allow_headers=["Content-Type"])

    # --- login: username + sandi (satu-satunya cara masuk) -------------------
    if cfg_auth.lokal_aktif:
        from .auth_lokal import pasang_middleware_lokal, pastikan_admin
        pasang_middleware_lokal(app, cfg_auth)
        with SessionLocal() as _s:
            if pastikan_admin(_s):
                _s.commit()
    else:
        print("PERINGATAN: login DIMATIKAN (AUTH_DISABLED=true, mode "
              "pengembangan). Jangan dipakai di produksi.")

    def ambil_session():
        with SessionLocal() as session:
            yield session

    # Rute analisis Fase 3 (ringkasan, rekonsiliasi, kualitas, kartu, telusur)
    from .api_analisis import pasang_router
    pasang_router(app, ambil_session)

    from .api_jelaskan import pasang_router as pasang_jelaskan
    pasang_jelaskan(app, ambil_session)

    # Rute Fase 4 (stok, aturan, simulasi, perencanaan, alarm, audit)
    from .api_fase4 import pasang_router_fase4
    pasang_router_fase4(app, ambil_session)

    # Rute Fase 6 (unggah file data lewat web)
    from .api_unggah import pasang_router_unggah
    pasang_router_unggah(app, ambil_session)

    # Rute Fase 7 (master grade & harga per grade)
    from .api_grade import pasang_router_grade
    pasang_router_grade(app, ambil_session)

    # Rute Fase 8 (master vendor: CRUD + template + impor massal)
    from .api_vendor import pasang_router_vendor
    pasang_router_vendor(app, ambil_session)

    # Rute modul Database (info, kosongkan, ekspor, impor)
    from .api_database import pasang_router_database
    pasang_router_database(app, ambil_session, engine)

    # Rute login/sesi/kelola pengguna (selalu terpasang; perilaku
    # menyesuaikan mode auth di .env)
    from .auth_lokal import pasang_router_auth
    pasang_router_auth(app, ambil_session, cfg_auth)

    @app.exception_handler(RequestValidationError)
    async def validasi_gagal(request: Request, exc: RequestValidationError):
        """Pesan error validasi dalam Bahasa Indonesia yang ramah."""
        pesan = []
        for e in exc.errors():
            kolom = ".".join(str(x) for x in e["loc"] if x != "body")
            tipe = e["type"]
            if "date" in tipe:
                pesan.append(f"Kolom '{kolom}': tanggal tidak valid. "
                             "Pakai pemilih tanggal atau format yyyy-mm-dd.")
            elif "greater_than" in tipe:
                pesan.append(f"Kolom '{kolom}': angka harus lebih dari 0.")
            elif "less_than" in tipe:
                pesan.append(f"Kolom '{kolom}': angka terlalu besar; cek lagi, "
                             "mungkin salah ketik.")
            elif tipe == "missing":
                pesan.append(f"Kolom '{kolom}' wajib diisi.")
            else:
                pesan.append(f"Kolom '{kolom}': nilai tidak valid ({e['msg']}).")
        return JSONResponse(status_code=422, content={"detail": " ".join(pesan)})

    @app.get("/api/sehat")
    def sehat():
        return {"status": "ok"}

    @app.get("/api/health")
    def health():
        """Pemeriksaan hidup + daftar fitur yang dikenal proses ini.

        Berguna untuk mendiagnosis "backend masih versi lama": bila fitur
        tidak ada di daftar, berarti proses yang berjalan adalah kode lama
        (mis. jendela API lama belum ditutup sehingga port 8000 dipakai ulang).
        TANPA data sensitif.
        """
        from .auth import info_mode
        # pid/folder/mulai dipakai untuk mengenali proses API yang MENJAWAB:
        # bila versinya beda dengan folder aplikasi, layar "beda versi"
        # menampilkan folder & PID-nya supaya bisa ditutup dengan tepat.
        proses = _info_proses()
        return {"status": "ok", "app": "op-margin", "versi": versi.VERSI,
                "login": info_mode(cfg_auth),
                "waktu": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "fitur": [
                    "ringkasan", "telusur", "margin-elemen", "5w1h",
                    "margin-bridge", "days-of-cover", "jelaskan",
                    "margin-bulanan-periode", "ekspor-xlsx",
                    "penerimaan-tren", "penerimaan-komposisi",
                    "alarm-tindakan", "stok-margin-panduan",
                    "input-harian", "input-stok", "input-pembelian",
                    "unggah-pratinjau", "unggah-mismatch-xlsx",
                    "vendor-profil",
                ],
                # versi kode ikut dilaporkan supaya mudah membandingkan
                # folder yang dijalankan dengan kode terbaru di repo
                "kode": versi.versi_folder(),
                "folder": proses["folder"], "pid": proses["pid"],
                "mulai": proses["mulai"],
                # None = tampilan web tidak disajikan dari API (mode terpisah).
                # Berisi folder bila mode satu-origin aktif (SAJIKAN_WEB=true).
                "web_statistik": getattr(app.state, "web_statistik", None)}

    # ------------------------------------------------------------ SICOM
    @app.get("/api/sicom")
    def riwayat_sicom(limit: int = 15, session: Session = Depends(ambil_session)):
        baris = session.scalars(
            select(Sicom).order_by(Sicom.tanggal.desc()).limit(min(limit, 100)))
        return [{"tanggal": s.tanggal.isoformat(), "usc_per_kg": s.usc_per_kg,
                 "kontrak": s.kontrak, "sumber": s.sumber, "catatan": s.catatan}
                for s in baris]

    @app.post("/api/sicom")
    def simpan_sicom(data: SicomMasuk, session: Session = Depends(ambil_session)):
        if data.tanggal > dt.date.today() + dt.timedelta(days=1):
            raise HTTPException(422, "Tanggal SICOM tidak boleh jauh di masa depan. "
                                     "Cek lagi tanggalnya.")
        lama = session.get(Sicom, data.tanggal)
        nilai_lama = lama.usc_per_kg if lama else None

        unggahan_id = _catat_input_manual(session, "sicom", data.model_dump(), data.pengisi)
        s = lama or Sicom(tanggal=data.tanggal, usc_per_kg=data.usc_per_kg)
        s.usc_per_kg = data.usc_per_kg
        s.kontrak = data.kontrak
        s.sumber = f"input manual ({data.pengisi})"
        s.catatan = data.catatan
        s.unggahan_id = unggahan_id
        session.merge(s)
        session.flush()
        bangun_mart(session)
        evaluasi_alarm(session)
        session.commit()
        return {"status": "tersimpan", "tanggal": data.tanggal.isoformat(),
                "usc_per_kg": data.usc_per_kg, "nilai_sebelumnya": nilai_lama,
                "pesan": ("Nilai lama {:.2f} diganti menjadi {:.2f}.".format(
                    nilai_lama, data.usc_per_kg) if nilai_lama is not None
                    else "Harga SICOM baru tersimpan.")}

    # ------------------------------------------------------------ Kurs
    @app.get("/api/kurs")
    def riwayat_kurs(limit: int = 15, session: Session = Depends(ambil_session)):
        baris = session.scalars(
            select(Kurs).order_by(Kurs.berlaku_dari.desc()).limit(min(limit, 100)))
        return [{"berlaku_dari": k.berlaku_dari.isoformat(),
                 "idr_per_usd": float(k.idr_per_usd),
                 "sumber": k.sumber, "catatan": k.catatan} for k in baris]

    @app.get("/api/kurs/berlaku")
    def kurs_berlaku(tanggal: dt.date, session: Session = Depends(ambil_session)):
        """Kurs yang berlaku pada tanggal itu: baris terbaru dengan
        berlaku_dari <= tanggal."""
        k = kurs_pada(session, tanggal)
        if k is None:
            raise HTTPException(404, f"Belum ada kurs yang berlaku untuk "
                                     f"{tanggal.strftime('%d/%m/%Y')}.")
        return {"tanggal": tanggal.isoformat(),
                "berlaku_dari": k.berlaku_dari.isoformat(),
                "idr_per_usd": float(k.idr_per_usd)}

    @app.post("/api/kurs")
    def simpan_kurs(data: KursMasuk, session: Session = Depends(ambil_session)):
        lama = session.get(Kurs, data.berlaku_dari)
        nilai_lama = float(lama.idr_per_usd) if lama else None

        unggahan_id = _catat_input_manual(session, "kurs", data.model_dump(), data.pengisi)
        k = lama or Kurs(berlaku_dari=data.berlaku_dari, idr_per_usd=data.idr_per_usd)
        k.idr_per_usd = data.idr_per_usd
        k.sumber = f"input manual ({data.pengisi})"
        k.catatan = data.catatan
        k.unggahan_id = unggahan_id
        session.merge(k)
        session.flush()
        bangun_mart(session)
        evaluasi_alarm(session)
        session.commit()
        return {"status": "tersimpan", "berlaku_dari": data.berlaku_dari.isoformat(),
                "idr_per_usd": data.idr_per_usd, "nilai_sebelumnya": nilai_lama,
                "pesan": ("Nilai lama {:,.0f} diganti menjadi {:,.0f}.".format(
                    nilai_lama, data.idr_per_usd) if nilai_lama is not None
                    else "Kurs baru tersimpan, berlaku sejak tanggal itu.")}

    # ------------------------------------------------------------ input harian
    @app.get("/api/input-harian")
    def ringkas_input_harian(hari: int = 7, session: Session = Depends(ambil_session)):
        """Bahan panel "kesegaran data" di halaman Input Harian.

        Isinya: umur tiap sumber, angka terakhir yang bisa dipakai sebagai
        isian awal, tanggal terakhir yang belum punya stok/pembelian, dan
        riwayat singkat supaya pengguna tahu apa yang sudah masuk.
        """
        hari = max(1, min(hari, 31))
        hari_ini = dt.date.today()

        wajib = {"SICOM": True, "Kurs": False, "Stok": True,
                 "Pembelian": True, "Tiket": True}
        sumber = data_terlambat(session)
        for x in sumber:
            x["wajib_harian"] = wajib.get(x["sumber"], True)

        m = session.scalars(select(MartHarian)
                            .where(MartHarian.stok_kg != None)  # noqa: E711
                            .order_by(MartHarian.tanggal.desc())).first()
        stok_terakhir = None if m is None else {
            "tanggal": m.tanggal.isoformat(),
            "stok_ton": m.stok_ton, "safety_ton": m.safety_ton,
            "days": m.days, "rasio_stok": m.rasio_stok,
        }
        sc = session.scalars(select(Sicom).order_by(Sicom.tanggal.desc())).first()
        k = session.scalars(select(Kurs).order_by(Kurs.berlaku_dari.desc())).first()

        rentang = [hari_ini - dt.timedelta(days=i) for i in range(hari - 1, -1, -1)]
        ada_stok = {t for (t,) in session.execute(select(Stok.tanggal).distinct())}
        ada_beli = {t for (t,) in session.execute(select(Pembelian.tanggal).distinct())}

        riwayat_stok = [{
            "tanggal": r.tanggal.isoformat(), "item_code": r.item_code,
            "stok_kg": float(r.stok_kg),
        } for r in session.scalars(select(Stok).order_by(
            Stok.tanggal.desc(), Stok.item_code).limit(5))]

        riwayat_beli = []
        for b in session.scalars(select(Pembelian).order_by(
                Pembelian.tanggal.desc(), Pembelian.id.desc()).limit(5)):
            qty = float(b.qty_kering_kg) or 0.0
            riwayat_beli.append({
                "tanggal": b.tanggal.isoformat(), "item_code": b.item_code,
                "kode_vendor": b.kode_vendor, "ticket_no": b.ticket_no,
                "qty_kering_kg": qty, "amount_rp": float(b.amount_rp),
                "harga_rp_per_kg": round(float(b.amount_rp) / qty, 2) if qty else None,
            })

        return {
            "hari_ini": hari_ini.isoformat(),
            "hari_dicek": hari,
            "sumber": sumber,
            "stok_terakhir": stok_terakhir,
            "sicom_terakhir": None if sc is None else {
                "tanggal": sc.tanggal.isoformat(), "usc_per_kg": sc.usc_per_kg},
            "kurs_terakhir": None if k is None else {
                "berlaku_dari": k.berlaku_dari.isoformat(),
                "idr_per_usd": float(k.idr_per_usd)},
            "tanggal_kosong": {
                "stok": [d.isoformat() for d in rentang if d not in ada_stok],
                "pembelian": [d.isoformat() for d in rentang if d not in ada_beli],
            },
            "riwayat_stok": riwayat_stok,
            "riwayat_pembelian": riwayat_beli,
        }

    @app.post("/api/stok")
    def simpan_stok(data: StokMasuk, session: Session = Depends(ambil_session)):
        """Simpan satu angka stok harian (total atau per grade).

        Menimpa baris dengan tanggal + jenis yang sama (koreksi tercatat di
        lapisan raw & audit), lalu membangun ulang mart dan alarm.
        """
        if data.tanggal > dt.date.today() + dt.timedelta(days=1):
            raise HTTPException(422, "Tanggal stok tidak boleh jauh di masa depan. "
                                     "Cek lagi tanggalnya.")
        kode = (data.item_code or "").strip()
        if kode and session.get(Grade, kode) is None:
            raise HTTPException(422, f"Grade '{kode}' belum ada di Master Grade. "
                                     "Tambahkan dulu di menu Grade & Harga.")

        # Jangan campur "total" dan "per grade" pada tanggal yang sama:
        # mart menjumlahkan semua baris stok per tanggal (bisa dobel).
        lain = [r for r in session.scalars(
            select(Stok).where(Stok.tanggal == data.tanggal)) if r.item_code != kode]
        if lain:
            jenis_lain = "total" if any(r.item_code == "" for r in lain) else "per grade"
            raise HTTPException(422, f"Tanggal {data.tanggal.strftime('%d/%m/%Y')} sudah "
                                     f"berisi stok {jenis_lain}. Pakai jenis yang sama "
                                     "supaya stok tidak terhitung dua kali.")

        lama = session.scalar(select(Stok).where(Stok.tanggal == data.tanggal,
                                                 Stok.item_code == kode))
        nilai_lama = float(lama.stok_kg) if lama else None

        unggahan_id = _catat_input_manual(session, "stok", data.model_dump(), data.pengisi)
        s = lama or Stok(tanggal=data.tanggal, item_code=kode, stok_kg=Decimal(0))
        # Decimal, bukan float: mart menjumlahkan kolom Numeric dan menolak
        # campuran float/Decimal (bug ini tertangkap tes).
        s.stok_kg = Decimal(str(data.stok_kg))
        s.catatan = data.catatan
        s.unggahan_id = unggahan_id
        session.add(s)
        session.flush()
        bangun_mart(session)
        evaluasi_alarm(session)
        session.commit()

        m = session.scalar(select(MartHarian).where(MartHarian.tanggal == data.tanggal))
        return {
            "status": "tersimpan", "tanggal": data.tanggal.isoformat(),
            "item_code": kode, "stok_kg": data.stok_kg,
            "nilai_sebelumnya": nilai_lama,
            "ringkasan": None if m is None else {
                "stok_ton": m.stok_ton, "safety_ton": m.safety_ton,
                "days": m.days, "rasio_stok": m.rasio_stok,
            },
            "pesan": (f"Stok {data.tanggal.strftime('%d/%m/%Y')} diperbarui"
                      f" (sebelumnya {nilai_lama:,.0f} kg)."
                      if nilai_lama is not None else
                      f"Stok {data.tanggal.strftime('%d/%m/%Y')} tersimpan."),
        }

    @app.post("/api/pembelian")
    def simpan_pembelian(data: PembelianMasuk,
                         session: Session = Depends(ambil_session)):
        """Simpan Amount pembelian satu tanggal (harga beli dihitung otomatis)."""
        if data.tanggal > dt.date.today() + dt.timedelta(days=1):
            raise HTTPException(422, "Tanggal pembelian tidak boleh jauh di masa depan. "
                                     "Cek lagi tanggalnya.")
        grade = (data.item_code or "ALL").strip() or "ALL"
        vendor = (data.kode_vendor or "").strip()
        tiket = (data.ticket_no or "").strip()
        if grade != "ALL" and session.get(Grade, grade) is None:
            raise HTTPException(422, f"Grade '{grade}' belum ada di Master Grade.")
        if vendor and session.get(Vendor, vendor) is None:
            raise HTTPException(422, f"Vendor '{vendor}' belum ada di Master Vendor.")

        # Granularitas: mart memakai baris rinci bila ada, jadi mencampur
        # "ALL" dengan baris rinci pada tanggal yang sama bikin angka kacau.
        ada = list(session.scalars(select(Pembelian).where(
            Pembelian.tanggal == data.tanggal)))
        kunci_baru = (grade, vendor, tiket)
        for b in ada:
            if ((b.item_code, b.kode_vendor, b.ticket_no) == kunci_baru):
                continue
            if b.item_code == "ALL" and grade != "ALL":
                raise HTTPException(422, "Tanggal ini sudah punya pembelian TOTAL. "
                                         "Kosongkan/ubah baris total itu dulu, atau "
                                         "pakai tingkat 'Total hari'.")
            if b.item_code != "ALL" and grade == "ALL":
                raise HTTPException(422, "Tanggal ini sudah punya pembelian rinci "
                                         "(per grade/vendor/tiket). Jangan tambah "
                                         "baris TOTAL pada tanggal yang sama.")

        lama = session.scalar(select(Pembelian).where(
            Pembelian.tanggal == data.tanggal, Pembelian.item_code == grade,
            Pembelian.kode_vendor == vendor, Pembelian.ticket_no == tiket))
        lama_dict = None if lama is None else {
            "qty_kering_kg": float(lama.qty_kering_kg),
            "amount_rp": float(lama.amount_rp)}

        unggahan_id = _catat_input_manual(session, "pembelian", data.model_dump(),
                                          data.pengisi)
        b = lama or Pembelian(tanggal=data.tanggal, item_code=grade,
                              kode_vendor=vendor, ticket_no=tiket,
                              qty_kering_kg=Decimal(0), amount_rp=Decimal(0))
        b.qty_kering_kg = Decimal(str(data.qty_kering_kg))
        b.amount_rp = Decimal(str(data.amount_rp))
        b.unggahan_id = unggahan_id
        session.add(b)
        session.flush()
        bangun_mart(session)
        evaluasi_alarm(session)
        session.commit()

        k = kurs_pada(session, data.tanggal)
        sc = sicom_pada(session, data.tanggal)
        harga_rp = data.amount_rp / data.qty_kering_kg
        harga_usc = (harga_rp / float(k.idr_per_usd) / 100
                     if k is not None else None)
        margin = (sc.usc_per_kg - harga_usc
                  if (sc is not None and harga_usc is not None) else None)
        return {
            "status": "tersimpan", "tanggal": data.tanggal.isoformat(),
            "item_code": grade, "kode_vendor": vendor, "ticket_no": tiket,
            "qty_kering_kg": data.qty_kering_kg, "amount_rp": data.amount_rp,
            "harga_rp_per_kg": round(harga_rp, 2),
            "harga_usc_per_kg": None if harga_usc is None else round(harga_usc, 4),
            "kurs": None if k is None else float(k.idr_per_usd),
            "sicom_usc": None if sc is None else sc.usc_per_kg,
            "margin_usc": None if margin is None else round(margin, 4),
            "nilai_sebelumnya": lama_dict,
            "pesan": ("Pembelian tanggal ini diperbarui." if lama_dict is not None
                      else "Pembelian tersimpan, harga beli dihitung otomatis."),
        }

    # --- (opsional) sajikan tampilan web dari API: satu-origin ---------------
    # Diperlukan bila aplikasi diakses lewat SATU hostname Cloudflare Tunnel
    # (mis. app.domain-anda.com) tanpa Cloudflare Pages. Keuntungannya:
    # tampilan web dan API satu situs, sehingga cookie sesi selalu terkirim
    # dan tidak perlu CORS / COOKIE_SAMESITE=none.
    _pasang_web_statistik(app, cfg_auth)

    return app


def _pasang_web_statistik(app: FastAPI, cfg_auth: KonfigurasiAuth) -> None:
    """Pasang `frontend/dist` sebagai berkas statis di akar aplikasi.

    Hanya aktif bila SAJIKAN_WEB=true. Bila foldernya belum ada (belum
    `npm run build`), aplikasi TETAP hidup dan hanya memberi peringatan —
    API tidak boleh mati gara-gara tampilan belum di-build.
    """
    if os.environ.get("SAJIKAN_WEB", "").strip().lower() not in ("1", "true", "ya"):
        return
    from fastapi.staticfiles import StaticFiles

    folder = pathlib.Path(os.environ.get("SAJIKAN_WEB_FOLDER", "").strip()
                          or pathlib.Path(__file__).resolve().parents[2]
                          / "frontend" / "dist")
    if not (folder / "index.html").is_file():
        sys.stderr.write(
            f"PERINGATAN: SAJIKAN_WEB=true tetapi {folder} belum berisi "
            "index.html. Jalankan 'npm run build' di folder frontend, "
            "atau isi SAJIKAN_WEB_FOLDER. API tetap berjalan.\n")
        return
    app.mount("/", StaticFiles(directory=str(folder), html=True), name="web")
    # Dicatat supaya diagnosa bisa memastikan mode satu-origin benar-benar aktif.
    app.state.web_statistik = str(folder)


# Instance untuk uvicorn: "app.main:app"
app = buat_app()
