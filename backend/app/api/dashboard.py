from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db
from shared.models import Document, DocumentStatus, Invoice, InvoicePartNumberItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_NAO_PROC = (DocumentStatus.received, DocumentStatus.processing)
_AGUARDANDO = (DocumentStatus.extracted, DocumentStatus.needs_review)


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    def count_docs(*statuses):
        return (
            db.scalar(
                select(func.count()).select_from(Document).where(Document.status.in_(statuses))
            )
            or 0
        )

    total_docs = db.scalar(select(func.count()).select_from(Document)) or 0
    total_invoices = db.scalar(select(func.count()).select_from(Invoice)) or 0
    valor = db.scalar(select(func.coalesce(func.sum(InvoicePartNumberItem.amount), 0))) or 0
    return {
        "documentos": total_docs,
        "invoices": total_invoices,
        "nao_processados": count_docs(*_NAO_PROC),
        "aguardando_revisao": count_docs(*_AGUARDANDO),
        "aprovados": count_docs(DocumentStatus.approved),
        "erros": count_docs(DocumentStatus.error),
        "valor_total_extraido": float(valor),
    }
