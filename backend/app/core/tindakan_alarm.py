"""Tindak lanjut tiap alarm: ke halaman mana, dan langkah apa yang harus dilakukan.

Latar belakang (permintaan pemilik): alarm hanya berbunyi tanpa memberi tahu
**dari mana** data harus dibetulkan. Modul ini menerjemahkan kode alarm menjadi
petunjuk kerja yang bisa langsung diklik:

    {
      "kategori": "data",              # kelompok tampilan
      "halaman": "input",              # id menu tujuan di tampilan web
      "halaman_label": "Input Harian",
      "judul": "Isi SICOM terbaru",
      "langkah": ["...", "..."],       # 2-3 langkah konkret
    }

`halaman` HARUS salah satu id menu yang ada di `frontend/src/App.tsx`
(STOK, REKONSILIASI, INPUT, UNGGAH, ATURAN, RINGKASAN). Bila id-nya tidak
dikenal, tampilan web mengabaikan tombolnya — karena itu ada tes yang menjaga
daftar ini.

PENTING: modul ini tidak mengubah cara alarm dinilai, dan tidak menebak angka.
Alarm tetap padam hanya kalau datanya benar dan evaluasi ulang dijalankan.
"""
from __future__ import annotations

import datetime as dt

#: Id menu yang dikenal tampilan web (lihat TAB di frontend/src/App.tsx).
HALAMAN_DIKENAL = {"stok", "rekonsiliasi", "input", "unggah", "aturan", "ringkasan"}

#: Urutan kelompok di layar: yang paling mendesak dulu.
URUTAN_KATEGORI = ["stok", "data", "selisih", "harga", "margin"]


def _tindakan(kategori: str, halaman: str, judul: str,
              langkah: list[str]) -> dict:
    assert halaman in HALAMAN_DIKENAL, f"halaman '{halaman}' tidak dikenal web"
    label = {
        "stok": "Stok & Days",
        "rekonsiliasi": "Rekonsiliasi",
        "input": "Input Harian",
        "unggah": "Unggah Data",
        "aturan": "Aturan Harga",
        "ringkasan": "Margin Performance",
    }[halaman]
    return {"kategori": kategori, "halaman": halaman, "halaman_label": label,
            "judul": judul, "langkah": langkah}


def tindakan_untuk(kode: str, tanggal_data: dt.date | None = None,
                   pesan: str = "") -> dict:
    """Petunjuk kerja untuk satu alarm. Tidak bergantung pada data lain selain
    tanggal & pesan yang sudah tersimpan di alarm itu sendiri."""
    if kode == "STOK_DI_BAWAH_SAFETY":
        tgl = tanggal_data.strftime("%d/%m/%Y") if tanggal_data else "terakhir"
        return _tindakan(
            "stok", "stok", "Putuskan: stok memang tipis, atau datanya belum diperbarui",
            [f"Buka Stok & Days, cari baris {tgl}: lihat stok, safety, dan days tersisa.",
             "Kalau stok fisik sebenarnya lebih besar, perbarui data stok lewat "
             "Unggah Data (sheet Stok) — alarm akan padam setelah evaluasi ulang.",
             "Kalau memang tipis, ajukan pembelian memakai harga beli maksimum "
             "di menu Aturan Harga, lalu catat keputusannya."])

    if kode == "MARGIN_DI_BAWAH_TARGET":
        return _tindakan(
            "margin", "ringkasan", "Cari penyebab margin turun di bulan itu",
            ["Buka Margin Performance, lihat kartu OP Margin bulanan vs target.",
             "Tekan Margin Bridge untuk bulan yang sama: lihat dua penyebabnya "
             "(perubahan SICOM dan perubahan OP Price).",
             "Kalau target yang keliru (bukan margin-nya), perbaiki target di "
             "kartu OP Margin bulanan — jangan mengubah angka aktual."])

    if kode == "SICOM_TERLAMBAT":
        return _tindakan(
            "data", "input", "Isi SICOM terbaru",
            ["Buka Input Harian, isi SICOM sesuai terbitan pasar terakhir "
             "(sumber dan catatan ikut diisi).",
             "Simpan; alarm dievaluasi ulang dan padam bila tanggalnya sudah "
             "dalam ambang.",
             "Kalau terbitan pasar belum keluar, jangan menebak angka — ulangi "
             "besok, dan pakai ambang SICOM yang realistis di Pengaturan alarm."])

    if kode == "KURS_TERLAMBAT":
        return _tindakan(
            "data", "input", "Isi kurs terbaru",
            ["Buka Input Harian, isi kurs pada tanggal berlakunya.",
             "Kurs hanya perlu diisi saat berubah — isi nilai terakhir yang "
             "berlaku, bukan rata-rata.",
             "Simpan, lalu evaluasi ulang alarm."])

    if kode == "STOK_TERLAMBAT":
        return _tindakan(
            "data", "unggah", "Unggah posisi stok terbaru",
            ["Buka Unggah Data, unggah file berisi sheet Stok (boleh hanya sheet itu).",
             "Pastikan tanggal posisi stok terakhir memang tanggal yang benar.",
             "Setelah unggah, alarm dinilai ulang otomatis; cek juga Stok & Days "
             "supaya nilai safety-nya masuk akal."])

    if kode == "TIKET_TERLAMBAT":
        return _tindakan(
            "data", "unggah", "Unggah tiket terbaru",
            ["Buka Unggah Data, unggah ekspor Master Data tiket yang terbaru.",
             "Cek tanggal tiket terakhir di Intake Analisis (Daftar intake terakhir).",
             "Setelah itu alarm padam sendiri; kalau tidak, jalankan Evaluasi ulang."])

    if kode == "SELISIH_REKONSILIASI":
        if tanggal_data is not None:
            return _tindakan(
                "selisih", "rekonsiliasi", "Putuskan angka mana yang dipakai",
                ["Buka Rekonsiliasi, lihat kartu 'Selisih yang sudah diketahui' "
                 "untuk periode ini (tiket vs Excel lama).",
                 "Tiket = sumber resmi tonase. Selisih TIDAK dikoreksi otomatis; "
                 "keputusan koreksi masih pertanyaan terbuka (lihat docs/ASUMSI.md).",
                 "Catat keputusan periode ini sebelum angka lama diubah, supaya "
                 "alarm berikutnya tidak berbunyi untuk hal yang sama."])
        return _tindakan(
            "selisih", "rekonsiliasi", "Telusuri tanggal yang selisihnya besar",
            ["Buka Rekonsiliasi, kartu 'Pemeriksaan harian: tiket vs pembelian'.",
             "Cari tanggal dengan selisih di atas ambang (baris berlatar kuning).",
             "Perbaiki data yang salah di Unggah Data (tiket atau pembelian), "
             "lalu evaluasi ulang — jangan mengubah ambang hanya untuk memadamkan alarm."])

    if kode == "HARGA_DI_ATAS_MAKS":
        return _tindakan(
            "harga", "aturan", "Bandingkan dengan aturan harga yang berlaku",
            ["Buka Aturan Harga, cari baris aturan yang berlaku untuk rasio stok "
             "terakhir.",
             "Bandingkan harga beli maksimum di baris itu dengan harga beli aktual "
             "yang dipakai.",
             "Kalau aturan masih berstatus CONTOH, harga maksimum belum final — "
             "perbarui aturannya dulu sebelum memakai alarm ini sebagai patokan."])

    # Kode baru yang belum punya panduan: tetap beri arah yang aman.
    return _tindakan(
        "data", "unggah", "Periksa data sumber alarm ini",
        ["Buka menu yang berkaitan dengan isi alarm dan periksa data terbarunya.",
         "Perbaiki data sumbernya lewat Unggah Data atau Input Harian.",
         "Jalankan Evaluasi ulang; alarm padam bila datanya sudah benar."])
