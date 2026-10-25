"""Alat baris perintah OP Margin (sementara, sebelum ada API & tampilan web).

Contoh pemakaian (dari folder backend):
  python -m app.cli init-db
  python -m app.cli import-template ../sample_data/Template_dan_Data_Awal_OP_Margin_v3.xlsx --pengunggah budi
  python -m app.cli import-tiket "ekspor master data.xlsx" --pengunggah budi
  python -m app.cli ringkasan 2026
  python -m app.cli rekomendasi
  python -m app.cli rencana 2027
  python -m app.cli atur-login-lokal
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib

from dotenv import load_dotenv

# Baca backend/.env (mis. DATABASE_URL) sebelum membuat koneksi database.
load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

from .core.perencanaan import hitung_rencana
from .core.rekomendasi import rekomendasi_harga
from .core import rumus
from .db import buat_engine, buat_session_factory
from .importer.template import impor_master_data, impor_template
from .models import Base, MartBulanan

from sqlalchemy import select

NAMA_BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
              "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def fmt_id(angka, desimal=4) -> str:
    """Format angka gaya Indonesia: 1.234.567,8901."""
    if angka is None:
        return "-"
    teks = f"{angka:,.{desimal}f}"
    return teks.replace(",", "_").replace(".", ",").replace("_", ".")


def main() -> None:
    ap = argparse.ArgumentParser(prog="op-margin")
    sub = ap.add_subparsers(dest="perintah", required=True)

    sub.add_parser("init-db", help="Buat semua tabel database")

    sub.add_parser("atur-login-lokal",
                   help="Setel .env ke login lokal (username+sandi) "
                        "untuk pemakaian di komputer sendiri")

    p = sub.add_parser("import-template", help="Impor template + data awal (.xlsx)")
    p.add_argument("file")
    p.add_argument("--pengunggah", default="?")

    p = sub.add_parser("import-tiket", help="Impor ekspor Master Data tiket (.xlsx)")
    p.add_argument("file")
    p.add_argument("--pengunggah", default="?")

    p = sub.add_parser("ringkasan", help="Ringkasan OP Margin per bulan untuk satu tahun")
    p.add_argument("tahun", type=int)

    p = sub.add_parser("rekomendasi", help="Harga beli maksimum menurut aturan stok")
    p.add_argument("--tanggal", help="dd/mm/yyyy (default: tanggal terakhir berdata)")

    p = sub.add_parser("rencana", help="Perencanaan margin tahun depan (pengganti Y27)")
    p.add_argument("tahun_target", type=int)

    args = ap.parse_args()

    if args.perintah == "atur-login-lokal":
        from .setup_env import atur_login_lokal
        hasil = atur_login_lokal()
        print(("Dibuat: " if hasil["dibuat"] else "Diperbarui: ") + hasil["jalur"])
        if hasil["diubah"]:
            for k in sorted(hasil["diubah"]):
                tampil = hasil["diubah"][k]
                if k == "SECRET_KEY":
                    tampil = "(kunci acak baru, 64 karakter)"
                print(f"  {k} -> {tampil}")
        else:
            print("  (tidak ada yang perlu diubah)")
        print("\nSekarang API memakai login lokal: username 'admin', "
              "sandi awal 'admin123'.")
        print("Jalankan ulang API (tutup jendela 'OP Margin - API', lalu "
              "start-web.bat) agar setelan ini terpakai.")
        return

    engine = buat_engine()
    Session = buat_session_factory(engine)

    if args.perintah == "init-db":
        Base.metadata.create_all(engine)
        print("Semua tabel sudah dibuat.")
        return

    with Session() as session:
        if args.perintah in ("import-template", "import-tiket"):
            Base.metadata.create_all(engine)
            fn = impor_template if args.perintah == "import-template" else impor_master_data
            hasil = fn(args.file, session, pengunggah=args.pengunggah)
            if hasil.duplikat_file:
                print("CATATAN: file yang sama persis pernah diunggah; data tidak digandakan.")
            print(f"Unggahan #{hasil.unggahan_id} selesai. Baris per tabel: {hasil.jumlah}")
            if hasil.peringatan:
                print(f"\n{len(hasil.peringatan)} peringatan:")
                for w in hasil.peringatan[:30]:
                    print("  -", w)
                if len(hasil.peringatan) > 30:
                    print(f"  ... dan {len(hasil.peringatan) - 30} lainnya (lihat tabel peringatan_data)")

        elif args.perintah == "ringkasan":
            baris = list(session.scalars(select(MartBulanan).where(
                MartBulanan.tahun == args.tahun).order_by(MartBulanan.bulan)))
            if not baris:
                print(f"Belum ada data untuk tahun {args.tahun}.")
                return
            print(f"\nRingkasan OP Margin {args.tahun} (US¢/kg, tonase kering)")
            print(f"{'Bulan':<6}{'SICOM':>12}{'OP Price':>12}{'OP Margin':>12}"
                  f"{'Ton':>14}{'Target':>9}{'Pencapaian':>12}{'vs Target':>11}")
            for b in baris:
                print(f"{NAMA_BULAN[b.bulan]:<6}{fmt_id(b.sicom_usc):>12}"
                      f"{fmt_id(b.harga_beli_usc):>12}{fmt_id(b.op_margin_usc):>12}"
                      f"{fmt_id(b.qty_ton, 3):>14}{fmt_id(b.target_usc, 1):>9}"
                      f"{fmt_id(b.pencapaian * 100 if b.pencapaian is not None else None, 1):>11}%"
                      f"{fmt_id(b.selisih_vs_target):>11}")
            sederhana = rumus.rata_rata_sederhana([b.op_margin_usc for b in baris])
            tertimbang = rumus.rata_rata_tertimbang(
                [(b.op_margin_usc, b.qty_ton) for b in baris])
            print(f"\nRata-rata tahun berjalan (sederhana, resmi) : {fmt_id(sederhana)}")
            print(f"Rata-rata tertimbang tonase (informasi)     : {fmt_id(tertimbang)}")

        elif args.perintah == "rekomendasi":
            tanggal = None
            if args.tanggal:
                tanggal = dt.datetime.strptime(args.tanggal, "%d/%m/%Y").date()
            h = rekomendasi_harga(session, tanggal)
            print(f"\nRekomendasi harga beli — status: {h.status}"
                  + (f" ({h.tanggal.strftime('%d/%m/%Y')})" if h.tanggal else ""))
            for a in h.alasan:
                print("  -", a)
            if h.status == "OK":
                print(f"\n  Harga beli maksimum : {fmt_id(h.harga_beli_maks_usc)} US¢/kg"
                      f" = Rp {fmt_id(h.harga_beli_maks_rp_kg, 2)}/kg")
                if h.harga_beli_aktual_terakhir_usc:
                    print(f"  Harga aktual terakhir ({h.tanggal_harga_aktual.strftime('%d/%m/%Y')}): "
                          f"{fmt_id(h.harga_beli_aktual_terakhir_usc)} US¢/kg")

        elif args.perintah == "rencana":
            hasil = hitung_rencana(session, args.tahun_target)
            print(f"\nPerencanaan OP Margin {args.tahun_target} (US¢/kg)")
            print(f"{'Bulan':<6}{'Dasar':>10}{'Penyesuaian':>13}{'Effort':>9}"
                  f"{'Net Margin':>12}  Tahun dasar")
            for r in hasil:
                tanda = " (perkiraan)" if r.perkiraan else ""
                print(f"{NAMA_BULAN[r.bulan]:<6}{fmt_id(r.rata_rata_dasar):>10}"
                      f"{fmt_id(r.penyesuaian_manual, 2):>13}{fmt_id(r.effort, 2):>9}"
                      f"{fmt_id(r.net_margin):>12}  {r.tahun_dipakai}{tanda}")


if __name__ == "__main__":
    main()
