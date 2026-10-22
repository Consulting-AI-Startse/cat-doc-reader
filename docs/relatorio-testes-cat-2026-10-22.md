# Relatório dos testes oficiais da CAT (22/10/2026) e os itens que geram

Análise da segunda versão do "TESTES - CAT DOC READER" (25 slides), cruzada
com o código e com o relatório anterior (`relatorio-testes-cat-2026-10.md`,
de 19/10). O PDF tem três etapas: **até 14/09**, **a partir de 02/10** e os
**testes oficiais a partir de 19/10**. As duas primeiras já estavam cobertas
pelo relatório anterior e pelas levas 14 e 15; o que importa aqui é a
terceira, cujos screenshots já mostram a tela das levas 14/15 (colunas
"Unit. c/ encargos", badge "fora da lista"). **O que aparece lá é defeito do
código atual** (`main` da CAT em `baa444f`, leva 15).

Escrito em 22/10/2026. O PDF é artefato do cliente e não é versionado (ver
`CLAUDE.md`); está na máquina do Luis.

## Os problemas, enumerados

| # | problema | documento(s) | etapa |
|---|---|---|---|
| P1 | Linhas N/C de serviço/embalagem (`0P-4349 INSTRUCTIONS`, `0P-6790 PACKING, CONTAINER`…) viram itens com qtd 1, unitário 0, total 0, algumas "fora da lista" | Invoice_R9PLK | 02/10 e **19/10 ("manteve erro")** |
| P2 | Sufixo gravado junto do part number: `5531000/S`, `4729218/D`, `5657043-CBL`. No `/S` a tela mostra "forn.: 5531000/ S" e um `01/S` foi parar no serial | 380_CI teste kau 2, INV E261008Q | 19/10 |
| P3 | PO errado, em três formas: prefixo perdido (`QIPP 068274` → `068274`); vários POs no cabeçalho com vírgula CJK (`QIPP65000、QIPP65001、QIPP92629、`) → nenhum gravado; "Order Number / Cust. PO" empilhados → gravou o do fornecedor (`600355588`) em vez de `QIPP53139` | K278868, invoice 11768 清关, Perkins 590063882 | 19/10 |
| P4 | Número da fatura: `DOCUMENT NO. 1270082320` não capturado; e o aviso "'CAT Invoice#' não localizado" aparece mesmo com o número certo (`CAT28260826A`) | 1-1270082320, invoice28 | 19/10 |
| P5 | Frete e embalagem: cliente quer **valores**; frete "ainda não vi pegando"; embalagem traz texto (`PALLET - EDI Packaging`, `CAIXA DI LEGNO`) copiado para todos os itens; o custo de embalagem é rateado no unitário "sendo que é a mesma para todos os itens". Regra do cliente: **por PN só se estiver na linha; se estiver em outra parte, é geral** | 0094999841, 2026RFM04744, 3YNDJ, Carraro | todas |
| P6 | Documento com muitas faturas perde faturas: 14/15 (2026RFM04632) e agora **10/18 (CIV FFAU5762790)** | 2 docs | 02/10 e 19/10 |
| P7 | Confiança 50% "como funciona?" | vários | até 14/09 |
| P8 | Unitário sem vírgula (`1,62 / 10` → 162) | 380_CI (3) | 02/10 |
| P9 | Qtd × unitário × total não validados | AE28 518920 | até 14/09 |
| P10 | Supplier Part No. vs Customer Part No. (`MN447750-31914C` vs `290-2789`) | 2026RFM04744, Carraro | 02/10 |
| P11 | `0V3456 END USE` e `I/C Material` como itens | CIVs de motor | até 14/09 e 02/10 |
| P12 | Fabricante vazio | Carraro | 02/10 |

## Cruzamento com o backlog

| # | estado | item |
|---|---|---|
| P7 | **resolvido** (o cliente diz "erros anteriores resolvidos") | B5, leva 11 |
| P8 | **resolvido** ("valor unitário sem vírgula resolvido") | B10, leva 14 |
| P9 | **resolvido** | B10, leva 14 |
| P10 | **resolvido** ("maioria resolvido") | B11, leva 15 |
| P11 | **resolvido** | B10 (`sem_valor`) e B5 |
| P6 | **em aberto, já no backlog** | B12, bloqueado. O FFAU5762790 é o segundo caso e reforça a hipótese 1 (truncamento): 18 faturas é mais JSON que 15. Pedir o `raw_extraction` dele também |
| P12 | **em aberto, é decisão** | pergunta 9 do `BACKLOG.md`, sem resposta |
| P5 | **parcial** | B10 gravou e mostrou `freight`/`packaging_cost`; sobraram três coisas, ver B20 |
| P1, P2, P3, P4 | **sem item** | novos: B16 a B19 |

## Itens novos: causa e solução

Todos seguem o princípio da leva 15: **o prompt dá a direção, o código
determinístico é o contrato, e a lista de PN liberados é o árbitro** quando a
forma do texto não basta. Cada item lista o que não pode quebrar, porque o
fluxo é generalista: regra que resolve um documento e quebra outro não serve.

### B16: PO: regra no prompt e resolução determinística (P3)

**Por que acontece.** O prompt não tem nenhuma regra sobre PO: ele só aparece
na lista de campos de saída (`structurer.py:60`). Não há regex, normalização
nem validação de forma; o valor passa direto do modelo para o banco
(`structurer.py:1398`, `doc_worker.py:206`). A confiança
(`confidence.py:124-142`) só confere se a string existe no texto, então
`068274` e `600355588` passam com "ok": os dois estão impressos. Não há regra
"PO do cabeçalho vale para todas as linhas", por isso o documento chinês ficou
sem nada. O `、` (U+3001) é trocado por espaço pela limpeza de não-latino
(`structurer.py:260-304`), então não é ele que apaga o valor.

**Solução.**
- Prompt: PO da Caterpillar tem a forma `QIP?nnnnn` (nos 28 PDFs são `QIPP`,
  `QIPD`, `QIPC`; **confirmar com a CAT que é regra**). Rótulos: `Cust. PO`,
  `Customer PO`, `P/O`, `Customer Order No.`, `PO NO`. Com dois valores
  empilhados, o do cliente é o com prefixo `QIP`. PO único no cabeçalho vale
  para todas as linhas.
- Código, `_resolve_purchase_order`, com `PO_RE = QIP[A-Z]\s*\d{5,6}` sobre o
  texto. PO do modelo é sufixo numérico de um `QIPP 068274` impresso →
  recompõe, nota. PO do modelo sem a forma e há um `QIP…` na mesma `<tr>` ou
  linha de texto → troca, nota (Perkins). Linha sem PO e cabeçalho com
  exatamente um → preenche, nota. Vários no cabeçalho sem mapeamento por
  linha → grava a lista e **problema** (revisão); nunca escolhe um.
- **O que não pode quebrar:** fornecedor cujo PO não seja `QIP` (se a CAT
  confirmar que existe) continua passando como veio, com nota "fora da forma".

### B17: número da fatura: rótulo genérico, e o aviso `CAT Invoice#` só quando importa (P4)

**Por que acontece.** Dois defeitos independentes:
- A regra 1 do prompt tem lista **fechada** de rótulos aceitos
  (`structurer.py:70-81`) e `DOCUMENT NO.` não está nela; o modelo obedeceu e
  devolveu nulo. Não há fallback.
- `_cat_invoice_numbers` (`structurer.py:726-746`) roda em **todo** documento
  e, quando não acha o formato `AA00 000000`, devolve a nota "'CAT Invoice#'
  nao localizado", que `_normalise` (`:1268`) empilha em `issues` sem olhar se
  o modelo já trouxe um número válido. Resultado: 10 dos 28 PDFs do corpus
  levam esse aviso e vão para revisão por causa dele. `CAT28260826A` não casa
  com o regex (letra no fim).

**Solução.**
- O aviso vira **nota** quando o modelo devolveu número e ele está localizado
  no texto; só é **problema** se o modelo também devolveu nulo.
- Regra 1 ganha `Document No.` / `Doc. No.` quando está no bloco de cabeçalho
  da fatura e não há outro rótulo de fatura. E um fallback determinístico:
  número nulo → procurar rótulo (`Invoice No|Document No|Nº|N°|Fattura n`)
  nas páginas classificadas como invoice, gravar com problema "localizado por
  rótulo, conferir".
- Generaliza junto a contagem de rótulos que o B12 já pedia (hoje só conta
  `CAT Invoice#`): serve aos dois itens.
- **O que não pode quebrar:** `Delivery note no.`, `Order number`, `CO Invoice
  Number` continuam rejeitados; a lista negativa fica.

### B18: linha sem valor (N/C) com forma de código não é item (P1)

**Por que acontece.** `0P-4349` casa com `PART_NUMBER_RE` (forma de 2
caracteres + hífen, `parts.py:31`), então vira status `cat`. E `cat` é
blindado em três lugares: `_charge_kind` devolve `None` para `cat`
(`structurer.py:583-598`); o descarte `sem_valor` só vale para `other_code` e
testa `is None`, e `0` não é `None` (`:1053`); o desvio para encargo exige
`kind and value`, e `0` é falso (`:1002`). Não existe tratamento de `N/C` em
lugar nenhum do repo. E "PACKING, CONTAINER" não casa com `_PACKAGING_RE`
(PACKING foi excluído de propósito: "PACKING RING" é peça).

**Solução.** A lista de PN decide, não o formato:
- Linha com valor zero ou `N/C` **e** fora da lista de liberados →
  `discarded_lines` com motivo "sem valor e fora da lista"; se a descrição for
  de embalagem ou frete, a nota diz isso (é descrição, não custo).
- Linha com valor zero **e na lista** → fica, com nota "item sem cobrança"
  (peça em garantia ou reposição gratuita é item real para o despacho).
- A soma não muda em nenhum dos dois casos (contribui zero), então a rede de
  segurança aritmética não pega erro aqui; por isso a lista é o critério, não
  a descrição.
- **O que não pode quebrar:** `674-8657` e qualquer PN com preço seguem
  intocados; a regra só olha linha de valor zero.

### B19: sufixo do part number: gravar a base, decidir pela lista (P2)

**Por que acontece.** Para `/S` e `/D`: `split_part_number` separa certo
(chave `5531000`, status `cat`), mas o banco guarda o **texto impresso**
(`part_number` como veio) e a coluna de sufixo não é persistida
(`doc_worker.py:194-199`). O "forn.: 5531000/ S" é o `supplier_part_number`
que o próprio modelo preencheu, passado sem validação (`structurer.py:1391`),
embora a regra 2 mande deixar nulo. Para `-CBL`: `PART_NUMBER_SUFFIX_RE` só
aceita `-NN` numérico (`parts.py:34`); então `5657043-CBL` vira `other_code`,
chave `5657043CBL`, "fora da lista", e o `_PN_TOKEN_RE` lê o token inteiro,
então `5657043` nunca entra como candidato.

**Solução.**
- Gravar `part_number` = base e persistir `part_number_suffix` (coluna nova,
  migração 0011); a tela mostra a base e o sufixo como meta, igual ao "forn.:".
- Sufixo alfabético (`-CBL`, `-XX`) reconhecido **apenas quando a base tem
  forma CAT e está na lista**: a lista é o árbitro, não se corta às cegas
  (`1R-0750` tem letra e é PN inteiro).
- `supplier_part_number` vindo do modelo é descartado quando é o mesmo código
  do `part_number` a menos de sufixo ou espaço; `serial_numbers` que coincide
  com o sufixo é descartado com nota.
- **O que não pode quebrar:** `663-7238~00`, `6064986-07`, `364-9717/01`
  continuam como hoje; `15.1301.466` (fornecedor) nunca é tocado.

### B20: encargos: valor de rodapé determinístico, texto de embalagem no lugar certo, e a decisão do rateio (P5)

**Por que acontece.**
- Frete e embalagem impressos no **rodapé de totais** (`Logistic Charges
  443.02`, `Inland Freight 249.53`, `I/C freight & ship 161.99`, `Trasporto
  158,30`) dependem só do modelo (regra 4 do prompt); o `_check_lines` só vê o
  que o modelo devolveu como `line_items`. Se o modelo ignora o rodapé, não há
  segunda chance.
- A leva 14 copia o **texto** de embalagem lido de linha sem preço para o
  campo `packaging` de **todas** as linhas (`structurer.py:1133-1142`). O
  cliente lê isso como "embalagem pegando outras coisas".
- `landed.apportion` rateia por unidade, igual em todas as linhas
  (`landed.py:52`). O cliente diz: na linha → por PN; fora → geral. Isso
  **responde a pergunta 8** do `BACKLOG.md` (divisor do rateio), mas conflita
  com o gabarito (`395,16 = 388,46 + 603/90`, que é rateio). **É decisão de
  produto, não de código.**

**Solução.**
- Varredura determinística do bloco de totais: rótulo `_FREIGHT_RE` ou
  `_PACKAGING_RE` seguido de valor; alimenta `_merge_charge` como hoje (igual
  conta uma vez, diferente soma e acusa, modelo nulo → preenche com nota).
  Reaproveita o padrão que já existe.
- Texto de embalagem vai para um campo descritivo **da invoice**, não copiado
  por linha; `packaging` da linha só quando a linha imprimiu.
- Rateio: levar o conflito à CAT com os dois números lado a lado (unitário
  impresso + "c/ encargos" rateado, ou encargo geral sem rateio). Até a
  resposta, o cálculo não muda.

## O que precisa da CAT

1. **Todo PO Caterpillar é `QIP?` + dígitos?** (B16)
2. **Rateio** (B20): o gabarito pede rateado, o usuário pede geral. Qual vale?
3. **`raw_extraction` e PDF do FFAU5762790**, além do 2026RFM04632 (B12).
4. Fabricante ausente (P12): segue sem resposta (pergunta 9).

## Quão confiável é esta leva

Alta confiança de que B16 a B20 resolvem o que está nos slides; confiança
média de que o próximo relatório da CAT vem menor. Quatro razões, e duas
viraram item:

1. **Não existe linha de base medida.** O gabarito (38 linhas, 16 faturas)
   nunca foi rodado como regressão; cada leva é validada por teste sintético
   do caso do slide. Não dá para dizer se a leva 14 melhorou ou piorou a
   acurácia global. → **B22.**
2. **O padrão é reativo:** cliente acha documento novo, nasce regra nova. Os
   itens que dependem de lista (B18, B19) envelhecem bem; os que dependem de
   regex de texto (B16, B20) envelhecem mal.
3. **Uma chamada só, documento inteiro, 16k tokens, sem ler
   `finish_reason`.** É o ponto mais frágil e nenhum item o muda, exceto o
   B12 se a hipótese do truncamento se confirmar. → **B21.**
4. **Regra determinística só corrige o que o modelo devolveu.** Linha que o
   modelo pulou não tem segunda chance; a soma acusa, mas é revisão, não
   correção.

Por item: B17 e B18 altas (critério objetivo, sem depender do modelo); B19
média-alta; B16 média (assume que todo PO é `QIP?nnnnn`, visto em 28 PDFs,
não confirmado); B20 média-baixa (rodapé é a parte menos padronizada da
fatura, e metade do item é decisão); B12 desconhecida sem o `raw`.

## Ordem sugerida

B21 (uma linha, decide o B12); B17 e B18 (baratos, visíveis em todo
documento); B22 antes da próxima leva de código, para medir o antes; B16 e
B19 (mesmo padrão da leva 15); B20 e B12 (dependem de resposta da CAT e de
artefato).
