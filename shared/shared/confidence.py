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
