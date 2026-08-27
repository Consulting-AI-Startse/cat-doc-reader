from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DocumentStatus(str, enum.Enum):

    received = "received"
    processing = "processing"
    extracted = "extracted"
    needs_review = "needs_review"
    approved = "approved"
    rejected = "rejected"
    error = "error"


class Document(Base):

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"),
        default=DocumentStatus.received,
        nullable=False,
        index=True,
    )

    source_filename: Mapped[str | None] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(64), default="manual_upload", nullable=False)
    blob_path: Mapped[str | None] = mapped_column(String(1024))

    extraction_confidence: Mapped[float | None] = mapped_column(sa.Float)
    raw_extraction: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    invoices: Mapped[list[Invoice]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    events: Mapped[list[DocumentEvent]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Invoice(Base):

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    invoice_number: Mapped[str | None] = mapped_column(String(128), index=True)
    invoice_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str | None] = mapped_column(String(3))
    total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="invoices")
    line_items: Mapped[list[InvoicePartNumberItem]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoicePartNumberItem(Base):

    __tablename__ = "invoice_part_number_items"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )

    part_number: Mapped[str | None] = mapped_column(String(64), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    purchase_order: Mapped[str | None] = mapped_column(String(128), index=True)
    incoterm: Mapped[str | None] = mapped_column(String(16))
    country_of_origin: Mapped[str | None] = mapped_column(String(128))
    domestic_freight: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    packaging: Mapped[str | None] = mapped_column(String(128))
    exporter: Mapped[str | None] = mapped_column(String(256))
    supplier: Mapped[str | None] = mapped_column(String(256))
    manufacturer: Mapped[str | None] = mapped_column(String(256))

    invoice: Mapped[Invoice] = relationship(back_populates="line_items")


class DocumentEvent(Base):

    __tablename__ = "document_events"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(256))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="events")
