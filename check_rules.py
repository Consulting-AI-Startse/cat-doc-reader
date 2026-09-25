"""Confere _num, PART_NUMBER_RE e a chave de duplicata contra o corpus real.

Rode de dentro de function\\:  & $PY ..\\check_rules.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "function"))
sys.path.insert(0, os.getcwd())

from pipeline.structurer import _num, _invoice_supplier, PART_NUMBER_RE
from shared.dedupe import normalise_invoice_number, normalise_supplier

falhas = []


def check(label, got, expected):
    ok = (got is None and expected is None) or (
        isinstance(got, float) and expected is not None and abs(got - expected) < 0.005
    ) or got == expected
    print(("  OK   " if ok else "  FALHA") + f" {label:<26} -> {got!r:>14}   esperado {expected!r}")
    if not ok:
        falhas.append(label)


print("=== _num: formato americano (135 ocorrencias no corpus) ===")
for s, e in [("29,579.82", 29579.82), ("119,031.66", 119031.66), ("29,687.90", 29687.90),
             ("4,040.3700", 4040.37), ("27,324.00", 27324.00), ("495,000.0", 495000.0),
             ("108.08", 108.08), ("0.03", 0.03), ("228.60", 228.60)]:
    check(s, _num(s), e)

print("=== _num: formato europeu (44 ocorrencias -- era 1000x errado) ===")
for s, e in [("6.398,88", 6398.88), ("14.927,64", 14927.64), ("1.617,50", 1617.50),
             ("22.944,02", 22944.02), ("76.376,72", 76376.72), ("1.301,54", 1301.54),
             ("399,93", 399.93), ("287,07", 287.07), ("161,75", 161.75)]:
    check(s, _num(s), e)

print("=== _num: bordas ===")
for s, e in [("USD 29,579.82", 29579.82), ("1.234", 1234.0), ("16", 16.0),
             ("-1.234,50", -1234.50), ("(500.00)", -500.0),
             ("", None), ("abc", None), (None, None)]:
    check(repr(s), _num(s), e)

print("=== PART_NUMBER_RE: deve ACEITAR (part numbers reais do corpus) ===")
aceitar = ["1234567", "6511308", "6522586", "652-2586", "463-8344", "674-8657",
           "473-7719", "630-7662", "598-3750", "188-4651", "665-8295",
           "5P-1465", "5P-0179", "7G-5837", "9G-9180"]
for pn in aceitar:
    check(pn, bool(PART_NUMBER_RE.match(pn)), True)

print("=== PART_NUMBER_RE: deve REJEITAR ===")
rejeitar = ["0V3456",            # marcacao de end use, 6 caracteres
            "I/C Material",      # prosa
            "500001092",         # part number do fornecedor, 9 digitos
            "15.1301.466",       # codigo do fornecedor italiano
            "364-9717/01",       # PN com sufixo de revisao
            "93848310",          # numero de documento
            "AE28 518937",       # CAT Invoice#
            "QIPP27001",         # purchase order
            "F4E09020",          # serial / PIN
            "463-83444"]        # digito extra
for pn in rejeitar:
    check(pn, bool(PART_NUMBER_RE.match(pn)), False)

print("=== normalise_supplier: variantes do mesmo fornecedor tem de colidir ===")
# Os seis fornecedores sao os do CIV MRKU6295556; o DOKTAS e o caso que motivou
# a normalizacao (forma juridica turca em quatro pedacos).
for grupo in [
    ["DOKTAS DOKUMCULUK TIC. VE SAN. A.S.", "Doktas Dokumculuk Tic ve San AS",
     "doktas dokumculuk ticaret ve sanayi a.s."],
    ["Groeneveld-BEKA GmbH", "GROENEVELD BEKA GMBH", "Groeneveld  BEKA  gmbh"],
    ["TECNORD s.r.l.", "TECNORD S.R.L", "Tecnord SRL"],
    ["CATTINI e FIGLIO S.P.A.", "Cattini e Figlio SpA"],
    ["Bosch Rexroth DSI S.A.S.", "BOSCH REXROTH DSI SAS"],
    ["Dana Graziano S.r.l.", "DANA GRAZIANO SRL"],
]:
    chaves = {normalise_supplier(v) for v in grupo}
    check(grupo[0][:24], len(chaves), 1)

print("=== normalise_supplier: fornecedores distintos NAO podem colidir ===")
distintos = ["Groeneveld-BEKA GmbH", "TECNORD s.r.l.", "ROTOTECH S.P.A.",
             "CATTINI e FIGLIO S.P.A.", "Bosch Rexroth DSI S.A.S.",
             "Dana Graziano S.r.l.", "DOKTAS DOKUMCULUK TIC. VE SAN. A.S."]
check("7 fornecedores do CIV", len({normalise_supplier(v) for v in distintos}), 7)

print("=== normalise_supplier: bordas ===")
# 'CO' no meio e palavra, no fim e 'company' -- por isso o corte e so no fim.
check("CO no meio", normalise_supplier("CO PRODUCTS LTD"), "COPRODUCTS")
# Nome que e so forma juridica: chave ruim e melhor que chave nenhuma, porque
# None desliga a checagem de duplicata para a fatura inteira.
check("so forma juridica", normalise_supplier("S.A."), "SA")
for v in ["", "   ", "...", None]:
    check(repr(v), normalise_supplier(v), None)

print("=== normalise_invoice_number ===")
for v, e in [("739 /01", "73901"), ("AE28 518937", "AE28518937"),
             ("26-2100870", "262100870"), ("cd970373103", "CD970373103"),
             ("VE 3246", "VE3246"), ("", None), (None, None)]:
    check(repr(v), normalise_invoice_number(v), e)

print("=== _invoice_supplier: fornecedor da fatura sai das linhas ===")
um = [{"supplier": "TECNORD s.r.l."}, {"supplier": "TECNORD s.r.l."}]
check("3 linhas, 1 fornecedor", _invoice_supplier(um), ("TECNORD s.r.l.", None))
check("nenhum fornecedor", _invoice_supplier([{"supplier": None}]), (None, None))
# A premissa "uma invoice, um fornecedor" foi conferida no CIV, mas se quebrar
# tem de virar nota -- e o aviso que manda o documento para revisao.
misto = [{"supplier": "A LTDA"}, {"supplier": "B LTDA"}, {"supplier": "A LTDA"}]
nome, aviso = _invoice_supplier(misto)
check("2 fornecedores: vence o frequente", nome, "A LTDA")
check("2 fornecedores: avisa", aviso is not None, True)

print()
if falhas:
    print(f"{len(falhas)} FALHA(S): {falhas}")
    sys.exit(1)
print("tudo certo")
