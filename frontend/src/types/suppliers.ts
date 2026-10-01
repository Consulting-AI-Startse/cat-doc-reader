// Relatório de confiança por fornecedor (backend/app/api/suppliers.py).
// As frações vêm de 0 a 1; nulo quando não há invoice com nota.

export interface SupplierRow {
  supplier_key: string | null;
  supplier: string | null;
  invoices: number;
  /** Quantas têm nota por campo. As médias saem só delas. */
  invoices_scored: number;
  mean_confidence: number | null;
  min_confidence: number | null;
  flagged_invoices: number;
  flagged_rate: number | null;
  fields_scored: number;
  fields_corrected: number;
  /** Campos corrigidos na revisão / campos pontuados: a medida de acerto. */
  correction_rate: number | null;
  review_rate: number | null;
  weakest_field: string | null;
  last_seen: string | null;
  last_document_id: string | null;
}

export interface SupplierReport {
  days: number;
  suppliers: SupplierRow[];
}

export interface FieldStats {
  field: string;
  scored: number;
  low: number;
  ambiguous: number;
  not_located: number;
  corrected: number;
  problems: number;
  mean_score: number | null;
}

export interface SupplierInvoice {
  invoice_id: string;
  invoice_number: string | null;
  document_id: string;
  document_status: string;
  source_filename: string | null;
  created_at: string | null;
  min_field_confidence: number | null;
  mean_field_confidence: number | null;
  flagged_fields: number | null;
  corrected_fields: number | null;
}

export interface SupplierDetail {
  supplier: SupplierRow | null;
  fields: FieldStats[];
  invoices: SupplierInvoice[];
}
