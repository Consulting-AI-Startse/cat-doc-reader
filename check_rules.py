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

print()
if falhas:
    print(f"{len(falhas)} FALHA(S): {falhas}")
    sys.exit(1)
print("tudo certo")
