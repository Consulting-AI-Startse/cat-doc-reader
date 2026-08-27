"""initial schema (documents, invoices, part number items, events)

Revision ID: 0001
Revises:
Create Date: 2026-07-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "received", "processing", "extracted", "needs_review",
                "approved", "rejected", "error",
                name="document_status",
            ),
            nullable=False,
        ),
        sa.Column("source_filename", sa.String(length=512), nullable=True),
        sa.Column("source", sa.String(length=64), server_default="manual_upload", nullable=False),
        sa.Column("blob_path", sa.String(length=1024), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("raw_extraction", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_status", "documents", ["status"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sa.String(length=128), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("total", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoices_document_id", "invoices", ["document_id"])
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])

    op.create_table(
        "invoice_part_number_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("part_number", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("purchase_order", sa.String(length=128), nullable=True),
        sa.Column("incoterm", sa.String(length=16), nullable=True),
        sa.Column("country_of_origin", sa.String(length=128), nullable=True),
        sa.Column("domestic_freight", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("packaging", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("exporter", sa.String(length=256), nullable=True),
        sa.Column("supplier", sa.String(length=256), nullable=True),
        sa.Column("manufacturer", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_part_number_items_invoice_id", "invoice_part_number_items", ["invoice_id"])
    op.create_index("ix_invoice_part_number_items_part_number", "invoice_part_number_items", ["part_number"])
    op.create_index("ix_invoice_part_number_items_purchase_order", "invoice_part_number_items", ["purchase_order"])

    op.create_table(
        "document_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=256), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_events_document_id", "document_events", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_events_document_id", table_name="document_events")
    op.drop_table("document_events")
    op.drop_index("ix_invoice_part_number_items_purchase_order", table_name="invoice_part_number_items")
    op.drop_index("ix_invoice_part_number_items_part_number", table_name="invoice_part_number_items")
    op.drop_index("ix_invoice_part_number_items_invoice_id", table_name="invoice_part_number_items")
    op.drop_table("invoice_part_number_items")
    op.drop_index("ix_invoices_invoice_number", table_name="invoices")
    op.drop_index("ix_invoices_document_id", table_name="invoices")
    op.drop_table("invoices")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_table("documents")
    sa.Enum(name="document_status").drop(op.get_bind(), checkfirst=True)
