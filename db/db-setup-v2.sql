BEGIN;
DROP TABLE IF EXISTS document_events CASCADE;
DROP TABLE IF EXISTS invoice_events CASCADE;
DROP TABLE IF EXISTS invoice_part_number_items CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS alembic_version CASCADE;
DROP TYPE IF EXISTS invoice_status CASCADE;
DROP TYPE IF EXISTS document_status CASCADE;
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
CREATE TYPE document_status AS ENUM ('received', 'processing', 'extracted', 'needs_review', 'approved', 'rejected', 'error');
CREATE TABLE documents (
    id UUID NOT NULL,
    status document_status NOT NULL,
    source_filename VARCHAR(512),
    source VARCHAR(64) DEFAULT 'manual_upload' NOT NULL,
    blob_path VARCHAR(1024),
    extraction_confidence FLOAT,
    raw_extraction JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id)
);
CREATE INDEX ix_documents_status ON documents (status);
CREATE TABLE invoices (
    id UUID NOT NULL,
    document_id UUID NOT NULL,
    invoice_number VARCHAR(128),
    invoice_date DATE,
    currency VARCHAR(3),
    total NUMERIC(18, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);
CREATE INDEX ix_invoices_document_id ON invoices (document_id);
CREATE INDEX ix_invoices_invoice_number ON invoices (invoice_number);
CREATE TABLE invoice_part_number_items (
    id UUID NOT NULL,
    invoice_id UUID NOT NULL,
    part_number VARCHAR(64),
    description TEXT,
    quantity NUMERIC(18, 4),
    unit_price NUMERIC(18, 4),
    amount NUMERIC(18, 2),
    purchase_order VARCHAR(128),
    incoterm VARCHAR(16),
    country_of_origin VARCHAR(128),
    domestic_freight NUMERIC(18, 2),
    packaging VARCHAR(128),
    exporter VARCHAR(256),
    supplier VARCHAR(256),
    manufacturer VARCHAR(256),
    PRIMARY KEY (id),
    FOREIGN KEY(invoice_id) REFERENCES invoices (id) ON DELETE CASCADE
);
CREATE INDEX ix_invoice_part_number_items_invoice_id ON invoice_part_number_items (invoice_id);
CREATE INDEX ix_invoice_part_number_items_part_number ON invoice_part_number_items (part_number);
CREATE INDEX ix_invoice_part_number_items_purchase_order ON invoice_part_number_items (purchase_order);
CREATE TABLE document_events (
    id UUID NOT NULL,
    document_id UUID NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    actor VARCHAR(256),
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);
CREATE INDEX ix_document_events_document_id ON document_events (document_id);
INSERT INTO alembic_version (version_num) VALUES ('0002');
COMMIT;
