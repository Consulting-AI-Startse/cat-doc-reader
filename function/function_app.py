import json
import logging
from uuid import UUID

import azure.functions as func

from doc_worker import process_document_task

# Nome valido de fila: minusculas, numeros e hifen, 3-63 caracteres.
QUEUE_NAME = "document-processing"

logger = logging.getLogger("function_app")

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="process_document", methods=["POST"])
@app.queue_output(
    arg_name="msg", queue_name=QUEUE_NAME, connection="AzureWebJobsStorage"
)
def process_document(req: func.HttpRequest, msg: func.Out[str]) -> func.HttpResponse:
    """Apenas enfileira. O processamento nao cabe num request HTTP: o backend
    espera com timeout de 60s e o gateway do Functions corta em ~230s."""
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("invalid json body", status_code=400)

    document_id = body.get("document_id")
    if not document_id:
        return func.HttpResponse("missing document_id", status)

    try:
        UUID(str(document_id))
    except (ValueError, AttributeError, TypeError):
        return func.HttpResponse("document_id nao e um UUID", status_code=400)

    msg.set(json.dumps({"document_id": str(document_id)}))
    logger.info("documento %s enfileirado em %s", document_id, QUEUE_NAME)

    return func.HttpResponse(
        json.dumps({"status": "queued", "document_id": str(document_id)}),
        mimetype="application/json",
        status_code=202,
    )


def _document_id_from(body: bytes) -> str:
    """Aceita {"document_id": "..."} ou o id cru, para nao dep
    codificacao que a fila usa."""
    text = body.decode("utf-8").strip()
    try:
        return str(json.loads(text)["document_id"])
    except (ValueError, KeyError, TypeError):
        return text


@app.queue_trigger(
    arg_name="msg", queue_name=QUEUE_NAME, connection="AzureWebJobsStorage"
)
def process_document_worker(msg: func.QueueMessage) -> None:
    document_id = _document_id_from(msg.get_body())
    logger.info(
        "processando documento %s (tentativa %s)", document_id, msg.dequeue_count
    )
    process_document_task(UUID(document_id))
    logger.info("documento %s concluido", document_id)


@app.queue_trigger(
    arg_name="msg",
    queue_name=QUEUE_NAME + "-poison",
    connection="AzureWebJobsStorage",
)
def process_document_poison(msg: func.QueueMessage) -> None:
    """Sem isto, uma mensagem que esgotou as tentativas desaparece em silencio e
    o documento fica preso em 'processing' para sempre."""
    logger.error(
        "POISON: documento %s falhou %s vezes e foi descartado; o registro fica "
        "em 'processing' ate ser reprocessado",
        _document_id_from(msg.get_body()),
        msg.dequeue_count,
    )