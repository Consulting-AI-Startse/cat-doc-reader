import type { FieldConfidence, FieldConfidenceMap } from "../types/document";

// Os três status que mandam o documento para revisão (FLAGGED no backend).
const FLAGGED = new Set(["low", "ambiguous", "not_located"]);

export function isFlagged(e: FieldConfidence | undefined): boolean {
  return !!e && FLAGGED.has(e.status);
}

/** Destaque da célula. Âmbar para leitura duvidosa, vermelho para valor que
 *  nem aparece no texto — este é o pior: pode ser invenção do modelo. */
export function fcClass(e: FieldConfidence | undefined): string {
  if (!e) return "";
  switch (e.status) {
    case "low":
    case "ambiguous":
      return "bg-amber-100 ring-1 ring-inset ring-amber-400";
    case "not_located":
      return "bg-red-50 ring-1 ring-inset ring-red-400";
    case "corrected":
      return "bg-emerald-50";
    default:
      return "";
  }
}

export function pct(v: number | null | undefined): string {
  return v == null ? "-" : `${Math.round(v * 100)}%`;
}

/** O que o revisor lê ao passar o mouse: o motivo, não só o número. */
export function fcTitle(e: FieldConfidence | undefined): string | undefined {
  if (!e) return undefined;
  switch (e.status) {
    case "low":
      return `Confiança do OCR ${pct(e.score)}: leitura duvidosa, confira no PDF`;
    case "ambiguous":
      return `Leitura ambígua: o documento também traz "${e.twin}"`;
    case "not_located":
      return "Valor não localizado no texto do documento";
    case "corrected":
      return "Corrigido na revisão";
    case "ok":
      return e.score == null ? undefined : `Confiança do OCR ${pct(e.score)}`;
    default:
      return undefined;
  }
}

/** A nota que volta no PATCH. O campo cujo valor mudou desde a extração vira
 *  'corrected' — é a taxa de correção que valida a própria nota no relatório
 *  por fornecedor. Comparar com o valor original, e não marcar no onChange,
 *  faz quem desfaz a edição voltar ao status de antes. */
export function withCorrections(
  fc: FieldConfidenceMap | null,
  orig: Record<string, string>,
  current: Record<string, string>
): FieldConfidenceMap | null {
  if (!fc) return null;
  const out: FieldConfidenceMap = {};
  for (const [k, e] of Object.entries(fc)) {
    const changed = k in orig && (current[k] ?? "").trim() !== (orig[k] ?? "").trim();
    out[k] =
      changed && e.status !== "corrected" ? { score: e.score, status: "corrected", was: e.status } : e;
  }
  return out;
}
