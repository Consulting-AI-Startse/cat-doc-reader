r"""Confere o structurer contra o gabarito do cliente, offline.

Precisa de raw-civ-cap.json em Downloads (a ultima extracao do CIV).
Rode da raiz do repo:  & .\function\.venv\Scripts\python.exe .\check_structurer.py
"""
import json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "function"))
from pipeline.structurer import _normalise, _SYSTEM_PROMPT

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

print()
if falhas:
    print(f"{len(falhas)} FALHA(S): {falhas}")
    sys.exit(1)
print("tudo certo")
