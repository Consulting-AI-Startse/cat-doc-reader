r"""Confere o structurer contra o gabarito do cliente, offline.

Precisa de raw-civ-cap.json em Downloads (a ultima extracao do CIV).
Rode da raiz do repo:  & .\function\.venv\Scripts\python.exe .\check_structurer.py
"""
import json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "function"))
from pipeline.structurer import (_ENGINE_RULES, _normalise, _snum, _SYSTEM_PROMPT,
                                 candidate_part_numbers)

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
#  - 'I/C Material' e prosa: nao e item, e sai de line_items (mas e preservada).
#  - '5P-1465' e part number CAT de 2+4: e item, e TEM de sobreviver -- era o
#    que o filtro velho, por sete digitos, apagava.
payload["invoices"][-1]["line_items"].extend([
    {"part_number": "I/C Material", "quantity": "1", "unit_price": "1.00", "amount": "1.00"},
    {"part_number": "5P-1465", "quantity": "2", "unit_price": "10.00", "amount": "20.00"},
])

out = _normalise(payload, 0.9, [], None, content)
lines = [l for i in out["invoices"] for l in i["line_items"]]
descartadas = [d for i in out["invoices"] for d in i["discarded_lines"]]

# INVERSAO DELIBERADA (25/09). Ate aqui a regra era "nenhuma linha descartada",
# e este teste travava isso. O cliente pediu para ignorar item sem part number,
# e o criterio passou a ser a CLASSIFICACAO, nao um regex de sete digitos --
# que era o que apagava part number legitimo. O que nao e codigo sai de
# line_items, mas continua em discarded_lines com o motivo.
print("=== 1. so o que nao e codigo sai, e nada se perde ===")
check("itens na saida", len(lines), 9)
check("linha 'I/C Material' saiu de line_items",
      any(l["part_number"] == "I/C Material" for l in lines), False)
check("mas esta preservada em discarded_lines",
      any(d["part_number"] == "I/C Material" for d in descartadas), True)
# Este continua sendo o teste que importa: part number legitimo de 2+4 nunca
# pode ser descartado. E o caso que derrubou dois dos quatro documentos.
check("linha '5P-1465' sobreviveu",
      any(l["part_number"] == "5P-1465" for l in lines), True)

print("=== 2. status por part number ===")
by_pn = {l["part_number"]: l for l in lines}
check("status de 'I/C Material' no descarte",
      next(d for d in descartadas if d["part_number"] == "I/C Material")["part_number_status"],
      "not_a_code")
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
check("nota de rateio registrada", any("rateados" in v for v in out["notes"]), True)
# A embalagem entra na conferencia: 90 x 388,46 + 603,00 = 35.564,40, que e o
# total impresso. Enquanto ficava de fora, esta fatura acusava "nao fecha".
check("e o total da CD970373103 fecha",
      any("nao fecha" in v and "CD970373103" in v for v in out["validation"]), False)

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

print("=== 9. serial: uma linha impressa vira um registro por serial ===")
# Fatura 93872204, de motor: QTY 7 de 6522586 e sete seriais numa tabela
# 'Part Number | Serial Number'. Os seriais NAO sao consecutivos (pula 68-70 e
# 72-78), entao completar a sequencia seria inventar dado.
SERIAIS = ["XWE42867", "XWE42871", "XWE42879", "XWE42880",
           "XWE42881", "XWE42882", "XWE42883"]
motor = {"invoices": [{
    "invoice_number": "AE28 519364", "supplier": "Caterpillar, Inc.",
    "total": "124894.80", "packaging_cost": "608.82",
    "line_items": [{"part_number": "6522586", "quantity": "7",
                    "unit_price": "17755.14", "amount": "124285.98",
                    "serial_numbers": SERIAIS}]}], "confidence": 0.95}
saida = _normalise(motor, 0.95, content="6522586", exigem_serial={"6522586"})
linhas = saida["invoices"][0]["line_items"]
check("7 registros, um por serial", len(linhas), 7)
check("todos com o mesmo part number", {l["part_number"] for l in linhas}, {"6522586"})
check("os sete seriais, na ordem lida", [l["serial_number"] for l in linhas], SERIAIS)
check("quantidade 1 em cada", {l["quantity"] for l in linhas}, {"1"})
check("amount = unit_price", {l["amount"] for l in linhas}, {"17755.14"})
# A expansao nao pode quebrar a conferencia aritmetica: 7 x 17755.14 continua
# fechando com o total impresso. Sem quantidade 1 daria 7x e TODA fatura de
# motor entraria em needs_review com erro falso.
check("total impresso preservado", saida["invoices"][0]["total"], "124894.80")
check("nenhuma nota de total que nao fecha",
      any("nao fecha" in v for v in saida["validation"]), False)

print("=== 9b. serial: o que falta vira nota, nunca invencao ===")
faltando = {"invoices": [{"invoice_number": "X", "total": "35510.28",
    "line_items": [{"part_number": "6522586", "quantity": "7",
                    "unit_price": "17755.14", "amount": "35510.28",
                    "serial_numbers": ["XWE42867", "XWE42871"]}]}], "confidence": 0.95}
r = _normalise(faltando, 0.95, content="6522586", exigem_serial={"6522586"})
check("expande no que foi lido, nao na quantidade", len(r["invoices"][0]["line_items"]), 2)
check("e avisa a divergencia",
      any("2 serial(is) lido(s)" in v for v in r["validation"]), True)

semnada = {"invoices": [{"invoice_number": "X", "total": "17755.14",
    "line_items": [{"part_number": "6522586", "quantity": "1",
                    "unit_price": "17755.14", "amount": "17755.14"}]}], "confidence": 0.95}
r = _normalise(semnada, 0.95, content="6522586", exigem_serial={"6522586"})
check("motor sem serial mantem a linha", len(r["invoices"][0]["line_items"]), 1)
check("e avisa que falta", any("exige serial number" in v for v in r["validation"]), True)
check("serial fica nulo", r["invoices"][0]["line_items"][0]["serial_number"], None)

print("=== 9c. quem nao exige serial nao e cobrado ===")
r = _normalise(semnada, 0.95, content="6522586", exigem_serial=set())
check("sem aviso quando a peca nao exige",
      any("exige serial number" in v for v in r["validation"]), False)

print("=== 9d. serial fora do padrao dos irmaos vira nota ===")
misto = {"invoices": [{"invoice_number": "X", "total": "2.00",
    "line_items": [{"part_number": "6522586", "quantity": "2",
                    "unit_price": "1.00", "amount": "2.00",
                    "serial_numbers": ["XWE42867", "1234"]}]}], "confidence": 0.95}
r = _normalise(misto, 0.95, content="6522586", exigem_serial={"6522586"})
check("formatos diferentes sao sinalizados",
      any("formatos diferentes" in v for v in r["validation"]), True)

print("=== 9e. o prompt de motor so entra quando ha motor ===")
low = re.sub(r"\s+", " ", _ENGINE_RULES.lower())
check("pede a lista de seriais", '"serial_numbers"' in low, True)
check("proibe inventar para fechar a quantidade", "do not invent a serial" in low, True)
check("proibe o modelo expandir sozinho", "do not split the line yourself" in low, True)
check("traz o caso medido", "xwe42867" in low, True)
check("nao esta no prompt padrao", "serial_numbers" in _SYSTEM_PROMPT.replace(
    '"manufacturer", "serial_numbers"', ""), False)

print("=== 9f. a pre-varredura acha o part number no texto cru ===")
check("acha o motor", "6522586" in candidate_part_numbers("QTY 7 6522586 CAPTIVE"),  True)
check("aceita a forma com hifen", "463-8344" in candidate_part_numbers("item 463-8344 x2"), True)
check("descarta prosa", candidate_part_numbers("nenhum codigo aqui"), [])

print("=== 10. gate: linha sem part number sai de line_items, mas nao some ===")
# A nota 'END USE' da fatura 93872204 vinha como item, com o preco do motor, e
# estourava o total. Removida ANTES da soma, o total fecha com o impresso.
com_lixo = {"invoices": [{"invoice_number": "AE28 519364", "total": "124894.80",
    "packaging_cost": "608.82", "line_items": [
        {"part_number": "6522586", "quantity": "7", "unit_price": "17755.14",
         "amount": "124285.98"},
        {"part_number": "I/C Material 0V3456", "description": "END USE: CAPTIVE ENGINE",
         "quantity": "1", "unit_price": "17755.14", "amount": "17755.14"}]}],
    "confidence": 0.95}
r = _normalise(com_lixo, 0.95, content="6522586")
inv = r["invoices"][0]
check("so o item real fica", [l["part_number"] for l in inv["line_items"]], ["6522586"])
check("a linha descartada e preservada", len(inv["discarded_lines"]), 1)
check("com o motivo junto",
      "nao tem forma de codigo" in (inv["discarded_lines"][0]["discard_reason"] or ""), True)
check("o descarte e anunciado como NOTA",
      any("sem part number descartada" in v for v in r["notes"]), True)
# Descarte nao e defeito: se estiver errado, quem acusa e a aritmetica. Tratar
# como defeito mandaria toda CIV de motor para revisao, porque todas trazem a
# nota 'END USE'.
check("e nao como problema", r["validation"], [])
# O ganho do descarte ANTES da soma: sem a linha fantasma, a aritmetica fecha.
check("a soma passa a fechar com o impresso",
      any("nao fecha" in v for v in r["validation"]), False)

print("=== 10b. campo vazio tambem sai ===")
vazio = {"invoices": [{"invoice_number": "X", "total": "10.00", "line_items": [
    {"part_number": "463-8344", "quantity": "1", "unit_price": "10.00", "amount": "10.00"},
    {"part_number": "", "description": "linha em branco"}]}], "confidence": 0.95}
r = _normalise(vazio, 0.95, content="463-8344")
check("uma linha fica", len(r["invoices"][0]["line_items"]), 1)
check("uma sai", len(r["invoices"][0]["discarded_lines"]), 1)

print("=== 10c. codigo de fornecedor NAO e descartado ===")
# '15.1301.466' e codigo de fornecedor italiano: nunca estara na PN Liberados
# e e item real. Derrubar por "nao esta na lista" apagaria metade do corpus.
fornecedor = {"invoices": [{"invoice_number": "739 /01", "total": "20.00", "line_items": [
    {"part_number": "15.1301.466", "quantity": "1", "unit_price": "20.00", "amount": "20.00"}]}],
    "confidence": 0.95}
r = _normalise(fornecedor, 0.95, content="15.1301.466")
check("other_code sobrevive", len(r["invoices"][0]["line_items"]), 1)
check("e nao foi descartado", len(r["invoices"][0]["discarded_lines"]), 0)

print("=== 10d. o cao de guarda: descarte errado quebra a soma ===")
# Se o filtro derrubar uma linha legitima, a soma para de fechar e o documento
# vai para revisao sozinho. E o que torna o filtro auditavel em vez de cego.
frete = {"invoices": [{"invoice_number": "X", "total": "110.00", "line_items": [
    {"part_number": "463-8344", "quantity": "1", "unit_price": "100.00", "amount": "100.00"},
    {"part_number": None, "description": "FRETE", "amount": "10.00"}]}], "confidence": 0.95}
r = _normalise(frete, 0.95, content="463-8344")
check("a linha sem codigo saiu", len(r["invoices"][0]["discarded_lines"]), 1)
check("e a aritmetica acusa", any("nao fecha" in v for v in r["validation"]), True)

print("=== 11. nota nao derruba o documento para revisao ===")
# Enquanto tudo caia em 'validation', uma fatura lida sem um unico erro ia para
# needs_review so por ter embalagem cobrada -- o rateio virava "defeito".
limpa = {"invoices": [{"invoice_number": "CD970373103", "total": "35564.40",
    "packaging_cost": "603.00", "line_items": [
        {"part_number": "663-7238", "quantity": "90", "unit_price": "388.46",
         "amount": "34961.40"}]}], "confidence": 0.95}
r = _normalise(limpa, 0.95, content="663-7238 6637238")
check("nenhum problema", r["validation"], [])
check("mas o rateio fica registrado",
      any("rateados" in n for n in r["notes"]), True)
check("confianca intacta", r["confidence"], 0.95)

print("=== 11b. defeito de verdade continua derrubando ===")
quebrada = {"invoices": [{"invoice_number": "X", "total": "999.00", "line_items": [
    {"part_number": "463-8344", "quantity": "1", "unit_price": "10.00", "amount": "10.00"}]}],
    "confidence": 0.95}
r = _normalise(quebrada, 0.95, content="463-8344")
check("total que nao fecha e problema",
      any("nao fecha" in v for v in r["validation"]), True)
check("e derruba a confianca", r["confidence"], 0.50)

print()
if falhas:
    print(f"{len(falhas)} FALHA(S): {falhas}")
    sys.exit(1)
print("tudo certo")
