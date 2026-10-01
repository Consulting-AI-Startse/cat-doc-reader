import { api } from "./client";
import type { SupplierDetail, SupplierReport } from "../types/suppliers";

export const getSupplierReport = (days: number) =>
  api<SupplierReport>(`/suppliers/confidence?days=${days}`);

// Chave ausente = invoices sem fornecedor: o backend lê a falta do parâmetro.
export const getSupplierDetail = (key: string | null, days: number) =>
  api<SupplierDetail>(
    `/suppliers/confidence/detail?days=${days}` + (key == null ? "" : `&key=${encodeURIComponent(key)}`)
  );
