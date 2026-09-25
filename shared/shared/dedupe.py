"""Chave de duplicata: (invoice_number, supplier) normalizados.

Premissa do cliente: "INVOICES DUPLICADAS PRECISAM SER SINALIZADAS
(INVOICE + FORNECEDOR)". A comparacao nao pode ser sobre o texto cru -- o mesmo
fornecedor sai do OCR como 'DOKTAS DOKUMCULUK TIC. VE SAN. A.S.', 'Doktas
Dokumculuk Tic ve San AS' e variantes, e nenhuma delas casa com igualdade.

Mora no shared porque as DUAS aplicacoes precisam: a function marca na
gravacao, o backend remarca quando o revisor corrige o fornecedor a mao.
"""
from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Document, DocumentStatus, Invoice

# Sufixos de forma juridica. Removidos so do FIM do nome, nunca do meio: 'CO'
# no meio e palavra ('CO PRODUCTS'), no fim e 'company'.
_LEGAL_SUFFIXES = {
    "SA", "SAS", "SARL", "SASU", "SAU", "SL", "SLU", "SRL", "SPA", "SPRL",
    "GMBH", "MBH", "AG", "KG", "OHG", "UG",
    "LTDA", "LTD", "LIMITED", "PLC", "INC", "LLC", "CORP", "CORPORATION",
    "CO", "COMPANY", "BV", "NV", "AB", "OY", "AS", "ASA", "APS",
    "PTE", "PTY", "EIRELI", "ME", "EPP",
    # Turco: 'Ticaret ve Sanayi Anonim Sirketi' vira 'TIC. VE SAN. A.S.'
    "TIC", "SAN", "VE", "ANONIM", "SIRKETI", "TICARET", "SANAYI",
}

_NOT_ALNUM = re.compile(r"[^A-Z0-9]+")

# Status que tiram o documento do jogo: nenhum dos dois representa fatura que
# entrou no sistema de verdade.
_MORTOS = (DocumentStatus.rejected, DocumentStatus.error)


def _fold(text: str) -> str:
    """Maiusculas sem acento. 'Groeneveld' e 'GROENEVELD' sao o mesmo nome."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


def normalise_supplier(value) -> str | None:
    """Chave de fornecedor, ou None se nao der para formar uma.

    'DOKTAS DOKUMCULUK TIC. VE SAN. A.S.' -> 'DOKTASDOKUMCULUK'
    'Groeneveld-BEKA GmbH'                -> 'GROENEVELDBEKA'
    """
    if value is None:
        return None
    folded = _fold(str(value))
    # Os pontos caem primeiro para que 'S.R.L.' vire um token 'SRL' em vez de
    # tres tokens de uma letra.
    tokens = [t for t in _NOT_ALNUM.split(folded.replace(".", "")) if t]
    if not tokens:
        return None

    trimmed = list(tokens)
    while len(trimmed) > 1 and trimmed[-1] in _LEGAL_SUFFIXES:
        trimmed.pop()

    # Fornecedor cujo nome inteiro e forma juridica existe ('S.A.' sozinho num
    # campo mal lido). Melhor uma chave ruim que chave nenhuma.
    return "".join(trimmed) or "".join(tokens)


def normalise_invoice_number(value) -> str | None:
    """'739 /01' -> '73901'. Espaco e barra sao do layout, nao do numero."""
    if value is None:
        return None
    return _NOT_ALNUM.sub("", _fold(str(value))) or None


def find_original(
    db: Session,
    *,
    invoice_number_key: str | None,
    supplier_key: str | None,
    exclude_invoice_id: uuid.UUID | None = None,
) -> Invoice | None:
    """A invoice mais antiga com a mesma chave, ou None.

    Decisao do cliente: o antigo e sempre a referencia e nunca e marcado; quem
    recebe a marca e o novo. Por isso 'a mais antiga' -- ordenar por created_at
    ascendente devolve a original mesmo quando ja existem varias copias.

    As duas metades da chave sao exigidas. Sem elas o casamento seria por
    ausencia: toda invoice sem numero seria duplicata de toda outra sem numero.

    So entra como original quem nao e copia de ninguem. Sem isso a terceira
    entrada apontaria para a segunda, que aponta para a primeira, e a tela
    teria de subir a corrente para dizer de onde a fatura veio.

    E documento rejeitado ou com erro NAO e referencia. Rejeitar quer dizer
    "esta leitura nao presta, vou subir de novo" -- se ele continuasse valendo,
    o reenvio corrigido voltaria marcado como copia do scan ruim que acabou de
    ser descartado, e o revisor nao teria como desmarcar.
    """
    if not invoice_number_key or not supplier_key:
        return None

    stmt = (
        select(Invoice)
        .where(
            Invoice.invoice_number_key == invoice_number_key,
            Invoice.supplier_key == supplier_key,
            Invoice.duplicate_of_id.is_(None),
            Invoice.document_id.in_(
                select(Document.id).where(Document.status.notin_(_MORTOS))
            ),
        )
        .order_by(Invoice.created_at.asc(), Invoice.id.asc())
        .limit(1)
    )
    if exclude_invoice_id is not None:
        stmt = stmt.where(Invoice.id != exclude_invoice_id)
    return db.scalars(stmt).first()


def reresolve_dependents(db: Session, document_id) -> list[Invoice]:
    """Reavalia quem apontava para as invoices deste documento. Devolve as mexidas.

    A marca de duplicata e calculada na GRAVACAO, entao ela envelhece: rejeitar
    o documento A depois de B ter sido marcado como copia dele deixaria B
    apontando para um documento descartado. Chamado pelo endpoint de rejeicao,
    depois de o status ja estar gravado -- e por isso que o find_original aqui
    ja nao enxerga A.

    Se sobrar outra copia viva com a mesma chave, B passa a apontar para ela;
    se nao sobrar nenhuma, B deixa de ser duplicata.
    """
    orfas = db.scalars(
        select(Invoice).where(
            Invoice.duplicate_of_id.in_(
                select(Invoice.id).where(Invoice.document_id == document_id)
            )
        )
    ).all()
    mexidas = []
    for inv in orfas:
        nova = find_original(
            db,
            invoice_number_key=inv.invoice_number_key,
            supplier_key=inv.supplier_key,
            exclude_invoice_id=inv.id,
        )
        anterior = inv.duplicate_of_id
        inv.duplicate_of_id = None if nova is None else nova.id
        if inv.duplicate_of_id != anterior:
            mexidas.append(inv)
    return mexidas
