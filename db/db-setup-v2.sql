-- db-setup-v2.sql -- schema achatado, head 0007.
--
-- GERADO, nao editar a mao: sai de 'alembic upgrade base:head --sql' com os
-- tipos finais aplicados direto no CREATE, em vez de CREATE + ALTER.
-- Para regerar, ver STRUCTURE.md.
--
-- O stamp no fim tem de bater com a head das migracoes. Ja ficou em '0002'
-- enquanto a 0003 existia, o que faria um ambiente novo nascer com
-- incoterm VARCHAR(16) -- exatamente o que estourou em producao. E ficou na
-- 0003 enquanto 0004-0006 existiam: sem fornecedor na invoice, sem chave de
-- duplicata, sem lista de PN e sem serial.

BEGIN;
DROP TABLE IF EXISTS serial_rules CASCADE;
DROP TABLE IF EXISTS released_part_numbers CASCADE;
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

-- Running upgrade  -> 0001

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
    currency VARCHAR(16), 
    total NUMERIC(18, 2), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    supplier TEXT, 
    invoice_number_key VARCHAR(128), 
    supplier_key VARCHAR(128), 
    duplicate_of_id UUID, 
    field_confidence JSONB, 
    min_field_confidence FLOAT, 
    mean_field_confidence FLOAT, 
    flagged_fields INTEGER, 
    corrected_fields INTEGER, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    CONSTRAINT fk_invoices_duplicate_of_id FOREIGN KEY(duplicate_of_id) REFERENCES invoices (id) ON DELETE SET NULL
);

CREATE INDEX ix_invoices_document_id ON invoices (document_id);

CREATE INDEX ix_invoices_invoice_number ON invoices (invoice_number);

CREATE INDEX ix_invoices_duplicate_of_id ON invoices (duplicate_of_id);

CREATE INDEX ix_invoices_duplicate_key ON invoices (invoice_number_key, supplier_key);

CREATE TABLE invoice_part_number_items (
    id UUID NOT NULL, 
    invoice_id UUID NOT NULL, 
    part_number VARCHAR(64), 
    description TEXT, 
    quantity NUMERIC(18, 4), 
    unit_price NUMERIC(18, 4), 
    amount NUMERIC(18, 2), 
    purchase_order VARCHAR(128), 
    incoterm TEXT, 
    country_of_origin TEXT, 
    domestic_freight NUMERIC(18, 2), 
    packaging TEXT, 
    exporter TEXT, 
    manufacturer TEXT, 
    serial_number VARCHAR(64), 
    field_confidence JSONB, 
    PRIMARY KEY (id), 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id) ON DELETE CASCADE
);

CREATE INDEX ix_invoice_part_number_items_invoice_id ON invoice_part_number_items (invoice_id);

CREATE INDEX ix_invoice_part_number_items_part_number ON invoice_part_number_items (part_number);

CREATE INDEX ix_invoice_part_number_items_purchase_order ON invoice_part_number_items (purchase_order);

CREATE INDEX ix_invoice_part_number_items_serial_number ON invoice_part_number_items (serial_number);

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

CREATE TABLE released_part_numbers (
    part_number VARCHAR(32) NOT NULL, 
    name TEXT, 
    requires_serial BOOLEAN DEFAULT false NOT NULL, 
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    import_batch VARCHAR(128), 
    PRIMARY KEY (part_number)
);

CREATE INDEX ix_released_part_numbers_requires_serial ON released_part_numbers (requires_serial) WHERE requires_serial;

CREATE TABLE serial_rules (
    id SERIAL NOT NULL, 
    substrings TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    manual_part_numbers TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_serial_rules_singleton CHECK (id = 1)
);

INSERT INTO serial_rules (id) VALUES (1);

INSERT INTO alembic_version (version_num) VALUES ('0007');

COMMIT;
