"""Confere _num, PART_NUMBER_RE e a chave de duplicata contra o corpus real.

Rode de dentro de function\\:  & $PY ..\\check_rules.py
"""
import sys, os
# O console do Windows com saida em pipe usa cp1252, e o teste imprime o
# fornecedor turco (DOKTAS com cedilha): o print estourava UnicodeEncodeError
# na VM da CAT, com a logica certa. O CI e Linux e nunca viu isso.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "function"))
sys.path.insert(0, os.getcwd())

from pipeline.structurer import (_num, _invoice_supplier, PART_NUMBER_RE,
                                 _charge_kind, _derive_line_numbers)
from shared.landed import apportion
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

print("=== _num: um separador so, sem zero a esquerda no milhar (leva 14) ===")
# Freudenberg: o modelo derivou '0.162' de '1,62 / 10' e a regra antiga leu
# 162. A Graziano imprime '5700,000', que a regra antiga lia como 5.700.000.
for s, e in [("0.162", 0.162), ("0,162", 0.162), ("1234.567", 1234.567),
             ("5700,000", 5700.0), ("12.345", 12345.0), ("1.234.567", 1234567.0),
             ("1,234", 1234.0), ("12,345,678", 12345678.0), ("0,5", 0.5)]:
    check(s, _num(s), e)

print("=== _derive_line_numbers: o amount impresso e a ancora ===")
for label, args, esperado in [
    ("CIV 3YNDJ: valor no unitario", (2.0, 36826.0, 36826.0), (18413.0, 36826.0, "unit_price")),
    ("preco por 10 (Freudenberg)", (5.0, 1.62, 0.81), (0.162, 0.81, "unit_price")),
    ("preco por 100", (4.0, 250.0, 10.0), (2.5, 10.0, "unit_price")),
    ("amount ausente", (3.0, 2.5, None), (2.5, 7.5, "amount")),
    ("unit_price ausente", (4.0, None, 10.0), (2.5, 10.0, "unit_price")),
    ("conta certa nao muda", (2.0, 5.0, 10.0), (5.0, 10.0, None)),
    ("quantidade 1 nao tem o que derivar", (1.0, 7.0, 9.0), (7.0, 9.0, None)),
    ("quantidade zero", (0.0, 7.0, 9.0), (7.0, 9.0, None)),
    ("quantidade ausente", (None, 7.0, 9.0), (7.0, 9.0, None)),
    ("erro sem padrao fica como veio", (3.0, 7.0, 50.0), (7.0, 50.0, None)),
]:
    u, a, campo, _ = _derive_line_numbers(*args)
    check(label, (u, a, campo), esperado)

print("=== _charge_kind: encargo x peca ===")
for label, li, status, esperado in [
    ("_PackagingSale", {"part_number": "_PackagingSale"}, "not_a_code", "packaging_cost"),
    ("I/C freight & ship", {"part_number": None, "description": "I/C freight & ship"}, "missing", "freight"),
    ("Logistic Charges", {"part_number": "Logistic Charges 1"}, "not_a_code", "freight"),
    ("CAIXA DE MADEIRA", {"part_number": "x", "description": "CAIXA DE MADEIRA"}, "not_a_code", "packaging_cost"),
    ("codigo PACKAGING", {"part_number": "PACKAGING"}, "other_code", "packaging_cost"),
    # peca: codigo de fornecedor nao vira encargo pela descricao
    ("15.1301.466 PACKING RING", {"part_number": "15.1301.466", "description": "PALLET RING"}, "other_code", None),
    ("PACKING RING sem codigo", {"part_number": None, "description": "PACKING RING"}, "missing", None),
    ("part number CAT nunca", {"part_number": "463-8344", "description": "FREIGHT"}, "cat", None),
    ("prosa qualquer", {"part_number": "I/C Material"}, "not_a_code", None),
]:
    check(label, _charge_kind(li, status), esperado)

print("=== apportion: so linha com preco entra no divisor ===")
pu, vals = apportion([(90, 388.46)], 603.0)
check("gabarito CD970373103", vals, [("395.16", "35564.40")])
pu, vals = apportion([(1, 18413.0), (1, 18413.0), (1, None)], 161.99)
check("3YNDJ: por 2, nao 3", round(pu, 4), 80.995)
check("linha sem preco nao recebe", vals[2], None)
check("sem encargo nada e rateado", apportion([(1, 10.0)], 0), (None, [None]))
check("quantidade zero fora", apportion([(0, 10.0), (2, 5.0)], 4.0)[1], [None, ("7", "14.00")])
# 4 casas no unitario, como o unit_price: com 2, 0,162 + 0,2 virava 0,36.
check("peca de centavos", apportion([(5, 0.162)], 1.0)[1], [("0.362", "1.81")])
check("Decimal tambem (backend)", apportion([(__import__("decimal").Decimal("2"),
      __import__("decimal").Decimal("5"))], __import__("decimal").Decimal("1"))[1], [("5.5", "11.00")])

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

# --- confianca por campo (function/pipeline/confidence.py) -------------------
# Texto e palavras sinteticos, montados a partir dos casos do CIV: roda no CI,
# que nao tem o raw-civ-cap.json. A regressao com o CIV inteiro fica no
# check_structurer.py.
from pipeline import confidence as fc
from pipeline.structurer import _normalise
from shared.confidence import summarise


def palavras(texto, notas=None):
    """Indice (offset, length, confidence) de cada palavra; 0.99 por padrao."""
    import re as _re
    notas = notas or {}
    return [(m.start(), m.end() - m.start(), notas.get(m.group(), 0.99))
            for m in _re.finditer(r"\S+", texto)]


print("=== confianca: a PIOR ocorrencia decide ===")
# Rodada de 10/09: '26-2100870' aparece duas vezes e so uma esta a 0.573. Pela
# melhor ocorrencia, o defeito sumia.
txt = "NUMBER 26-2100870 DATE 22/07 ... Invoice Nr. 26-2100870 Total"
idx = fc.WordIndex(palavras(txt))
idx_ruim = fc.WordIndex([w if w[0] != txt.index("26-2100870") else (w[0], w[1], 0.573)
                         for w in palavras(txt)])
check("duas ocorrencias limpas", fc.score_identifier("26-2100870", txt, idx)["status"], "ok")
e = fc.score_identifier("26-2100870", txt, idx_ruim)
check("uma ruim: status", e["status"], "low")
check("uma ruim: nota", e["score"], 0.573)

print("=== confianca: gemeo confundivel ===")
# Rodada de 01/10: o modelo copiou '26-2I00870', lido com confianca ALTA numa
# pagina; '26-2100870' esta impresso em outra. So o gemeo acusa.
txt = "Commercial Invoice Nr. 26-2I00870 ... NUMERO/ NUMBER 26-2100870"
e = fc.score_identifier("26-2I00870", txt, fc.WordIndex(palavras(txt)))
check("I x 1: ambigua", e["status"], "ambiguous")
check("I x 1: aponta o gemeo", e.get("twin"), "26-2100870")
check("I x 1: nota abaixo do limite", e["score"] < fc.LOW_CONFIDENCE, True)
txt = "Ref. enc .: QIPPO1280 ... Purchase Order Nr, QIPP01280"
check("O x 0: ambigua", fc.score_identifier("QIPP01280", txt, fc.WordIndex(palavras(txt)))["status"],
      "ambiguous")
txt = "PO QIPP99551 PO QIPP99551"
check("sem gemeo: ok", fc.score_identifier("QIPP99551", txt, fc.WordIndex(palavras(txt)))["status"],
      "ok")

print("=== confianca: fronteira e nao localizado ===")
txt = "Part Nr. 561-7001X ... 9561-7001"
check("nao casa dentro de outro codigo",
      fc.score_identifier("561-7001", txt, fc.WordIndex(palavras(txt)))["status"], "not_located")
check("PN nas duas formas", fc.anchors_of("4638344", "item 463-8344 x") != [], True)

print("=== confianca: numero procurado como impresso, perto do part number ===")
linha = "561-7001 HYDR PUMP 128 108,53 13.891,84"
longe = "x" * 2000 + " 90 "
txt = linha + longe
idx = fc.WordIndex(palavras(txt))
check("impresso europeu acha", fc.score_number("13.891,84", 13891.84, txt, idx,
                                               fc.anchors_of("561-7001", txt))["status"], "ok")
check("convertido acha pela variante", fc.score_number(None, 13891.84, txt, idx,
                                                       fc.anchors_of("561-7001", txt))["status"], "ok")
# '90' existe no texto, mas a 2000 caracteres do part number: fora da janela.
check("fora da janela nao conta", fc.score_number("90", 90.0, txt, idx,
                                                  fc.anchors_of("561-7001", txt))["status"], "not_located")
check("'50' nao casa em '1.050'", fc.score_number("50", 50.0, "PN 1.050,00", fc.WordIndex([]), [0])["status"],
      "not_located")
check("tres casas italianas", "114,000" in fc.number_forms(None, 114.0), True)

print("=== confianca: o structurer pontua, e campo marcado SEMPRE deixa nota ===")
txt = "Invoice 26-2I00870 ... NUMBER 26-2100870 ... 364-9717 30 282,36 8.470,80 QIPP99551 Total 8.470,80"
payload = {"invoices": [{"invoice_number": "26-2I00870", "total": "8.470,80", "line_items": [
    {"part_number": "364-9717", "quantity": "30", "unit_price": "282,36", "amount": "8.470,80",
     "purchase_order": "QIPP99551"}]}], "confidence": 0.99}
r = _normalise(payload, None, [], None, txt, set(), palavras(txt))
inv = r["invoices"][0]
check("cabecalho pontuado", sorted(inv["field_confidence"]), ["invoice_number", "total"])
check("linha pontuada", sorted(inv["line_items"][0]["field_confidence"]),
      ["amount", "part_number", "purchase_order", "quantity", "unit_price"])
check("a ambigua vira nota", any("26-2I00870" in v and "ambigua" in v for v in r["validation"]), True)
check("confianca vem dos campos", r["confidence_source"], "fields")
# 0.99 do modelo nao salva: quem decide e o pior campo.
check("e o modelo nao decide", r["confidence"] < fc.LOW_CONFIDENCE, True)
check("a do modelo fica para auditoria", r["model_confidence"], 0.99)
sem = _normalise(payload, None, [], None, txt, set())
check("sem indice: nada muda", (sem["confidence_source"], sem["invoices"][0]["field_confidence"]),
      ("model", None))

print("=== confianca: registro expandido por serial ===")
txt = "6522586 7 17.755,14 124.285,98 XWE42867 XWE42871"
payload = {"invoices": [{"invoice_number": "X", "total": "35510.28", "line_items": [
    {"part_number": "6522586", "quantity": "2", "unit_price": "17.755,14", "amount": "35.510,28",
     "serial_numbers": ["XWE42867", "XWE42871"]}]}], "confidence": 0.99}
r = _normalise(payload, None, [], None, txt, {"6522586"}, palavras(txt))
reg = r["invoices"][0]["line_items"][0]["field_confidence"]
check("quantidade 1 e calculada", reg["quantity"]["status"], "derived")
check("amount = unit_price e calculado", reg["amount"]["status"], "derived")
check("o serial tem nota propria", reg["serial_number"]["status"], "ok")

print("=== summarise: agregados da invoice ===")
s = summarise({"invoice_number": {"score": 0.5, "status": "ambiguous"}},
              [{"quantity": {"score": 0.97, "status": "ok"},
                "amount": {"score": None, "status": "derived"}},
               {"purchase_order": {"score": 0.41, "status": "corrected", "was": "low"}}])
check("minima", s["min_field_confidence"], 0.5)
check("media", s["mean_field_confidence"], 0.735)
check("marcados", s["flagged_fields"], 1)
# Corrigido sai da minima e da media -- o valor e do revisor --, mas conta.
check("corrigidos", s["corrected_fields"], 1)
check("sem nota nenhuma", summarise(None, [None]),
      {"min_field_confidence": None, "mean_field_confidence": None,
       "flagged_fields": 0, "corrected_fields": 0})

print("=== relatorio por fornecedor ===")
from shared.confidence import field_breakdown, supplier_report


def fatura(key, nome, quando, media, minima, marcados=0, header=None, linhas=None,
           status="needs_review"):
    return {"supplier_key": key, "supplier": nome, "created_at": quando,
            "document_id": "doc-" + quando, "document_status": status,
            "mean_field_confidence": media, "min_field_confidence": minima,
            "flagged_fields": marcados, "header_fc": header, "lines_fc": linhas or []}


ok = {"score": 0.99, "status": "ok"}
cattini = [
    fatura("CATTINIFIGLIO", "CATTINI e FIGLIO S.P.A.", "2026-09-10", 0.90, 0.50, 1,
           {"invoice_number": {"score": 0.5, "status": "ambiguous", "twin": "26-2I00870"},
            "total": ok}, [{"quantity": ok, "amount": {"score": None, "status": "derived"}}]),
    fatura("CATTINIFIGLIO", "CATTINI E FIGLIO SPA", "2026-10-01", 0.98, 0.97, 0,
           {"invoice_number": {"score": 0.5, "status": "corrected", "was": "ambiguous"},
            "total": ok}, [{"quantity": ok}], status="approved"),
]
bosch = [fatura("BOSCHREXROTHDSI", "Bosch Rexroth DSI S.A.S.", "2026-10-01", 0.99, 0.99, 0,
                {"invoice_number": ok}, [{"quantity": ok}])]
# Gravada antes da 0007, ou no modo local: conta como invoice, nao como nota.
antiga = [fatura("TECNORD", "TECNORD s.r.l.", "2026-09-01", None, None)]
rel = supplier_report(cattini + bosch + antiga)
por = {l["supplier_key"]: l for l in rel}
check("o pior fornecedor primeiro", [l["supplier_key"] for l in rel],
      ["CATTINIFIGLIO", "BOSCHREXROTHDSI", "TECNORD"])
check("nome exibido e o mais recente", por["CATTINIFIGLIO"]["supplier"], "CATTINI E FIGLIO SPA")
check("media das medias", por["CATTINIFIGLIO"]["mean_confidence"], 0.94)
check("pior minima", por["CATTINIFIGLIO"]["min_confidence"], 0.5)
check("invoices com campo a conferir", por["CATTINIFIGLIO"]["flagged_invoices"], 1)
# 'derived' nao foi lido: nao conta como pontuado. Sao 3 + 3 campos lidos.
check("campos pontuados", por["CATTINIFIGLIO"]["fields_scored"], 6)
check("taxa de correcao", por["CATTINIFIGLIO"]["correction_rate"], round(1 / 6, 4))
check("metade em revisao", por["CATTINIFIGLIO"]["review_rate"], 0.5)
check("campo mais fraco", por["CATTINIFIGLIO"]["weakest_field"], "invoice_number")
check("sem nota: conta a invoice", (por["TECNORD"]["invoices"], por["TECNORD"]["invoices_scored"]),
      (1, 0))
check("sem nota: sem media", por["TECNORD"]["mean_confidence"], None)
campos = {c["field"]: c for c in field_breakdown(cattini)}
check("invoice_number: 1 ambigua, 1 corrigida",
      (campos["invoice_number"]["ambiguous"], campos["invoice_number"]["corrected"]), (1, 1))
# A nota do corrigido nao fala mais do valor gravado: fica fora da media.
check("corrigido fora da media", campos["invoice_number"]["mean_score"], 0.5)

# --- texto fora do alfabeto latino (escopo decidido em 08/10) ----------------
from pipeline.structurer import _latin_only

print("=== _latin_only: o que fica e o que sai ===")
check("chines sai, latino fica", _latin_only("发动机 / ENGINE AR-COMPL"), ("ENGINE AR-COMPL", True))
check("so chines vira None", _latin_only("上海卡特彼勒"), (None, True))
check("cirilico tambem sai", _latin_only("ДВИГАТЕЛЬ ENGINE"), ("ENGINE", True))
# Fornecedores do corpus: acento latino nao e alfabeto estrangeiro.
check("turco fica intacto", _latin_only("DOKTAŞ DÖKÜMCÜLÜK TİC."), ("DOKTAŞ DÖKÜMCÜLÜK TİC.", False))
check("moeda e simbolo ficam", _latin_only("€ 1.234,50 №5 × 2"), ("€ 1.234,50 №5 × 2", False))
check("largura cheia vira ASCII", _latin_only("ＰＮ６５１１３０８"), ("PN6511308", False))
check("sinal sobrevive ao aparo", _latin_only("金额 -1.234,50"), ("-1.234,50", True))
check("sem remocao, sem aparo", _latin_only(" 1 PALLET / "), (" 1 PALLET / ", False))

print("=== _normalise: o filtro chega no que e gravado ===")
payload = {"invoices": [{"invoice_number": "INV-88", "invoice_number_source": "发票号码",
                         "total": "100.00", "line_items": [
    {"part_number": "651-1308", "description": "发动机 ENGINE", "quantity": "1",
     "unit_price": "100.00", "amount": "100.00", "supplier": "上海卡特彼勒"}]}],
           "confidence": 0.99}
r = _normalise(payload, None, [], None, "", set())
li = r["invoices"][0]["line_items"][0]
check("descricao sem chines", li["description"], "ENGINE")
check("supplier so em chines: nulo", li["supplier"], None)
check("parcial vira nota", any("removido de 2 campo" in n for n in r["notes"]), True)
# O rotulo vai para a nota, nao para a revisao: e de onde o numero veio.
check("vazio vira problema", [v for v in r["validation"] if "alfabeto" in v],
      ["campo(s) escrito(s) so fora do alfabeto latino, gravado(s) vazio(s): "
       "invoices[0].line_items[0].supplier"])
limpo = _normalise({"invoices": [{"invoice_number": "INV-88", "total": "100.00", "line_items": [
    {"part_number": "651-1308", "description": "ENGINE", "quantity": "1",
     "unit_price": "100.00", "amount": "100.00", "supplier": "CAT"}]}]}, None, [], None, "", set())
check("documento latino: sem nota", [n for n in limpo["notes"] if "alfabeto" in n], [])
vazio = _normalise({"confidence": 0.9}, None, [], None, "", set())
check("payload sem invoices: chaves intactas",
      any("chaves recebidas: ['confidence']" in v for v in vazio["validation"]), True)


# --- unit e unit_weight (migracao 0008) --------------------------------------
from pipeline.structurer import _unit_weight

print("=== _unit_weight: o modelo copia, o codigo divide e converte ===")
check("unitario em KG", _unit_weight("t", {"unit_weight": "19,81", "weight_uom": "KG"}),
      ("19.81000", None))
check("da linha / quantidade", _unit_weight("t", {"line_weight": "594,30", "quantity": "30",
                                                  "weight_uom": "kg"}), ("19.81000", None))
check("LB vira kg", _unit_weight("t", {"unit_weight": "10", "weight_uom": "LBS."}),
      ("4.53592", None))
check("sem peso: nada", _unit_weight("t", {"unit": "PCS"}), (None, None))
peso, nota = _unit_weight("t", {"unit_weight": "2.5"})
check("sem unidade: KG com nota", (peso, "assumido KG" in (nota or "")), ("2.50000", True))
peso, nota = _unit_weight("t", {"unit_weight": "2.5", "weight_uom": "TON"})
check("unidade desconhecida: nulo", (peso, "desconhecida" in (nota or "")), (None, True))
peso, nota = _unit_weight("t", {"line_weight": "50", "weight_uom": "KG"})
check("linha sem quantidade: nulo", (peso, "sem quantidade" in (nota or "")), (None, True))

print("=== unit_weight: calculado antes da expansao por serial ===")
# O registro expandido tem quantidade 1: dividir o peso da linha por ele daria
# o peso das 7 unidades em cada registro.
payload = {"invoices": [{"invoice_number": "93872204", "total": "35510.28", "line_items": [
    {"part_number": "6522586", "quantity": "2", "unit_price": "17755.14", "amount": "35510.28",
     "unit": "EA", "line_weight": "1700", "weight_uom": "KG",
     "serial_numbers": ["XWE42867", "XWE42871"]}]}], "confidence": 0.99}
r = _normalise(payload, None, [], None, "", {"6522586"})
regs = r["invoices"][0]["line_items"]
check("dois registros", len(regs), 2)
check("cada um com o peso de UM motor", [x["unit_weight"] for x in regs], ["850.00000"] * 2)
check("unidade emitida", regs[0]["unit"], "EA")


# --- classificacao de paginas: invoice x packing list -------------------------
from pipeline.pages import classify_pages, page_spans, only_in_pages

PB = "<!-- PageBreak -->"
FATURA_1 = "INVOICE No. 9028078388\nPart Number Qty Unit Price Amount\n463-8344 2 10.00 USD 20.00\n"
FATURA_2 = "Page 2\n5P-1465 1 5.00 5.00\nTOTAL AMOUNT USD 25.00\n"
PACKING = "PACKING LIST\nInvoice No. 9028078388\nPart Number Qty Net Weight Gross Weight\n463-8344 2 1.5 KG 2.0 KG\n674-8657 4 CARTON\n"
DOC = FATURA_1 + PB + FATURA_2 + PB + PACKING

print("=== page_spans: os marcadores viram paginas, e o content nao e reescrito ===")
spans = page_spans(DOC)
check("tres paginas", [s["page_number"] for s in spans], [1, 2, 3])
check("cobrem o content inteiro", (spans[0]["start"], spans[-1]["end"]), (0, len(DOC)))
check("sem sobreposicao", all(a["end"] == b["start"] for a, b in zip(spans, spans[1:])), True)
check("pagina 3 e a de packing", "PACKING LIST" in DOC[spans[2]["start"]:spans[2]["end"]], True)
check("sem marcador: uma pagina", len(page_spans("so texto")), 1)

print("=== classify_pages: titulo decide, preco desmente, moeda solta nao ===")
k = classify_pages(DOC, 3)
check("packing list na pagina 3", k["packing_list_pages"], [3])
check("fatura nas paginas 1 e 2", k["invoice_pages"], [1, 2])
check("nenhuma mista", k["mixed_pages"], [])
check("contagem bate com o OCR", k["page_count_mismatch"], False)
check("divergencia de contagem e sinalizada", classify_pages(DOC, 5)["page_count_mismatch"], True)
# 'Invoice No.' no packing list nao o torna fatura: INVOICE pesa zero.
check("'Invoice No.' nao vira fatura", classify_pages(PACKING)["pages"][0]["kind"], "packing_list")
# O rodape legal da Dana imprime 'Cap. Soc. € 60.000.000' na pagina do packing list.
check("moeda no rodape nao desmente o titulo",
      classify_pages("PACKING LIST\nPALLETS 2\nCap. Soc. € 60.000,00")["pages"][0]["kind"], "packing_list")
check("titulo E rotulo de preco: mista",
      classify_pages("PACKING LIST\n463-8344 UNIT PRICE 10.00")["pages"][0]["kind"], "mixed")
# Fatura italiana imprime peso na propria fatura (TECNORD: 'Netto' 5x) e cita a
# DDT como referencia. Nenhum dos dois a torna packing list.
check("peso na fatura continua fatura",
      classify_pages("Prezzo 10,00 Netto 2,0 Netto 3,0 DDT n. 2603712 Importo 20,00")["pages"][0]["kind"],
      "invoice")
check("nota de entrega sem preco e embarque",
      classify_pages("DOCUMENTO DI TRASPORTO n. 2603712\n463-8344 2 pz")["pages"][0]["kind"], "packing_list")
check("loadlist tambem", classify_pages("Loadlist 409539 Dimensions 120X80")["pages"][0]["kind"], "packing_list")
check("duas marcas de peso sem titulo: embarque",
      classify_pages("Net Weight 167,00 Gross Weight 180,00")["pages"][0]["kind"], "packing_list")
check("uma marca so: nada", classify_pages("GROSS WEIGHT 1.200")["pages"][0]["kind"], "unknown")
check("pagina vazia: nada", classify_pages("")["pages"][0]["kind"], "unknown")

print("=== only_in_pages: so acusa o que existe exclusivamente no packing list ===")
pags = k["pages"]
check("674-8657 so na pagina 3", only_in_pages("674-8657", DOC, pags), True)
check("463-8344 esta na 1 e na 3", only_in_pages("463-8344", DOC, pags), False)
check("ausente nao acusa", only_in_pages("999-9999", DOC, pags), False)
check("vazio nao acusa", only_in_pages(None, DOC, pags), False)

print("=== _normalise: nota para o revisor, problema so quando pede humano ===")
linhas = [{"part_number": "463-8344", "quantity": "2", "unit_price": "10.00", "amount": "20.00"},
          {"part_number": "5P-1465", "quantity": "1", "unit_price": "5.00", "amount": "5.00"}]
ok = _normalise({"invoices": [{"invoice_number": "9028078388", "total": "25.00",
                               "line_items": linhas}]}, None, [], None, DOC, set(), None, k)
check("packing list vira nota", any("packing list" in n for n in ok["notes"]), True)
check("e nao problema", [v for v in ok["validation"] if "packing" in v], [])
check("page_kinds sai no resultado", [p["kind"] for p in ok["page_kinds"]],
      ["invoice", "invoice", "packing_list"])
check("documento limpo: nenhum problema", ok["validation"], [])
# O modelo desobedeceu a regra 12 e tirou uma linha do packing list.
furada = _normalise({"invoices": [{"invoice_number": "9028078388", "total": "25.00",
                                   "line_items": linhas + [
    {"part_number": "674-8657", "quantity": "4", "unit_price": "1.00", "amount": "4.00"}]}]},
                    None, [], None, DOC, set(), None, k)
check("linha do packing list e acusada",
      [v for v in furada["validation"] if "674-8657" in v and "packing" in v] != [], True)
check("mas nao e descartada", len(furada["invoices"][0]["line_items"]), 3)
# E a rede de seguranca: a linha a mais estoura o total impresso.
check("e a aritmetica confirma", any("nao fecha" in v for v in furada["validation"]), True)
mista = _normalise({"invoices": []}, None, [], None, "", set(), None,
                   classify_pages("PACKING LIST\n463-8344 UNIT PRICE 10.00"))
check("pagina mista pede revisao", any("titulo de packing list E preco" in v for v in mista["validation"]), True)
so_packing = _normalise({"invoices": []}, None, [], None, "", set(), None, classify_pages(PACKING))
check("documento sem fatura e acusado",
      any("nenhuma pagina de fatura" in v for v in so_packing["validation"]), True)
check("contagem divergente e nota, nao problema",
      (any("classificacao de paginas contou" in n for n in
           _normalise({"invoices": []}, None, [], None, DOC, set(), None, classify_pages(DOC, 5))["notes"]),
       any("contou" in v for v in
           _normalise({"invoices": []}, None, [], None, DOC, set(), None, classify_pages(DOC, 5))["validation"])),
      (True, False))
check("sem classificacao: nada muda",
      _normalise({"invoices": []}, None, [], None, "", set())["page_kinds"], [])


print("=== provavelmente nao e invoice: os quatro motivos ===")
from pipeline.pages import has_invoice_title
check("titulo em italiano", has_invoice_title("FATTURA N. 2573"), True)
check("titulo em portugues", has_invoice_title("Fatura Nº 9028078388"), True)
check("sem titulo", has_invoice_title("CERTIFICATE OF ORIGIN"), False)
# 'invoiced' nao e titulo: fronteira de palavra.
check("palavra derivada nao conta", has_invoice_title("to be invoiced later"), False)

CARTA = "Dear Sir,\nPlease find attached the certificate of origin.\nBest regards"
carta = _normalise({"invoices": []}, None, [], None, CARTA, set(), None, classify_pages(CARTA))
check("carta: marcada", carta["not_invoice"]["likely"], True)
check("carta: sem titulo e sem invoice",
      [m.split(" (")[0] for m in carta["not_invoice"]["reasons"]],
      ["nenhuma palavra de titulo de fatura no documento", "o modelo nao achou nenhuma invoice no documento"])
check("carta: vai para revisao", any(v.startswith("provavelmente nao e uma invoice")
                                     for v in carta["validation"]), True)
check("so packing list: marcado com o motivo de embarque",
      "todas as paginas sao packing list / nota de entrega" in so_packing["not_invoice"]["reasons"], True)
check("fatura de verdade: sem marca", ok["not_invoice"], {"likely": False, "reasons": []})
check("sem classificacao de paginas: nunca marca",
      _normalise({"invoices": []}, None, [], None, CARTA, set())["not_invoice"]["likely"], False)

# Campo inventado: com indice de palavras, o que o modelo devolveu e nao existe
# no texto vira 'not_located'. Metade ou mais, com pelo menos 4 campos, marca.
TEXTO = "INVOICE 123\n463-8344 2 10,00 20,00\nTOTAL 20,00"
palavras = [(0, len(TEXTO), 0.99)]
inventada = {"invoices": [{"invoice_number": "999", "total": "77,00", "line_items": [
    {"part_number": "674-8657", "quantity": "5", "unit_price": "3,00", "amount": "15,00"}]}]}
r = _normalise(inventada, None, [], None, TEXTO, set(), palavras, classify_pages(TEXTO))
check("campos inventados: marcado", any("nao existem no texto" in m for m in r["not_invoice"]["reasons"]), True)
lida = {"invoices": [{"invoice_number": "123", "total": "20,00", "line_items": [
    {"part_number": "463-8344", "quantity": "2", "unit_price": "10,00", "amount": "20,00"}]}]}
r = _normalise(lida, None, [], None, TEXTO, set(), palavras, classify_pages(TEXTO))
check("campos lidos: sem marca", r["not_invoice"]["likely"], False)
# Leitura RUIM nao e documento errado: nota baixa, valor presente.
fraca = [(0, len(TEXTO), 0.30)]
r = _normalise(lida, None, [], None, TEXTO, set(), fraca, classify_pages(TEXTO))
check("fatura mal escaneada: revisao, mas sem marca",
      (r["not_invoice"]["likely"], r["confidence"] < 0.85), (False, True))

# --- metricas de processamento por periodo (dashboard) ------------------------
from datetime import datetime, timedelta, timezone
from shared.metrics import processing_report, _percentile

print("=== _percentile: nearest-rank, sem numpy ===")
check("mediana de 4", _percentile([4, 1, 3, 2], 0.5), 2.0)
check("p90 de 10", _percentile(list(range(1, 11)), 0.9), 9.0)
check("um valor so", _percentile([7.0], 0.9), 7.0)
check("vazio", _percentile([], 0.5), None)

T0 = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def doc(status, started=10, done=70, reviewed=False, invoices=None):
    return {"status": status, "created_at": T0,
            "started_at": T0 + timedelta(seconds=started) if started is not None else None,
            "processed_at": T0 + timedelta(seconds=done) if done is not None else None,
            "reviewed": reviewed, "invoices": invoices or []}


fc_ok = {"part_number": {"score": 0.99, "status": "ok"}}
fc_corr = {"part_number": {"score": 0.6, "status": "corrected", "was": "low"}}
inv = lambda amount, dup=False, fc=fc_ok: {"duplicate": dup, "amount": amount,
                                           "header_fc": None, "lines_fc": [fc]}

print("=== processing_report: contagens, taxas e tempos ===")
r = processing_report([
    doc("extracted", invoices=[inv(100.0)]),                       # auto
    doc("approved", invoices=[inv(50.0, fc=fc_corr)]),             # auto (aprovado direto)
    doc("approved", reviewed=True, invoices=[inv(30.0)]),          # passou por revisao
    doc("needs_review", done=130, invoices=[inv(20.0), inv(20.0, dup=True)]),
    doc("rejected", invoices=[inv(999.0)]),                        # leitura descartada
    doc("error", started=10, done=40),                             # erro com fim gravado
    doc("error", started=10, done=None),                           # erro antigo, sem fim
    doc("processing", done=None),
])
check("documentos", r["documentos"], 8)
check("invoices (com a copia)", r["invoices"], 6)
check("duplicatas", r["duplicatas"], 1)
check("nao processados", r["nao_processados"], 1)
check("aguardando revisao", r["aguardando_revisao"], 2)
check("aprovados / rejeitados / erros", (r["aprovados"], r["rejeitados"], r["erros"]), (2, 1, 2))
# Fora: a copia (20), o rejeitado (999) e os erros.
check("valor sem copia nem rejeitado", r["valor_total_extraido"], 200.0)
# Terminados: 5 (o erro e o processing nao). Auto: extracted e approved direto;
# o rejeitado sem revisao NAO e sucesso do agente -- a leitura nao prestou.
check("auto: 2 de 5 terminados", (r["terminados"], r["auto_extracted"], r["auto_rate"], r["review_rate"]),
      (5, 2, 0.4, 0.6))
# 60 s x4 (extracted, approved, approved, rejected), 120 (needs_review), 30 (erro).
check("processamento: n conta so quem terminou", r["processing_seconds"]["n"], 6)
check("mediana do processamento", r["processing_seconds"]["median"], 60.0)
check("p90 do processamento", r["processing_seconds"]["p90"], 120.0)
check("upload ate resultado", (r["turnaround_seconds"]["median"], r["turnaround_seconds"]["n"]), (70.0, 6))
# Pontuados: 4 invoices que contam (100, 50, 30, 20); corrigido: 1.
check("campos corrigidos / pontuados", (r["fields_corrected"], r["fields_scored"]), (1, 4))
check("taxa de correcao", r["fields_corrected_rate"], 0.25)

print("=== processing_report: bordas ===")
vazio = processing_report([])
check("vazio: zeros", (vazio["documentos"], vazio["valor_total_extraido"]), (0, 0.0))
check("vazio: taxas None", (vazio["auto_rate"], vazio["fields_corrected_rate"]), (None, None))
check("vazio: duracao None", (vazio["processing_seconds"]["median"], vazio["processing_seconds"]["n"]), (None, 0))
# processed_at antes do evento: relogio, nao duracao.
atras = processing_report([doc("extracted", started=100, done=50)])
check("delta negativo fica fora", atras["processing_seconds"]["n"], 0)
check("mas o turnaround conta", atras["turnaround_seconds"]["n"], 1)


print("=== serie diaria: um ponto por dia, inclusive o vazio ===")
from shared.metrics import daily_series
D1 = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)   # 12h em Brasilia
D3 = datetime(2026, 10, 14, 1, 30, tzinfo=timezone.utc)   # 13/10 22h30 em Brasilia
def doc_em(quando, status, reviewed=False, not_invoice=False, seg=60):
    return {"status": status, "created_at": quando, "started_at": quando,
            "processed_at": quando + timedelta(seconds=seg), "reviewed": reviewed,
            "not_invoice": not_invoice, "invoices": []}
serie = daily_series([doc_em(D1, "extracted"), doc_em(D1, "needs_review", seg=120),
                      doc_em(D3, "error"), doc_em(D3, "rejected", not_invoice=True)],
                     days=4, today=datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc))
check("quatro dias, com o vazio", [p["date"] for p in serie],
      ["2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14"])
check("dia vazio com zeros", (serie[0]["received"], serie[0]["processing_median"]), (0, None))
check("12/10: um auto, um revisao", (serie[1]["auto"], serie[1]["review"]), (1, 1))
# 22h30 de Brasilia e o dia 13, mesmo sendo 14 em UTC.
check("upload da noite cai no dia certo", serie[2]["received"], 2)
check("13/10: erro e nao-invoice", (serie[2]["error"], serie[2]["not_invoice"]), (1, 1))
check("mediana do dia", serie[1]["processing_median"], 60.0)
check("Tudo: do primeiro upload ate hoje",
      len(daily_series([doc_em(D1, "extracted")], 0,
                       today=datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc))), 3)
check("sem documento e sem hoje: vazio", daily_series([], 0), [])
check("relatorio conta nao-invoice",
      processing_report([doc_em(D1, "rejected", not_invoice=True)])["nao_invoice"], 1)

print()
if falhas:
    print(f"{len(falhas)} FALHA(S): {falhas}")
    sys.exit(1)
print("tudo certo")
