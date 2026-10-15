"""Classificacao de pagina: fatura, packing list, as duas ou nada.

Um terco do plano de aceitacao e "PDF com Invoice + Packing List", e ate
aqui o documento inteiro ia para o modelo com a esperanca de que ele
ignorasse o packing list sozinho. A decisao passa a ser nossa e
deterministica, ANTES do LLM -- o mesmo padrao de `_cat_invoice_numbers` e
da pre-varredura de serial: perguntar ao modelo "esta pagina e packing
list?" devolveria o palpite que a regra existe para eliminar.

O Document Intelligence nao devolve markdown por pagina: devolve uma string
so, com `<!-- PageBreak -->` entre as paginas. Os spans saem desses
marcadores. O `content` NUNCA e reescrito: a confianca por campo localiza
valores por offset nele.
"""
import re

PAGE_BREAK_RE = re.compile(r"<!--\s*PageBreak\s*-->")

# Titulo de documento de embarque. Medido no CIV (35 paginas, 6
# fornecedores): alem de "Packing List" o corpus traz nota de entrega
# italiana ("DOCUMENTO DI TRASPORTO", "DDT", "DELIVERY NOTE") e o "Loadlist"
# da Bosch -- paginas que listam part number e quantidade SEM preco, e que o
# modelo transformava em item. Para o que importa aqui sao todos a mesma
# coisa: pagina de onde nao sai linha de fatura.
_TITLE_RE = re.compile(
    r"\b(?:PACKING\s*LIST|PACK(?:ING)?\s*SLIP|PACKLIST\w*|PACKLISTE|"
    r"LISTA\s+DE\s+EMBALAGEM|LISTA\s+DI\s+IMBALLO|"
    r"LOAD\s*LIST|SHIPPING\s*LIST|BILL\s+OF\s+LADING)\b", re.IGNORECASE)
# Titulo FRACO: a propria fatura cita a nota de entrega como referencia
# ("Delivery note no./Date", "DDT n. 2603712" -- a regra 1 do prompt ate
# lista esse rotulo). Com rotulo de preco na mesma pagina e fatura citando a
# DDT; sem preco e a DDT. Nunca `mixed`.
_WEAK_TITLE_RE = re.compile(
    r"\b(?:DELIVERY\s*NOTE|DOCUMENTO\s+DI\s+TRASPORTO|D\.?D\.?T\.?)\b", re.IGNORECASE)
# Corpo de documento de embarque: peso, volume, embalagem. Sozinho nao decide
# muito: fatura italiana imprime "Netto"/"Peso Bruto" na propria fatura
# (TECNORD, Cattini), e a regra 10 do prompt ate conta com isso.
_BODY_RE = re.compile(
    r"\b(?:NET\s*WEIGHT|GROSS\s*WEIGHT|N\.?\s?W\.?|G\.?\s?W\.?|CARTONS?|CTNS?|"
    r"PALLETS?|DIMENSIONS?|MEAS(?:UREMENT)?S?|PESO\s+(?:LIQUIDO|BRUTO)|"
    r"NETTO|BRUTTO)\b", re.IGNORECASE)
# Rotulo de preco: o que uma fatura tem e um packing list nao. "INVOICE"
# sozinho pesa zero de proposito: packing list cita "Invoice No." e isso nao
# o torna fatura.
_PRICE_RE = re.compile(
    r"\b(?:UNIT\s*PRICE|TOTAL\s*AMOUNT|AMOUNT|SUBTOTAL|SUB-TOTAL|PRICE|"
    r"PREZZO|IMPORTO|PRE[CÇ]O|VALOR\s+TOTAL)\b", re.IGNORECASE)
# Moeda solta. Conta como sinal de fatura numa pagina sem titulo de embarque,
# mas nao desmente o titulo: o rodape legal da Dana imprime "Cap. Soc.
# € 60.000.000,00" na propria pagina do packing list.
_CURRENCY_RE = re.compile(
    r"\b(?:USD|EUR|GBP|TRY|PLN|CNY|BRL|CHF|JPY)\b|[$€£]", re.IGNORECASE)

INVOICE, PACKING_LIST, MIXED, UNKNOWN = "invoice", "packing_list", "mixed", "unknown"


def page_spans(content: str) -> list[dict]:
    """Um span por pagina, 1-based pela ordem no markdown.

    A pagina 1 e o que vem antes do primeiro marcador; sem marcador, o
    documento inteiro e uma pagina. Os spans cobrem o content inteiro, sem
    sobreposicao -- o marcador fica no fim da pagina que ele encerra.
    """
    spans = []
    start = 0
    for n, m in enumerate(PAGE_BREAK_RE.finditer(content), start=1):
        spans.append({"page_number": n, "start": start, "end": m.end()})
        start = m.end()
    spans.append({"page_number": len(spans) + 1, "start": start, "end": len(content)})
    return spans


def _classify(text: str) -> tuple[str, int, int, list[str]]:
    """(kind, packing_score, money_score, evidencia) de UMA pagina.

    A ordem das regras e o que a calibracao no CIV ensinou:
    - titulo de embarque decide, e so rotulo de PRECO o desmente (`mixed`);
      moeda solta no rodape nao conta contra ele;
    - sem titulo, qualquer sinal de dinheiro e fatura, mesmo com peso impresso
      -- senao as 4 paginas da TECNORD e as 3 da Cattini viravam `mixed`;
    - sem titulo e sem dinheiro, duas marcas de peso/volume bastam para
      embarque (tabela de volumes sem cabecalho); uma so e `unknown`, porque
      a capa do CIV traz "GROSS WEIGHT" uma vez e nao e nada.
    """
    titles = _TITLE_RE.findall(text)
    weak = _WEAK_TITLE_RE.findall(text)
    body = _BODY_RE.findall(text)
    prices = _PRICE_RE.findall(text)
    currency = _CURRENCY_RE.findall(text)
    packing = 3 * len(titles) + 2 * len(weak) + len(body)
    money = 2 * len(prices) + len(currency)
    evidencia = []
    for grupo in (titles, weak, body, prices):
        if grupo:
            evidencia.append("%s x%d" % (grupo[0].upper(), len(grupo)))

    if titles:
        kind = MIXED if prices else PACKING_LIST
    elif weak and not prices:
        kind = PACKING_LIST
    elif money:
        kind = INVOICE
    elif len(body) >= 2:
        kind = PACKING_LIST
    else:
        kind = UNKNOWN
    return kind, packing, money, evidencia


def classify_pages(content: str, page_count: int | None = None) -> dict:
    """Classifica cada pagina e resume o que o prompt e a revisao precisam.

    Pagina `mixed` (titulo de embarque E rotulo de preco) vai ao modelo como
    fatura e vira problema: so um humano diz se a tabela de itens e a de
    volumes dividem a pagina. `page_count` e o que o OCR contou; divergir do
    markdown e nota, nunca erro.
    """
    pages = []
    for span in page_spans(content):
        kind, packing, money, evidencia = _classify(content[span["start"]:span["end"]])
        pages.append(dict(span, kind=kind, packing_score=packing,
                          money_score=money, evidence=evidencia))
    return {
        "page_count": len(pages),
        "pages": pages,
        "invoice_pages": [p["page_number"] for p in pages if p["kind"] == INVOICE],
        "packing_list_pages": [p["page_number"] for p in pages if p["kind"] == PACKING_LIST],
        "mixed_pages": [p["page_number"] for p in pages if p["kind"] == MIXED],
        "ocr_page_count": page_count or 0,
        "page_count_mismatch": bool(page_count) and page_count != len(pages),
    }


def only_in_pages(value, content: str, pages: list[dict], kind: str = PACKING_LIST) -> bool:
    """Verdadeiro se TODA ocorrencia de `value` cai em pagina do tipo dado.

    Falso quando o valor nao aparece ou aparece em alguma outra pagina: a
    pos-checagem so acusa linha cujo part number existe exclusivamente no
    packing list.
    """
    needle = (str(value) if value is not None else "").strip()
    if not needle or not pages:
        return False
    alvo = [p for p in pages if p["kind"] == kind]
    if not alvo:
        return False
    achou = False
    for m in re.finditer(re.escape(needle), content):
        achou = True
        if not any(p["start"] <= m.start() < p["end"] for p in alvo):
            return False
    return achou
