export type DocumentStatus =
  | "received"
  | "processing"
  | "extracted"
  | "needs_review"
  | "approved"
  | "rejected"
  | "error";
/** Nota do OCR para um campo extraído (function/pipeline/confidence.py).
 *  - low: a palavra foi lida com confiança baixa
 *  - ambiguous: o documento também traz o valor com um caractere confundível
 *    trocado (`twin`), ex.: 26-2I00870 × 26-2100870
 *  - not_located: o valor não aparece no texto do OCR
 *  - derived / unanchored: calculado, ou sem part number para ancorar o número
 *  - corrected: o revisor editou; `was` guarda o status anterior */
export type FieldStatus =
  | "ok"
  | "low"
  | "ambiguous"
  | "not_located"
  | "derived"
  | "unanchored"
  | "corrected";

export interface FieldConfidence {
  score: number | null;
  status: FieldStatus;
  twin?: string;
  was?: FieldStatus;
}

export type FieldConfidenceMap = Record<string, FieldConfidence>;

// Uma linha de part number (o grão do output). Todos os campos podem vir nulos.
export interface LineItem {
  part_number: string | null;
  /** Um registro por serial: motor repete o mesmo part number. */
  serial_number: string | null;
  description: string | null;
  quantity: string | number | null;
  unit_price: string | number | null;
  amount: string | number | null;
  purchase_order: string | null;
  incoterm: string | null;
  country_of_origin: string | null;
  domestic_freight: string | number | null;
  packaging: string | number | null;
  exporter: string | null;
  manufacturer: string | null;
  /** Nulo no modo local e nas linhas gravadas antes da migração 0007. */
  field_confidence: FieldConfidenceMap | null;
}

// A fatura da qual esta e copia. Preenchido so na copia: a primeira entrada e
// a referencia e nunca recebe marca.
export interface DuplicateOf {
  invoice_id: string;
  document_id: string;
  invoice_number: string | null;
  supplier: string | null;
}

// Um invoice dentro de um documento.
export interface Invoice {
  id: string;
  invoice_number: string | null;
  invoice_date: string | null;
  supplier: string | null;
  currency: string | null;
  total: string | number | null;
  /** Cabeçalho (invoice_number, total). Os agregados cobrem cabeçalho e linhas. */
  field_confidence: FieldConfidenceMap | null;
  min_field_confidence: number | null;
  mean_field_confidence: number | null;
  flagged_fields: number | null;
  corrected_fields: number | null;
  duplicate_of: DuplicateOf | null;
  line_items: LineItem[];
}

/** Linha que o filtro tirou de line_items por não ter part number. Não some:
 *  fica aqui com o motivo, para o revisor poder discordar. */
export interface DiscardedLine {
  invoice_number: string | null;
  part_number: string | null;
  description: string | null;
  amount: string | null;
  reason: string | null;
}

export interface DocumentEvent {
  event_type: string;
  actor: string | null;
  created_at: string;
}

// Documento completo (a tela de revisão).
export interface DocumentDetail {
  id: string;
  status: DocumentStatus;
  source_filename: string | null;
  source: string;
  blob_path: string | null;
  extraction_confidence: number | null;
  error_message: string | null;
  created_at: string;
  /** Defeitos: é isto que derruba o documento para needs_review. */
  validation: string[];
  /** Registro de cálculo (rateio, linha descartada). Não pede revisão. */
  notes: string[];
  discarded_lines: DiscardedLine[];
  invoices: Invoice[];
  events: DocumentEvent[];
}
// Item da lista de documentos (dashboard).
export interface DocumentListItem {
  id: string;
  status: DocumentStatus;
  source_filename: string | null;
  source: string;
  created_at: string;
  invoice_count: number;
  total: string | number | null;
}

export interface Metrics {
  documentos: number;
  invoices: number;
  nao_processados: number;
  aguardando_revisao: number;
  aprovados: number;
  erros: number;
  valor_total_extraido: number;
}
// --- Payload do PATCH (revisão humana): a mesma forma que o backend espera. ---

export interface LineInput {
  part_number: string | null;
  serial_number: string | null;
  description: string | null;
  quantity: string | null;
  unit_price: string | null;
  amount: string | null;
  purchase_order: string | null;
  incoterm: string | null;
  country_of_origin: string | null;
  domestic_freight: string | null;
  packaging: string | null;
  exporter: string | null;
  manufacturer: string | null;
  field_confidence: FieldConfidenceMap | null;
}

export interface InvoiceInput {
  invoice_number: string | null;
  invoice_date: string | null;
  supplier: string | null;
  currency: string | null;
  total: string | null;
  field_confidence: FieldConfidenceMap | null;
  line_items: LineInput[];
}

export interface DocumentUpdate {
  invoices: InvoiceInput[];
}
