r"""Confere o structurer contra o gabarito do cliente, offline.

Precisa de raw-civ-cap.json em Downloads (a ultima extracao do CIV).
Rode da raiz do repo:  & .\function\.venv\Scripts\python.exe .\check_structurer.py
"""
import json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "function"))
from pipeline.structurer import _normalise, _snum, _SYSTEM_PROMPT

RAW = os.path.join(os.path.expanduser("~"), "Downloads", "raw-civ-cap.json")

# Coluna Material do Gabarito_DocReader.xlsx, para os 8 materiais do CIV.
GABARITO_MATERIAL = {"6637238", "6064986", "4638344", "4638343",
                     "4638341", "3649717", "5617001", "3215765"}
# Fatura CD970373103: 90 x 388,46 + 603,00 de embalagem -> 395,16 e 35.564,40
GABARITO_LANDED = ("395.16", "35564.40")

falhas = []


def check(label, got, expected):
    ok = got == expected
    print(("  OK   " if ok else "  FALHA") + f" {label:<44} {got!r} (esperado {expected!r})")
    if not ok:
        falhas.append(label)


if not os.path.exists(RAW):
    sys.exit(f"nao achei {RAW} -- rode a extracao do CIV antes")

raw = json.load(open(RAW, encoding="utf-8-sig"))["raw_extraction"]
content = raw["content"]

# Remonta o payload do modelo a partir do que ficou gravado, e injeta o
# encargo de embalagem que a fatura CD970373103 imprime.
payload = {"invoices": [], "confidence": 0.9}
for inv in raw["structured"]["invoices"]:
    payload["invoices"].append({
        "invoice_number": inv.get("invoice_number"),
        "invoice_date": inv.get("invoice_date"),
        "currency": inv.get("currency"),
        "total": inv.get("total"),
        "line_items": [dict(l) for l in (inv.get("line_items") or [])],
    })
payload["invoices"][0]["packaging_cost"] = "603,00"

# Linhas sinteticas na ULTIMA invoice, para nao contaminar a invoice[0],
# que e a do rateio: quantidade extra ali mudaria o valor por unidade.
#  - 'I/C Material' e prosa: o filtro antigo descartava a linha.
#  - '5P-1465' e part number CAT de 2+4: o filtro antigo tambem a apagava.
payload["invoices"][-1]["line_items"].extend([
    {"part_number": "I/C Material", "quantity": "1", "unit_price": "1.00", "amount": "1.00"},
    {"part_number": "5P-1465", "quantity": "2", "unit_price": "10.00", "amount": "20.00"},
])

out = _normalise(payload, 0.9, [], None, content)
lines = [l for i in out["invoices"] for l in i["line_items"]]

print("=== 1. nenhuma linha descartada ===")
check("total de linhas na saida", len(lines), 10)
check("linha 'I/C Material' sobreviveu",
      any(l["part_number"] == "I/C Material" for l in lines), True)
check("linha '5P-1465' sobreviveu",
      any(l["part_number"] == "5P-1465" for l in lines), True)

print("=== 2. status por part number ===")
by_pn = {l["part_number"]: l for l in lines}
check("status de 'I/C Material'", by_pn["I/C Material"]["part_number_status"], "not_a_code")
# 'not_printed' e o certo aqui: o formato e valido mas 5P-1465 nao esta
# neste documento. O que importa e nao ser 'not_a_code' nem 'other_code'.
check("status de '5P-1465'", by_pn["5P-1465"]["part_number_status"], "not_printed")
check("normalizado de '5P-1465'", by_pn["5P-1465"]["part_number_normalised"], "5P1465")

print("=== 3. normalizado casa com a coluna Material do gabarito ===")
norm = {l["part_number_normalised"] for l in lines if l["part_number_status"] in ("cat", "not_printed")}
check("materiais do gabarito cobertos", len(GABARITO_MATERIAL & norm), 8)

print("=== 4. rateio de embalagem (fatura CD970373103) ===")
first = out["invoices"][0]["line_items"][0]
check("unit_price segue o impresso", first["unit_price"], "388.46")
check("unit_price_landed", first["unit_price_landed"], GABARITO_LANDED[0])
check("amount_landed", first["amount_landed"], GABARITO_LANDED[1])
check("nota de rateio na validation",
      any("rateados" in v for v in out["validation"]), True)

print("=== 5. encargos auditaveis na saida ===")
check("'packaging_cost' emitido no invoice", "packaging_cost" in out["invoices"][0], True)
check("'freight' emitido no invoice", "freight" in out["invoices"][0], True)

print("=== 6. prompt declara os campos que o codigo le ===")
shape = _SYSTEM_PROMPT.split("HARD RULES")[0]
check("'packaging_cost' no shape do prompt", "packaging_cost" in shape, True)
check("'freight' no shape do prompt", "freight" in shape, True)

print("=== 7. prompt manda COPIAR o numero, nunca normalizar ===")
# Pedir normalizacao ao modelo custou o defeito do eu1.pdf: o mesmo
# '22.944,02' impresso voltou 22944.02 em quatro runs e 22.94 em outros
# quatro. As linhas acertaram sempre, porque '161,75 x 10 = 1.617,50' ancora a
# convencao; o total esta sozinho. Quem converte e o _num(), que e
# deterministico -- mas so recebe a chance se o modelo copiar.
# Espaco colapsado: o prompt e quebrado em linhas, entao uma frase procurada
# inteira nao casa se o corte cair no meio dela.
low = re.sub(r"\s+", " ", _SYSTEM_PROMPT.lower())
check("manda copiar exatamente", "exactly as the document prints it" in low, True)
check("proibe normalizar para ponto", "do not normalise to a decimal point" in low, True)
check("proibe remover separador de milhar", "do not remove thousands separators" in low, True)
check("traz o caso medido como evidencia", "22.944,02" in low, True)
# A instrucao antiga dizia o oposto; se voltar, as duas se contradizem e o
# modelo obedece a que quiser.
check("instrucao antiga nao voltou", "plain digits with a period" in low, False)
check("'as a number' nao sobrou na regra 4", "as a number, when the" in low, False)
# Excecao unica: o unit_price derivado nunca foi impresso, entao nao ha o que
# copiar. Sem esta frase a regra 3 e a 6 se contradizem.
check("excecao do unit_price derivado dita", "one exception" in low, True)

print("=== 8. saida do structurer sai convertida, nunca como impressa ===")
# Este e o defeito que a regra 6 quase introduziu: o modelo passou a devolver
# '6.398,88' e o Decimal() do doc_worker levanta InvalidOperation nesse texto,
# gravando NULL em silencio. A conferencia aritmetica NAO pega, porque ela usa
# _num. Documento salvo vazio sem nota e o modo de falha que o repo combate.
for impresso, esperado in [("6.398,88", "6398.88"), ("1.617,50", "1617.5"),
                           ("29,579.82", "29579.82"), ("22.944,02", "22944.02"),
                           ("52", "52"), ("287.07", "287.07"),
                           ("USD 1.234,50", "1234.5"), (None, None), ("abc", None)]:
    check(f"_snum({impresso!r})", _snum(impresso), esperado)

europeu = {"invoices": [{"invoice_number": "1090257290", "total": "22.944,02",
                         "line_items": [
                             {"part_number": "674-8657", "quantity": "52",
                              "unit_price": "287,07", "amount": "14.927,64"},
                             {"part_number": "463-8344", "quantity": "10",
                              "unit_price": "161,75", "amount": "1.617,50"},
                             {"part_number": "5P-1465", "quantity": "16",
                              "unit_price": "399,93", "amount": "6.398,88"}]}],
           "confidence": 0.95}
saida = _normalise(europeu, 0.95, content="1090257290 674-8657 463-8344 5P-1465")
inv = saida["invoices"][0]
check("total convertido", inv["total"], "22944.02")
check("amounts convertidos", [li["amount"] for li in inv["line_items"]],
      ["14927.64", "1617.5", "6398.88"])
check("unit_prices convertidos", [li["unit_price"] for li in inv["line_items"]],
      ["287.07", "161.75", "399.93"])
# O que o doc_worker faz com a saida: se algum campo nao virar Decimal, ele
# grava NULL calado.
from decimal import Decimal, InvalidOperation
def vira_decimal(v):
    try: return Decimal(str(v)) is not None
    except (InvalidOperation, ValueError): return False
numericos = [inv["total"]] + [li[k] for li in inv["line_items"]
                              for k in ("quantity", "unit_price", "amount")]
check("todos viram Decimal no worker", all(vira_decimal(v) for v in numericos), True)
# A soma tem de continuar fechando com o total impresso -- sem nota de erro.
check("nenhuma nota de total que nao fecha",
      any("nao fecha" in v for v in saida["validation"]), False)

print()
if falhas:
    print(f"{len(falhas)} FALHA(S): {falhas}")
    sys.exit(1)
print("tudo certo")
