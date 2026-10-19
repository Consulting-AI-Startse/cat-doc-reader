# Relatório dos testes da CAT ("TESTES - CAT DOC READER") e plano de correção

Análise do relatório de erros que a CAT mandou em outubro de 2026 (13 slides,
duas etapas de teste: **até 14/09/2026** e **a partir de 02/10/2026**), cruzada
com o código deste repo e com o log de espelhamento (`docs/sync-cat.md`). Para
cada erro: a causa, se já foi corrigido, e o que falta. O plano de levas está no
fim, e os itens novos entraram no `BACKLOG.md` (10, 11 e 12).

Escrito em 19/10/2026. O PDF do cliente não é versionado (artefato do cliente,
ver `CLAUDE.md`); está na máquina do Luis.

## O que estava em produção em cada etapa

Os dois repos têm históricos independentes, então a data de cada leva no
`docs/sync-cat.md` é o que diz qual código a CAT testou:

| etapa de teste | código em produção | o que já existia |
|---|---|---|
| até 14/09 | o `init` de 27/08 — a primeira leva só foi em 21/09 | nada: sem filtro de linha, sem lista de PN, sem confiança por campo, sem serial |
| a partir de 02/10 | leva 11 (merge em 01/10); as levas 12 e 13 só em 14/10 | descarte de linha sem código, serial, confiança do OCR por campo, lista de PN (só para decidir serial), painel "Decisões da extração" |

Os screenshots da etapa 2 mostram "confiança do OCR: mínima 85% · média 98%"
e o painel de linhas removidas, que são da leva 11. Nada nos slides depende
das levas 12 e 13 (packing list, métricas, "provavelmente não é invoice").

## Etapa 1 (até 14/09): o que foi apontado e o estado hoje

| # | slide | causa no `init` | estado hoje |
|---|---|---|---|
| 1.1 | "Campos de valor não fazem validação" (quantidade × unitário × total) | só se conferia soma das linhas = total impresso; a linha não era conferida | **parcial.** Desde a leva 4 o `_check_lines` acusa `qty × unit ≠ amount`, mas só marca: o unitário errado continua gravado e a tela o mostra (ver 2.1) |
| 1.2 | "Confiança: como funciona? maioria mostra 50%" | `REVIEW_CONFIDENCE = 0.50`: qualquer problema de validação forçava a confiança do documento a 0.50, e a tela mostrava esse número como "confiança". Não era medida de nada, era a marca de "tem problema" | **corrigido** na leva 11: a confiança passou a ser medida no OCR, por campo (palavra fraca, gêmeo confundível, valor não localizado), e a tela mostra mínima e média. O 0.50 continua existindo só internamente, para forçar `needs_review` |
| 1.3 | Inv 0094999841: "Logistic Charges 443.02" e "Inland Freight 249.53" não vão para FRETE | o modelo devolve o frete no cabeçalho da invoice (`freight`), mas o worker nunca gravou esse campo. A coluna FRETE da tela é `domestic_freight`, um campo **por linha**, que só é preenchido quando o documento itemiza frete naquela linha | **não corrigido.** Ver 2.3 |
| 1.4 | AutoMotionShade IN260306005: "Packaging - Sales 40 × 2.15 = 86.00" virou item | sem filtro de linha | **parcial.** Hoje a linha sai da tabela (não tem forma de código) e vai para "linhas removidas", mas os 86.00 **somem da conta**: `packaging_cost` fica vazio, a soma deixa de fechar e o documento vai para revisão com a nota errada ("total não fecha") |
| 1.5 | 93847052 (motor): "I/C Material" e "0V3456 END USE" como itens, com o preço do motor | sem filtro de linha | "I/C Material" **corrigido** (leva 5: não é código, sai da tabela). "0V3456" **não**: tem forma de código, é mantido como "código do fornecedor" e continua na tabela, como o slide 9 ainda mostra |
| 1.6 | CIV 3YNDB: `5831412`, quantidade 3, unitário 119031.6 = total | a fatura tem **uma** coluna de preço ("SELLING PRICE", que é o estendido); o modelo copiou o estendido no unitário | **não corrigido.** Mesmo defeito do 2.1 |

## Etapa 2 (a partir de 02/10): o que falta

| # | slide | causa raiz | gravidade |
|---|---|---|---|
| 2.1 | CIV 3YNDJ: `2 × 6522600 = 36.826,00`; a tela mostra 2 registros com unitário 36826 **e** total 36826 cada | (a) o modelo copiou o estendido no unitário; (b) o `_check_lines` acusa ("2.0 x 36826.0 = 73652.00, mas amount = 36826.00") mas não corrige; (c) a expansão por serial cria um registro por serial com `amount = unit_price`, então o banco guarda **73.652** de valor numa linha de 36.826. A conferência do total passa porque soma a linha impressa antes de expandir | alta: valor errado gravado em toda CIV de motor com quantidade maior que 1 |
| 2.2 | mesma CIV: "encargos 161.99 rateados a 53.9967 por unidade" | o rateio divide por 3 unidades, contando a linha 0V3456 (quantidade 1, sem preço). O certo é 161.99 / 2 = 80.995 | média |
| 2.3 | mesma CIV: coluna FRETE vazia; "adicionar validação/divisão no valor e frete" | o structurer já calcula `unit_price_landed` e `amount_landed` (unitário com frete e embalagem rateados) e `freight` / `packaging_cost` da invoice, mas nada disso é gravado nem exibido: morre no `raw_extraction`. O gabarito da CAT (fatura CD970373103) espera **395,16 = 388,46 + 603/90**, ou seja, o cliente quer o unitário com o encargo rateado | alta: é a expectativa do contrato |
| 2.4 | 0V3456 "END USE" continua na tabela (o cliente riscou) | é mantido por desenho: "código do fornecedor" é item real (`15.1301.466` nas faturas italianas) e nunca estará na lista de PN. Mas esta linha **não tem preço nem valor** | média |
| 2.5 | 380_Commercial Invoice (Carraro): part number `148409` em vez de `2396739`; `448034` e `448035` "CAIXA DE MADEIRA" como itens; FABRICANTE vazio; frete 158,30 não aparece | (a) a linha imprime o código do fornecedor **e** o código do cliente (2396739, que tem forma CAT); o modelo escolheu o do fornecedor, e **a lista de PN liberados não é consultada por linha**, só para decidir se a peça exige serial, então nada corrige; (b) caixa de madeira é embalagem, sem preço, mas o código tem forma de código; (c) fabricante nulo porque o documento não imprime e a regra 7 do prompt proíbe inventar; (d) frete: 1.3 | **alta: "part number errado, MAIORIA"** |
| 2.6 | 2026RFM04744 (Bergstrom, Clydesdale, Widney; 16 páginas): "Supplier Part No. MN447750-31914C" vs "Customer Part No. 290-2789"; Clydesdale `K000403546P` vs `446-3802`; "confiança baixa"; "embalagem ainda estranho" | mesma causa do 2.5(a). A confiança baixa é consequência: com o part number errado os números da linha ficam sem âncora no texto e saem como "não localizado" | alta |
| 2.7 | 2026RFM04632: 14 de 15 faturas reconhecidas (a faltante, reenviada sozinha, saiu certa) | sem o PDF não dá para cravar. Hipóteses: resposta do modelo truncada em `max_tokens = 16000` (o JSON por fatura é verboso, e o `finish_reason` não é lido), ou o modelo fundiu duas faturas. Hoje só existe aviso quando a contagem de `CAT Invoice#` no texto difere do número de invoices devolvidas | média; precisa do PDF |
| 2.8 | 380_Commercial Invoice (3) (Freudenberg): "1,62 / 10", quantidade 5, valor 0,81; a tela mostra unitário **162** | **reproduzido.** O modelo derivou `0.162` (regra 3, com ponto), e `_num("0.162")` devolve `162.0`: o ramo "um ponto só com três casas é milhar europeu" não exclui parte inteira zero | alta: valor 1000× errado gravado |
| 2.9 | "Part numbers que não são part numbers: aba pesquisar part number?"; "embalagens, fretes etc. ainda não add" | a lista de 206 mil PN existe no banco desde a leva 6 mas **não valida linha nenhuma**. O item 3 do BACKLOG previa `released` / `not_released` por linha e isso nunca foi implementado | alta: é a fonte da verdade do cliente, parada |

## Causas-raiz

Os 15 apontamentos se reduzem a seis causas:

1. **Unitário copiado do estendido, ou preço por N** (1.1, 1.6, 2.1, 2.8). O
   prompt pede para derivar, o modelo não obedece, e o código só acusa. E o
   `_num` quebra o unitário derivado `0.162`.
2. **Encargos de fatura não chegam ao banco nem à tela** (1.3, 2.3, 2.5d).
   `freight`, `packaging_cost`, `unit_price_landed` e `amount_landed` só
   existem no `raw_extraction`.
3. **Linha de encargo ou de nota tratada como item** (1.4, 1.5, 2.4, 2.5b):
   código sem preço, e embalagem ou frete com preço.
4. **Código do fornecedor no lugar do part number Caterpillar** (2.5a, 2.6,
   2.9), porque a lista de PN liberados não é usada por linha.
5. **Rateio conta linha sem preço** (2.2).
6. **Fatura faltando em documento com muitas faturas** (2.7).

## Plano de correção

### Leva 14: aritmética da linha, linhas de encargo, encargos gravados (causas 1, 2, 3, 5)

Tudo em `function/pipeline/structurer.py`, salvo indicação. A ordem nova dentro
do `_check_lines`, cada passo alimentando o seguinte:

```
classificar PN -> reclassificar encargo / descartar -> derivar unit_price | amount
-> somar amount -> confianca por campo -> peso -> expandir por serial
```

- **`_num`.** "Um ponto só com três casas" só é milhar europeu se a parte
  inteira tem de 1 a 3 dígitos e não começa com zero. `0.162` vira 0.162;
  `1.234` e `12.345` seguem como milhar (é o que o corpus imprime).
- **`_derive_unit_price(qty, unit, amount)`**, função pura chamada depois do
  `_num` e **antes** da expansão por serial (que copia o unitário para cada
  registro). Casos, em ordem: `amount` ausente com quantidade e unitário
  presentes → `amount = qty × unit`, derivado, entra na soma e o total julga;
  quantidade nula ou zero → nada; quantidade maior que 1, `unit ≈ amount` e
  `qty × unit ≠ amount` → `unit = amount / qty` (3YNDJ: 18.413); senão, se
  `amount / qty ≈ float("0.162")` lido como decimal simples → idem; senão
  mantém o problema de hoje. Quatro casas; se `qty × round4 ≠ amount` (100/3)
  vira problema, senão nota. O impresso fica em `unit_price_printed` e a nota o
  cita: marcar, nunca descartar. A confiança do campo passa a `derived`.
- **`_landed`.** O divisor soma só linhas com unitário numérico e quantidade
  positiva, o mesmo predicado do laço que grava o rateio. A nota diz o divisor.
- **Linhas de encargo.** Dois regex, `PACKAGING_RE` (PACK, CAIXA, CRATE,
  PALLET, PALETE, EMBALAGEM, WOODEN) e `FREIGHT_RE` (FREIGHT, FRETE, SHIPPING,
  TRANSPORT, CARRIAGE), sobre part number + descrição, **só para linha que não
  é part number CAT** (linha `cat` é sempre item: "PACKING RING" fica). Com
  valor, a linha vai para `discarded_lines` com o motivo e o valor vai para
  `packaging_cost` ou `freight` da invoice (se o modelo já reportou o mesmo
  valor no cabeçalho, não conta duas vezes; se reportou outro, soma e acusa).
  Invariante: o valor sai da soma das linhas e entra no encargo, e a
  conferência do total não muda.
- **Código sem preço nem valor não é item.** `other_code` sem `unit_price` e
  sem `amount` vai para `discarded_lines` ("código sem preço nem valor"): é o
  0V3456 e as caixas 448034/448035. Se a descrição for de embalagem, ela
  preenche o campo `packaging` das linhas mantidas que estiverem vazias.
  `other_code` **com** preço (`15.1301.466`) continua item. O parágrafo da
  exceção no `CLAUDE.md` muda junto.
- **Gravar e mostrar.** Migração `0009` (só colunas nulas, sem GRANT):
  `invoices.freight` e `invoices.packaging_cost` (18,2);
  `invoice_part_number_items.unit_price_landed` (18,4) e `amount_landed` (18,2).
  `db/db-setup-v2.sql` regerado. O rateio vira função pura em
  `shared/shared/landed.py`, usada pelo structurer e pelo PATCH, para que editar
  unitário, frete ou embalagem na tela recalcule no servidor. Na tela: o
  cabeçalho ganha "Frete" e "Embalagem (custo)"; a linha mantém "Unitário" como
  impresso e ganha "Unit. c/ encargos" e "Total c/ encargos", somente leitura;
  a coluna "Frete" atual vira "Frete da linha", que é o que o cliente confundiu.
- **Testes.** `check_rules.py`: tabela do `_num` (com as regressões `108.08` e
  `1.234`), seis casos do `_derive_unit_price`, regex de encargo, divisor do
  rateio. `check_structurer.py`: 3YNDJ sintético com serial → dois registros de
  18.413 e total 36.987,99 fechando; END USE + frete 161,99 → 80,995 por
  unidade; "Packaging - Sales 86.00" → `packaging_cost` 86 com a soma intacta;
  a seção 10d (linha legítima derrubada faz a soma não fechar) continua.
- Toca `shared/shared/`: a leva roda `build.ps1` na VM; migração pelo webssh.

### Leva 15: part number pela lista de PN liberados (causa 4)

- **Uma consulta por documento, como hoje.** A pré-varredura que hoje devolve
  "quais peças exigem serial" passa a devolver também "quais candidatos estão
  na lista", e `structure()` recebe `liberados: set[str]` ao lado de
  `exigem_serial`. Um set, e não um callable (como o BACKLOG item 3 sugeria):
  o structurer continua sem banco e testável offline.
- **`_resolve_cat_part_number(linha, texto, liberados)`**, para linha com
  status `other_code` ou `not_printed`: candidatos são os tokens com forma CAT
  numa janela de ±400 caracteres de cada ocorrência do código impresso, mais o
  campo alternativo que o modelo devolver. Fica quem está na lista (ou é o
  campo alternativo do modelo e está impresso); candidato já usado por outra
  linha da mesma invoice sai. Exatamente um → troca: `part_number` recebe o
  CAT, o antigo vai para `supplier_part_number`, status `cat`, com nota
  ("'148409' é código do fornecedor; gravado '2396739', confirmado pela
  lista"). Vários → problema listando-os, mantém o do modelo. Nenhum → nada.
  Resolve os três casos do relatório: Carraro, Bergstrom e Clydesdale.
- **Prompt, regra 2:** linha com dois códigos ("Supplier / Our Part No." e
  "Customer / Caterpillar / Material No.") → `part_number` é o do cliente, o
  outro vai em `supplier_part_number`. Barato, mas o modelo já ignorou o rótulo
  "Customer Part No." no 2026RFM04744: o passo determinístico é o contrato.
- **"Fora da lista" na tela.** Part number com forma CAT que não está na lista
  recebe status `not_released`, como nota (não problema: uma fatura de
  fornecedor inteira iria para revisão). A migração `0009` ganha
  `supplier_part_number` e `part_number_released`; o PATCH reconsulta a lista
  para part number editado. Badge na coluna Part #. É a resposta ao "aba
  pesquisar part number?" do cliente.
- Se as levas 14 e 15 saírem juntas, é uma migração `0009` só, e um webssh só.

### Leva 16: documento com muitas faturas (causa 6)

Bloqueada até termos o PDF 2026RFM04632 e o `raw_extraction` do documento.
O que vale fazer desde já, barato: ler o `finish_reason` da resposta do modelo
e registrar "resposta truncada" como problema quando for `length`. Depois:
contar rótulos distintos de número de fatura no texto e comparar com as
invoices devolvidas (generalizar o aviso que hoje só existe para
`CAT Invoice#`); se o truncamento se confirmar, chamar o modelo por grupo de
páginas (o `pages.py` já dá os spans).

## O que não muda, e por quê

- **"Código do fornecedor" com preço continua item.** Derrubar por "não está
  na lista de PN" apagaria as faturas de fornecedor inteiras (`15.1301.466`).
  O que muda é que, quando a linha também imprime um PN CAT, ele passa a
  vencer.
- **Fabricante ausente continua vazio.** O documento da Carraro não imprime
  fabricante; preencher com o fornecedor é inventar. Pergunta 3 abaixo.
- **O unitário impresso continua gravado como impresso.** O unitário com
  encargos entra ao lado, não no lugar. Pergunta 1 abaixo.

## Perguntas para a CAT

1. Unitário na tela: o impresso (388,46) com "unitário com encargos" (395,16)
   ao lado, que é a proposta, ou substituir pelo rateado?
2. Divisor do rateio de frete e embalagem: por unidade (hoje), por valor ou por
   peso? Com uma linha dá igual; com várias linhas, muda.
3. Fabricante ausente do documento: deixar vazio (hoje) ou assumir igual ao
   fornecedor, com nota?
4. 2026RFM04632: precisamos do PDF para diagnosticar a fatura que faltou.
