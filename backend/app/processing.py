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
    except Exception:
        logger.exception(
            "FALHA ao chamar a function para documento %s (url=%s)",
            document_id,
            settings.function_url,
        )
        raise
