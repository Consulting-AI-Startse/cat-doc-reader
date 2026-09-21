import json
import logging
import urllib.request
from uuid import UUID

from shared.config import settings

logger = logging.getLogger("uvicorn.error")


def enqueue_processing(document_id: UUID) -> None:
    if not settings.function_url:
        logger.error(
            "PROCESSAMENTO NAO DISPARADO: function_url vazio. "
            "Documento %s ficara preso em 'received'. Configure FUNCTION_URL no .env.",
            document_id,
        )
        return
    try:
        body = json.dumps({"document_id": str(document_id)}).encode("utf-8")
        request = urllib.request.Request(settings.function_url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        if settings.function_key:
            request.add_header("x-functions-key", settings.function_key)
        with urllib.request.urlopen(request, timeout=60) as response:
            response.read()
        logger.info("Function chamada com sucesso para documento %s", document_id)
    except Exception as exc:
        logger.exception(
            "FALHA ao chamar a function para documento %s (url=%s)",
            document_id,
            settings.function_url,
        )
        _mark_transport_error(document_id, exc)


def _mark_transport_error(document_id: UUID, exc: Exception) -> None:
    """A function nao foi alcancada (rede/auth/URL errada): marca o documento
    como erro pra nao ficar preso em "received" na tela. Se a function FOI
    alcancada mas falhou na extracao, quem grava status=error e o worker."""
    from shared.db import SessionLocal
    from shared.models import Document, DocumentEvent, DocumentStatus

    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        doc.status = DocumentStatus.error
        doc.error_message = f"falha ao acionar a function: {exc}"
        db.add(
            DocumentEvent(
                document_id=doc.id,
                event_type="error",
                actor="api",
                payload={"error": str(exc)},
            )
        )
        db.commit()
    except Exception:
        logger.exception("falha ao registrar erro de transporte do documento %s", document_id)
        db.rollback()
    finally:
        db.close()
