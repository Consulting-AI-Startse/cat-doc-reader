export type DocumentStatus =
  | "received"
  | "processing"
  | "extracted"
  | "needs_review"
  | "approved"
  | "rejected"
  | "error";

export interface LineItem {
  part_number: string | null;
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
  supplier: string | null;
  manufacturer: string | null;
}

export interface Invoice {
  id: string;
  invoice_number: string | null;
  invoice_date: string | null;
  currency: string | null;
  total: string | number | null;
  line_items: LineItem[];
}

export interface DocumentEvent {
  event_type: string;
  actor: string | null;
  created_at: string;
}

export interface DocumentDetail {
  id: string;
  status: DocumentStatus;
  source_filename: string | null;
  source: string;
  blob_path: string | null;
  extraction_confidence: number | null;
  error_message: string | null;
  created_at: string;
  invoices: Invoice[];
  events: DocumentEvent[];
}

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

export interface LineInput {
  part_number: string | null;
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
  supplier: string | null;
  manufacturer: string | null;
}

export interface InvoiceInput {
  invoice_number: string | null;
  invoice_date: string | null;
  currency: string | null;
  total: string | null;
  line_items: LineInput[];
}

export interface DocumentUpdate {
  invoices: InvoiceInput[];
}
