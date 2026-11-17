export type PreferensiLanjutan = {
  pemisah_desimal: "," | ".";
  format_tanggal: "dd/mm/yyyy" | "mm/dd/yyyy" | "yyyy-mm-dd";
  angka_ringkas: boolean;
  tema: "terang" | "gelap" | "sistem";
  kepadatan: "nyaman" | "ringkas";
  ukuran_huruf: "kecil" | "normal" | "besar";
  kurangi_animasi: boolean;
  halaman_awal: "ringkasan" | "analisis" | "stok" | "traceability";
  baris_per_halaman: 10 | 25 | 50 | 100;
  ingat_filter: boolean;
  pemisah_csv: "," | ";";
};
export const PREFERENSI_LANJUTAN_BAKU: PreferensiLanjutan = {
  pemisah_desimal: ",", format_tanggal: "dd/mm/yyyy", angka_ringkas: false,
  tema: "terang", kepadatan: "nyaman", ukuran_huruf: "normal", kurangi_animasi: false,
  halaman_awal: "ringkasan", baris_per_halaman: 25, ingat_filter: true, pemisah_csv: ",",
};
