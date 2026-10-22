# BACKLOG

Próximas features, ponderadas. A ordem é do mais fácil para o mais difícil, com
uma inversão deliberada (item 3), explicada abaixo.

Esforço: **XS** < 1h · **S** ~meio dia · **M** ~1–2 dias · **L** ~1 semana

**Todo item tem número, e o número não muda** -- nem quando o item é feito,
nem quando sai de ordem. A coluna `caminho` liga o item ao que o entregou:
`B11` (o item) → `#4` (PR deste repo) → `L15` (a leva) → `CAT#35` (o PR do lado
da CAT). A convenção está no `CLAUDE.md`. Os itens 1 a 9 e o 15 são de antes do
PR neste repo (19/10) e ficam sem caminho.

| # | item | esforço | valor | depende | caminho |
|---|---|---|---|---|---|
| ~~1~~ | ~~Poison handler grava status `error`~~ | XS | alto | **feito** | — |
| ~~2~~ | ~~`Unit` e `Unit Weight`~~ | S | médio | **feito** | — |
| ~~3~~ | ~~Lista de PN: tabela, import CSV e checagem~~ | M | **muito alto** | **feito** | — |
| ~~4~~ | ~~Serial Number~~ | M | alto | **feito** | — |
| ~~5~~ | ~~Confiança por campo e geral~~ | M | alto | **feito** | — |
| ~~6~~ | ~~Duplicatas por (invoice, fornecedor)~~ | M | médio | **feito** | — |
| ~~7~~ | ~~Classificação invoice × packing list~~ | M | alto | **feito** | — |
| ~~8~~ | ~~Relatório de confiança por fornecedor~~ | M | médio | **feito** | — |
| ~~9~~ | ~~Métricas de processamento por período~~ | M | médio | **feito** | — |
| ~~10~~ | ~~Aritmética da linha, linhas de encargo, frete/embalagem gravados~~ | M | **muito alto** | **feito** (leva 14) | #2 → L14 → CAT#34 |
| ~~11~~ | ~~Part number pela lista de PN: fornecedor × CAT, "fora da lista" na tela~~ | M | **muito alto** | **feito** (leva 15) | #4 → L15 → CAT#35 |
| 12 | **Leva 16:** documento com muitas faturas, fatura que falta | ? | alto | **bloqueado** (PDF e `raw_extraction` do 2026RFM04632) | → L16 |
| 13 | `Invoice Type`, `Import Process`, `CSAR`, `PFO`, `##` | ? | ? | **on hold** (desde 22/10; espera a CAT) | — |
| 14 | Word/Excel | ? | ? | **escopo indefinido** | — |
| ~~15~~ | ~~Texto fora do alfabeto latino~~ | S | médio | **feito** | — |
| 16 | PO: regra no prompt e resolução determinística (`QIP?nnnnn`) | S | alto | confirmar forma do PO com a CAT | — |
| 17 | Número da fatura: rótulo genérico, aviso `CAT Invoice#` só quando importa | S | alto | — | — |
| 18 | Linha sem valor (N/C) com forma de código não é item | S | alto | 3 (lista de PN) | — |
| 19 | Sufixo do part number: gravar a base, decidir pela lista | M | alto | 3 (lista de PN); migração 0011 | — |
| 20 | Encargos: valor de rodapé determinístico, texto de embalagem na invoice, decisão do rateio | M | alto | resposta da CAT sobre o rateio | — |

**A inversão:** o item 3 é M, não S, mas vem antes do 5 porque a lista de PN é a
fonte da verdade da validação e porque destrava o item 4 de graça.

## De onde vem o escopo

`SUBIR_FATURA_GA.xlsx`, do cliente, traz 22 campos (15 mandatórios), as
premissas do produto e o plano de aceitação. **Faltam 8 campos** no nosso
schema: `Unit`, `Unit Weight`, `Serial Number`, `Invoice Type`,
`Import Process`, `CSAR`, `PFO`, `##`. Dois são mandatórios (`Unit`,
`Serial Number`).

`FASES_LEITURA`, na mesma planilha, é o plano de aceitação — e mostra que um
terço do corpus é um caso que hoje não tratamos:

```
PDF apenas com Invoice ..................... 5
PDF e Imagens (JPEG, TIFF) ................. 5
PDF com Invoice + Packing List ............ 10   <- item 7
PDF escaneado / digitalizado .............. 10
Imagem, Word, Excel ...................... TBD
```

As colunas `Latino` e `Full Não Latino` estão vazias: o escopo de alfabeto ainda
não foi definido pelo cliente. **Decidido em 08/10: texto fora do alfabeto latino é
ignorado** — ver a seção abaixo do item 9.

---

## 1. Poison handler grava status `error` (XS) — **feito**

O problema: o worker morria, a mensagem batia em `MaxDequeueCount`, ia para
`document-processing-poison`, o handler executava com sucesso — e o documento
ficava em `processing` para sempre, sem erro e sem pista para quem revisa.
Aconteceu duas vezes com o CIV.

`doc_worker.mark_failed(document_id, message)` grava `DocumentStatus.error`, o
`error_message` e um `DocumentEvent` com `actor="poison"`;
`process_document_poison` chama essa função depois de logar.

Três decisões que valem registrar:

- **Estado terminal não é sobrescrito.** O worker pode ter comitado o resultado
  e morrido logo depois (OOM no fallback por imagem, host reciclado): aí o
  documento está correto e marcá-lo como `error` destruiria extração boa. Só
  `received` e `processing` viram `error`.
- **O log vem antes do banco.** Se a gravação falhar, a evidência já está no App
  Insights.
- **A falha de gravação estoura.** Vira nova tentativa do handler, o que resolve
  indisponibilidade momentânea do banco; engolir a exceção recriaria exatamente
  o buraco que a função existe para tapar.

Cuidado com o `dequeue_count` dentro do handler de poison: ele é o da mensagem
**na fila de poison**, que recomeça em 1. O número de falhas do worker é o
`maxDequeueCount` do `host.json` (hoje 2), não aquele.

## 2. `Unit` e `Unit Weight` (S) — feito em 08/10

**Como ficou.** Migração `0008`: `unit` `Text` (não `String(16)` — a `0003`
existe porque um incoterm estourou `VARCHAR(16)`) e `unit_weight`
`Numeric(18,5)`, **sempre em kg**. O modelo copia o peso como impresso, por
unidade (`unit_weight`) ou da linha (`line_weight`), mais a unidade de peso
(`weight_uom`); quem divide pela quantidade e converte LB/G para kg é o
`_unit_weight`, pela mesma razão da regra 6. O cálculo é sobre a linha
impressa, antes da expansão por serial — o registro expandido tem quantidade
1. Peso sem unidade impressa assume KG com nota; unidade desconhecida grava
nulo com nota. Teste no `check_rules.py`.

O texto abaixo é o plano original.


Dois campos que o cliente pede e não temos. `Unit` é mandatório (a unidade:
`pcs`, `kg`). `Unit Weight` é o `Peso Unitário` do gabarito, com verdade
conhecida para conferir (`3649717 → 19,81`).

- migração `0004`: `unit` `String(16)` e `unit_weight` `Numeric(18,5)` em
  `invoice_part_number_items`
- `shared/shared/models.py`, o dict emitido em `structurer._normalise`, o shape
  do prompt, `_serialize_line` e `LineIn` em `backend/app/api/documents.py`

## 3. Lista de PN Liberados (M)

**Completo em 20/10 (leva 15).** Até ali a lista só decidia `requires_serial`.
Agora a mesma consulta por documento devolve também os liberados, e com eles
o structurer troca o código do fornecedor pelo part number CAT impresso na
mesma linha (`_resolve_cat_part_number`); depois do structurer, uma segunda
consulta marca cada linha gravada (`part_number_released`), e a tela mostra
"fora da lista". Saiu como set `liberados` passado ao `structure()`, e não
como o callable sugerido abaixo: o structurer continua sem banco e testável
offline.

`PN Liberados.xlsx` tem **206.769 part numbers** com descrição, em duas colunas
(`PECA`, `NOME`), **sem hífen** — exatamente a convenção do nosso
`part_number_normalised`.

Testada contra o que já extraímos:

| | |
|---|---|
| part numbers que extraímos | **18 de 18 na lista** |
| valores que rejeitamos | **6 de 6 ausentes** |

`6637238 = PUMP GP-LUB`, `7G5837 = HUB-SPROCKET`, `5P1465 = HOSE BK`,
`6511308 = ENGINE AR-COMPL`. Ausentes: `0V3456`, `QIPP27001`, `F4E09020`,
`500001092`.

**Decisão do cliente: a lista é a fonte da verdade.** O que não está nela não é
part number. Isso rebaixa `PART_NUMBER_RE` a pré-filtro barato — ele continua
descartando prosa antes da consulta, mas deixa de ser o juiz.

### Modelo

Migração `0005`, tabela `released_part_numbers`:

| coluna | tipo | nota |
|---|---|---|
| `part_number` | `String(32)` PK | normalizado, maiúsculo, sem hífen |
| `name` | `Text` | o `NOME` da planilha |
| `is_engine` | `Boolean` indexado | derivado de `name` — usado pelo item 4 |
| `imported_at` | timestamptz | |
| `import_batch` | `String(64)` | arquivo + data, para auditoria |

### A checagem, do jeito eficiente

**Uma consulta por documento**, não por linha:

```sql
SELECT part_number, name, is_engine
  FROM released_part_numbers
 WHERE part_number = ANY(:lista)
```

Um round-trip, índice de PK, tipicamente menos de 50 valores. Nunca carregar
206 mil linhas na memória da function a cada invocação.

O structurer não conhece banco e não deve passar a conhecer: `doc_worker` passa
um **callable opcional** `lookup(pns) -> dict` para `structure()`. Default
`None` — aí a checagem é pulada e nada quebra, inclusive no `MockStructurer` e
nos testes offline.

Em `_check_lines`, cada linha passa a ter `released` ou `not_released`. Fora da
lista → nota em `validation` e documento para `needs_review`. **A linha nunca é
descartada**: a regra de marcar em vez de apagar continua valendo; o que muda é
quem julga.

### Import por CSV

- `POST /parts/import` — multipart, mesmo padrão de `/documents/upload`
- `csv.reader` em streaming, upsert em lotes de ~5.000 com
  `ON CONFLICT (part_number) DO UPDATE`. 206 mil linhas não podem virar 206 mil
  round-trips.
- resposta com `{recebidas, inseridas, atualizadas, ignoradas, erros[]}`
- `GET /parts/stats` para a tela mostrar total e último import

### Tela

`frontend/src/pages/PartNumbers.tsx`, registrada em `main.tsx` (uma linha antes
do catch-all) e linkada no menu do `AppShell.tsx` (Documentos, Part numbers,
Fornecedores).

Dois detalhes achados na exploração:

- `components/FileUpload.tsx` é reaproveitável mas está **hardcoded em PDF em
  três pontos** (teste `.pdf`, `accept=".pdf"`, preview em `<iframe>` e o texto
  "Arraste o documento (PDF) aqui"). Precisa de props `accept` / `match` /
  `hint` e preview opcional — para CSV o análogo é uma tabela das primeiras
  linhas, não um iframe.
- `api/client.ts` descarta o corpo do erro (`throw new Error(status)`), então o
  `detail` do FastAPI nunca chega à tela. Para relatar erro por linha do CSV,
  estender `api()`.

## 4. Serial Number (M) — feito em 25/09

Mandatório, e a premissa "TELA DE MANUTENÇÃO PARA ITENS COM SERIAL NUMBER" diz
que serial é entidade de primeira classe. Então **tabela própria**, uma linha
por serial.

**A tabela própria não foi necessária.** O cliente esclareceu que motor repete
o **mesmo** part number, uma vez por serial — e não que um registro tenha vários
seriais. Então `serial_number` é coluna de `invoice_part_number_items`
(migração `0006`), e o structurer expande a linha impressa em N registros com
quantidade 1 e `amount` = `unit_price`.

Confirmado na fatura **93872204**, de motor: `QTY 7` de `6522586` e sete
seriais numa tabela `Part Number | Serial Number` separada da tabela de itens.
Os seriais são `XWE42867, 42871, 42879, 42880, 42881, 42882, 42883` — **não
consecutivos**, então checagem de continuidade numérica estaria errada; o que
vale é o formato, e serial que destoa dos irmãos vira nota.

Nesse layout o cabeçalho tem **duas** colunas, não quatro: o `Pin Number`
aparece como rótulo de seção solto, sem valor. Não há coluna de PIN no schema
— nenhum documento do corpus traz valor nela.

A quantidade 1 nos registros expandidos não é detalhe: sem ela a soma das
linhas daria 7× o total impresso e **toda** fatura de motor entraria em
`needs_review` com erro falso.

**Só preenchemos quando o part number for motor** — e a regra sai de graça do
item 3: `is_engine`, derivado do `NOME` da lista (`ENGINE AR-COMPL` para
`6511308` e `6522586`). Sem motor, não pedimos nem gravamos serial.

### Serial x PIN, respondido (24/09)

A pergunta 4 tinha resposta de negócio: **é motor → o valor é Serial; não é
motor → é PIN.** Um motor tem várias peças, logo vários seriais, e os seriais
do mesmo motor seguem um padrão — o que dá um segundo sinal, de conferência:
serial que destoa do formato dos irmãos na mesma invoice recebe nota.

**Mas `is_engine` não é `NOME` contendo `ENGINE`.** Medido na `PN Liberados.xlsx`
(206.769 linhas): `ENGINE` em qualquer posição casa **910** peças, quase todas
acessório — `SUPPORT-ENGINE`, `FILM-ENGINE OIL`, `CHART-ENGINE`,
`PLATE-ENGINE S/N`. O que é motor de verdade é o prefixo `ENGINE AR` (*AR* =
arrangement): **588** peças, e é onde caem os dois PNs conhecidos. Sobram 8
casos de fronteira (`ENGINE GP` ×3, `ENGINE-PREP` ×2, `ENGINE SUPPORT` ×2,
`ENGINE STALL.`) — `ENGINE GP` é o único duvidoso.

### Regras alinhadas com o cliente (25/09)

**1. `is_engine` vira coluna da lista de PN, não heurística nossa.** A CAT
acrescenta uma terceira coluna booleana na `PN Liberados.xlsx`. Isso mata a
ambiguidade medida acima (`ENGINE AR` x `ENGINE GP`) e tira a régua de nós, que
não somos donos do dado.

Sugerido ao cliente: chamar a coluna de **"requer serial"**, não "é motor". O
contrato diz "MOTOR **E OUTROS (MAPEAR)**", e com o nome por intenção os tais
"outros" entram depois só marcando mais linhas — sem migração e sem código.

**2. Quem decide se o documento tem motor é uma consulta, não o LLM.** Entre o
extractor (sem LLM) e o structurer (com LLM), varrer o `content` com o
`PART_NUMBER_RE`, normalizar e consultar a tabela. Só então escolher entre o
prompt normal e o de motor. Uma chamada de LLM, e a decisão é deterministica --
perguntar ao modelo devolveria o julgamento probabilistico que a coluna existe
para eliminar. Mesmo padrão do `_cat_invoice_numbers()`, que ja varre o
`content` antes de decidir.

Medido, e o custo e ruido: tabela com as 206.769 linhas ocupa **18 MB**, carrega
em **0,42 s** (`COPY`) e a consulta de ~50 part numbers leva **0,43 ms** de ida e
volta Python->PG->Python (`Index Scan` na PK). No CIV, 83 mil chars de OCR rendem
**22 candidatos**; a pre-varredura leva 0,43 ms. A chamada do LLM leva segundos.
O que nao se pode e carregar as 206 mil linhas na memoria da function.

**3. Motor repete o MESMO part number, uma vez por serial.** Uma linha impressa
com `6511308` e quantidade 3 vira **3 registros** de `6511308`, cada um com seu
serial. Então `serial_number` e **coluna do item**, nao tabela propria -- a
tabela separada so seria necessaria se um registro tivesse varios seriais.

Dois corolarios:

- **PN repetido numa fatura de motor e legitimo.** Qualquer checagem futura do
  tipo "mesmo PN duas vezes e suspeito" estaria errada para motor.
- **A expansao e nossa, nao do LLM.** O prompt de motor pede
  `"serial_numbers": [...]` na linha e o `_normalise` explode. Pedir ao modelo
  que ja devolva explodido o convida a inventar serial para fechar a
  quantidade quando o OCR so leu dois.

**Ponto aberto:** a expansao quebra a conferencia aritmetica do `_check_lines`,
que soma os `amount` e compara com o total impresso -- 3 registros com o valor
cheio dao 3x o total, e toda fatura de motor entraria em `needs_review` com erro
falso. Proposto: cada registro expandido fica com **quantidade 1 e
`amount` = `unit_price`**, o que preserva a soma. Aguardando confirmacao.

Bordas, todas marcando e nunca completando: quantidade 3 com 2 seriais lidos ->
expande em 2 e deixa nota; motor sem nenhum serial -> mantem 1 linha e deixa
nota, porque serial e mandatorio para motor pelo contrato.

**Pendência do próprio contrato:** o `SUBIR_FATURA_GA.xlsx` diz, em
`Serial Number`, "MANDATÓRIO APENAS QUANDO FOR MOTOR **E OUTROS (MAPEAR)**".
Então "não é motor ⇒ é PIN" vale hoje, mas as outras categorias ainda não foram
mapeadas pela CAT. A classificação tem de ser uma regra nomeada e trocável, não
um `if` espalhado.

## 5. Confiança por campo e geral (M) — feito em 01/10

**Como ficou.** `function/pipeline/confidence.py` dá nota a cada campo com três
sinais, e não um só:

- **leitura fraca**: menor confiança de palavra na **pior** ocorrência do valor
  (pela melhor, o `26-2100870` a 0.573 sumia — ele aparece duas vezes);
- **leitura ambígua**: o documento também traz o valor com um caractere
  confundível trocado (O/0, I/1, S/5, B/8, Z/2). Na rodada de 01/10 do CIV o
  modelo copiou `26-2I00870` de uma página onde o OCR leu o `I` com confiança
  **alta**: a palavra não acusa nada, o gêmeo `26-2100870` acusa;
- **não localizado**: o valor não aparece no texto.

Medido no CIV, nas duas rodadas (10/09 e 01/10): 52 campos, os 2 defeitos
marcados, nenhum campo bom. Teste em `check_structurer.py` seção 12, e as
regras isoladas no `check_rules.py`, que roda no CI.

Número é procurado **como impresso** (`35.564,40`), então a nota é dada dentro
do `_normalise`, antes do `_snum`. Com nota por campo, a confiança do
documento é a mínima dos campos e o limite do documento é o do campo (0.85): a
auto-reportada do modelo deixa de decidir e fica em `model_confidence`. Sem
índice de palavras (modo local, mock), nada muda.

Gravação: migração `0007` (JSONB por linha e por cabeçalho, agregados em
coluna na invoice). O `PATCH` recria as linhas, então a nota viaja no payload;
a tela marca como `corrected` o campo cujo valor mudou, e isso alimenta o
item 8.

O texto abaixo é o plano original, mantido como registro.


Requisito escrito ("CONFIDENCE SCORE GERAL E POR CAMPO"). Já prototipado e
validado: 52 campos do CIV, **2 marcados** (`26-2100870`, `QIPPO1280`), **zero
falsos positivos** — os dois marcados são os dois defeitos reais do documento.

Mecanismo: localizar cada campo no `content` e pontuar pela **menor confiança de
palavra** do trecho. Identificadores (`part_number`, `invoice_number`,
`purchase_order`) buscam no documento inteiro; numéricos só na janela de ±1500
chars da âncora da linha — `90` aparece 86 vezes no CIV e busca global não diz
nada.

Exige o extractor entregar o índice completo de palavras (offset, length,
confiança) **em memória**; `doc_worker` descarta antes de gravar, como já faz
com `tables_summary`.

Saída: `min_field_confidence` (governa `needs_review`, porque uma média esconde
um campo catastrófico) e `mean_field_confidence` (número de qualidade).
Substitui a confiança auto-reportada pelo modelo, que já medimos ser inútil.

Vale só no caminho Document Intelligence. O modo local pontua por página, não
por palavra, e já declara `word_confidence_available: false`.

## 6. Duplicatas (M) — feito em 24/09

Premissa: "INVOICES DUPLICADAS PRECISAM SER SINALIZADAS (INVOICE + FORNECEDOR)".
Chave `(invoice_number, supplier)` normalizados — o que exige normalização de
fornecedor antes (`DOKTAS DOKUMCULUK TIC. VE SAN. A.S.` e variantes).

### Como ficou

**`supplier` sobe para `Invoice`.** Hoje é coluna de `InvoicePartNumberItem`, e
a chave pedida é de nível fatura — metade dela mora no nível errado. O
`DocumentDetail.tsx` já contorna isso lendo `inv.line_items[0]?.supplier` e
escrevendo com `setAllLines`, que é o schema denunciando o próprio erro.

A condição para subir era "toda invoice tem um fornecedor só". Conferido no
`raw-civ-cap.json`, que é o documento mais difícil do corpus (35 páginas, **6
invoices de 6 fornecedores diferentes**): as 6 têm **exatamente um** `supplier`
distinto — inclusive a `26VX0515`, que tem 3 linhas. O mesmo vale para
`exporter`. Ressalva: é saída do modelo, não gabarito; o gabarito do cliente não
tem coluna de fornecedor. Se algum dia aparecer fatura com dois fornecedores, a
decisão se inverte.

Corolário que importa para a checagem: **um documento contém N invoices**, então
a duplicata é por invoice, nunca por documento.

- **Marcar, nunca descartar** — nota em `validation` + `needs_review`, como o
  `_check_lines` já faz. Mas a marcação é **visual na própria invoice**, não só
  uma linha no meio das outras notas de validação.
- **Só o novo é marcado.** O antigo é a referência, sempre.
- **Sem backfill.** O banco de produção começa zerado.

## 7. Classificação invoice × packing list (M) — feito em 14/10

Premissa: "IDENTIFICAR AQUILO QUE É UMA INVOICE OU NÃO". São **10 dos 30
documentos** do plano de aceitação, e até aqui mandávamos o documento inteiro
para o LLM e torcíamos para ele ignorar o packing list.

**Como ficou.** Decisão por página, **antes** do LLM e determinística, em
`function/pipeline/pages.py`. O plano original falava num "markdown por
página que o extractor local já produz" — **não existe**: o Document
Intelligence devolve uma string só, com `<!-- PageBreak -->` entre as páginas.
Os spans saem desses marcadores, e o `content` nunca é reescrito (a confiança
por campo localiza por offset nele).

Por página, três sinais em regex: **título de embarque** (`PACKING LIST`,
`LOADLIST`, e a família fraca `DDT` / `DELIVERY NOTE` / `DOCUMENTO DI
TRASPORTO`), **rótulo de preço** (`UNIT PRICE`, `AMOUNT`, `PREZZO`, `PREÇO`...)
e **moeda solta**. Título forte com preço é `mixed` (vai ao modelo como fatura
e vira problema); título sem preço é `packing_list`; sem título, qualquer
dinheiro é `invoice`, e duas marcas de peso sem dinheiro é `packing_list`.
`INVOICE` sozinho pesa zero: packing list cita "Invoice No.".

**Calibrado no CIV (35 páginas, 6 fornecedores):** 17 páginas de fatura, 11
de embarque, nenhuma mista. Três coisas que a calibração ensinou e que o
teste trava (`check_structurer.py` seção 13, `check_rules.py`): fatura
italiana imprime `Netto` e cita a DDT como referência, e continua fatura; o
rodapé legal da Dana imprime `€` na página do packing list, e ela continua
packing list; e a família "nota de entrega" nunca é `mixed`, porque a própria
fatura a cita.

O modelo recebe a lista de páginas no user message e a regra 12 do prompt
(nunca criar item de página de embarque; usar só para peso e embalagem). Como
prompt é pedido e não contrato, o `_normalise` confere: linha cujo part number
só existe em página de embarque recebe problema (marcar, nunca descartar — e a
aritmética confirma, porque a linha a mais estoura o total). Documento em que
**nenhuma** página é fatura vai para revisão com "nenhuma página de fatura
identificada": é o "é invoice ou não" do contrato.

Sem migração: `page_kinds` vai no `raw_extraction.structured`, sai no payload
e aparece no painel "Decisões da extração" da revisão.

**"Provavelmente não é invoice" (14/10, leva 13).** A primeira versão só
reconhecia documento de embarque; carta, certificado ou contrato chegavam ao
modelo como fatura e caíam na revisão pela razão genérica. Agora o
`_normalise` marca o documento quando qualquer destes vale: nenhuma palavra
de título de fatura (`INVOICE`, `FATTURA`, `FATURA`, `FAKTURA`, `FACTURE`,
`FACTURA`, `RECHNUNG`, `NOTA FISCAL`) no documento **inteiro** — as páginas de
continuação do CIV não trazem a palavra, então nunca por página —; todas as
páginas são de embarque; o modelo não achou nenhuma invoice; ou metade ou mais
dos campos devolvidos não existem no texto (com pelo menos 4 campos).

A confiança média do OCR **não** entra, decidido com o Luis: ela mede a
leitura, não o tipo, e um terço do plano de aceitação é escaneado — fatura
real mal escaneada sairia como "não é invoice". Quem mede invenção é o campo
que não existe no texto. O CIV sai sem marca (1 campo não localizado em 52).
A marca aparece como faixa vermelha no topo da revisão, no padrão da
duplicata, e não bloqueia: o revisor rejeita se concordar.

**Não coberto:** pedido de compra, cotação e proforma têm preço e trazem
"invoice" no texto ("invoice to"), então passam como fatura. Separar exige
título próprio (`PURCHASE ORDER`, `QUOTATION`, `PROFORMA`) e documento real
para calibrar.

**Pendente, fora do código:** rodar `classify_pages` nos raw JSONs dos 10 PDFs
"Invoice + Packing List" do corpus (estão na máquina do Luis). O teste
sintético prova a mecânica; a cobertura das keywords em outras línguas é
hipótese até ser medida.

## 8 e 9

- **Relatório de confiança por fornecedor** — **feito em 01/10.** Página
  `/fornecedores` e `GET /suppliers/confidence` (+ `/detail`). Por fornecedor
  (`supplier_key` do item 6): confiança média e pior campo, invoices com campo
  a conferir, campos **corrigidos na revisão** sobre campos lidos — a medida de
  acerto que valida a própria nota — e o campo que mais dá trabalho. Ficam fora
  documento rejeitado ou com erro e cópia de duplicata, pelas mesmas razões do
  item 6. O período conta pela data do **documento**: o PATCH recria as
  invoices, e a data delas é a da última edição. Invoice sem nota (modo local,
  anterior à 0007) conta como invoice e não entra nas médias. A agregação é
  pura, em `shared/confidence.py`, e o teste está no `check_rules.py`.
- **Métricas de processamento por período** — **feito em 14/10.** Premissa
  "MÉTRICAS DE PERFORMANCE DO AGENTE, DE PROCESSAMENTO E POR PERÍODO".
  `GET /dashboard/metrics?days=` (0 = tudo) e a agregação pura em
  `shared/metrics.py`, testada no `check_rules.py`. Além das contagens: tempo
  de processamento (evento `processing` → `processed_at`) e upload → resultado,
  mediana e p90; fração de documentos terminados **sem** passar por revisão
  (rejeitado não conta como sucesso); campos corrigidos sobre pontuados;
  duplicatas. **Mudança de semântica:** `valor_total_extraido` deixa de somar
  cópia de duplicata, rejeitado e erro. O worker passou a gravar `processed_at`
  também no erro — o `created_at` do evento não serve de fim, porque o `now()`
  do Postgres é o início da transação. Tela: seletor 7/30/90/Tudo e a fileira
  de performance do agente.

  **Leva 13:** os números saíram da página de documentos, que ficou só com a
  lista e o upload, e foram para a aba **Performance** (`/performance`): cards
  do agente e de volume, barras por dia por desfecho (sem revisão, revisão,
  erro, em processamento) e o tempo mediano por dia. Gráfico em SVG, sem
  biblioteca — seria dependência nova no Artifactory da CAT. O dia é o de
  Brasília (em UTC, upload das 22h caía no dia seguinte), e dia sem documento
  entra com zero, para a parada aparecer.

## 15. Texto fora do alfabeto latino — feito em 08/10

Decisão: **ignorar todo vocabulário não latino.** Eram duas coisas diferentes:

- **A tela quebrava pelo nome do arquivo, não pelo conteúdo.** O `GET
  /documents/{id}/file` punha o nome cru no `Content-Disposition`, e cabeçalho
  HTTP é latin-1: `发票_6511308.pdf` dava `UnicodeEncodeError`, 500, e o
  visualizador de PDF da revisão ficava em branco. O nome agora vai em
  `filename*` (RFC 5987), com fallback ASCII em `filename`.
- **Os campos extraídos saem só com o latino.** Regra 9 no prompt (copiar a
  versão latina de valor bilíngue, nunca traduzir) e, como prompt não é
  contrato, `_latin_only` em toda string do payload dentro do `_normalise` —
  vale para Azure, modo local e mock. Acento latino fica (DOKTAŞ), forma de
  largura cheia vira ASCII (`ＰＮ６５１１３０８`), dígito e moeda ficam.

O texto do OCR **não** é filtrado: a confiança por campo localiza valores por
offset no `content`, e reescrevê-lo deslocaria tudo. Marcar, não descartar:
campo que perdeu parte do texto vira nota; campo que ficou **vazio** (supplier
só em chinês) vira problema e vai para revisão, porque um supplier nulo
desliga a checagem de duplicata sem avisar. O `invoice_number_source` é
exceção — é rótulo, não valor. Teste no `check_rules.py`.

## 10, 11 e 12 — o relatório de testes da CAT (19/10)

A CAT testou em duas etapas (até 14/09 e a partir de 02/10) e mandou 13
slides de erros. A análise completa, erro a erro, com o que já foi corrigido e
o que falta, está em `docs/relatorio-testes-cat-2026-10.md`. Resumo:

- **10 — Aritmética da linha e encargos (M) — feito em 19/10, leva 14.** O modelo copia o valor
  estendido no unitário (`2 × 6522600 = 36.826` sai com unitário 36.826, e a
  expansão por serial grava 73.652); `_num("0.162")` devolve 162; linha de
  encargo ("Packaging - Sales 86.00") ou de nota sem preço (0V3456 END USE,
  "CAIXA DE MADEIRA") fica na tabela ou some da conta; o rateio divide pela
  linha sem preço; e `freight`, `packaging_cost`, `unit_price_landed` nunca
  são gravados nem exibidos, embora o gabarito espere 395,16 = 388,46 + 603/90.
  Correção: derivar o unitário de `amount / qty` antes da expansão, consertar
  o `_num`, mover encargo de linha para `packaging_cost` / `freight`, descartar
  `other_code` sem preço nem valor, migração `0009` e colunas na tela.
  De carona, do mesmo relatório: a vírgula tinha o defeito do ponto
  (`5700,000` da Graziano lido como 5.700.000), e o `CAT 657-3755` da
  AutoMotionShade era descartado por não ter forma de código.
- **11 — Part number pela lista (M, depende do 3) — feito em 20/10, leva 15.** "Part number errado,
  MAIORIA": a linha imprime código do fornecedor e código do cliente
  (`148409` × `2396739`, `MN447750-31914C` × `290-2789`) e o modelo escolhe o
  do fornecedor. Resolver por linha com a lista de PN (um set `liberados`
  passado ao structurer, da mesma consulta do serial), `supplier_part_number`
  no item, e status `not_released` na tela como nota.
- **12 — Muitas faturas: a leva 16 (bloqueado).** 2026RFM04632 saiu com 14
  de 15; a fatura que faltou, reenviada sozinha, saiu certa. Esforço só se
  mede depois do diagnóstico.

  **Para destravar:** o PDF do 2026RFM04632 e o `raw_extraction` do documento
  gravado (o `GET /documents/{id}/raw`), que estão do lado do Luis e da CAT.

  **Hipóteses, na ordem de teste:**
  1. resposta do modelo truncada em `max_tokens = 16000` -- o JSON por
     fatura é verboso, e o `finish_reason` da resposta não é lido, então o
     truncamento não deixaria rastro se o modelo fechasse o JSON cedo;
  2. o modelo fundiu duas faturas numa;
  3. a fatura caiu numa página classificada como embarque (`pages.py`).

  **O que dá para fazer antes do PDF, barato:** ler o `finish_reason` e
  registrar "resposta truncada" como problema quando for `length`; e
  generalizar o aviso que hoje só existe para `CAT Invoice#` -- contar os
  rótulos distintos de número de fatura no texto e comparar com as invoices
  devolvidas. Se o truncamento se confirmar, a correção é chamar o modelo por
  grupo de páginas (o `pages.py` já dá os spans).

## 16 a 20 — os testes oficiais da CAT (22/10)

A segunda versão do relatório da CAT (25 slides, com a etapa de **testes
oficiais a partir de 19/10**, já sobre as levas 14 e 15) confirma resolvidos
os itens 5, 10 e 11 e traz cinco problemas sem item. A análise, erro a erro,
está em `docs/relatorio-testes-cat-2026-10-22.md`. Todos seguem o princípio
da leva 15: o prompt dá a direção, o código determinístico é o contrato, e a
lista de PN liberados é o árbitro quando a forma do texto não basta.

- **16 — PO (S).** `QIPP 068274` gravado como `068274`; três POs no cabeçalho
  (`QIPP65000、QIPP65001、QIPP92629、`) e nenhum gravado; "Order Number /
  Cust. PO" empilhados e o gravado foi o do fornecedor. O prompt não tem
  regra nenhuma sobre PO e nada valida a forma. Regra no prompt
  (`QIP?nnnnn`, rótulos, PO único do cabeçalho vale para as linhas) e
  `_resolve_purchase_order` determinístico: recompõe prefixo, troca pelo
  `QIP…` da mesma linha, preenche do cabeçalho quando é um só; vários sem
  mapeamento → problema, nunca escolhe.
- **17 — Número da fatura (S).** `DOCUMENT NO. 1270082320` não capturado
  (lista fechada de rótulos na regra 1); e o aviso "'CAT Invoice#' nao
  localizado" sai em todo documento sem o formato `AA00 000000` (10 dos 28 do
  corpus) e força revisão mesmo com o número certo. Aviso vira nota quando o
  modelo trouxe número localizado; rótulo `Document No.` aceito; fallback por
  rótulo nas páginas de invoice; generaliza a contagem de rótulos do item 12.
- **18 — Linha sem valor (S, depende do 3).** `0P-4349 INSTRUCTIONS N/C` e
  afins têm forma CAT, e `cat` é blindado em três lugares (`_charge_kind`,
  `sem_valor`, `kind and value`); `0` não é `None`. Valor zero **e** fora da
  lista → descartada com motivo; valor zero **e** na lista → fica, com nota
  "item sem cobrança". A soma não muda nos dois casos, por isso a lista é o
  critério.
- **19 — Sufixo do part number (M, depende do 3).** `5531000/S` gravado com
  sufixo (a base é calculada mas não persistida) e o modelo ainda preenche
  `supplier_part_number` com o mesmo código; `5657043-CBL` vira `other_code`
  porque o sufixo só aceita `-NN`. Gravar a base, persistir
  `part_number_suffix` (migração 0011), sufixo alfabético só quando a base
  está na lista, descartar `supplier_part_number` e serial iguais ao próprio
  código.
- **20 — Encargos (M).** Frete e embalagem de rodapé dependem só do modelo;
  o texto de embalagem é copiado para todas as linhas; e o cliente quer
  encargo geral sem rateio, o que conflita com o gabarito (395,16 =
  388,46 + 603/90). Varredura determinística do bloco de totais alimentando o
  `_merge_charge`; texto de embalagem na invoice, não por linha; o rateio
  espera a resposta da pergunta 8.

Segundo caso do item 12: **CIV FFAU5762790, 10 de 18 faturas.** Reforça a
hipótese do truncamento (18 faturas é mais JSON que 15). Pedir o
`raw_extraction` dele também.

---

## Perguntas em aberto para a CAT

1. O que são **`CSAR`**, **`PFO`** e **`##`**? Não aparecem em nenhum dos 28
   documentos que temos.
2. **`Invoice Type`** e **`Import Process`** vêm do documento ou são atribuídos
   pelo despachante? No gabarito o `Processo` é constante no arquivo inteiro, o
   que sugere atribuído.
3. Quais **incoterms tornam `Domestic Freight` obrigatório**? A própria planilha
   diz "MAPEAR".
4. ~~Nas CIVs de motor o cabeçalho é `Part Number / Serial Number / Pin Number`,
   com três valores para quatro colunas (`6511308  F4E09020  ENGINE`).
   `F4E09020` é Serial ou PIN?~~ **Respondido em 24/09** — é motor → Serial;
   não é motor → PIN. Ver item 4. Fica em aberto **quais são os "outros"** que
   a planilha manda mapear.
5. ~~`Latino` / `Full Não Latino` na `FASES_LEITURA` — quais documentos e quais
   alfabetos?~~ **Decidido em 08/10:** fora do latino é ignorado.
6. Com que frequência a **lista de PN** é atualizada? Define se o import precisa
   de versionamento ou se sobrescrever basta.
7. O gabarito tem `Adição 6` **duplicada** em duas faturas, com o total da
   adição repetido nas duas linhas (30 × 569,46 = 17.083,80, mas as duas dizem
   34.167,60). É intencional?
8. Unitário na tela: o impresso com "unitário com encargos" ao lado (proposta),
   ou substituir pelo rateado? E o divisor do rateio: unidade, valor ou peso?
9. Fabricante ausente do documento (Carraro): vazio ou igual ao fornecedor,
   com nota?
10. 2026RFM04632 (14 de 15 faturas) e CIV FFAU5762790 (10 de 18): precisamos
    do PDF e do `raw_extraction` dos dois.
11. **Todo PO Caterpillar é `QIP?` + dígitos?** Nos 28 PDFs são `QIPP`, `QIPD`
    e `QIPC`. Define o item 16.
12. Rateio, de novo (pergunta 8): o usuário disse em 19/10 que encargo fora da
    linha "é geral", mas o gabarito pede rateado. Qual vale? Define o item 20.
