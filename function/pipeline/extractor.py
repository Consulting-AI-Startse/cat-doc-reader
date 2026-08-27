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


class DocumentExtractor(ABC):

    @abstractmethod
    def extract(self, content: bytes) -> dict[str, Any]:
        ...


_MAX_CONTENT_CHARS = 60000


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


class DocumentIntelligenceExtractor(DocumentExtractor):
    """prebuilt-invoice pre-pass. Returns the structured fields it can find plus
    the full document text, which the structurer mines for the fields the
    prebuilt model does not return (incoterm, packaging, exporter, ...)."""

    MODEL_ID = "prebuilt-invoice"

    def __init__(self, endpoint: str, key: str | None = None) -> None:
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

    def extract(self, content: bytes) -> dict[str, Any]:
        poller = self._client.begin_analyze_document(
            self.MODEL_ID, body=content, content_type="application/octet-stream"
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
        return {
            "model": self.MODEL_ID,
            "confidence": min(confidences) if confidences else 0.0,
            "invoices": invoices,
            "content": text[:_MAX_CONTENT_CHARS],
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
