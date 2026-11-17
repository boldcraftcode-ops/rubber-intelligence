import { fmtBerat } from "./bersama";

export type SatuanBeratApi = "kg" | "ton" | "MT";
type SatuanInternal = "kg" | "ton";

/** Satuan asal setiap field volume yang dipakai dari payload API. */
export const SATUAN_FIELD_API: Readonly<Record<string, SatuanBeratApi>> = {
  wet_kg: "kg", dry_kg: "kg", sample_kg: "kg", reject_kg: "kg",
  qty_kg: "kg", qty_kering_kg: "kg", total_kg: "kg", kg_total: "kg",
  biasa_kg: "kg", eudr_kg: "kg", dry_total_kg: "kg", volume_kg: "kg",
  volume_pabrik_kg: "kg", volume_tanpa_kolektor_kg: "kg", total_dry_kg: "kg",
  dry_ton: "ton", wet_ton: "ton", reject_ton: "ton", total_ton: "ton",
  ton: "ton", qty_ton: "ton", stok_ton: "ton", safety_ton: "ton",
  kapasitas_ton: "ton", pemakaian_ton: "ton", pemakaian_harian_ton: "ton",
  stok_awal_ton: "ton", stok_akhir_ton: "ton", intake_ton: "ton",
  dry_mt: "MT", traceable_mt: "MT", untraceable_mt: "MT", volume_mt: "MT",
  total_dry_mt: "MT", dry_total_6bulan_mt: "MT", dry_rata_bulanan_mt: "MT",
  ton_kering: "MT", period_turnover_mt: "MT", total_dry_6bulan_mt: "MT", batas_mt: "MT",
};

const kgPerSatuan: Record<SatuanInternal, number> = { kg: 1, ton: 1000 };

/** Konversi numerik berat API; MT dan ton sama-sama 1.000 kg. */
export function konversiSatuanBerat(nilai: number, dari: SatuanBeratApi, ke: SatuanBeratApi): number {
  const sumber: SatuanInternal = dari === "kg" ? "kg" : "ton";
  const tujuan: SatuanInternal = ke === "kg" ? "kg" : "ton";
  return nilai * kgPerSatuan[sumber] / kgPerSatuan[tujuan];
}

/** Format field berat API dengan mengonversi ke kg lalu menyatukan nilai + label. */
export function fmtFieldBerat(nilai: number | null | undefined, field: string): string {
  const sumber = SATUAN_FIELD_API[field];
  if (nilai === null || nilai === undefined || !Number.isFinite(nilai) || !sumber) return "–";
  return fmtBerat(konversiSatuanBerat(nilai, sumber, "kg"));
}
