"""Lista de part numbers liberados: normalizacao, consulta e regra de serial.

Mora no shared porque as duas aplicacoes precisam: o backend importa a lista e
edita as regras, a function consulta a cada documento.

A consulta e sempre UMA por documento, com `part_number = ANY(...)`. Carregar
as 206.769 linhas na memoria da function a cada invocacao seria 18 MB por
chamada para responder o que um Index Scan responde em 0,4 ms.
"""
from __future__ import annotations

import csv
import io as _io
import re

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .models import ReleasedPartNumber, SerialRules

_NOT_ALNUM = re.compile(r"[^A-Z0-9]+")

# A forma de um part number CAT mora aqui, e nao no structurer, porque o
# backend tambem precisa dela: o PATCH reconfere na lista o part number que o
# revisor editou, e '663-7238~00' tem de virar a mesma chave nos dois lados.
#
# Prefixo de 3 alfanumericos com hifen opcional ('463-8344', '6511308') ou de
# 2 SEMPRE com hifen ('5P-1465', '7G-5837'). O hifen no caso curto e o que
# separa um part number real da marcacao de end use '0V3456', que tem a mesma
# forma sem hifen.
PART_NUMBER_RE = re.compile(r"^(?:[0-9A-Z]{3}-?[0-9]{4}|[0-9A-Z]{2}-[0-9]{4})$")
# Sufixo de revisao/planta que a Caterpillar imprime junto do part number:
# '663-7238~00', '6064986-07', '364-9717/01'. Nao faz parte do numero.
PART_NUMBER_SUFFIX_RE = re.compile(r"^(?P<base>.+?)(?P<suffix>[~/][0-9A-Z]{1,3}|-[0-9]{2})$")
# A AutoMotionShade imprime 'CAT 657-3755': o prefixo e da marca.
CAT_PREFIX_RE = re.compile(r"^CAT[\s:#-]+(\S+)$", re.IGNORECASE)


def split_part_number(text: str):
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


def part_number_key(value) -> str | None:
    """Chave da lista para um part number como impresso ou editado.

    Part number CAT perde marca, sufixo e hifen ('CAT 663-7238~00' ->
    '6637238'), que e a forma da lista e da coluna Material do gabarito. O
    resto so perde o que nao e alfanumerico, como no import da lista.
    """
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().upper()
    m = CAT_PREFIX_RE.match(text)
    if m and PART_NUMBER_RE.match(split_part_number(m.group(1))[0]):
        text = m.group(1)
    base, _ = split_part_number(text)
    if PART_NUMBER_RE.match(base):
        return base.replace("-", "")
    return normalise_part_number(text)


def normalise_part_number(value) -> str | None:
    """Forma canonica da chave: maiuscula, sem hifen nem sufixo de revisao.

    O mesmo documento imprime '463-8344' e '6637238', e o gabarito do cliente
    usa a forma sem hifen ('663-7238~00' -> '6637238'). A lista tem de ser
    consultada por uma chave so, senao metade das linhas nao casa.
    """
    if value is None:
        return None
    return _NOT_ALNUM.sub("", str(value).upper()) or None


def lookup(db: Session, part_numbers) -> dict[str, ReleasedPartNumber]:
    """{chave normalizada: linha} para os part numbers que existem na lista.

    Uma consulta, um round-trip. Quem nao voltar no dicionario nao esta
    liberado -- e a linha continua sendo gravada, com nota, porque a regra do
    repo e marcar e nunca descartar.
    """
    chaves = sorted({k for k in (normalise_part_number(p) for p in part_numbers) if k})
    if not chaves:
        return {}
    linhas = db.scalars(
        select(ReleasedPartNumber).where(ReleasedPartNumber.part_number.in_(chaves))
    ).all()
    return {linha.part_number: linha for linha in linhas}


def released_flags(db: Session, part_numbers) -> list[bool | None]:
    """Para cada part number: True na lista, False fora dela, None sem como
    julgar (vazio, ou a lista ainda nao foi importada).

    Lista vazia nao e "nada esta liberado": sem esta distincao, um ambiente
    novo marcaria toda linha de toda fatura como fora da lista. Duas consultas
    por documento, nunca uma por linha.
    """
    keys = [part_number_key(p) for p in part_numbers]
    if not any(keys):
        return [None] * len(keys)
    if db.scalar(select(ReleasedPartNumber.part_number).limit(1)) is None:
        return [None] * len(keys)
    found = lookup(db, [k for k in keys if k])
    return [None if not k else (k in found) for k in keys]


def get_rules(db: Session) -> SerialRules:
    """A linha unica de regras. A 0005 a cria, entao ela sempre existe."""
    regras = db.get(SerialRules, 1)
    if regras is None:
        # Banco criado por caminho que nao passou pela 0005 (db-setup-v2.sql
        # desatualizado, por exemplo). Melhor criar do que estourar na tela.
        regras = SerialRules(id=1, substrings=[], manual_part_numbers=[])
        db.add(regras)
        db.flush()
    return regras


def _condicao(substrings, manuais):
    """Expressao SQL de 'esta peca exige serial', com os parametros.

    COALESCE no nome porque uma linha da planilha real vem com nome vazio, e
    `NULL ILIKE '%x%'` e NULL -- que viola o NOT NULL da coluna e aborta o
    UPDATE inteiro. Uma linha em 206.769 derrubando a regra toda.
    """
    padroes = ["%%%s%%" % s.strip() for s in substrings if s and s.strip()]
    chaves = [k for k in (normalise_part_number(p) for p in manuais) if k]
    if not padroes and not chaves:
        return text("false"), {}
    partes, params = [], {}
    if padroes:
        partes.append("COALESCE(name,'') ILIKE ANY(:padroes)")
        params["padroes"] = padroes
    if chaves:
        partes.append("part_number = ANY(:chaves)")
        params["chaves"] = chaves
    return text("(%s)" % " OR ".join(partes)), params


def preview(db: Session, substrings, manuais, amostra: int = 8) -> dict:
    """Quantas pecas a regra marcaria, e exemplos. NAO grava nada.

    E o que torna a tela segura: 'ENGINE' casa 910 pecas, quase todas
    acessorio ('SUPPORT-ENGINE', 'FILM-ENGINE OIL', 'CHART-ENGINE'), enquanto
    'ENGINE AR' casa 588 e nenhum falso positivo. Sem ver isso antes de
    salvar, quem digita 'ENGINE' acha que acertou.
    """
    cond, params = _condicao(substrings, manuais)
    total = db.scalar(select(func.count()).select_from(ReleasedPartNumber).where(cond).params(**params))
    exemplos = db.execute(
        select(ReleasedPartNumber.part_number, ReleasedPartNumber.name)
        .where(cond).params(**params)
        .order_by(ReleasedPartNumber.part_number)
        .limit(amostra)
    ).all()
    return {
        "marcadas": total or 0,
        "total_na_lista": db.scalar(select(func.count()).select_from(ReleasedPartNumber)) or 0,
        "exemplos": [{"part_number": pn, "name": nome} for pn, nome in exemplos],
    }


def recompute(db: Session, substrings, manuais) -> int:
    """Reaplica a regra na tabela inteira. Devolve quantas ficaram marcadas.

    206.769 linhas em 0,81 s, medido. Barato o bastante para rodar a cada
    mudanca de regra e a cada import, que e o que mantem requires_serial
    coerente com o que a tela mostra.
    """
    cond, params = _condicao(substrings, manuais)
    db.execute(
        text("UPDATE released_part_numbers SET requires_serial = %s" % cond.text).bindparams(**params)
        if params else text("UPDATE released_part_numbers SET requires_serial = false")
    )
    return db.scalar(
        select(func.count()).select_from(ReleasedPartNumber).where(ReleasedPartNumber.requires_serial)
    ) or 0


# Primeira celula que significa cabecalho, nao part number.
_CABECALHOS = ("PECA", "PE\u00c7A", "PART_NUMBER", "PART NUMBER", "PN")

# Limite da coluna part_number no schema.
_MAX_CHAVE = 32


def decode_csv(bruto: bytes) -> str:
    """Texto do CSV, tolerando o que o Excel do Windows produz."""
    try:
        return bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel no Windows salva CSV em latin-1 com frequencia.
        return bruto.decode("latin-1")


def parse_csv(texto: str) -> dict:
    """Le o CSV da lista de PN. Devolve o que gravar e o que aconteceu.

    Funcao pura: sem banco, sem HTTP. Ficou aqui e nao no endpoint porque e
    LOGICA, e logica precisa de teste barato -- testar isso pelo TestClient do
    FastAPI arrastava o httpx, que nao esta no requirements.txt do backend e
    quebraria o CI da CAT em 'from fastapi.testclient import TestClient'.

    Linha invalida NAO derruba o arquivo: e contada e explicada. Um CSV de 206
    mil linhas com tres defeitos tem de importar o resto e dizer quais falharam.

    A conta fecha sempre: recebidas = validas + duplicadas + len(erros).
    """
    linhas = list(csv.reader(_io.StringIO(texto)))
    if not linhas:
        return {"vazio": True, "validas": [], "recebidas": 0, "duplicadas": 0, "erros": []}

    # Cabecalho e opcional: so pulamos se a primeira celula for um titulo
    # conhecido. Pular por heuristica apagaria a primeira peca do arquivo.
    inicio = 1 if (linhas[0][0] if linhas[0] else "").strip().upper() in _CABECALHOS else 0

    recebidas = 0
    duplicadas = 0
    erros: list[str] = []
    vistos: set[str] = set()
    validas: list[tuple[str, str | None]] = []

    for n, linha in enumerate(linhas[inicio:], start=inicio + 1):
        if not linha or not any(c.strip() for c in linha):
            continue
        recebidas += 1
        chave = normalise_part_number(linha[0])
        if not chave:
            if len(erros) < 20:
                erros.append("linha %d: part number vazio ou sem caractere util" % n)
            continue
        if len(chave) > _MAX_CHAVE:
            if len(erros) < 20:
                erros.append(
                    "linha %d: part number '%s' tem mais de %d caracteres"
                    % (n, chave, _MAX_CHAVE)
                )
            continue
        # Repetida dentro do proprio arquivo: o upsert em lote reclama de duas
        # linhas com a mesma chave no mesmo comando. Nao e erro, mas e contada
        # -- "ignoradas" sem explicacao e o mesmo defeito de documento gravado
        # sem nota.
        if chave in vistos:
            duplicadas += 1
            continue
        vistos.add(chave)
        nome = (linha[1].strip() if len(linha) > 1 and linha[1] else None) or None
        validas.append((chave, nome))

    return {"vazio": False, "validas": validas, "recebidas": recebidas,
            "duplicadas": duplicadas, "erros": erros}
