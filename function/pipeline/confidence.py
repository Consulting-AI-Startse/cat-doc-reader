"""Confianca por campo, medida no OCR -- nunca perguntada ao modelo.

A confianca auto-reportada pelo GPT nao vale nada: um documento voltou com
0.95 e quatro defeitos. Aqui cada valor que o structurer devolveu e procurado
no texto do Document Intelligence e recebe a nota das palavras que o cobrem.

Tres sinais, todos medidos no CIV (52 campos, as duas rodadas de 10/09 e
01/10, zero falso positivo):

- **leitura fraca**: a menor confianca de palavra, na PIOR ocorrencia do valor.
  Na rodada de 10/09, '26-2100870' aparece duas vezes e so uma esta a 0.573 --
  pela melhor ocorrencia o defeito sumia.
- **leitura ambigua**: o documento tambem traz o valor com um caractere
  confundivel trocado (O/0, I/1...). Na rodada de 01/10 o modelo copiou
  '26-2I00870' de uma pagina onde o OCR leu o I com confianca ALTA; a
  confianca da palavra nao acusa nada, mas '26-2100870' esta impresso em outra
  pagina.
- **nao localizado**: o valor nao aparece no texto. O '50,000' italiano
  convertido em 50000 foi pego assim.

So vale no caminho Document Intelligence: o modo local pontua por pagina, nao
por palavra, e nao entrega o indice.
"""
import bisect
import re

# Mesmo corte do extractor (LOW_CONFIDENCE), que ja separa as palavras ruins.
# Os dois defeitos medidos no CIV estao a 0.57; calibrar com o corpus.
LOW_CONFIDENCE = 0.85
# Nota de quem tem gemeo confundivel: abaixo do limite de proposito, para que
# a leitura ambigua derrube o documento mesmo com palavras limpas.
AMBIGUOUS_SCORE = 0.50
# Numero so e procurado perto do part number da linha: '90' aparece 86 vezes
# no CIV, e uma busca global acharia sempre uma ocorrencia qualquer.
NUMBER_WINDOW = 1500

# O que o OCR troca. Medido: 'I' por '1' no numero da invoice da Cattini e 'O'
# por '0' no pedido da Bosch.
CONFUSABLE = {"O": "0", "0": "O", "I": "1", "1": "I", "L": "1",
              "S": "5", "5": "S", "B": "8", "8": "B", "Z": "2", "2": "Z"}

FLAGGED = ("low", "ambiguous", "not_located")

IDENTIFIER_FIELDS = ("part_number", "purchase_order")
NUMBER_FIELDS = ("quantity", "unit_price", "amount")


class WordIndex:
    """Palavras do OCR ordenadas por offset: (offset, length, confidence)."""

    def __init__(self, words):
        self._words = sorted(
            (int(o), int(n), float(c)) for o, n, c in words
            if o is not None and n is not None and c is not None
        )
        self._offsets = [w[0] for w in self._words]
        self._longest = max((w[1] for w in self._words), default=0)

    def min_conf(self, start: int, end: int):
        """Menor confianca entre as palavras que tocam [start, end). None se nenhuma."""
        i = bisect.bisect_left(self._offsets, start - self._longest)
        worst = None
        for offset, length, conf in self._words[i:]:
            if offset >= end:
                break
            if offset + length > start:
                worst = conf if worst is None else min(worst, conf)
        return worst


def _identifier_re(value: str):
    # Fronteira alfanumerica: '7001' nao pode casar dentro de '561-7001X'.
    return re.compile(r"(?<![0-9A-Za-z])" + re.escape(value) + r"(?![0-9A-Za-z])")


def _number_re(value: str):
    # Fronteira numerica: '50' nao casa em '1.050' nem em '50,00' -- mas casa
    # em 'QTY 50 PCS'.
    return re.compile(r"(?<![0-9.,])" + re.escape(value) + r"(?![0-9]|[.,][0-9])")


def _occurrences(pattern, content: str, windows=None):
    if windows is None:
        return [(m.start(), m.end()) for m in pattern.finditer(content)]
    seen = set()
    for lo, hi in windows:
        for m in pattern.finditer(content, max(0, lo), min(len(content), hi)):
            seen.add((m.start(), m.end()))
    return sorted(seen)


def _twin(value: str, content: str):
    """O mesmo valor com UM caractere confundivel trocado, se estiver impresso."""
    upper = value.upper()
    for i, ch in enumerate(upper):
        swap = CONFUSABLE.get(ch)
        if swap is None:
            continue
        candidate = value[:i] + swap + value[i + 1:]
        if _identifier_re(candidate).search(content):
            return candidate
    return None


def _grade(occurrences, index: WordIndex):
    """(score, status) pela PIOR ocorrencia."""
    if not occurrences:
        return None, "not_located"
    notas = [index.min_conf(a, b) for a, b in occurrences]
    notas = [n for n in notas if n is not None]
    # Nenhuma palavra cobre o trecho: o valor esta no texto, mas sem nota.
    score = min(notas) if notas else None
    if score is not None and score < LOW_CONFIDENCE:
        return score, "low"
    return score, "ok"


def _entry(score, status, **extra):
    out = {"score": None if score is None else round(score, 4), "status": status}
    out.update({k: v for k, v in extra.items() if v is not None})
    return out


def score_identifier(value, content: str, index: WordIndex):
    if value is None or not str(value).strip():
        return None
    value = str(value).strip()
    forms = [value]
    # O mesmo documento imprime '463-8344' e '4638344'.
    if "-" in value:
        forms.append(value.replace("-", ""))
    elif re.fullmatch(r"[0-9A-Z]{7}", value):
        forms.append(value[:3] + "-" + value[3:])
    occ = []
    for form in forms:
        occ.extend(_occurrences(_identifier_re(form), content))
    score, status = _grade(occ, index)
    twin = _twin(value, content) if occ else None
    if twin is not None:
        return _entry(min(score if score is not None else 1.0, AMBIGUOUS_SCORE),
                      "ambiguous", twin=twin)
    return _entry(score, status)


def number_forms(printed, value):
    """Formas em que o numero pode estar impresso. A copiada pelo modelo primeiro.

    A regra 6 do prompt manda copiar como impresso ('35.564,40'), mas o modelo
    as vezes normaliza; dai as variantes do valor convertido.
    """
    forms = []
    if printed is not None and str(printed).strip():
        forms.append(str(printed).strip())
    if value is not None:
        # Tres casas tambem: a Graziano imprime '114,000' e '5700,000'.
        for casas in (2, 3):
            us = "{:,.{}f}".format(value, casas)
            eu = us.replace(",", "\0").replace(".", ",").replace("\0", ".")
            forms += [us, eu, us.replace(",", ""), eu.replace(".", "")]
        if value == int(value):
            n = int(value)
            forms += [str(n), "{:,}".format(n), "{:,}".format(n).replace(",", ".")]
    out = []
    for f in forms:
        if f not in out:
            out.append(f)
    return out


def score_number(printed, value, content: str, index: WordIndex, anchors=None):
    """`anchors`: offsets do part number da linha. None = documento inteiro."""
    if value is None and (printed is None or not str(printed).strip()):
        return None
    windows = None
    if anchors is not None:
        if not anchors:
            return _entry(None, "not_located")
        windows = [(a - NUMBER_WINDOW, a + NUMBER_WINDOW) for a in anchors]
    occ = []
    for form in number_forms(printed, value):
        occ = _occurrences(_number_re(form), content, windows)
        if occ:
            break
    score, status = _grade(occ, index)
    return _entry(score, status)


def anchors_of(part_number, content: str):
    """Offsets do part number no texto, nas duas formas (com e sem hifen)."""
    if part_number is None or not str(part_number).strip():
        return []
    value = str(part_number).strip()
    forms = {value, value.replace("-", "")}
    if re.fullmatch(r"[0-9A-Z]{7}", value):
        forms.add(value[:3] + "-" + value[3:])
    out = set()
    for form in forms:
        out.update(a for a, _ in _occurrences(_identifier_re(form), content))
    return sorted(out)


def derived():
    """Campo que nao foi lido, foi calculado: nao tem nota de OCR."""
    return _entry(None, "derived")


def line_confidence(li: dict, content: str, index: WordIndex, to_number) -> dict:
    """Nota de cada campo da linha IMPRESSA, antes da expansao por serial.

    `to_number` e o _num do structurer: a variante de formato sai do valor
    convertido por ele, para nao haver duas regras de leitura de numero.
    """
    fc = {}
    for field in IDENTIFIER_FIELDS:
        entry = score_identifier(li.get(field), content, index)
        if entry:
            fc[field] = entry
    anchors = anchors_of(li.get("part_number"), content)
    for field in NUMBER_FIELDS:
        printed = li.get(field)
        if printed is None or not str(printed).strip():
            continue
        if not anchors:
            # Sem part number no texto nao ha janela, e uma busca global por
            # '90' acharia sempre alguma coisa. Quem acusa a linha e o proprio
            # part number, marcado como nao localizado.
            fc[field] = _entry(None, "unanchored")
            continue
        fc[field] = score_number(printed, to_number(printed), content, index, anchors)
    return fc


def describe(tag: str, field: str, value, entry) -> str | None:
    """A nota que o revisor ve. None se o campo nao pede revisao."""
    if not entry or entry.get("status") not in FLAGGED:
        return None
    status = entry["status"]
    if status == "ambiguous":
        return ("%s.%s '%s': leitura ambigua -- o documento tambem traz '%s'"
                % (tag, field, value, entry.get("twin")))
    if status == "not_located":
        return "%s.%s '%s': valor nao localizado no texto do OCR" % (tag, field, value)
    return ("%s.%s '%s': confianca do OCR %.2f, abaixo de %.2f"
            % (tag, field, value, entry["score"], LOW_CONFIDENCE))


def document_min(field_confidences):
    """Menor nota entre todos os campos pontuados. None se nenhum tem nota."""
    notas = [e["score"] for fc in field_confidences for e in (fc or {}).values()
             if e and e.get("score") is not None]
    return min(notas) if notas else None
