from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db
from shared.confidence import field_breakdown, supplier_report
from shared.models import Document, DocumentStatus, Invoice

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

# Rejeitar quer dizer "esta leitura nao presta" e erro nao tem leitura: nenhum
# dos dois diz nada sobre como o fornecedor imprime. Mesma regra da duplicata.
_CONTAM = (DocumentStatus.extracted, DocumentStatus.needs_review, DocumentStatus.approved)


def _invoices(db: Session, days: int, supplier_key: str | None = None, so_um: bool = False):
    q = (
        select(Invoice, Document.status, Document.source_filename, Document.created_at)
        .join(Document, Invoice.document_id == Document.id)
        .where(Document.status.in_(_CONTAM))
        # A copia de uma duplicata e a mesma fatura: contaria duas vezes.
        .where(Invoice.duplicate_of_id.is_(None))
        .options(selectinload(Invoice.line_items))
    )
    # A data e a do DOCUMENTO: o PATCH recria as invoices, entao a delas e a
    # da ultima edicao, e o periodo passaria a contar quando foi revisado.
    if days > 0:
        q = q.where(Document.created_at >= datetime.now(timezone.utc) - timedelta(days=days))
    if so_um:
        q = q.where(Invoice.supplier_key.is_(None) if supplier_key is None
                    else Invoice.supplier_key == supplier_key)
    out = []
    for inv, status, filename, recebido in db.execute(q).all():
        out.append({
            "supplier_key": inv.supplier_key,
            "supplier": inv.supplier,
            "invoice_id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "document_id": str(inv.document_id),
            "document_status": status.value,
            "source_filename": filename,
            "created_at": recebido.isoformat() if recebido else None,
            "min_field_confidence": inv.min_field_confidence,
            "mean_field_confidence": inv.mean_field_confidence,
            "flagged_fields": inv.flagged_fields,
            "corrected_fields": inv.corrected_fields,
            "header_fc": inv.field_confidence,
            "lines_fc": [li.field_confidence for li in inv.line_items],
        })
    return out


@router.get("/confidence")
def confidence_by_supplier(
    days: int = Query(0, ge=0, description="janela em dias; 0 = tudo"),
    db: Session = Depends(get_db),
):
    return {"days": days, "suppliers": supplier_report(_invoices(db, days))}


# A chave vai em query, nao no caminho: fornecedor ausente tem chave nula, e
# '(sem fornecedor)' tambem precisa de detalhe.
@router.get("/confidence/detail")
def supplier_detail(
    key: str | None = Query(None, description="supplier_key; ausente = sem fornecedor"),
    days: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    invs = _invoices(db, days, key, so_um=True)
    resumo = supplier_report(invs)
    return {
        "supplier": resumo[0] if resumo else None,
        "fields": field_breakdown([i for i in invs if i["min_field_confidence"] is not None]),
        "invoices": [
            {k: i[k] for k in ("invoice_id", "invoice_number", "document_id", "document_status",
                               "source_filename", "created_at", "min_field_confidence",
                               "mean_field_confidence", "flagged_fields", "corrected_fields")}
            for i in sorted(invs, key=lambda i: str(i["created_at"] or ""), reverse=True)
        ],
    }
