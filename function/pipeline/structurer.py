import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from pipeline import confidence as fieldconf

logger = logging.getLogger("structurer")

# Um desvio maior que isto reprova a conferencia aritmetica.
TOLERANCE_ABS = 0.02
TOLERANCE_REL = 0.005

# Part number CAT: prefixo de 3 alfanumericos com hifen opcional
# ('463-8344', '6511308') ou de 2 SEMPRE com hifen ('5P-1465', '7G-5837').
# O hifen no caso curto e o que separa um part number real da marcacao de
# end use '0V3456', que tem a mesma forma sem hifen.
PART_NUMBER_RE = re.compile(r"^(?:[0-9A-Z]{3}-?[0-9]{4}|[0-9A-Z]{2}-[0-9]{4})$")
# Codigo qualquer: nao e part number CAT, mas tambem nao e prosa.
CODE_RE = re.compile(r"^[0-9A-Z][0-9A-Z\-/._]{2,29}$")
# Sufixo de revisao/planta que a Caterpillar imprime junto do part number:
# '663-7238~00', '6064986-07', '364-9717/01'. Nao faz parte do numero.
PART_NUMBER_SUFFIX_RE = re.compile(r"^(?P<base>.+?)(?P<suffix>[~/][0-9A-Z]{1,3}|-[0-9]{2})$")
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
"currency", "freight", "packaging_cost", "total", "line_items": [{"part_number", "description",
"quantity", "unit_price", "amount", "purchase_order", "incoterm",
"country_of_origin", "domestic_freight", "packaging", "exporter", "supplier",
"manufacturer", "serial_numbers"}]}], "confidence": 0..1}

Every monetary and quantity field above is a STRING copied as printed -- see
rule 6. "confidence" is the one number you report as a number.

HARD RULES — these are the errors that have actually occurred:

1. INVOICE NUMBER. Use the number the DOCUMENT gives as its own invoice
   number. Accept any of these labels: "Invoice Number", "Invoice No.",
   "Commercial Invoice Nr.", "Fattura", "Faktura", "Facture", and on
   Caterpillar intercompany invoices "CAT Invoice#". Copy it exactly as
   printed, including spaces and separators.
   These are NOT the invoice number: "Delivery note no./Date",
   "Order number/Date", "CAT Order number", "Purchase Order Number",
   "Customs Reference Nr.", "CO Invoice Number", "Number/Date", and the
   PDF filename.
   In "invoice_number_source" report the literal label you read it from.
   If the document carries no invoice-number label at all, return null and
   say so there. Do not take it from the filename.

2. PART NUMBERS. Copy the part number EXACTLY as the document prints it,
   character for character, including hyphens: "463-8344" stays "463-8344",
   "5P-1465" stays "5P-1465". Caterpillar prints both the hyphenated and the
   plain form; reproduce whichever is on the page. Never construct, pad or
   reformat one. If a line's part number is a description fragment or an
   end-use note (for example "I/C Material" or "0V3456 END USE:"), still
   return the line, and put the text you read in "part_number".

3. PRICES. amount = quantity x unit_price. The per-unit price goes in
   "unit_price" and never in "amount". If the document shows a quantity and an
   extended amount only, derive unit_price = amount / quantity.

4. FREIGHT. Report freight ONCE, at invoice level, in "freight". Do not repeat the
   invoice freight on every line. Use "domestic_freight" on a line only when the
   document itemises freight for that specific line.

   Put a packaging or crating CHARGE in "packaging_cost", copied as printed
   (rule 6), when the document bills one ("plus package", "packing charge", "embalagem"). Report it
   ONCE, at invoice level. "packaging" is a different field and stays the
   physical description of the packing ("1 PALLET").

5. TOTAL. "total" is the invoice total as printed on the document, including
   freight. Read it; do not compute it.

6. NUMBERS. Copy every number EXACTLY as the document prints it, as a JSON
   string. "22.944,02" stays "22.944,02"; "29,579.82" stays "29,579.82".
   Keep the separators and the sign. Convert nothing, round nothing, drop no
   digit. Do NOT normalise to a decimal point and do NOT remove thousands
   separators. Code downstream converts both conventions.
   This rule exists because you get it wrong: on one invoice, the same printed
   "22.944,02" came back as 22944.02 in four runs and as 22.94 in four others.
   The LINE amounts were right every time, because "161,75 x 10 = 1.617,50"
   anchors the convention; the invoice TOTAL stands alone with no anchor, so
   the separator became a guess. Copying removes the guess.
   A currency symbol or code next to the number is not part of it; leave it out.
   ONE exception: the unit_price you derive under rule 3 was never printed, so
   there is nothing to copy -- write that one with a period as the decimal
   separator and no thousands separator. Every number you READ is copied.

7. Never invent a value; use null when a field is absent from the document.

8. "confidence" is your calibrated confidence in the extraction as a whole.
   Report below 0.90 whenever the scan is poor, a label is ambiguous, or you had
   to infer rather than read a value.
"""

# Acrescentado ao prompt SO quando a pre-varredura achou, na lista de PN
# liberados, alguma peca marcada como "exige serial". Nao vale a pena carregar
# estas instrucoes nas outras faturas: elas so tem como efeito o modelo procurar
# uma tabela que nao existe.
_ENGINE_RULES = """\

9. SERIAL NUMBERS. This document contains at least one part that carries serial
   numbers. Somewhere in it there is a table pairing part numbers with serials,
   with a header like "Part Number | Serial Number" (a "Pin Number" column may
   appear, empty or elsewhere).

   For each line item, return every serial that belongs to its part number, as
   a list of strings in "serial_numbers", copied exactly as printed.

   A real example, with quantity 7:

       |   Part Number | Serial Number   |
       |       6522586 | XWE42867        |
       |       6522586 | XWE42871        |
       ... five more rows ...

   -> that line gets "serial_numbers": ["XWE42867","XWE42871", ...] with all 7.

   Do NOT invent a serial to match the quantity, and do NOT renumber: the seven
   above are not consecutive. Return only what is printed. If a line has no
   serial in the document, return an empty list.
   Do NOT split the line yourself -- keep ONE line item per printed row, with
   the full quantity; this code expands it.
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


def _snum(v) -> str | None:
    """Numero em forma canonica: '6.398,88' -> '6398.88'. None se nao for numero.

    Existe porque a regra 6 passou a mandar o modelo COPIAR o numero como
    impresso, em vez de normalizar. Quem normaliza agora e o _num(), que e
    deterministico -- mas a saida do structurer precisa sair convertida, senao
    o Decimal() do doc_worker recebe '6.398,88', levanta InvalidOperation e o
    campo e gravado NULL sem uma nota. Era o pior modo de falha possivel: a
    conferencia aritmetica passa (ela usa _num) e o documento e salvo vazio.

    Quatro casas e o maximo do schema (Numeric(18,4) em quantity e unit_price);
    os zeros a direita saem para nao gravar '52.0000' onde se le '52'.
    """
    n = _num(v)
    if n is None:
        return None
    return ("%.4f" % n).rstrip("0").rstrip(".") or "0"


def _num(v):
    """Converte para float aceitando '124,285.98' e '124.285,98'.

    O corpus tem os dois formatos: fornecedores dos EUA imprimem
    '29,579.82' e os europeus '6.398,88'. Decide pelo separador que
    aparece POR ULTIMO -- esse e o decimal.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace(" ", "").replace("\u00a0", "")
    if not t:
        return None
    for symbol in ("USD", "EUR", "BRL", "GBP", "SEK", "TRY", "$", "R$", "€"):
        t = t.replace(symbol, "")
    negative = t.startswith("-") or (t.startswith("(") and t.endswith(")"))
    t = t.strip("()-")

    last_comma, last_dot = t.rfind(","), t.rfind(".")
    if last_comma > -1 and last_dot > -1:
        if last_comma > last_dot:          # 6.398,88 -> decimal e a virgula
            t = t.replace(".", "").replace(",", ".")
        else:                              # 29,579.82 -> decimal e o ponto
            t = t.replace(",", "")
    elif last_comma > -1:
        # Uma virgula so: decimal se sobrarem 1 ou 2 casas, senao milhar.
        t = t.replace(",", "." if len(t) - last_comma - 1 in (1, 2) else "")
    elif last_dot > -1 and len(t) - last_dot - 1 == 3 and len(t.replace(".", "")) > 3:
        # 1.234 sem centavos e milhar europeu. '108.08' tem 2 casas, nao entra.
        t = t.replace(".", "")

    try:
        value = float(t)
    except ValueError:
        return None
    return -value if negative else value

def _split_part_number(text: str):
    """(base, sufixo). So separa se o que sobra for part number valido.

    A guarda importa: '463-8344' casa inteiro na primeira linha e nunca chega
    ao corte, senao viraria '463-83'.
    """
    if PART_NUMBER_RE.match(text):
        return text, None
    m = PART_NUMBER_SUFFIX_RE.match(text)
    if m and PART_NUMBER_RE.match(m.group("base")):
        return m.group("base"), m.group("suffix")
    return text, None


def _classify_part_number(pn, content: str):
    """(impresso, normalizado, sufixo, status, aviso). Nunca descarta a linha.

    'impresso' sai como esta no documento -- e o que permite rastrear o valor.
    'normalizado' e a forma sem hifen nem sufixo, que e o formato da coluna
    Material do gabarito ('663-7238~00' -> '6637238').
    """
    content = content or ""
    if pn is None or not str(pn).strip():
        return None, None, None, "missing", "part_number ausente"

    text = str(pn).strip()
    base, suffix = _split_part_number(text)

    if PART_NUMBER_RE.match(base):
        normalised = base.replace("-", "")
        if text in content or base in content:
            return text, normalised, suffix, "cat", None
        # Nao esta impresso assim: tenta a outra forma antes de acusar, porque
        # o mesmo documento imprime '463-8344' e '6637238'.
        alternative = normalised[:3] + "-" + normalised[3:] if len(normalised) == 7 else base
        if alternative in content:
            return text, normalised, suffix, "cat", None
        return text, normalised, suffix, "not_printed", (
            "part_number '%s' tem formato CAT mas nao aparece no texto" % text
        )

    if CODE_RE.match(text):
        return text, None, None, "other_code", (
            "part_number '%s' nao tem formato CAT; mantido como codigo do fornecedor" % text
        )
    return text, None, None, "not_a_code", "part_number '%s' nao tem forma de codigo" % text


def _invoice_supplier(kept: list):
    """(fornecedor, aviso). O modelo responde por linha; a fatura tem um so.

    Conferido no CIV, que tem 6 invoices de 6 fornecedores: nenhuma delas
    mistura fornecedor entre as proprias linhas. Se algum dia misturar, esta
    funcao e que descobre -- vence o mais frequente e a divergencia vira nota,
    em vez de o valor ser escolhido em silencio.
    """
    nomes = [str(li.get("supplier")).strip() for li in kept
             if li.get("supplier") and str(li.get("supplier")).strip()]
    if not nomes:
        return None, None

    distintos = {}
    for nome in nomes:
        distintos[nome] = distintos.get(nome, 0) + 1
    escolhido = max(distintos, key=lambda n: (distintos[n], -nomes.index(n)))
    if len(distintos) == 1:
        return escolhido, None
    return escolhido, (
        "linhas trazem %d fornecedores diferentes (%s); gravado o mais "
        "frequente, '%s'" % (len(distintos), ", ".join(sorted(distintos)), escolhido)
    )


def _landed(kept: list, extra):
    """Rateia encargos de nivel de fatura por unidade. Nao sobrescreve nada.

    O cliente soma a embalagem ao preco unitario: na fatura CD970373103 sao
    90 x 388,46 = 34.961,40 mais 603,00 de embalagem, e o gabarito pede
    395,16 e 35.564,40 -- ou seja 603/90 por unidade. So dois documentos de
    28 trazem esse encargo, entao isto e um ramo condicional, nao uma regra.
    O divisor (unidades, peso ou valor) ainda precisa de confirmacao do
    cliente; com uma linha unica os tres dao o mesmo resultado.
    """
    total_qty = 0.0
    for li in kept:
        q = _num(li.get("quantity"))
        if q:
            total_qty += q
    if not extra or total_qty <= 0:
        return None
    per_unit = extra / total_qty
    for li in kept:
        unit = _num(li.get("unit_price"))
        qty = _num(li.get("quantity"))
        if unit is None:
            continue
        li["unit_price_landed"] = "%.2f" % (unit + per_unit)
        if qty is not None:
            li["amount_landed"] = "%.2f" % ((unit + per_unit) * qty)
    return per_unit


def _close(a, b) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= max(TOLERANCE_ABS, TOLERANCE_REL * max(abs(a), abs(b)))


def candidate_part_numbers(content: str) -> list[str]:
    """Tudo no texto cru que TEM FORMA de part number CAT.

    Rede larga de proposito: serve para uma unica pergunta -- este documento
    menciona alguma peca que exige serial? Falso positivo aqui so faz o prompt
    de motor ser usado a mais, e ele nao obriga o modelo a inventar serial.

    Medido no CIV, o pior documento do corpus: 83 mil caracteres de OCR sujo
    rendem 22 candidatos, e a consulta que os resolve leva 0,4 ms.
    """
    achados = []
    vistos = set()
    for bruto in re.findall(r"[0-9A-Za-z][0-9A-Za-z\-]{4,15}", content or ""):
        texto = bruto.upper()
        base, _ = _split_part_number(texto)
        if PART_NUMBER_RE.match(base) and base not in vistos:
            vistos.add(base)
            achados.append(base)
    return achados


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
    def structure(self, extraction: dict[str, Any], exigem_serial=None) -> dict[str, Any]:
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
        # Atributo, nao literal, para uma subclasse poder ajustar sem
        # duplicar structure(). Modelos fora do Azure capam em valores
        # diferentes.
        self._max_tokens = 16000

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

    def structure(self, extraction: dict[str, Any], exigem_serial=None) -> dict[str, Any]:
        """`exigem_serial`: chaves normalizadas que exigem serial, da lista de PN.

        Quem decide isso e uma consulta, nao o modelo: perguntar ao LLM "esta
        fatura e de motor?" devolveria o julgamento probabilistico que a coluna
        requires_serial existe para eliminar.
        """
        exigem_serial = exigem_serial or set()
        content = extraction.get("content") or ""

        prepass = {"invoices": []}
        for inv in extraction.get("invoices") or []:
            if isinstance(inv, dict):
                inv = dict(inv)
                inv.pop("invoice_number", None)
                prepass["invoices"].append(inv)

        user = _USER_TEMPLATE.format(
            prepass=json.dumps(prepass, ensure_ascii=False, default=str),
            content=content,
        )

        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system",
                 "content": _SYSTEM_PROMPT + (_ENGINE_RULES if exigem_serial else "")},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=self._max_tokens,
        )

        payload = json.loads(response.choices[0].message.content or "{}")
        numbers, note = _cat_invoice_numbers(content)
        return _normalise(payload, extraction.get("confidence"), numbers, note,
                          content, exigem_serial, extraction.get("words"))


def _expand_serials(tag: str, li: dict, exige_serial: bool):
    """(registros, avisos, notas). Uma linha impressa vira um registro por serial.

    Regra do cliente: motor repete o MESMO part number, uma vez para cada
    serial. A fatura 93872204 traz 'QTY 7' de 6522586 e sete seriais
    (XWE42867, 42871, 42879...), que nao sao consecutivos -- por isso a
    expansao copia o que foi lido e nunca completa a sequencia.

    Os registros saem com quantidade 1 e amount = unit_price. Sem isso a soma
    das linhas daria 7x o total impresso e a conferencia aritmetica, que existe
    para achar defeito, acusaria erro em TODA fatura de motor.
    """
    lidos = li.get("serial_numbers") or []
    # String e UM valor, nunca uma lista de caracteres. No CIV o modelo
    # devolveu "336624491166044672" (o codigo da palete da Bosch, nem serial
    # era) e o laco abaixo o percorria letra a letra: 128 pecas de 561-7001
    # viraram 18 registros de 1, com seriais '3', '3', '6'...
    if isinstance(lidos, str):
        lidos = [lidos]
    seriais = [str(x).strip() for x in lidos if str(x).strip()]
    avisos = []
    notas = []

    if seriais and not exige_serial:
        # Quem decide se a peca leva serial e a lista de PN, nunca o modelo: o
        # shape do prompt sempre traz "serial_numbers", e ele preenche com o
        # que parecer serial. Expandir aqui destruia a linha impressa -- e a
        # conferencia aritmetica nao acusa, porque soma a linha ANTES da
        # expansao. E nota, nao defeito: a linha gravada fica como impressa, e
        # o valor descartado fica registrado para auditoria.
        notas.append(
            "%s: '%s' nao exige serial pela lista de PN; serial(is) devolvido(s) "
            "pelo modelo ignorado(s): %s" % (tag, li.get("part_number"), ", ".join(seriais))
        )
        seriais = []

    if not seriais:
        if exige_serial:
            # Serial e mandatorio para motor pelo contrato do cliente. Sem ele o
            # documento tem de chegar ao revisor dizendo o que falta.
            avisos.append(
                "%s: '%s' exige serial number e nenhum foi lido" % (tag, li.get("part_number"))
            )
        return [dict(li, serial_number=None)], avisos, notas

    qty = _num(li.get("quantity"))
    if qty is not None and abs(qty - len(seriais)) > 0.001:
        avisos.append(
            "%s: quantidade %s e %d serial(is) lido(s); expandido em %d"
            % (tag, li.get("quantity"), len(seriais), len(seriais))
        )

    # Serial que destoa do formato dos irmaos: os do mesmo motor seguem um
    # padrao (todos 'XWE428xx' na 93872204), entao o que foge merece um olhar.
    formatos = {re.sub(r"[0-9]", "#", s_) for s_ in seriais}
    if len(formatos) > 1:
        avisos.append(
            "%s: seriais com formatos diferentes (%s)" % (tag, ", ".join(sorted(formatos)))
        )

    unit = _num(li.get("unit_price"))
    registros = []
    for serial in seriais:
        registros.append(dict(
            li,
            serial_number=serial,
            quantity="1",
            amount=_s(li.get("unit_price")) if unit is not None else li.get("amount"),
        ))
    return registros, avisos, notas


def _record_confidence(fc: dict, registro: dict, content: str, index,
                       tag: str, issues: list) -> dict:
    """Nota de um registro gravado. Registro com serial veio da expansao:
    quantidade e amount nao foram lidos -- sao 1 e unit_price por construcao
    --, entao saem como 'derived'; o serial e lido, e tem nota propria."""
    out = dict(fc)
    serial = registro.get("serial_number")
    if serial:
        out["quantity"] = fieldconf.derived()
        out["amount"] = fieldconf.derived()
        entry = fieldconf.score_identifier(serial, content, index)
        out["serial_number"] = entry
        aviso = fieldconf.describe(tag, "serial_number", serial, entry)
        if aviso:
            issues.append(aviso)
    return out


# Status que NAO sao item de fatura. Derrubar por "nao esta na lista de PN
# liberados" seria errado: 'other_code' existe porque o corpus tem codigo de
# fornecedor ('15.1301.466'), que nunca estara na PN Liberados e e item real.
_NAO_E_ITEM = ("not_a_code", "missing")


def _check_lines(tag: str, raw_lines: list, content: str, exigem_serial=None, index=None):
    """Confere PN e aritmetica, separando o que nao e item de fatura.

    A linha descartada NAO some: sai de line_items e vai para discarded_lines,
    com o motivo. Um filtro que apagava linha sem sete digitos ja destruiu os
    itens de dois dos quatro documentos de teste, porque '674-8657' e part
    number legitimo -- entao aqui o criterio e a classificacao, e o dado fica.

    O descarte acontece ANTES da soma, de proposito. Na fatura de motor
    93872204 a nota 'I/C Material 0V3456 / END USE' vinha como item com o preco
    do motor e estourava o total; sem ela a soma fecha com o impresso. E a
    reciproca e a rede de seguranca do filtro: se ele derrubar uma linha
    legitima, a soma para de fechar e o documento vai para revisao sozinho.
    """
    kept = []
    descartadas = []
    issues = []
    notas = []
    running = 0.0
    exigem_serial = exigem_serial or set()

    for n, li in enumerate(raw_lines):
        printed, normalised, suffix, status, note = _classify_part_number(
            li.get("part_number"), content
        )
        li = dict(
            li,
            part_number=printed,
            part_number_normalised=normalised,
            part_number_suffix=suffix,
            part_number_status=status,
        )
        if status in _NAO_E_ITEM:
            descartadas.append(dict(li, discard_reason=note or "sem part number"))
            continue
        if note:
            issues.append("%s.line[%d]: %s" % (tag, n, note))

        # Pontuada a linha IMPRESSA, antes de _num e da expansao: e o valor
        # como impresso ('35.564,40') que se acha no texto do OCR.
        fc = None
        if index is not None:
            fc = fieldconf.line_confidence(li, content, index, _num)
            for field, entry in fc.items():
                aviso = fieldconf.describe("%s.line[%d]" % (tag, n), field, li.get(field), entry)
                if aviso:
                    issues.append(aviso)

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

        # A expansao vem depois da conferencia aritmetica da linha impressa:
        # conferir os registros expandidos seria comparar 1 x unit_price com
        # ele mesmo, o que nao testa nada.
        registros, avisos, notas_serial = _expand_serials(
            "%s.line[%d]" % (tag, n), li, normalised in exigem_serial
        )
        issues.extend(avisos)
        notas.extend(notas_serial)
        if fc is not None:
            for registro in registros:
                registro["field_confidence"] = _record_confidence(
                    fc, registro, content, index, "%s.line[%d]" % (tag, n), issues)
        kept.extend(registros)

    if descartadas:
        # Registro, nao problema: se o descarte estiver errado, quem acusa e a
        # aritmetica -- a soma para de fechar e AQUELA nota manda para revisao.
        # Tratar o descarte como problema mandaria toda CIV de motor para
        # revisao, porque todas trazem a nota 'END USE'.
        notas.append(
            "%s: %d linha(s) sem part number descartada(s): %s"
            % (tag, len(descartadas),
               "; ".join(str(d.get("part_number") or "(vazio)") for d in descartadas))
        )

    return kept, issues, notas, running, descartadas


def _normalise(payload: dict[str, Any], prepass_confidence, cat_numbers=None,
               cat_note=None, content: str = "", exigem_serial=None,
               words=None) -> dict[str, Any]:
    """Forca a saida do modelo no contrato do structurer e valida o que der.

    O numero da invoice e o do proprio documento: 10 das 28 faturas do corpus
    nao tem 'CAT Invoice#', e o gabarito do cliente pede o numero do
    fornecedor. Quando um 'CAT Invoice#' existe no texto ele prevalece, porque
    o modelo ja declarou essa origem tendo usado outro campo.

    O total gravado e o total impresso no documento; soma das linhas + frete e
    conferencia, nao fonte. Encargos de nivel de fatura sao rateados em
    unit_price_landed, sem tocar em unit_price.

    `words`: o indice de palavras do Document Intelligence, (offset, length,
    confidence). Com ele cada campo ganha nota de OCR e a confianca do
    documento passa a ser a menor delas; sem ele (modo local, mock) nada muda.
    """
    word_index = fieldconf.WordIndex(words) if words else None
    issues = []
    # Duas listas de proposito. 'issues' sao defeitos e derrubam a confianca
    # para REVIEW_CONFIDENCE; 'notas' sao decisoes de calculo que o revisor
    # tem direito de auditar mas que nao pedem revisao. Enquanto tudo caia em
    # 'issues', uma fatura lida sem um erro ia para needs_review so por ter
    # embalagem cobrada.
    notas = []
    entries = [i for i in (payload.get("invoices") or []) if isinstance(i, dict)]
    skipped = len(payload.get("invoices") or []) - len(entries)
    if skipped:
        issues.append("%d entrada(s) de invoice invalida(s) ignorada(s)" % skipped)

    if not entries:
        # Falha silenciosa que ja aconteceu: o modelo devolve '{}' ou
        # '{"invoices": []}', o documento e gravado sem nenhuma linha e quem
        # revisa abre uma tela vazia sem explicacao. A confianca zerada ja
        # mandava para needs_review, mas sem dizer por que.
        issues.append(
            "modelo nao devolveu nenhuma invoice (chaves recebidas: %s); "
            "documento gravado vazio" % (sorted(payload) or "nenhuma")
        )

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
        kept, line_issues, line_notes, running, descartadas = _check_lines(
            tag, raw_lines, content, exigem_serial, word_index)
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
        packaging_cost = _num(inv.get("packaging_cost"))
        # A embalagem entra na conferencia porque o total impresso a inclui: na
        # CD970373103 sao 90 x 388,46 = 34.961,40 mais 603,00, e o documento
        # imprime 35.564,40. Enquanto ela ficava de fora, TODA fatura com
        # embalagem cobrada acusava "total nao fecha" -- falso positivo que
        # mandava para revisao um documento lido sem um erro.
        computed = running + (freight or 0.0) + (packaging_cost or 0.0)

        if reported is None:
            total = ("%.2f" % computed) if kept else None
            issues.append("%s: total nao informado, usando soma das linhas + encargos" % tag)
        else:
            total = "%.2f" % reported
            if not _close(reported, computed):
                issues.append(
                    "%s: total impresso %.2f nao fecha com soma das linhas + "
                    "frete + embalagem %.2f" % (tag, reported, computed)
                )

        header_fc = None
        if word_index is not None:
            # O total gravado e o impresso; quando nao ha impresso, e a soma --
            # calculada, sem nota de OCR.
            header_fc = {
                "invoice_number": fieldconf.score_identifier(number, content, word_index),
                "total": (fieldconf.score_number(inv.get("total"), reported, content, word_index)
                          if reported is not None else fieldconf.derived()),
            }
            header_fc = {k: v for k, v in header_fc.items() if v}
            for field, entry in header_fc.items():
                aviso = fieldconf.describe(
                    tag, field, number if field == "invoice_number" else inv.get("total"), entry)
                if aviso:
                    issues.append(aviso)

        extra = (packaging_cost or 0.0) + (freight or 0.0)
        per_unit = _landed(kept, extra)
        notas.extend(line_notes)
        if per_unit:
            notas.append(
                "%s: encargos %.2f rateados a %.4f por unidade em "
                "unit_price_landed (unit_price segue como impresso)"
                % (tag, extra, per_unit)
            )

        line_items = []
        for li in kept:
            line_items.append({
                "part_number": _s(li.get("part_number")),
                "part_number_normalised": li.get("part_number_normalised"),
                "serial_number": li.get("serial_number"),
                "part_number_suffix": li.get("part_number_suffix"),
                "part_number_status": li.get("part_number_status"),
                "description": li.get("description"),
                "quantity": _snum(li.get("quantity")),
                "unit_price": _snum(li.get("unit_price")),
                "unit_price_landed": li.get("unit_price_landed"),
                "amount": _snum(li.get("amount")),
                "amount_landed": li.get("amount_landed"),
                "purchase_order": li.get("purchase_order"),
                "incoterm": li.get("incoterm"),
                "country_of_origin": li.get("country_of_origin"),
                "domestic_freight": _snum(li.get("domestic_freight")),
                "packaging": _s(li.get("packaging")),
                "exporter": li.get("exporter"),
                "supplier": li.get("supplier"),
                "manufacturer": li.get("manufacturer"),
                "field_confidence": li.get("field_confidence"),
            })

        supplier, supplier_note = _invoice_supplier(kept)
        if supplier_note:
            issues.append("%s: %s" % (tag, supplier_note))

        invoices.append({
            "invoice_number": number,
            "invoice_date": inv.get("invoice_date"),
            "supplier": supplier,
            "currency": inv.get("currency"),
            # Emitidos para que unit_price_landed seja auditavel: sem eles nao
            # se sabe de que encargo veio o rateio.
            "freight": _snum(inv.get("freight")),
            "packaging_cost": _snum(inv.get("packaging_cost")),
            "total": total,
            "field_confidence": header_fc,
            "line_items": line_items,
            # Nao sao itens, mas tambem nao somem: quem revisa precisa poder
            # ver o que o filtro tirou, e por que.
            "discarded_lines": descartadas,
        })

    candidates = []
    for c in (payload.get("confidence"), prepass_confidence):
        try:
            candidates.append(float(c))
        except (TypeError, ValueError):
            pass
    confidence = min(candidates) if candidates else 0.0
    source = "model"

    # A auto-reportada do modelo deixa de decidir quando ha evidencia do OCR:
    # ela fica em 'model_confidence', para auditoria, e quem governa e o pior
    # campo. Media esconderia um campo catastrofico.
    if word_index is not None:
        piores = fieldconf.document_min(
            [inv["field_confidence"] for inv in invoices]
            + [li["field_confidence"] for inv in invoices for li in inv["line_items"]])
        if piores is not None:
            confidence, source = piores, "fields"

    if issues:
        confidence = min(confidence, REVIEW_CONFIDENCE)
        for problem in issues:
            logger.warning("VALIDACAO: %s", problem)
    for nota in notas:
        logger.info("NOTA: %s", nota)

    return {"invoices": invoices, "confidence": confidence,
            "confidence_source": source,
            "model_confidence": payload.get("confidence"),
            "validation": issues, "notes": notas}


class MockStructurer(LLMStructurer):

    def structure(self, extraction: dict[str, Any], exigem_serial=None) -> dict[str, Any]:
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
                    "serial_number": None,
                    "supplier": it.get("supplier"),
                    "manufacturer": it.get("manufacturer"),
                })
            invoices.append({
                "invoice_number": inv.get("invoice_number"),
                "invoice_date": inv.get("invoice_date"),
                "supplier": _invoice_supplier(line_items)[0],
                "currency": inv.get("currency"),
                "total": f"{total:.2f}" if line_items else None,
                "line_items": line_items,
            })
        return {"invoices": invoices, "confidence": extraction.get("confidence")}
