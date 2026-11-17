import { createContext, ReactNode, useContext, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ambilJson, aturPreferensiFormat, kirimMetode, PREFERENSI_TAMPILAN_BAKU, PreferensiFormat } from "./bersama";

export type DataPreferensi = {
  efektif: PreferensiFormat;
  pribadi: Partial<PreferensiFormat>;
  bawaan: PreferensiFormat;
  terkunci: Record<keyof PreferensiFormat, boolean>;
};

type PatchPreferensi = { [K in keyof PreferensiFormat]?: PreferensiFormat[K] | null };
type KonteksPreferensi = DataPreferensi & {
  admin: boolean;
  memuat: boolean;
  gagal: boolean;
  simpanPribadi: (nilai: PatchPreferensi) => Promise<void>;
  simpanBawaan: (nilai: Partial<PreferensiFormat>, terkunci?: Partial<Record<keyof PreferensiFormat, boolean>>) => Promise<void>;
};

const BAKU: DataPreferensi = {
  efektif: PREFERENSI_TAMPILAN_BAKU,
  pribadi: {},
  bawaan: PREFERENSI_TAMPILAN_BAKU,
  terkunci: { desimal_angka: false, desimal_persen: false, satuan_berat: false },
};
const Konteks = createContext<KonteksPreferensi>({
  ...BAKU, admin: false, memuat: false, gagal: false,
  simpanPribadi: async () => {}, simpanBawaan: async () => {},
});

export function PreferensiProvider({ children, admin }: { children: ReactNode; admin: boolean }) {
  const qc = useQueryClient();
  const query = useQuery<DataPreferensi>({
    queryKey: ["preferensi"],
    queryFn: () => ambilJson("/api/preferensi"),
    initialData: BAKU,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const nilai = query.data ?? BAKU;
  useEffect(() => { aturPreferensiFormat(nilai.efektif); }, [nilai.efektif]);

  const simpanPribadi = async (patch: PatchPreferensi) => {
    const baru = await kirimMetode("/api/preferensi", "PUT", patch) as DataPreferensi;
    qc.setQueryData(["preferensi"], baru);
  };
  const simpanBawaan = async (
    preferensi: Partial<PreferensiFormat>,
    terkunci?: Partial<Record<keyof PreferensiFormat, boolean>>,
  ) => {
    await kirimMetode("/api/preferensi/bawaan", "PUT", { nilai: preferensi, terkunci });
    await qc.invalidateQueries({ queryKey: ["preferensi"] });
  };

  return <Konteks.Provider value={{ ...nilai, admin, memuat: query.isLoading, gagal: !!query.error,
    simpanPribadi, simpanBawaan }}>{children}</Konteks.Provider>;
}

export function usePreferensi() { return useContext(Konteks); }
