from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy.orm import Session

from shared.config import settings
from shared.db import SessionLocal
from shared.dedupe import find_original, normalise_invoice_number, normalise_supplier
from shared.models import (
    Document,
    DocumentEvent,
    DocumentStatus,
    Invoice,
    InvoicePartNumberItem,
)
from shared.storage import BlobStorage, get_blob_storage

from pipeline.extractor import DocumentExtractor, MockExtractor, tables_summary
from pipeline.structurer import LLMStructurer, MockStructurer

# Gancho do modo local. doc_worker_local.py esta no .funcignore e nao vai para o
# Function App, entao la este import falha e sobra None -- o caminho de producao
# segue direto. E o que mantem ESTE arquivo identico ao do repo da Caterpillar:
# enquanto os blocos de modo local moravam aqui, ele divergia em ~24 linhas e
# nenhum diff dele aplicava la.
try:
    import doc_worker_local as _local
except ModuleNotFoundError:
    _local = None

CONFIDENCE_THRESHOLD = 0.90


def build_extractor() -> DocumentExtractor:
    if _local and (extractor := _local.build_extractor()) is not None:
        return extractor
    if settings.use_real_services:
        from pipeline.extractor import DocumentIntelligenceExtractor

        return DocumentIntelligenceExtractor(
            endpoint=settings.azure_docintel_endpoint,
            key=settings.azure_docintel_key or None,
            high_resolution=settings.azure_docintel_high_res,
        )
    return MockExtractor()


def build_structurer() -> LLMStructurer:
    if _local and (structurer := _local.build_structurer()) is not None:
        return structurer
    if settings.use_real_services:
        from pipeline.structurer import AzureOpenAIStructurer

        return AzureOpenAIStructurer(
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
            key=settings.azure_openai_key or None,
        )
    return MockStructurer()


def _dec(v) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _date(v) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def process_document(
    document_id: UUID,
    db: Session,
    storage: BlobStorage,
    extractor: DocumentExtractor,
    structurer: LLMStructurer,
) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise ValueError(f"documento {document_id} nao existe")

    doc.status = DocumentStatus.processing
    db.add(DocumentEvent(document_id=doc.id, event_type="processing", actor="worker"))
    db.commit()

    try:
        content = storage.download(doc.blob_path)
        extraction = extractor.extract(content)
        result = structurer.structure(extraction)

        doc.invoices.clear()
        duplicates = []
        for inv in result.get("invoices", []):
            invoice = Invoice(
                invoice_number=inv.get("invoice_number"),
                invoice_date=_date(inv.get("invoice_date")),
                supplier=inv.get("supplier"),
                invoice_number_key=normalise_invoice_number(inv.get("invoice_number")),
                supplier_key=normalise_supplier(inv.get("supplier")),
                currency=inv.get("currency"),
                total=_dec(inv.get("total")),
            )
            for li in inv.get("line_items", []):
                invoice.line_items.append(
                    InvoicePartNumberItem(
                        part_number=li.get("part_number"),
                        description=li.get("description"),
                        quantity=_dec(li.get("quantity")),
                        unit_price=_dec(li.get("unit_price")),
                        amount=_dec(li.get("amount")),
                        purchase_order=li.get("purchase_order"),
                        incoterm=li.get("incoterm"),
                        country_of_origin=li.get("country_of_origin"),
                        domestic_freight=_dec(li.get("domestic_freight")),
                        packaging=li.get("packaging"),
                        exporter=li.get("exporter"),
                        manufacturer=li.get("manufacturer"),
                    )
                )
            doc.invoices.append(invoice)

            # A duplicata e por INVOICE, nao por documento: um CIV traz seis
            # faturas de seis fornecedores, e so uma delas pode ser repetida.
            #
            # O flush antes da busca e o que faz a deteccao funcionar DENTRO do
            # mesmo documento: sem ele, a segunda copia de uma fatura repetida
            # no proprio PDF nao encontraria a primeira, que ainda estaria so na
            # memoria da sessao.
            db.flush()
            original = find_original(
                db,
                invoice_number_key=invoice.invoice_number_key,
                supplier_key=invoice.supplier_key,
                exclude_invoice_id=invoice.id,
            )
            if original is not None:
                invoice.duplicate_of_id = original.id
                duplicates.append(
                    "invoice '%s' (%s) ja existe no documento %s; marcada como "
                    "duplicada -- a primeira e a referencia"
                    % (invoice.invoice_number, invoice.supplier, original.document_id)
                )

        confidence = result.get("confidence")
        doc.extraction_confidence = confidence
        stored = dict(extraction)
        if stored.get("tables"):
            stored["tables"] = tables_summary(stored["tables"])
        doc.raw_extraction = dict(
            stored, structured=result, validation=result.get("validation")
        )
        doc.processed_at = datetime.now(timezone.utc)

        validation = list(result.get("validation") or []) + duplicates
        if validation:
            db.add(
                DocumentEvent(
                    document_id=doc.id,
                    event_type="validation",
                    actor="worker",
                    payload={"issues": validation},
                )
            )

        # Duplicata sempre vai para revisao humana, por mais limpa que a
        # extracao tenha saido: a confianca mede a leitura, nao o fato de a
        # fatura ja ter entrado antes.
        ok = (confidence or 0) >= CONFIDENCE_THRESHOLD and not duplicates
        doc.status = DocumentStatus.extracted if ok else DocumentStatus.needs_review
        db.add(DocumentEvent(document_id=doc.id, event_type=doc.status.value, actor="worker"))
    except Exception as exc:
        doc.status = DocumentStatus.error
        doc.error_message = str(exc)
        db.add(
            DocumentEvent(
                document_id=doc.id,
                event_type="error",
                actor="worker",
                payload={"error": str(exc)},
            )
        )
    try:
        db.commit()
    except Exception as exc:    
        db.rollback()
        doc = db.get(Document, document_id)
        if doc is not None:
            doc.status = DocumentStatus.error
            doc.error_message = f"falha ao gravar no banco: {exc}"
            db.add(
                DocumentEvent(
                    document_id=doc.id,
                    event_type="error",
                    actor="worker",
                    payload={"error": str(exc)},
                )
            )
            try:
                db.commit()
            except Exception:
                db.rollback()

    db.refresh(doc)
    return doc


def mark_failed(document_id: UUID, message: str) -> str:
    """Grava o fracasso que o worker nao conseguiu gravar sozinho.

    O `except` do process_document() so roda se o processo continuar vivo. Quando
    ele morre antes disso -- OOM no fallback por imagem, host reciclado -- ninguem
    escreve nada e o documento fica em 'processing' para sempre, sem erro e sem
    pista para quem revisa. Aconteceu duas vezes com o CIV.

    Devolve o que foi feito, para o chamador registrar no log.
    """
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return "not_found"

        # Estado terminal nao e sobrescrito: o worker pode ter comitado o
        # resultado e morrido logo depois, e ai o documento esta correto --
        # marca-lo como error destruiria extracao boa.
        if doc.status not in (DocumentStatus.received, DocumentStatus.processing):
            return f"already_final:{doc.status.value}"

        doc.status = DocumentStatus.error
        doc.error_message = message
        db.add(
            DocumentEvent(
                document_id=doc.id,
                event_type="error",
                actor="poison",
                payload={"error": message},
            )
        )
        db.commit()
        return "marked"
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_document_task(document_id: UUID) -> None:
    db = SessionLocal()
    try:
        process_document(
            document_id, db, get_blob_storage(), build_extractor(), build_structurer()
        )
    finally:
        db.close()
