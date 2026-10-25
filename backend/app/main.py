"""API OP Margin (Fase 2): input cepat harian SICOM & kurs + riwayat.

- Backend hanya mendengarkan 127.0.0.1 (lihat CARA_MENJALANKAN).
- Setiap input manual dicatat sebagai "unggahan" di lapisan raw supaya
  setiap angka tetap bisa ditelusuri asal-usulnya.
- Mart dibangun ulang otomatis setelah setiap perubahan.
- Peran/Cloudflare Access menyusul di fase keamanan; pembatasan peran
  belum aktif di fase ini.
"""
from __future__ import annotations

import pathlib

from dotenv import load_dotenv

# Baca backend/.env SEBELUM konfigurasi apa pun dibaca. Variabel yang sudah
# ada di lingkungan (mis. di-set service/OS) TIDAK ditimpa.
load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

import datetime as dt
import hashlib
import json

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from . import versi
from .auth import JALUR_BEBAS, KonfigurasiAuth, VerifikatorAccess
from .core.alarm import evaluasi_alarm
from .core.lookup import kurs_pada
from .db import buat_engine, buat_session_factory
from .mart import bangun_mart
from .models import Base, Kurs, RawBaris, RawUnggahan, Sicom

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


def _dibuka_dari_komputer_sendiri(request: Request) -> bool:
    """True bila permintaan datang dari browser di komputer yang sama
    (localhost / 127.0.0.1). Dipakai untuk memberi petunjuk yang tepat saat
    mode login tidak cocok dengan cara aplikasi dibuka."""
    host = (request.url.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    klien = request.client.host if request.client else ""
    return klien in ("127.0.0.1", "::1", "localhost")


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
                           allow_methods=["GET", "POST"],
                           allow_headers=["Content-Type"])

    # --- login lokal (form sendiri, data pengguna di database) --------------
    if cfg_auth.lokal_aktif:
        from .auth_lokal import pasang_middleware_lokal, pastikan_admin
        pasang_middleware_lokal(app, cfg_auth)
        with SessionLocal() as _s:
            if pastikan_admin(_s):
                _s.commit()
    # --- verifikasi Cloudflare Access ---------------------------------------
    elif cfg_auth.aktif:
        import jwt as _jwt

        verifikator = VerifikatorAccess(cfg_auth)

        @app.middleware("http")
        async def wajib_login(request: Request, call_next):
            jalur = request.url.path
            if not jalur.startswith("/api") or jalur in JALUR_BEBAS:
                return await call_next(request)
            token = request.headers.get("Cf-Access-Jwt-Assertion") \
                or request.cookies.get("CF_Authorization")
            if not token:
                pesan = ("Belum login. Akses halaman lewat alamat resmi "
                         "aplikasi (Cloudflare Access) lalu masuk dengan "
                         "email kantor Anda.")
                if _dibuka_dari_komputer_sendiri(request) and not cfg_auth.produksi:
                    pesan += (" CATATAN: proses API ini berjalan di komputer "
                              "Anda sendiri dengan mode login Cloudflare "
                              "Access, dan Access tidak bisa dipakai di "
                              "localhost. Untuk memakai aplikasi di komputer "
                              "ini, isi backend/.env dengan AUTH_MODE=lokal "
                              "(lihat backend/.env.example) lalu jalankan "
                              "ulang API.")
                return JSONResponse(status_code=401, content={"detail": pesan})
            try:
                klaim = verifikator.verifikasi(token)
            except _jwt.ExpiredSignatureError:
                return JSONResponse(status_code=401, content={
                    "detail": "Sesi login sudah kedaluwarsa. Muat ulang halaman "
                              "untuk login kembali."})
            except _jwt.PyJWTError:
                return JSONResponse(status_code=401, content={
                    "detail": "Token login tidak sah. Muat ulang halaman; bila "
                              "masih gagal hubungi admin."})
            request.state.email = klaim.get("email")
            return await call_next(request)
    elif not cfg_auth.produksi:
        if cfg_auth.aktif:
            print("PERINGATAN: mode login Cloudflare Access AKTIF di luar "
                  "produksi. Access hanya bekerja lewat domain yang dilindungi "
                  "Cloudflare, jadi di localhost semua halaman akan muncul "
                  "'Belum login'. Untuk pemakaian di komputer sendiri, isi "
                  "backend/.env dengan AUTH_MODE=lokal (lihat "
                  "backend/.env.example) lalu jalankan ulang API.")
        else:
            print("PERINGATAN: autentikasi NONAKTIF (mode development). "
                  "Jangan dipakai di produksi.")

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
        return {"status": "ok", "app": "op-margin", "versi": versi.VERSI,
                "login": info_mode(cfg_auth),
                "waktu": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "fitur": [
                    "ringkasan", "telusur", "margin-elemen", "5w1h",
                    "margin-bridge", "days-of-cover", "jelaskan",
                    "margin-bulanan-periode", "ekspor-xlsx",
                ],
                # versi kode ikut dilaporkan supaya mudah membandingkan
                # folder yang dijalankan dengan kode terbaru di repo
                "kode": versi.versi_folder()}

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

    return app


app = buat_app()
