"""Menanyakan langsung ke API yang sedang berjalan di localhost:8000.

Dipakai `diagnosa.bat` dan bisa juga dijalankan sendiri:

    .venv\\Scripts\\python -m app.tanya_api

Yang dicari: apakah proses yang menjawab di port 8000 memakai KODE TERBARU
(ada /api/health versi baru, ada /api/auth/mode) dan mode login apa yang
sedang dipakainya. Ini membedakan "kode di folder sudah benar" dari
"proses lama masih hidup".
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASIS = "http://127.0.0.1:8000"


def _ambil(jalur: str, waktu: float = 5.0):
    """Kembalikan (status, isi_dict_atau_teks)."""
    try:
        with urllib.request.urlopen(BASIS + jalur, timeout=waktu) as r:
            teks = r.read().decode("utf-8", "replace")
            return r.status, teks
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # koneksi ditolak, timeout, dll.
        return None, f"{type(e).__name__}: {e}"


def _rapi(teks: str) -> str:
    try:
        return json.dumps(json.loads(teks), ensure_ascii=False)
    except Exception:
        return teks.strip()[:400]


def main() -> int:
    print(f"  Alamat: {BASIS}")
    status, teks = _ambil("/api/health")
    if status is None:
        print("  /api/health : TIDAK ADA JAWABAN")
        print(f"    {teks}")
        print("  -> API belum berjalan. Jalankan start-web.bat.")
        return 1
    print(f"  /api/health : {status} {_rapi(teks)}")

    # Tanda kode terbaru: health memuat "login" dan versi 0.6.1+
    kode_baru = '"login"' in teks
    status2, teks2 = _ambil("/api/auth/mode")
    print(f"  /api/auth/mode : {status2} {_rapi(teks2)}")

    print()
    if status2 == 200:
        try:
            cara = json.loads(teks2).get("cara")
        except Exception:
            cara = None
        if cara == "username-sandi":
            print("  SIMPULAN: API memakai LOGIN LOKAL (username + sandi).")
            print("  Silakan login di http://localhost:5173 (Ctrl+F5 dulu).")
        else:
            print(f"  SIMPULAN: login nonaktif (cara={cara}).")
        return 0
    if status == 200 and not kode_baru:
        print("  SIMPULAN: proses di port 8000 memakai KODE LAMA")
        print("  (health tidak memuat info login, /api/auth/mode tidak ada).")
        print("  Tutup jendela OP Margin - API yang lama, lalu jalankan")
        print("  start-web.bat lagi.")
        return 1
    print("  SIMPULAN: API menjawab tetapi tidak menyediakan /api/auth/mode.")
    print("  Periksa pesan di atas.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
