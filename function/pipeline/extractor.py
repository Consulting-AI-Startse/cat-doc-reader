import hashlib
import os
import random
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Any

_SUPPLIERS = [
    "Perkins Engines Company Ltd.", "ACME Corp", "Globex Industries",
    "Stark Manufacturing", "Wuxi Diesel Co.",
]
_MANUFACTURERS = ["Perkins", "Caterpillar Inc.", "Bosch", "Cummins", "Denso"]
_EXPORTERS = ["Perkins Shipping UK", "Globex Export LLC", "Stark Logistics", "Wuxi Export Co."]
_PRODUCTS = [
    "MODULE AR-DEF", "Hydraulic pump", "Steel bearing set", "Diesel filter",
    "Track roller", "Cylinder seal kit", "Brake assembly", "Alternator unit",
]
_INCOTERMS = ["FOB", "CIF", "EXW", "FCA", None, None]
_COUNTRIES = ["United Kingdom", "China", "United States", "Germany", "Brazil"]
_CURRENCIES = ["USD", "EUR", "BRL"]
_PACKAGING_TYPES = ["EUROPALLET", "Caixa de madeira", "Pallet", "Skid"]


LOW_CONFIDENCE = 0.85
MAX_LOW_CONFIDENCE_WORDS = 120
SPARSE_PAGE_WORDS = 20
MAX_TABLE_CELLS = 4000


class DocumentExtractor(ABC):

    @abstractmethod
    def extract(self, content: bytes) -> dict[str, Any]:
        ...


def _field(fields: dict, name: str):
    """prebuilt-invoice field values, tolerant of SDK version differences."""
    f = fields.get(name) if fields else None
    if f is None:
        return None
    for attr in ("value_string", "value_date", "value_number", "value_integer"):
        v = getattr(f, attr, None)
        if v is not None:
            return str(v) if attr == "value_date" else v
    currency = getattr(f, "value_currency", None)
    if currency is not None:
        return getattr(currency, "amount", None)
    return getattr(f, "content", None)


def _spans(obj):
    """offset/length dentro de content -- leve e permite achar o valor no texto.

    O SDK usa 'spans' (lista) em campos e celulas, mas 'span' (singular) em
    palavras. Ler so 'spans' devolvia lista vazia para toda palavra ruim, o
    que tornava impossivel localizar o trecho no content.
    """
    raw = getattr(obj, "spans", None)
    if raw is None:
        one = getattr(obj, "span", None)
        raw = [one] if one is not None else []
    out = []
    for s in raw or []:
        out.append({"offset": getattr(s, "offset", None), "length": getattr(s, "length", None)})
    return out


def _pages_of(obj):
    """so o numero da pagina; poligono por celula seria grande demais."""
    return sorted({
        getattr(r, "page_number", None)
        for r in (getattr(obj, "bounding_regions", None) or [])
        if getattr(r, "page_number", None) is not None
    })


def _tables_of(result):
    out = []
    cells_left = MAX_TABLE_CELLS
    for t in (getattr(result, "tables", None) or []):
        cells = []
        for c in (getattr(t, "cells", None) or []):
            if cells_left <= 0:
                break
            cells.append({
                "row": getattr(c, "row_index", None),
                "col": getattr(c, "column_index", None),
                "row_span": getattr(c, "row_span", None) or 1,
                "col_span": getattr(c, "column_span", None) or 1,
                "kind": getattr(c, "kind", None) or "content",
                "content": getattr(c, "content", None),
                "spans": _spans(c),
            })
            cells_left -= 1
        out.append({
            "rows": getattr(t, "row_count", None),
            "columns": getattr(t, "column_count", None),
            "pages": _pages_of(t),
            "cells": cells,
        })
        if cells_left <= 0:
            break
    return out


def _pages_and_quality(result):
    """Resumo por pagina, palavras ruins e um placar do documento.

    A lista completa de palavras nao entra: 35 paginas viram megabytes. O que
    fica e o suficiente para responder "quao bem o OCR leu este documento".
    """
    pages = []
    candidates = []
    total_words = 0
    all_confidences = []

    for p in (getattr(result, "pages", None) or []):
        words = list(getattr(p, "words", None) or [])
        page_number = getattr(p, "page_number", None)
        confidences = [
            w.confidence for w in words if getattr(w, "confidence", None) is not None
        ]
        total_words += len(words)
        all_confidences.extend(confidences)

        pages.append({
            "page_number": page_number,
            "angle": getattr(p, "angle", None),
            "word_count": len(words),
            "min_word_confidence": min(confidences) if confidences else None,
            "mean_word_confidence": (
                round(sum(confidences) / len(confidences), 4) if confidences else None
            ),
            # Media com poucas palavras nao significa nada. A pagina 32 do CIV
            # tem UMA palavra a 0.31 e parecia ilegivel -- esta em branco, o
            # que o OCR leu foi ruido do scanner. Quem consumir o resumo por
            # pagina deve ignorar as marcadas aqui.
            "sparse": len(words) < SPARSE_PAGE_WORDS,
        })

        for w in words:
            c = getattr(w, "confidence", None)
            if c is not None and c < LOW_CONFIDENCE:
                candidates.append({
                    "page": page_number,
                    "content": getattr(w, "content", None),
                    "confidence": c,
                    "spans": _spans(w),
                })

    # As PIORES, nao as primeiras. Com o corte aplicado durante a varredura o
    # limite se esgotava nas paginas iniciais e o resto do documento ficava
    # invisivel -- justamente onde estao as paginas piores.
    candidates.sort(key=lambda w: w["confidence"])
    low = candidates[:MAX_LOW_CONFIDENCE_WORDS]

    dense = [
        pg for pg in pages
        if not pg["sparse"] and pg["mean_word_confidence"] is not None
    ]
    quality = {
        "page_count": len(pages),
        "word_count": total_words,
        "min_word_confidence": min(all_confidences) if all_confidences else None,
        # A media do documento e ponderada por palavra, entao paginas esparsas
        # nao a distorcem.
        "mean_word_confidence": (
            round(sum(all_confidences) / len(all_confidences), 4) if all_confidences else None
        ),
        "blank_or_sparse_pages": [pg["page_number"] for pg in pages if pg["sparse"]],
        "worst_dense_page": (
            min(dense, key=lambda pg: pg["mean_word_confidence"])["page_number"]
            if dense else None
        ),
        "words_below_threshold": len(candidates),
        "words_below_threshold_kept": len(low),
        "threshold": LOW_CONFIDENCE,
        "sparse_page_words": SPARSE_PAGE_WORDS,
    }
    return pages, low, quality


def tables_summary(tables):
    """O que vale gravar. As celulas ja estao no content como HTML; guardar de
    novo custa ~4x o texto do documento no jsonb sem acrescentar informacao."""
    return [
        {
            "rows": t["rows"],
            "columns": t["columns"],
            "pages": t["pages"],
            "cell_count": len(t["cells"]),
            "header_cells": sum(1 for c in t["cells"] if c["kind"] == "columnHeader"),
        }
        for t in tables
    ]


class DocumentIntelligenceExtractor(DocumentExtractor):
    """prebuilt-invoice pre-pass. Returns the structured fields it can find plus
    the full document text, which the structurer mines for the fields the
    prebuilt model does not return (incoterm, packaging, exporter, ...)."""

    MODEL_ID = "prebuilt-layout"

    def __init__(
            self,
            endpoint: str,
            key: str | None = None,
            high_resolution: bool = True,
        ) -> None:
        from azure.ai.documentintelligence import DocumentIntelligenceClient

        if not endpoint:
            raise ValueError("AZURE_DOCINTEL_ENDPOINT nao configurado")

        if key:
            from azure.core.credentials import AzureKeyCredential   

            credential = AzureKeyCredential(key)
        else:
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()

        self._client = DocumentIntelligenceClient(endpoint=endpoint, credential=credential)
        self._features = ["ocrHighResolution"] if high_resolution else None


    def extract(self, content: bytes) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if self._features:
            options["features"] = self._features

        poller = self._client.begin_analyze_document(
            self.MODEL_ID,
            body=content,
            content_type="application/octet-stream",
            output_content_format="markdown",
            **options,
        )
        result = poller.result()    

        invoices = []
        confidences = []
        for document in result.documents or []:
            fields = document.fields or {}
            if document.confidence is not None:
                confidences.append(float(document.confidence))

            items = []
            items_field = fields.get("Items")
            for entry in (getattr(items_field, "value_array", None) or []):
                item_fields = getattr(entry, "value_object", None) or {}
                items.append({
                    "part_number": _field(item_fields, "ProductCode"),
                    "description": _field(item_fields, "Description"),
                    "quantity": _field(item_fields, "Quantity"),
                    "unit_price": _field(item_fields, "UnitPrice"),
                    "amount": _field(item_fields, "Amount"),
                    "purchase_order": _field(fields, "PurchaseOrder"),
                    "supplier": _field(fields, "VendorName"),
                })

            invoices.append({
                "invoice_number": _field(fields, "InvoiceId"),
                "invoice_date": _field(fields, "InvoiceDate"),
                "currency": _field(fields, "CurrencyCode"),
                "total": _field(fields, "InvoiceTotal"),
                "items": items,
            })

        text = result.content or ""
        pages, low_words, quality = _pages_and_quality(result)
        return {
            "model": self.MODEL_ID,
            "confidence": min(confidences) if confidences else None,
            "invoices": invoices,
            "content": text,
            "tables": _tables_of(result),
            "pages": pages,
            "low_confidence_words": low_words,
            "quality": quality,
        }


class MockExtractor(DocumentExtractor):

    def extract(self, content: bytes) -> dict[str, Any]:
        seed = int.from_bytes(hashlib.sha256(content + os.urandom(8)).digest()[:8], "big")
        rng = random.Random(seed)

        invoices = []
        for _ in range(rng.randint(2, 3)):
            currency = rng.choice(_CURRENCIES)
            supplier = rng.choice(_SUPPLIERS)
            manufacturer = rng.choice(_MANUFACTURERS)
            exporter = rng.choice(_EXPORTERS)
            incoterm = rng.choice(_INCOTERMS)
            origin = rng.choice(_COUNTRIES)
            po = f"QIPD{rng.randint(10000, 99999)}"
            inv_no = f"{rng.randint(24, 25)}CINVDX{rng.randint(100000, 999999)}"
            inv_dt = date.today() - timedelta(days=rng.randint(0, 90))

            items = []
            for _ in range(rng.randint(1, 3)):
                qty = rng.randint(1, 40)
                unit = round(rng.uniform(40, 1800), 2)
                items.append({
                    "part_number": str(rng.randint(1000000, 9999999)),
                    "description": rng.choice(_PRODUCTS),
                    "quantity": qty,
                    "unit_price": unit,
                    "amount": round(qty * unit, 2),
                    "purchase_order": po if rng.random() > 0.15 else f"QIPD{rng.randint(10000, 99999)}",
                    "incoterm": incoterm,
                    "country_of_origin": origin,
                    "domestic_freight": round(rng.uniform(0, 500), 2),
                    "packaging": f"{rng.choice(_PACKAGING_TYPES)} {rng.choice([1200, 1000, 800])}x{rng.choice([800, 600])}x{rng.randint(200, 400)} mm",
                    "exporter": exporter,
                    "supplier": supplier,
                    "manufacturer": manufacturer,
                })
            invoices.append({
                "invoice_number": inv_no,
                "invoice_date": inv_dt.isoformat(),
                "currency": currency,
                "items": items,
            })

        conf = round(rng.uniform(0.70, 0.89), 2) if rng.random() < 0.2 else round(rng.uniform(0.91, 0.99), 2)
        return {"model": "mock-prebuilt-invoice", "confidence": conf, "invoices": invoices}
