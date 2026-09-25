# BACKLOG

Próximas features, ponderadas. A ordem é do mais fácil para o mais difícil, com
uma inversão deliberada (item 3), explicada abaixo.

Esforço: **XS** < 1h · **S** ~meio dia · **M** ~1–2 dias · **L** ~1 semana

| # | item | esforço | valor | depende |
|---|---|---|---|---|
| ~~1~~ | ~~Poison handler grava status `error`~~ | XS | alto | **feito** |
| 2 | `Unit` e `Unit Weight` | S | médio | — |
| 3 | Lista de PN: tabela, import CSV e checagem | M | **muito alto** | — |
| 4 | Serial Number (tabela própria + regra ENGINE) | M | alto | 3 |
| 5 | Confiança por campo e geral | M | alto | — |
| ~~6~~ | ~~Duplicatas por (invoice, fornecedor)~~ | M | médio | **feito** |
| 7 | Classificação invoice × packing list | L | alto | — |
| 8 | Relatório de confiança por fornecedor | M | médio | 5 |
| 9 | Métricas de processamento por período | M | médio | — |
| — | `Invoice Type`, `Import Process`, `CSAR`, `PFO`, `##` | ? | ? | **bloqueado** |
| — | Não-latino; Word/Excel | ? | ? | **escopo indefinido** |

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
não foi definido pelo cliente.

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

## 2. `Unit` e `Unit Weight` (S)

Dois campos que o cliente pede e não temos. `Unit` é mandatório (a unidade:
`pcs`, `kg`). `Unit Weight` é o `Peso Unitário` do gabarito, com verdade
conhecida para conferir (`3649717 → 19,81`).

- migração `0004`: `unit` `String(16)` e `unit_weight` `Numeric(18,5)` em
  `invoice_part_number_items`
- `shared/shared/models.py`, o dict emitido em `structurer._normalise`, o shape
  do prompt, `_serialize_line` e `LineIn` em `backend/app/api/documents.py`

## 3. Lista de PN Liberados (M)

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
do catch-all) e linkada no `AppShell.tsx`, que hoje não tem menu.

Dois detalhes achados na exploração:

- `components/FileUpload.tsx` é reaproveitável mas está **hardcoded em PDF em
  três pontos** (teste `.pdf`, `accept=".pdf"`, preview em `<iframe>` e o texto
  "Arraste o documento (PDF) aqui"). Precisa de props `accept` / `match` /
  `hint` e preview opcional — para CSV o análogo é uma tabela das primeiras
  linhas, não um iframe.
- `api/client.ts` descarta o corpo do erro (`throw new Error(status)`), então o
  `detail` do FastAPI nunca chega à tela. Para relatar erro por linha do CSV,
  estender `api()`.

## 4. Serial Number (M)

Mandatório, e a premissa "TELA DE MANUTENÇÃO PARA ITENS COM SERIAL NUMBER" diz
que serial é entidade de primeira classe. Então **tabela própria**, uma linha
por serial.

Migração `0006`: `invoice_item_serial_numbers` (`id`, `item_id` FK CASCADE,
`serial_number` `String(64)` indexado, `created_at`).

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

## 5. Confiança por campo e geral (M)

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

## 7. Classificação invoice × packing list (L)

Premissa: "IDENTIFICAR AQUILO QUE É UMA INVOICE OU NÃO". São **10 dos 30
documentos** do plano de aceitação, e hoje não temos nada: mandamos o documento
inteiro para o LLM e torcemos para ele ignorar o packing list.

Decisão por página, aproveitando o markdown por página que o extractor local já
produz.

## 8 e 9

- **Relatório de confiança por fornecedor** — depende de 5 e da normalização do 6.
- **Métricas de processamento por período** — premissa "MÉTRICAS DE PERFORMANCE
  DO AGENTE, DE PROCESSAMENTO E POR PERÍODO".

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
5. `Latino` / `Full Não Latino` na `FASES_LEITURA` — quais documentos e quais
   alfabetos?
6. Com que frequência a **lista de PN** é atualizada? Define se o import precisa
   de versionamento ou se sobrescrever basta.
7. O gabarito tem `Adição 6` **duplicada** em duas faturas, com o total da
   adição repetido nas duas linhas (30 × 569,46 = 17.083,80, mas as duas dizem
   34.167,60). É intencional?
