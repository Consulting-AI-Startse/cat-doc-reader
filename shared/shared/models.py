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
    Index,
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
    __table_args__ = (
        # A consulta de duplicata filtra pelas duas colunas juntas, sempre.
        Index("ix_invoices_duplicate_key", "invoice_number_key", "supplier_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    invoice_number: Mapped[str | None] = mapped_column(String(128), index=True)
    invoice_date: Mapped[date | None] = mapped_column(Date)

    # Fornecedor e do cabecalho da fatura, nao da linha. Morou em
    # InvoicePartNumberItem ate a 0004, e a tela ja denunciava o erro lendo
    # 'line_items[0].supplier' e escrevendo em todas as linhas de uma vez.
    # Conferido no CIV, o documento mais dificil do corpus: 6 invoices de 6
    # fornecedores, cada uma com um fornecedor so.
    supplier: Mapped[str | None] = mapped_column(Text)

    # As duas metades da chave de duplicata, normalizadas (shared/dedupe.py).
    # Gravadas em coluna, e nao calculadas na consulta, porque o indice
    # composto e o que evita varrer a tabela a cada documento novo.
    invoice_number_key: Mapped[str | None] = mapped_column(String(128))
    supplier_key: Mapped[str | None] = mapped_column(String(128))

    # Aponta para a PRIMEIRA invoice com esta chave. Preenchido so na copia: a
    # original e a referencia e nunca recebe marca.
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), index=True
    )
    # String(16), nao (3): a migracao 0003 alargou depois de um documento
    # trazer moeda fora do padrao ISO de tres letras.
    currency: Mapped[str | None] = mapped_column(String(16))
    total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="invoices")
    # remote_side: auto-referencia, entao o SQLAlchemy precisa saber qual lado
    # e o "um" -- sem isso ele le a FK como colecao e o relacionamento nao monta.
    duplicate_of: Mapped[Invoice | None] = relationship(
        "Invoice", remote_side="Invoice.id", lazy="joined"
    )
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
    # Text, nao String(n): a 0003 alargou os seis campos abaixo depois de um
    # incoterm real estourar VARCHAR(16). Campo livre de documento nao tem
    # tamanho previsivel.
    incoterm: Mapped[str | None] = mapped_column(Text)
    country_of_origin: Mapped[str | None] = mapped_column(Text)
    domestic_freight: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    packaging: Mapped[str | None] = mapped_column(Text)
    exporter: Mapped[str | None] = mapped_column(Text)
    manufacturer: Mapped[str | None] = mapped_column(Text)

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
