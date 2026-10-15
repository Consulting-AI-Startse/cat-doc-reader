from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db
from shared.metrics import processing_report
from shared.models import Document, Invoice

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _docs(db: Session, days: int) -> list[dict]:
    """Os documentos do periodo, no formato que shared.metrics agrega.

    Uma consulta com as relacoes carregadas: volume de POV, e a agregacao
    e pura de proposito -- o teste dela roda sem banco (check_rules.py).
    """
    q = select(Document).options(
        selectinload(Document.invoices).selectinload(Invoice.line_items),
        selectinload(Document.events),
    )
    # A data e a do DOCUMENTO (upload), como no relatorio por fornecedor: o
    # PATCH recria as invoices, e a data delas e a da ultima edicao.
    if days > 0:
        q = q.where(Document.created_at >= datetime.now(timezone.utc) - timedelta(days=days))
    out = []
    for doc in db.scalars(q).all():
        inicio = [e.created_at for e in doc.events if e.event_type == "processing"]
        out.append({
            "status": doc.status.value,
            "created_at": doc.created_at,
            "started_at": min(inicio) if inicio else None,
            "processed_at": doc.processed_at,
            "reviewed": any(e.event_type == "needs_review" for e in doc.events),
            "invoices": [{
                "duplicate": inv.duplicate_of_id is not None,
                "amount": sum(float(li.amount) for li in inv.line_items
                              if li.amount is not None),
                "header_fc": inv.field_confidence,
                "lines_fc": [li.field_confidence for li in inv.line_items],
            } for inv in doc.invoices],
        })
    return out


@router.get("/metrics")
def metrics(
    days: int = Query(0, ge=0, description="janela em dias; 0 = tudo"),
    db: Session = Depends(get_db),
):
    return {"days": days, **processing_report(_docs(db, days))}
