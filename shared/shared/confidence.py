"""Agregados da confianca por campo de uma invoice.

Mora no shared porque roda dos dois lados: o doc_worker grava na extracao, e
o PATCH do backend recalcula a cada salvar -- o PATCH recria todas as linhas,
entao os agregados nao podem depender de quem gravou primeiro.

Quem da a nota de cada campo e function/pipeline/confidence.py; aqui so se
soma. Cada entrada e {"score": float|None, "status": str}, e o status
'corrected' e posto pela tela de revisao quando o revisor edita o campo, com
o status anterior em 'was'.
"""
from __future__ import annotations

FLAGGED = ("low", "ambiguous", "not_located")
CORRECTED = "corrected"


def _entries(header_fc, lines_fc):
    for fc in [header_fc, *lines_fc]:
        for entry in (fc or {}).values():
            if isinstance(entry, dict):
                yield entry


def summarise(header_fc, lines_fc) -> dict:
    """min, media, marcados e corrigidos. Tudo None/0 quando nao ha nota.

    O campo corrigido sai da minima e da media: o valor gravado passou a ser o
    do revisor, e a nota do OCR nao fala mais dele. Mas conta em 'corrected',
    que e a medida de acerto que valida a propria nota.
    """
    notas = []
    flagged = 0
    corrected = 0
    for entry in _entries(header_fc, lines_fc):
        status = entry.get("status")
        if status == CORRECTED:
            corrected += 1
            continue
        if status in FLAGGED:
            flagged += 1
        score = entry.get("score")
        if score is not None:
            notas.append(float(score))
    return {
        "min_field_confidence": min(notas) if notas else None,
        "mean_field_confidence": round(sum(notas) / len(notas), 4) if notas else None,
        "flagged_fields": flagged,
        "corrected_fields": corrected,
    }


# --- relatorio por fornecedor --------------------------------------------------
#
# Funcoes puras sobre dicts, para o teste rodar sem banco nem HTTP (o CI da CAT
# nao tem httpx). Quem monta os dicts e o endpoint em backend/app/api/suppliers.py.
#
# Cada invoice de entrada: supplier_key, supplier, invoice_id, invoice_number,
# document_id, document_status, created_at, min_field_confidence,
# mean_field_confidence, flagged_fields, corrected_fields, header_fc, lines_fc.

# 'derived' e 'unanchored' nao foram lidos: nao entram na conta de pontuados.
_SCORED = ("ok", "low", "ambiguous", "not_located", CORRECTED)


def _ratio(a, b):
    return round(a / b, 4) if b else None


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 4) if values else None


def field_breakdown(invoices: list[dict]) -> list[dict]:
    """Por campo: quantas vezes foi pontuado, marcado e corrigido. Pior primeiro."""
    stats: dict[str, dict] = {}
    for inv in invoices:
        for fc in [inv.get("header_fc"), *(inv.get("lines_fc") or [])]:
            for field, entry in (fc or {}).items():
                status = (entry or {}).get("status")
                if status not in _SCORED:
                    continue
                s = stats.setdefault(field, {"field": field, "scored": 0, "low": 0,
                                             "ambiguous": 0, "not_located": 0,
                                             CORRECTED: 0, "_scores": []})
                s["scored"] += 1
                if status != "ok":
                    s[status] += 1
                if status != CORRECTED and entry.get("score") is not None:
                    s["_scores"].append(float(entry["score"]))
    out = []
    for s in stats.values():
        s["mean_score"] = _mean(s.pop("_scores"))
        s["problems"] = s["low"] + s["ambiguous"] + s["not_located"] + s[CORRECTED]
        out.append(s)
    out.sort(key=lambda s: (-s["problems"] / s["scored"], s["field"]))
    return out


def supplier_report(invoices: list[dict]) -> list[dict]:
    """Uma linha por fornecedor, o de menor confianca media primeiro.

    Quem chama ja tirou as invoices que nao contam: documento rejeitado ou com
    erro (rejeitar e "esta leitura nao presta", nao uma fatura) e copia de
    duplicata (a mesma fatura contaria duas vezes).

    Invoice sem nota (modo local, gravada antes da 0007) entra em 'invoices'
    mas nao nas medias: 'invoices_scored' diz quantas sustentam o numero.
    """
    grupos: dict[str | None, list[dict]] = {}
    for inv in invoices:
        grupos.setdefault(inv.get("supplier_key"), []).append(inv)

    linhas = []
    for key, invs in grupos.items():
        invs = sorted(invs, key=lambda i: str(i.get("created_at") or ""))
        com_nota = [i for i in invs if i.get("min_field_confidence") is not None]
        campos = field_breakdown(com_nota)
        pontuados = sum(c["scored"] for c in campos)
        corrigidos = sum(c[CORRECTED] for c in campos)
        fraco = next((c["field"] for c in campos if c["problems"]), None)
        ultimo = invs[-1]
        linhas.append({
            "supplier_key": key,
            # O nome impresso varia ('DOKTAS ... A.S.' e variantes); vale o mais recente.
            "supplier": ultimo.get("supplier"),
            "invoices": len(invs),
            "invoices_scored": len(com_nota),
            "mean_confidence": _mean(i.get("mean_field_confidence") for i in com_nota),
            "min_confidence": min((i["min_field_confidence"] for i in com_nota), default=None),
            "flagged_invoices": sum(1 for i in com_nota if (i.get("flagged_fields") or 0) > 0),
            "flagged_rate": _ratio(sum(1 for i in com_nota if (i.get("flagged_fields") or 0) > 0),
                                   len(com_nota)),
            "fields_scored": pontuados,
            "fields_corrected": corrigidos,
            "correction_rate": _ratio(corrigidos, pontuados),
            "review_rate": _ratio(sum(1 for i in invs if i.get("document_status") == "needs_review"),
                                  len(invs)),
            "weakest_field": fraco,
            "last_seen": ultimo.get("created_at"),
            "last_document_id": ultimo.get("document_id"),
        })
    # Sem nota vai para o fim: nao da para dizer que e o pior.
    linhas.sort(key=lambda l: (l["mean_confidence"] is None, l["mean_confidence"] or 0,
                               str(l["supplier"] or "")))
    return linhas
