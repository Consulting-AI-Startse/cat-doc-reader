import { api, apiBase } from "./client";
import type { ImportResult, PartsStats, RulesPreview, SerialRules } from "../types/parts";

export const getPartsStats = () => api<PartsStats>("/parts/stats");

export const getSerialRules = () => api<SerialRules>("/parts/serial-rules");

export const previewSerialRules = (substrings: string[], manual_part_numbers: string[]) =>
  api<RulesPreview>("/parts/serial-rules/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ substrings, manual_part_numbers }),
  });

export const putSerialRules = (substrings: string[], manual_part_numbers: string[]) =>
  api<SerialRules>("/parts/serial-rules", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ substrings, manual_part_numbers }),
  });

// Multipart não passa pelo api(): o fetch precisa montar o boundary sozinho, e
// definir Content-Type à mão quebra o upload. Mesmo motivo do /documents/upload.
export async function importParts(file: File): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${apiBase()}/parts/import`, { method: "POST", body: form });
  if (!res.ok) {
    let detalhe = "";
    try {
      const corpo = await res.json();
      detalhe = typeof corpo?.detail === "string" ? corpo.detail : "";
    } catch {
      // corpo não era JSON
    }
    throw new Error(detalhe ? `${res.status} — ${detalhe}` : `${res.status} ${res.statusText}`);
  }
  return res.json();
}
