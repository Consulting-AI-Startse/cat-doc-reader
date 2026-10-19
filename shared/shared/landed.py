"""Rateio de frete e embalagem da fatura sobre as linhas: o unitario "com encargos".

Mora no shared porque as duas aplicacoes calculam: a function na extracao, e o
backend no PATCH, quando o revisor corrige unitario, frete ou embalagem. Se o
backend nao recalculasse, o valor gravado seria o da extracao, nao o da tela.

O cliente soma o encargo ao preco unitario: na fatura CD970373103 sao
90 x 388,46 = 34.961,40 mais 603,00 de embalagem, e o gabarito pede 395,16 e
35.564,40 -- ou seja 603/90 por unidade. O divisor (unidade, peso ou valor)
ainda e pergunta aberta ao cliente; com uma linha so os tres dao o mesmo.

Funcao pura sobre numeros: o structurer chega com floats do _num, o backend
com Decimal, e o teste roda sem banco.
"""
from __future__ import annotations


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def apportion(lines, extra):
    """(por_unidade, [(unit_price_landed, amount_landed) | None por linha]).

    `lines`: [(quantidade, unit_price)] na ordem das linhas. `extra`: frete +
    embalagem da fatura.

    So entra no divisor a linha que tem unitario e quantidade positiva -- o
    mesmo criterio de quem recebe o rateio. Na CIV 3YNDJ a nota '0V3456 END
    USE' (quantidade 1, sem preco) entrava na conta, e o frete de 161,99 saiu
    rateado por 3 unidades quando eram 2 motores.

    Os valores saem como texto com duas casas, que e o que o gabarito traz
    (395,16), e servem tanto ao JSON do structurer quanto ao Decimal do banco.
    Sem encargo, ou sem linha elegivel, nada e rateado: (None, [None, ...]).
    """
    pairs = [(_f(q), _f(u)) for q, u in lines]
    eligible = [(q, u) for q, u in pairs if u is not None and q is not None and q > 0]
    total_qty = sum(q for q, _ in eligible)
    extra = _f(extra) or 0.0
    if not extra or total_qty <= 0:
        return None, [None] * len(pairs)
    per_unit = extra / total_qty
    out = []
    for q, u in pairs:
        if u is None or q is None or q <= 0:
            out.append(None)
            continue
        out.append(("%.2f" % (u + per_unit), "%.2f" % ((u + per_unit) * q)))
    return per_unit, out
