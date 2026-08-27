import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("structurer")

# Um desvio maior que isto reprova a conferencia aritmetica.
TOLERANCE_ABS = 0.02
TOLERANCE_REL = 0.005

# Part numbers da Caterpillar sao 7 digitos. "0V3456" e "I/C Material" nao sao PN.
PART_NUMBER_RE = re.compile(r"^\d{7}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Confianca imposta quando qualquer validacao falha. Precisa ficar abaixo de
# CONFIDENCE_THRESHOLD (0.90) em doc_worker para forcar 'needs_review'.
REVIEW_CONFIDENCE = 0.50

# Montado em pedacos de proposito: filtros de email (URL Defense) reescrevem
# URLs literais no codigo e corrompem o escopo do token.
_AOAI_SCOPE = "https" + "://" + ".".join(["cognitiveservices", "azure", "com"]) + "/" + ".default"

# O modelo declarou ter lido o numero da invoice em "CAT Invoice#" mesmo quando
# devolveu o numero de outro campo. Entao lemos nos mesmos, do texto do OCR.
# O OCR intercala as duas colunas do topo do documento, entao o valor NAO vem
# logo depois do rotulo -- procuramos pelo formato do numero numa janela apos o
# rotulo e, se falhar, no documento inteiro.
CAT_LABEL_RE = re.compile(r"CAT\s*Invoice\s*#", re.IGNORECASE)
CAT_NUMBER_RE = re.compile(r"\b([A-Z]{2}\d{2})\s*(\d{6})\b")
CAT_WINDOW = 400

_SYSTEM_PROMPT = """\
You are a data-structuring engine for Caterpillar supplier invoices.
A document may contain MULTIPLE invoices; each invoice has MULTIPLE part-number lines.

Return ONLY JSON in exactly this shape:

{"invoices": [{"invoice_number", "invoice_number_source", "invoice_date" (YYYY-MM-DD),
"currency", "freight", "total", "line_items": [{"part_number", "description",
"quantity", "unit_price", "amount", "purchase_order", "incoterm",
"country_of_origin", "domestic_freight", "packaging", "exporter", "supplier",
"manufacturer"}]}], "confidence": 0..1}

HARD RULES — these are the errors that have actually occurred:

1. INVOICE NUMBER. Take it from the field labelled "CAT Invoice#" and nowhere else.
   These are NOT the invoice number, even though they look like one:
   "Number/Date", "CO Invoice Number", "Delivery note no./Date", "Order number/Date",
   "CAT Order number", "Purchase Order Number", and the PDF filename.
   In "invoice_number_source" report the literal label you actually read it from.
   If you could not find "CAT Invoice#", say so there — do not claim you used it.

2. PART NUMBERS. A part_number must appear literally in the document as a part
   number and is 7 digits. Never construct one. If a value is a description
   fragment, a marking, or an end-use note (for example "I/C Material END USE:"
   or "END USE: CAPTIVE ENGINE"), it is not a part number and must NOT become a
   line item at all.

3. PRICES. amount = quantity x unit_price. The per-unit price goes in
   "unit_price" and never in "amount". If the document shows a quantity and an
   extended amount only, derive unit_price = amount / quantity.

4. FREIGHT. Report freight ONCE, at invoice level, in "freight". Do not repeat the
   invoice freight on every line. Use "domestic_freight" on a line only when the
   document itemises freight for that specific line.

5. TOTAL. "total" is the invoice total as printed on the document, including
   freight. Read it; do not compute it.

6. NUMBERS. Plain digits with a period as decimal separator. No thousands
   separators, no currency symbols, no spaces.

7. Never invent a value; use null when a field is absent from the document.

8. "confidence" is your calibrated confidence in the extraction as a whole.
   Report below 0.90 whenever the scan is poor, a label is ambiguous, or you had
   to infer rather than read a value.
"""

_USER_TEMPLATE = """\
Below is a Document Intelligence pre-pass of a supplier invoice document, followed by
the document's full text.

Treat the pre-pass as UNVERIFIED CANDIDATES, not as facts. It is known to pick the
wrong invoice number and to invent line items out of description text. The full
document text is the authority; the pre-pass is only a hint.

The pre-pass does not provide incoterm, country_of_origin, domestic_freight,
packaging, exporter, supplier or manufacturer — find those in the full text and
attach them to the correct line item. Do not carry a value across invoices unless
the text says it applies to both.

## Pre-pass JSON (unverified)
{prepass}

## Full document text (authoritative)
{content}
"""


def _s(v) -> str | None:
    return None if v is None else str(v)


def _num(v):
    """Converte para float aceitando '124,285.98'. Devolve None se nao der."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace(" ", "")
    if not t:
        return None
    for symbol in ("USD", "EUR", "BRL", "$", "R$", "€"):
        t = t.replace(symbol, "")
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif t.count(",") == 1 and len(t.split(",")[1]) in (1, 2):
        t = t.replace(",", ".")
    else:
        t = t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _close(a, b) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= max(TOLERANCE_ABS, TOLERANCE_REL * max(abs(a), abs(b)))


def _cat_invoice_numbers(content: str):
    """Devolve (numeros, aviso). Aviso != None quando a leitura foi menos segura."""
    content = content or ""
    found = []
    for label in CAT_LABEL_RE.finditer(content):
        hit = CAT_NUMBER_RE.search(content[label.end():label.end() + CAT_WINDOW])
        if hit:
            number = hit.group(1) + " " + hit.group(2)
            if number not in found:
                found.append(number)
    if found:
        return found, None

    for hit in CAT_NUMBER_RE.finditer(content):
        number = hit.group(1) + " " + hit.group(2)
        if number not in found:
            found.append(number)
    if found:
        return found, ("rotulo 'CAT Invoice#' nao ajudou; numero localizado pelo "
                       "formato no documento")
    return [], "'CAT Invoice#' nao localizado no texto"


class LLMStructurer(ABC):

    @abstractmethod
    def structure(self, extraction: dict[str, Any]) -> dict[str, Any]:
        ...


class AzureOpenAIStructurer(LLMStructurer):

    def __init__(
        self,
        endpoint: str,
        deployment: str,
        api_version: str,
        key: str | None = None,
    ) -> None:
        from openai import AzureOpenAI

        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT nao configurado")
        if not deployment:
            raise ValueError("AZURE_OPENAI_DEPLOYMENT nao configurado")

        self._deployment = deployment

        if key:
            self._client = AzureOpenAI(
                azure_endpoint=endpoint, api_version=api_version, api_key=key
            )
        else:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            self._client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_version=api_version,
                azure_ad_token_provider=get_bearer_token_provider(
                    DefaultAzureCredential(), _AOAI_SCOPE
                ),
            )

    def structure(self, extraction: dict[str, Any]) -> dict[str, Any]:
        content = extraction.get("content") or ""

        # invoice_number do pre-pass fica fora: contamina a resposta do modelo.
        prepass = {
            k: v for k, v in extraction.items() if k != "content"
        }
        for inv in prepass.get("invoices") or []:
            if isinstance(inv, dict):
                inv.pop("invoice_number", None)

        user = _USER_TEMPLATE.format(
            prepass=json.dumps(prepass, ensure_ascii=False, default=str),
            content=content,
        )

        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=8000,
        )

        payload = json.loads(response.choices[0].message.content or "{}")
        numbers, note = _cat_invoice_numbers(content)
        return _normalise(payload, extraction.get("confidence"), numbers, note)


def _check_lines(tag: str, raw_lines: list):
    """Descarta linhas sem PN valido e confere a aritmetica das que sobram."""
    kept = []
    issues = []
    running = 0.0

    for n, li in enumerate(raw_lines):
        pn = li.get("part_number")
        if pn is None or not PART_NUMBER_RE.match(str(pn).strip()):
            issues.append(
                "%s.line[%d]: descartada, part_number '%s' nao tem formato de PN"
                % (tag, n, pn)
            )
            continue

        qty = _num(li.get("quantity"))
        unit = _num(li.get("unit_price"))
        amount = _num(li.get("amount"))

        if amount is None:
            issues.append("%s.line[%d]: amount ausente" % (tag, n))
        else:
            running += amount

        if unit is None:
            issues.append("%s.line[%d]: unit_price ausente" % (tag, n))
        elif qty is not None and amount is not None and not _close(qty * unit, amount):
            issues.append(
                "%s.line[%d]: %s x %s = %.2f, mas amount = %.2f"
                % (tag, n, qty, unit, qty * unit, amount)
            )

        kept.append(li)

    return kept, issues, running


def _normalise(payload: dict[str, Any], prepass_confidence, cat_numbers=None, cat_note=None) -> dict[str, Any]:
    """Forca a saida do modelo no contrato do structurer e valida o que der.

    O numero da invoice vem do texto ('CAT Invoice#') quando conseguimos ler --
    o modelo declara essa origem mesmo quando usou outro campo. O total gravado
    e o total impresso no documento; soma das linhas + frete e conferencia, nao
    fonte.
    """
    issues = []
    entries = [i for i in (payload.get("invoices") or []) if isinstance(i, dict)]
    skipped = len(payload.get("invoices") or []) - len(entries)
    if skipped:
        issues.append("%d entrada(s) de invoice invalida(s) ignorada(s)" % skipped)

    cat_numbers = cat_numbers or []
    if cat_note:
        issues.append(cat_note)

    if entries and len(cat_numbers) == len(entries):
        authoritative = cat_numbers
    elif len(cat_numbers) == 1 and len(entries) == 1:
        authoritative = cat_numbers
    else:
        authoritative = [None] * len(entries)
        if cat_numbers:
            issues.append(
                "%d 'CAT Invoice#' para %d invoice(s); mantido o numero do modelo"
                % (len(cat_numbers), len(entries))
            )

    invoices = []
    for index, inv in enumerate(entries):
        tag = "invoice[%d]" % index

        raw_lines = [li for li in (inv.get("line_items") or []) if isinstance(li, dict)]
        kept, line_issues, running = _check_lines(tag, raw_lines)
        issues.extend(line_issues)

        number = inv.get("invoice_number")
        expected = authoritative[index]
        if expected:
            if number and str(number).strip() != expected:
                issues.append(
                    "%s: modelo devolveu invoice_number '%s' (origem declarada: '%s'), "
                    "texto diz 'CAT Invoice#' = '%s'; usando o do texto"
                    % (tag, number, inv.get("invoice_number_source"), expected)
                )
            number = expected
        elif not number:
            issues.append("%s: invoice_number ausente" % tag)

        date = inv.get("invoice_date")
        if date and not DATE_RE.match(str(date)):
            issues.append("%s: invoice_date '%s' fora do formato YYYY-MM-DD" % (tag, date))

        currency = inv.get("currency")
        if currency and not CURRENCY_RE.match(str(currency).strip().upper()):
            issues.append("%s: currency '%s' invalida" % (tag, currency))

        freight = _num(inv.get("freight"))
        reported = _num(inv.get("total"))
        computed = running + (freight or 0.0)

        if reported is None:
            total = ("%.2f" % computed) if kept else None
            issues.append("%s: total nao informado, usando soma das linhas + frete" % tag)
        else:
            total = "%.2f" % reported
            if not _close(reported, computed):
                issues.append(
                    "%s: total impresso %.2f nao fecha com soma das linhas + frete %.2f"
                    % (tag, reported, computed)
                )

        line_items = []
        for li in kept:
            line_items.append({
                "part_number": _s(li.get("part_number")),
                "description": li.get("description"),
                "quantity": _s(li.get("quantity")),
                "unit_price": _s(li.get("unit_price")),
                "amount": _s(li.get("amount")),
                "purchase_order": li.get("purchase_order"),
                "incoterm": li.get("incoterm"),
                "country_of_origin": li.get("country_of_origin"),
                "domestic_freight": _s(li.get("domestic_freight")),
                "packaging": _s(li.get("packaging")),
                "exporter": li.get("exporter"),
                "supplier": li.get("supplier"),
                "manufacturer": li.get("manufacturer"),
            })

        invoices.append({
            "invoice_number": number,
            "invoice_date": inv.get("invoice_date"),
            "currency": inv.get("currency"),
            "total": total,
            "line_items": line_items,
        })

    candidates = []
    for c in (payload.get("confidence"), prepass_confidence):
        try:
            candidates.append(float(c))
        except (TypeError, ValueError):
            pass
    confidence = min(candidates) if candidates else 0.0

    if issues:
        confidence = min(confidence, REVIEW_CONFIDENCE)
        for problem in issues:
            logger.warning("VALIDACAO: %s", problem)

    return {"invoices": invoices, "confidence": confidence, "validation": issues}


class MockStructurer(LLMStructurer):

    def structure(self, extraction: dict[str, Any]) -> dict[str, Any]:
        invoices = []
        for inv in extraction.get("invoices", []):
            line_items = []
            total = 0.0
            for it in inv.get("items", []):
                amount = it.get("amount")
                if amount is not None:
                    total += float(amount)
                line_items.append({
                    "part_number": _s(it.get("part_number")),
                    "description": it.get("description"),
                    "quantity": _s(it.get("quantity")),
                    "unit_price": _s(it.get("unit_price")),
                    "amount": _s(amount),
                    "purchase_order": it.get("purchase_order"),
                    "incoterm": it.get("incoterm"),
                    "country_of_origin": it.get("country_of_origin"),
                    "domestic_freight": _s(it.get("domestic_freight")),
                    "packaging": _s(it.get("packaging")),
                    "exporter": it.get("exporter"),
                    "supplier": it.get("supplier"),
                    "manufacturer": it.get("manufacturer"),
                })
            invoices.append({
                "invoice_number": inv.get("invoice_number"),
                "invoice_date": inv.get("invoice_date"),
                "currency": inv.get("currency"),
                "total": f"{total:.2f}" if line_items else None,
                "line_items": line_items,
            })
        return {"invoices": invoices, "confidence": extraction.get("confidence")}