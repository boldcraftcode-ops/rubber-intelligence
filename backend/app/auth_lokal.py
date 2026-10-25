"""Login lokal: form username+sandi, data pengguna di tabel `pengguna`.

Dipakai bila AUTH_MODE=lokal di .env (pengganti Cloudflare Access).

Cara kerja:
- POST /api/auth/login memverifikasi sandi (PBKDF2-SHA256) lalu menanam
  cookie sesi HttpOnly berisi JWT (ditandatangani SECRET_KEY, HS256).
- Middleware memeriksa cookie itu di setiap permintaan /api/* kecuali
  jalur bebas (health, login).
- Peran: "admin" boleh kelola pengguna + aksi berbahaya modul Database;
  "pengguna" hanya memakai aplikasi.
- Akun pertama dibuat otomatis: admin / admin123 — WAJIB segera diganti.

Keamanan:
- SECRET_KEY minimal 32 karakter; di produksi aplikasi menolak start bila
  kosong/pendek (gagal-tertutup, konsisten dengan mode Access).
- Hash sandi PBKDF2-SHA256 240.000 iterasi + salt acak per pengguna.
- Jeda 0,5 dtk pada login gagal (menghambat tebak-tebakan massal) dan
  setiap percobaan tercatat di audit log.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import secrets
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.alarm import catat_audit
from .models import Pengguna

COOKIE_SESI = "op_sesi"
SESI_JAM = 12  # masa berlaku sesi (jam)
JALUR_BEBAS_LOKAL = ("/api/health", "/api/sehat", "/api/auth/login",
                     "/api/auth/mode")

_ITERASI = 240_000


# ----------------------------------------------------------------------------
# Hash sandi (PBKDF2-SHA256, pustaka standar — tanpa dependensi baru)
# ----------------------------------------------------------------------------
def hash_sandi(sandi: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", sandi.encode(), bytes.fromhex(salt), _ITERASI)
    return f"pbkdf2${_ITERASI}${salt}${h.hex()}"


def cek_sandi(sandi: str, tersimpan: str) -> bool:
    try:
        _, iterasi, salt, target = tersimpan.split("$")
        h = hashlib.pbkdf2_hmac("sha256", sandi.encode(),
                                bytes.fromhex(salt), int(iterasi))
        return hmac.compare_digest(h.hex(), target)
    except (ValueError, TypeError):
        return False


# ----------------------------------------------------------------------------
# Token sesi (JWT di cookie HttpOnly)
# ----------------------------------------------------------------------------
def _buat_token(p: Pengguna, secret: str) -> str:
    kini = dt.datetime.now(dt.timezone.utc)
    return jwt.encode({
        "sub": p.username, "nama": p.nama, "peran": p.peran,
        "iat": kini, "exp": kini + dt.timedelta(hours=SESI_JAM),
    }, secret, algorithm="HS256")


def _baca_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"],
                      options={"require": ["exp", "sub"]})


def _pasang_cookie(response: Response, token: str, produksi: bool) -> None:
    response.set_cookie(
        COOKIE_SESI, token, max_age=SESI_JAM * 3600, httponly=True,
        samesite="lax",  # frontend & api satu site (subdomain sama) -> aman
        secure=produksi, path="/")


# ----------------------------------------------------------------------------
# Middleware
# ----------------------------------------------------------------------------
def pasang_middleware_lokal(app, cfg) -> None:
    from fastapi.responses import JSONResponse

    @app.middleware("http")
    async def wajib_login_lokal(request: Request, call_next):
        jalur = request.url.path
        if not jalur.startswith("/api") or jalur in JALUR_BEBAS_LOKAL:
            return await call_next(request)
        token = request.cookies.get(COOKIE_SESI)
        if not token:
            return JSONResponse(status_code=401, content={
                "detail": "Belum login. Masukkan username dan sandi Anda."})
        try:
            klaim = _baca_token(token, cfg.secret)
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={
                "detail": "Sesi login sudah berakhir. Silakan login lagi."})
        except jwt.PyJWTError:
            return JSONResponse(status_code=401, content={
                "detail": "Sesi tidak sah. Silakan login lagi."})
        request.state.email = klaim["sub"]
        request.state.pengguna = klaim
        return await call_next(request)


def info_pengguna(request: Request) -> dict | None:
    """Klaim pengguna dari middleware; None bila auth nonaktif (dev)."""
    return getattr(request.state, "pengguna", None)


def wajib_admin(request: Request) -> None:
    """403 bila pengguna login bukan admin. Mode dev (tanpa auth) diloloskan."""
    p = info_pengguna(request)
    if p is not None and p.get("peran") != "admin":
        raise HTTPException(403, "Hanya admin yang boleh melakukan aksi ini. "
                                 "Hubungi admin aplikasi Anda.")


# ----------------------------------------------------------------------------
# Akun admin pertama
# ----------------------------------------------------------------------------
def pastikan_admin(session: Session) -> bool:
    """Buat akun admin awal bila tabel pengguna masih kosong.
    Mengembalikan True bila akun baru dibuat."""
    ada = session.scalar(select(Pengguna).limit(1))
    if ada:
        return False
    sandi_awal = os.environ.get("ADMIN_SANDI_AWAL", "admin123")
    session.add(Pengguna(username="admin", nama="Administrator",
                         hash_sandi=hash_sandi(sandi_awal), peran="admin"))
    print("PERHATIAN: akun awal dibuat -> username 'admin', sandi "
          f"'{sandi_awal}'. SEGERA ganti sandi setelah login pertama!")
    return True


# ----------------------------------------------------------------------------
# Skema
# ----------------------------------------------------------------------------
class LoginMasuk(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    sandi: str = Field(min_length=1, max_length=200)


class GantiSandiMasuk(BaseModel):
    sandi_lama: str
    sandi_baru: str = Field(min_length=8, max_length=200,
                            description="Minimal 8 karakter")


class PenggunaBaru(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-z0-9._-]+$")
    nama: str = Field(min_length=1, max_length=100)
    sandi: str = Field(min_length=8, max_length=200)
    peran: str = Field(default="pengguna", pattern=r"^(admin|pengguna)$")


class PenggunaUbah(BaseModel):
    aktif: bool | None = None
    peran: str | None = Field(None, pattern=r"^(admin|pengguna)$")
    sandi_baru: str | None = Field(None, min_length=8, max_length=200)


# ----------------------------------------------------------------------------
# Rute /api/auth
# ----------------------------------------------------------------------------
def _pesan_bukan_lokal(cfg) -> str:
    """Penjelasan saat form username+sandi dipakai padahal mode bukan lokal."""
    if cfg.aktif:
        return ("Aplikasi ini memakai login Cloudflare Access, bukan username "
                "dan sandi, jadi form ini tidak bisa dipakai. Buka aplikasi "
                "lewat alamat resminya (domain yang dilindungi Access) dan "
                "masuk dengan email kantor Anda. Jika ini komputer Anda "
                "sendiri (localhost), atur AUTH_MODE=lokal di backend/.env "
                "lalu jalankan ulang API.")
    return ("Login sedang tidak aktif di proses API ini (mode development), "
            "jadi tidak perlu masuk. Bila form ini tetap muncul, muat ulang "
            "halaman; kalau masih muncul, jalankan ulang start-web.bat.")


def pasang_router_auth(app, ambil_session, cfg):
    router = APIRouter(prefix="/api/auth")
    dep = Depends(ambil_session)
    lokal_aktif = cfg.mode == "lokal" and not cfg.auth_disabled

    @router.get("/mode")
    def mode_login():
        """Cara login yang berlaku di proses ini — TANPA login, tanpa rahasia.

        Dipakai tampilan web: bila mode Access, form username+sandi tidak akan
        pernah berhasil, jadi form itu tidak ditampilkan.
        """
        from .auth import info_mode
        return info_mode(cfg)

    @router.post("/login")
    def login(data: LoginMasuk, response: Response, session: Session = dep):
        if not lokal_aktif:
            raise HTTPException(422, _pesan_bukan_lokal(cfg))
        p = session.get(Pengguna, data.username.strip().lower())
        if p is None or not p.aktif or not cek_sandi(data.sandi, p.hash_sandi):
            time.sleep(0.5)  # perlambat percobaan tebak sandi
            catat_audit(session, data.username, "login-gagal", "auth",
                        {"alasan": "username/sandi salah atau akun nonaktif"})
            session.commit()
            raise HTTPException(401, "Username atau sandi salah. Bila lupa "
                                     "sandi, hubungi admin untuk reset.")
        p.login_terakhir = dt.datetime.utcnow()
        catat_audit(session, p.username, "login", "auth", {"nama": p.nama})
        session.commit()
        _pasang_cookie(response, _buat_token(p, cfg.secret), cfg.produksi)
        return {"status": "ok", "username": p.username, "nama": p.nama,
                "peran": p.peran,
                "pesan": f"Selamat datang, {p.nama}."}

    @router.post("/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE_SESI, path="/")
        return {"status": "ok", "pesan": "Anda sudah keluar."}

    @router.get("/saya")
    def saya(request: Request, session: Session = dep):
        if not lokal_aktif:
            # Mode development / mode Access: tidak ada sesi lokal.
            email = getattr(request.state, "email", None)
            return {"username": email or "dev", "nama": email or "Mode Development",
                    "peran": "admin", "mode": cfg.mode}
        klaim = info_pengguna(request)
        p = session.get(Pengguna, klaim["sub"]) if klaim else None
        if p is None or not p.aktif:
            raise HTTPException(401, "Akun tidak ditemukan / dinonaktifkan.")
        return {"username": p.username, "nama": p.nama, "peran": p.peran,
                "login_terakhir": p.login_terakhir.isoformat(timespec="seconds")
                if p.login_terakhir else None, "mode": "lokal"}

    @router.post("/ganti-sandi")
    def ganti_sandi(data: GantiSandiMasuk, request: Request,
                    session: Session = dep):
        klaim = info_pengguna(request)
        if klaim is None:
            raise HTTPException(422, "Ganti sandi hanya tersedia pada mode "
                                     "login lokal.")
        p = session.get(Pengguna, klaim["sub"])
        if p is None or not cek_sandi(data.sandi_lama, p.hash_sandi):
            raise HTTPException(422, "Sandi lama salah.")
        p.hash_sandi = hash_sandi(data.sandi_baru)
        catat_audit(session, p.username, "ganti-sandi", "auth", {})
        session.commit()
        return {"status": "ok", "pesan": "Sandi berhasil diganti."}

    # ------------------------------------------------ kelola pengguna (admin)
    @router.get("/pengguna")
    def daftar_pengguna(request: Request, session: Session = dep):
        wajib_admin(request)
        return [{
            "username": p.username, "nama": p.nama, "peran": p.peran,
            "aktif": p.aktif,
            "dibuat_pada": p.dibuat_pada.isoformat(timespec="seconds"),
            "login_terakhir": p.login_terakhir.isoformat(timespec="seconds")
            if p.login_terakhir else None,
        } for p in session.scalars(select(Pengguna).order_by(Pengguna.username))]

    @router.post("/pengguna")
    def tambah_pengguna(data: PenggunaBaru, request: Request,
                        session: Session = dep):
        wajib_admin(request)
        uname = data.username.strip().lower()
        if session.get(Pengguna, uname):
            raise HTTPException(422, f"Username '{uname}' sudah dipakai.")
        session.add(Pengguna(username=uname, nama=data.nama,
                             hash_sandi=hash_sandi(data.sandi), peran=data.peran))
        siapa = (info_pengguna(request) or {}).get("sub", "?")
        catat_audit(session, siapa, "tambah", "pengguna",
                    {"username": uname, "nama": data.nama, "peran": data.peran})
        session.commit()
        return {"status": "ok", "pesan": f"Pengguna '{uname}' dibuat."}

    @router.post("/pengguna/{username}")
    def ubah_pengguna(username: str, data: PenggunaUbah, request: Request,
                      session: Session = dep):
        wajib_admin(request)
        p = session.get(Pengguna, username)
        if p is None:
            raise HTTPException(404, f"Pengguna '{username}' tidak ditemukan.")
        siapa = (info_pengguna(request) or {}).get("sub", "?")
        # Admin tidak boleh mengunci dirinya sendiri keluar.
        if siapa == username and (data.aktif is False or
                                  (data.peran and data.peran != "admin")):
            raise HTTPException(422, "Anda tidak bisa menonaktifkan / menurunkan "
                                     "peran akun Anda sendiri.")
        perubahan: dict = {}
        if data.aktif is not None:
            p.aktif = data.aktif
            perubahan["aktif"] = data.aktif
        if data.peran:
            p.peran = data.peran
            perubahan["peran"] = data.peran
        if data.sandi_baru:
            p.hash_sandi = hash_sandi(data.sandi_baru)
            perubahan["sandi"] = "di-reset"
        if not perubahan:
            raise HTTPException(422, "Tidak ada yang diubah.")
        catat_audit(session, siapa, "ubah", "pengguna",
                    {"username": username, **perubahan})
        session.commit()
        return {"status": "ok", "pesan": f"Pengguna '{username}' diperbarui."}

    app.include_router(router)
