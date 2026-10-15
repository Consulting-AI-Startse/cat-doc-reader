"""Metricas de processamento por periodo, para o dashboard.

Premissa do contrato: "METRICAS DE PERFORMANCE DO AGENTE, DE PROCESSAMENTO E
POR PERIODO". Funcoes puras sobre dicts, pelo mesmo motivo do relatorio por
fornecedor em shared/confidence.py: o teste roda sem banco nem HTTP (o CI da
CAT nao tem httpx). Quem monta os dicts e backend/app/api/dashboard.py; o
filtro de periodo fica no SQL.

Cada documento de entrada:
  status        valor de DocumentStatus ('received', 'processing', 'extracted',
                'needs_review', 'approved', 'rejected', 'error')
  created_at    upload
  started_at    created_at do evento 'processing' do worker (None se nao houve)
  processed_at  fim do processamento, com ou sem sucesso (None se nao terminou)
  reviewed      True se o documento passou por 'needs_review' em algum momento
  not_invoice   True se o structurer marcou "provavelmente nao e invoice"
  invoices      lista de {duplicate: bool, amount: float|None,
                          header_fc: dict|None, lines_fc: list[dict|None]}

Precisa rodar em 3.11: o shared e vendorizado na function.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from .confidence import CORRECTED, _SCORED

# Terminou de processar: ou foi gravado com leitura, ou o humano ja decidiu.
_FINISHED = ("extracted", "needs_review", "approved", "rejected")
# Tem leitura que conta: rejeitar e "esta leitura nao presta", e erro nao tem
# leitura. Mesma regra da duplicata e do relatorio por fornecedor.
_COUNTS = ("extracted", "needs_review", "approved")


def _ratio(a, b):
    return round(a / b, 4) if b else None


def _percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank, sem numpy: o shared nao pode arrastar dependencia."""
    if not values:
        return None
    ordenado = sorted(values)
    k = max(1, math.ceil(p * len(ordenado)))
    return round(ordenado[min(k, len(ordenado)) - 1], 1)


def _durations(pairs) -> dict:
    """{median, p90, n} em segundos de (inicio, fim), ignorando par incompleto."""
    segundos = []
    for inicio, fim in pairs:
        if inicio is None or fim is None:
            continue
        delta = (fim - inicio).total_seconds()
        # Relogio: processed_at vem do Python da function, o evento do now() do
        # Postgres. Um delta negativo e desvio de relogio, nao duracao.
        if delta >= 0:
            segundos.append(delta)
    return {"median": _percentile(segundos, 0.5), "p90": _percentile(segundos, 0.9),
            "n": len(segundos)}


# O dia do grafico e o de Brasilia: em UTC, um upload das 22h caia no dia
# seguinte. Offset fixo e suficiente -- o Brasil nao tem horario de verao
# desde 2019.
_BRT = timezone(timedelta(hours=-3))


def _day(moment) -> date | None:
    if moment is None:
        return None
    if isinstance(moment, datetime):
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(_BRT).date()
    return moment


def _outcome(doc: dict) -> str:
    """Em que coluna da barra do dia o documento cai."""
    status = doc.get("status") or ""
    if status in ("received", "processing"):
        return "pending"
    if status == "error":
        return "error"
    if status in ("extracted", "approved") and not doc.get("reviewed"):
        return "auto"
    return "review"


def daily_series(docs: list[dict], days: int, today=None) -> list[dict]:
    """Uma entrada por dia do periodo, inclusive os dias sem documento.

    Dia sem documento entra com zeros: um grafico que pula o dia vazio
    esconde justamente a parada. `days` 0 vai do primeiro upload ate hoje.
    """
    hoje = _day(today) if today is not None else None
    dias = [d for d in (_day(doc.get("created_at")) for doc in docs) if d]
    if hoje is None:
        hoje = max(dias) if dias else None
    if hoje is None:
        return []
    if days > 0:
        inicio = hoje - timedelta(days=days - 1)
    else:
        inicio = min(dias) if dias else hoje
    por_dia: dict = {}
    for doc in docs:
        d = _day(doc.get("created_at"))
        if d is None or d < inicio or d > hoje:
            continue
        por_dia.setdefault(d, []).append(doc)
    out = []
    d = inicio
    while d <= hoje:
        grupo = por_dia.get(d, [])
        contagem = {"pending": 0, "auto": 0, "review": 0, "error": 0}
        for doc in grupo:
            contagem[_outcome(doc)] += 1
        out.append({
            "date": d.isoformat(),
            "received": len(grupo),
            **contagem,
            "not_invoice": sum(1 for doc in grupo if doc.get("not_invoice")),
            "processing_median": _durations(
                (doc.get("started_at"), doc.get("processed_at")) for doc in grupo)["median"],
        })
        d += timedelta(days=1)
    return out


def processing_report(docs: list[dict], days: int = 0, today=None) -> dict:
    """Contagens, taxas e tempos do periodo. Tudo None/0 quando nao ha dado.

    - `valor_total_extraido` soma so invoice que conta: fora copia de
      duplicata, documento rejeitado e com erro. O endpoint antigo somava
      tudo, inclusive a copia -- a mesma fatura duas vezes.
    - `auto_rate` e a fracao dos documentos terminados que NUNCA passaram por
      needs_review e nao foram rejeitados: a medida de quanto o agente
      resolve sozinho. Aprovado depois de revisao conta como revisado, e
      rejeitado e leitura que nao prestou, mesmo que o limite nao tenha
      pegado.
    - `processing_seconds` e do evento 'processing' ate processed_at: o tempo
      do worker (OCR + LLM + gravacao). `turnaround_seconds` e do upload ate
      processed_at: o que o usuario espera. Documento que ainda nao terminou
      fica fora, e `n` diz quantos sustentam o numero.
    - `fields_corrected_rate` e campos corrigidos na revisao sobre campos
      pontuados: a medida de acerto que valida a propria nota de confianca.
    """
    por_status: dict[str, int] = {}
    invoices = duplicatas = 0
    valor = 0.0
    auto = terminados = 0
    pontuados = corrigidos = 0
    for doc in docs:
        status = doc.get("status") or ""
        por_status[status] = por_status.get(status, 0) + 1
        if status in _FINISHED:
            terminados += 1
            if status in ("extracted", "approved") and not doc.get("reviewed"):
                auto += 1
        for inv in doc.get("invoices") or []:
            invoices += 1
            if inv.get("duplicate"):
                duplicatas += 1
                continue
            if status not in _COUNTS:
                continue
            if inv.get("amount") is not None:
                valor += float(inv["amount"])
            for fc in [inv.get("header_fc"), *(inv.get("lines_fc") or [])]:
                for entry in (fc or {}).values():
                    st = (entry or {}).get("status")
                    if st in _SCORED:
                        pontuados += 1
                        if st == CORRECTED:
                            corrigidos += 1

    return {
        "documentos": len(docs),
        "invoices": invoices,
        "nao_processados": por_status.get("received", 0) + por_status.get("processing", 0),
        "aguardando_revisao": por_status.get("extracted", 0) + por_status.get("needs_review", 0),
        "aprovados": por_status.get("approved", 0),
        "rejeitados": por_status.get("rejected", 0),
        "erros": por_status.get("error", 0),
        "duplicatas": duplicatas,
        "nao_invoice": sum(1 for d in docs if d.get("not_invoice")),
        "valor_total_extraido": round(valor, 2),
        "terminados": terminados,
        "auto_extracted": auto,
        "auto_rate": _ratio(auto, terminados),
        "review_rate": _ratio(terminados - auto, terminados),
        "processing_seconds": _durations(
            (d.get("started_at"), d.get("processed_at")) for d in docs),
        "turnaround_seconds": _durations(
            (d.get("created_at"), d.get("processed_at")) for d in docs),
        "fields_scored": pontuados,
        "fields_corrected": corrigidos,
        "fields_corrected_rate": _ratio(corrigidos, pontuados),
        "series": daily_series(docs, days, today),
    }
