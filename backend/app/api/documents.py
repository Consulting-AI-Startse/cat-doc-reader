import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db, get_storage
from app.processing import enqueue_processing
from shared.models import (
    Document,
    DocumentEvent,
    DocumentStatus,
    Invoice,
    InvoicePartNumberItem,
)

router = APIRouter(prefix="/documents", tags=["documents"])

_EDITABLE = (DocumentStatus.extracted, DocumentStatus.needs_review)


def _opt_str(v) -> str | None:
    v = v.strip() if isinstance(v, str) else v
    return v or None


def _opt_decimal(v) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        raise HTTPException(422, f"valor numérico inválido: {v!r}")


def _opt_date(v) -> date | None:
    v = _opt_str(v)
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise HTTPException(422, f"data inválida: {v!r}")


def _serialize_line(li: InvoicePartNumberItem) -> dict:
    return {
        "part_number": li.part_number,
        "description": li.description,
        "quantity": li.quantity,
        "unit_price": li.unit_price,
        "amount": li.amount,
        "purchase_order": li.purchase_order,
        "incoterm": li.incoterm,
        "country_of_origin": li.country_of_origin,
        "domestic_freight": li.domestic_freight,
        "packaging": li.packaging,
        "exporter": li.exporter,
        "supplier": li.supplier,
        "manufacturer": li.manufacturer,
    }


def _serialize_invoice(inv: Invoice) -> dict:
    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date,
        "currency": inv.currency,
        "total": inv.total,
        "line_items": [_serialize_line(li) for li in inv.line_items],
    }


def _serialize_document(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "status": doc.status.value,
        "source_filename": doc.source_filename,
        "source": doc.source,
        "blob_path": doc.blob_path,
        "extraction_confidence": doc.extraction_confidence,
        "error_message": doc.error_message,
        "created_at": doc.created_at,
        "invoices": [_serialize_invoice(i) for i in doc.invoices],
        "events": [
            {
                "event_type": e.event_type,
                "actor": e.actor,
                "created_at": e.created_at,
                "payload": e.payload,
            }
            for e in doc.events
        ],
    }


class LineIn(BaseModel):
    part_number: str | None = None
    description: str | None = None
    quantity: str | float | None = None
    unit_price: str | float | None = None
    amount: str | float | None = None
    purchase_order: str | None = None
    incoterm: str | None = None
    country_of_origin: str | None = None
    domestic_freight: str | float | None = None
    packaging: str | None = None
    exporter: str | None = None
    supplier: str | None = None
    manufacturer: str | None = None


class InvoiceIn(BaseModel):
    invoice_number: str | None = None
    invoice_date: str | None = None
    currency: str | None = None
    total: str | float | None = None
    line_items: list[LineIn] = []


class DocumentUpdate(BaseModel):
    invoices: list[InvoiceIn]


@router.get("")
def list_documents(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Document)
        .options(selectinload(Document.invoices))
        .order_by(Document.created_at.desc())
    ).all()
    out = []
    for d in rows:
        total = sum((i.total or Decimal(0)) for i in d.invoices)
        out.append({
            "id": str(d.id),
            "status": d.status.value,
            "source_filename": d.source_filename,
            "source": d.source,
            "created_at": d.created_at,
            "invoice_count": len(d.invoices),
            "total": total or None,
        })
    return out


@router.post("/upload")
def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
):
    doc = Document(
        status=DocumentStatus.received,
        source_filename=file.filename,
        source="manual_upload",
    )
    db.add(doc)
    db.flush()
    blob_path = f"incoming/{doc.id}/{file.filename}"
    storage.upload(blob_path, file.file.read())
    doc.blob_path = blob_path
    db.add(DocumentEvent(document_id=doc.id, event_type="received", actor="api"))
    db.commit()
    document_id = doc.id

    background.add_task(enqueue_processing, document_id)
    return {"id": str(document_id), "status": DocumentStatus.received.value}


@router.get("/{document_id}")
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "documento não encontrado")
    return _serialize_document(doc)


@router.get("/{document_id}/file")
def get_document_file(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
):
    doc = db.get(Document, document_id)
    if doc is None or not doc.blob_path:
        raise HTTPException(404, "documento ou arquivo não encontrado")
    data = storage.download(doc.blob_path)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{doc.source_filename or "document.pdf"}"'
        },
    )

@router.get("/{document_id}/raw")
def get_document_raw(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """Saida crua do OCR e do modelo. Existe para inspecao durante a fase de
    treinamento; nao passa pelo schema de revisao."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "documento nao encontrado")
    return {
        "id": str(doc.id),
        "status": doc.status.value,
        "extraction_confidence": doc.extraction_confidence,
        "error_message": doc.error_message,
        "raw_extraction": doc.raw_extraction,
    }


@router.patch("/{document_id}")
def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "documento não encontrado")
    if doc.status not in _EDITABLE:
        raise HTTPException(409, f"status atual ({doc.status.value}) não permite edição")

    doc.invoices.clear()
    for inv_in in payload.invoices:
        inv = Invoice(
            invoice_number=_opt_str(inv_in.invoice_number),
            invoice_date=_opt_date(inv_in.invoice_date),
            currency=_opt_str(inv_in.currency),
            total=_opt_decimal(inv_in.total),
        )
        for li in inv_in.line_items:
            inv.line_items.append(
                InvoicePartNumberItem(
                    part_number=_opt_str(li.part_number),
                    description=_opt_str(li.description),
                    quantity=_opt_decimal(li.quantity),
                    unit_price=_opt_decimal(li.unit_price),
                    amount=_opt_decimal(li.amount),
                    purchase_order=_opt_str(li.purchase_order),
                    incoterm=_opt_str(li.incoterm),
                    country_of_origin=_opt_str(li.country_of_origin),
                    domestic_freight=_opt_decimal(li.domestic_freight),
                    packaging=_opt_str(li.packaging),
                    exporter=_opt_str(li.exporter),
                    supplier=_opt_str(li.supplier),
                    manufacturer=_opt_str(li.manufacturer),
                )
            )
        doc.invoices.append(inv)

    db.add(DocumentEvent(document_id=doc.id, event_type="edited", actor="human"))
    db.commit()
    db.refresh(doc)
    return _serialize_document(doc)


@router.post("/{document_id}/approve")
def approve_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "documento não encontrado")
    if doc.status not in _EDITABLE:
        raise HTTPException(409, f"status atual ({doc.status.value}) não permite aprovação")
    doc.status = DocumentStatus.approved
    db.add(DocumentEvent(document_id=doc.id, event_type="approved", actor="human"))
    db.commit()
    return {"id": str(doc.id), "status": doc.status.value}


@router.post("/{document_id}/reject")
def reject_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "documento não encontrado")
    if doc.status not in _EDITABLE:
        raise HTTPException(409, f"status atual ({doc.status.value}) não permite rejeição")
    doc.status = DocumentStatus.rejected
    db.add(DocumentEvent(document_id=doc.id, event_type="rejected", actor="human"))
    db.commit()
    return {"id": str(doc.id), "status": doc.status.value}
