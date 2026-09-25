// A lista de part numbers liberados e a regra de quem exige serial number.

export interface PartsStats {
  total: number;
  requires_serial: number;
  ultimo_import: { batch: string | null; em: string } | null;
}

export interface ImportResult {
  recebidas: number;
  gravadas: number;
  ignoradas: number;
  /** Repetidas dentro do próprio arquivo. Não são erro, mas explicam as
   *  ignoradas: `recebidas = gravadas + duplicadas + erros`, sempre. */
  duplicadas_no_arquivo: number;
  total_na_lista: number;
  requires_serial: number;
  erros: string[];
}

export interface SerialRules {
  substrings: string[];
  manual_part_numbers: string[];
  updated_at: string;
  marcadas: number;
  total_na_lista: number;
}

export interface RulesPreview {
  marcadas: number;
  total_na_lista: number;
  /** Quantas estão marcadas hoje, para a tela mostrar o antes e o depois. */
  marcadas_hoje: number;
  exemplos: { part_number: string; name: string | null }[];
}
