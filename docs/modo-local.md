# Modo local — extractor (Docling) e structurer (OpenRouter)

## A decisão

Existem dois componentes de desenvolvimento que substituem os serviços da
Azure, cada um do seu lado do pipeline:

| componente | substitui | arquivo |
|---|---|---|
| `DoclingExtractor` | Document Intelligence | `function/pipeline/extractor_local.py` |
| `OpenRouterStructurer` | Azure OpenAI | `function/pipeline/structurer_local.py` |

**Nenhum dos dois vai para a VM da Caterpillar nem para o repo da CAT.** Não
são alternativas de produção. Servem para exercitar o pipeline — prompt, regras
de part number, rateio de embalagem, parsing do JSON — com documento real, sem
gastar serviço pago e sem depender da rede da CAT.

## Como é garantido que ficam fora do deploy

| barreira | onde | efeito |
|---|---|---|
| dependência separada | `function/requirements-local.txt` | o build do Oryx lê `requirements.txt`, nunca este. Vale só para o Docling: o structurer não tem dependência nova, o `openai` já está lá por causa do Azure |
| exclusão do pacote | `function/.funcignore` | os dois módulos, o requirements local e o `.env.local` não entram no zip |
| import condicional | `doc_worker.build_extractor()` / `build_structurer()` | só importam com `USE_LOCAL_EXTRACTOR` / `USE_LOCAL_STRUCTURER`, settings que não existem no Function App |

## Subir o ambiente

```bash
./start-local.sh          # sobe azurite, func, backend e frontend
./start-local.sh --status # so mostra o que esta de pe
./stop-local.sh           # derruba (Postgres fica, e servico do sistema)
```

Pre-requisitos, uma vez por maquina:

```bash
npm i -g azurite azure-functions-core-tools@4
cd function && uv venv --python 3.11 .venv   # 3.11 = runtime da function na Azure
uv pip install --python .venv/bin/python -r requirements.txt
```

O `start-local.sh` roda o `scripts/build.sh` antes de tudo, porque a function
importa `shared` de uma copia vendorizada e nao do pacote: `shared/pyproject.toml`
declara `requires-python = ">=3.14"` enquanto o runtime da function e 3.11, entao
instalar como pacote nao resolve. O deploy faz exatamente o mesmo.

No Windows/VM o equivalente e o `start-local.ps1`.

## Configuração

```bash
# docling: o indice de CPU evita baixar a stack CUDA inteira (varios GB)
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
uv pip install -r function/requirements-local.txt
```

`.env.local` na raiz — já coberto pelo `.gitignore` via `.env.*`, e lido com
precedência sobre `.env`:

```
USE_LOCAL_EXTRACTOR=true
USE_LOCAL_STRUCTURER=true
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4.1
```

Opcionais: `LOCAL_EXTRACTOR_FORCE_OCR` (ignora a camada de texto e OCRa a
página inteira — ajuda quando a camada é ruim, atrapalha quando é boa) e
`OPENROUTER_MAX_TOKENS` (padrão 16000; alguns modelos capam mais baixo).

Variável de ambiente vence o `.env.local`, que vence o `.env`.

### A matriz

As duas settings locais têm precedência sobre `USE_REAL_SERVICES` e decidem
cada uma o seu lado:

| `USE_LOCAL_EXTRACTOR` | `USE_LOCAL_STRUCTURER` | `USE_REAL_SERVICES` | extractor | structurer |
|---|---|---|---|---|
| false | false | false | Mock | Mock |
| false | false | true | Document Intelligence | Azure OpenAI |
| **true** | **true** | false | **Docling** | **OpenRouter** |
| true | false | false | Docling | Mock — **inútil**, ver abaixo |
| false | true | true | Document Intelligence | OpenRouter |

A quarta linha é a armadilha: o `MockStructurer` monta os invoices a partir de
`extraction["invoices"]`, e o Docling devolve essa lista vazia porque não tem
modelo de invoice. O documento sai sem nenhuma linha, mesmo com o OCR tendo
funcionado. Se a ideia é testar parsing, ligue os dois.

## Aviso de dado

O structurer local envia o **texto do documento** para uma API de terceiros,
que roteia para o provedor do modelo escolhido. São part numbers, preços e
condições comerciais de fornecedores da Caterpillar. Isso é uma decisão de
governança, não um detalhe técnico — é a mesma fronteira dos `.env` que
removemos do histórico, só que aqui o que sai é conteúdo, não identificador.

Use com o corpus que já está na sua máquina e com aval da StartSe. Nunca a
partir da VM.

## O que o structurer local reaproveita

Tudo. `OpenRouterStructurer` herda de `AzureOpenAIStructurer` e sobrescreve só
o `__init__`: troca o cliente e o nome do modelo. O `structure()` vem herdado
sem uma linha alterada, e com ele `_SYSTEM_PROMPT`, `_USER_TEMPLATE`,
`_cat_invoice_numbers`, `_check_lines`, `_classify_part_number`, `_landed` e
`_normalise`.

Isso é de propósito: o que está sendo testado tem de ser o prompt e o parsing
de produção, não uma cópia que pode divergir em silêncio.

`response_format={"type":"json_object"}` não é suportado por todo modelo do
OpenRouter. A classe avisa no log quando o modelo escolhido está fora da lista
conhecida (`openai/`, `anthropic/`, `google/gemini`, `mistralai/`). Se o
parsing falhar com `JSONDecodeError`, é o primeiro lugar para olhar.

## Como cada etapa falha

Regra das duas etapas: **nada passa calado**. Ou estoura, ou deixa nota em
`validation`. Documento gravado sem explicação é bug, não resultado.

### Extractor (Docling)

| situação | comportamento |
|---|---|
| docling não instalado | `ImportError` no construtor, dizendo para instalar `requirements-local.txt` |
| texto abaixo de 150 chars/página | `LocalExtractionFailed` com os scores — é o caso da página girada |
| PDF ilegível / corrompido | exceção do próprio Docling, propagada |
| scores `nan` | viram `null` no JSON, nunca `NaN` (que quebraria o `jsonb`) |

### Structurer (OpenRouter)

| situação | comportamento |
|---|---|
| `OPENROUTER_API_KEY` ausente | `ValueError` no construtor, apontando o `.env.local` |
| modelo sem suporte a modo JSON | `logger.warning` no construtor com a lista dos conhecidos |
| erro HTTP / rate limit / sem crédito | exceção do SDK `openai`, propagada |
| resposta não é JSON | `JSONDecodeError` — ver o aviso de modo JSON acima |
| **resposta é JSON válido mas sem invoices** | nota em `validation` e confiança 0.0 |

A última linha era uma falha silenciosa de verdade e foi corrigida em
`_normalise`, não aqui: o modelo devolvia `{}` ou `{"invoices": []}`, o
documento era gravado sem nenhuma linha e quem revisasse abria uma tela vazia
sem explicação. A confiança zerada já mandava para `needs_review`, mas sem
dizer por quê. Agora sai:

```
modelo nao devolveu nenhuma invoice (chaves recebidas: ['invoices']);
documento gravado vazio
```

Vale para o Azure OpenAI também — por isso a correção está no caminho de
produção, não no arquivo local.

## Dois caminhos: PDF e, se preciso, imagem

O extractor tenta primeiro o caminho **PDF**, em que o Docling usa a camada de
texto. É rápido e sai perfeito em PDF nativo. Depois conta os caracteres **por
página** e, para as páginas magras (< 150 chars), renderiza a página e converte
como **imagem**.

O fallback é por página, não por documento, e isso importa: no CIV as páginas 1
e 2 têm texto de verdade (913 e 1011 chars) e as outras 33 vêm vazias. Uma média
de documento daria 133 chars/página e reprovaria o arquivo inteiro — inclusive
as duas páginas boas.

| medição | resultado |
|---|---|
| Fatura turca (PDF nativo) | caminho `pdf`, 1.788 chars, 1 tabela, **14 s**. Os três part numbers |
| CIV páginas 4–6, caminho PDF | **62 chars, 0 tabelas** — o Docling perde essas páginas |
| CIV páginas 4–6, como imagem | 1.878 chars |
| CIV 6 páginas, `pdf+image` | 10.694 chars e **8 de 8 part numbers**, contra 4.581 e 7 de 8 só pelo PDF |

Não é resolução: `images_scale` 1.0 e 2.0 dão os mesmos 62 chars pelo caminho
PDF. É o caminho PDF→OCR do Docling que se perde nessas páginas.

Custo: ~13 s por página recuperada por imagem. Documento nativo não paga nada
disso, porque nenhuma página fica magra.

### Rotação: limite conhecido, não resolvido

Girar a página **não** muda o reconhecimento dos caracteres — o RapidOCR tem
classificador de ângulo por linha e acerta as letras de qualquer jeito. Muda a
**ordem de leitura** e o layout. Numa página a 180° sai
`35.564,40 Invoice Amount Payable` em vez de `Invoice Amount Payable 35.564,40`,
e o modelo de tabela não encontra tabela nenhuma.

Medido na página 4 do CIV: sem girar 1.878 chars e 0 tabelas; girada 180° 2.920
chars e **2 tabelas**, com a ordem certa.

Duas coisas foram testadas para detectar a rotação automaticamente e **as duas
falharam**:

- **Geometria** (perfil de projeção para achar o eixo do texto + assimetria de
  tinta para separar 0° de 180°): 7 acertos em 35 páginas, pior que os ~25% do
  acaso.
- **Sonda de OCR** nas quatro orientações: as margens são ruído — 0.992 contra
  0.991 de confiança, 882 contra 887 caracteres. Faz sentido, já que o texto
  reconhecido é o mesmo; só a ordem muda.

O sinal confiável é o **layout** (tabela encontrada), mas isso exige uma
conversão completa por orientação, e cada `convert()` do Docling não devolve a
memória: com 7 GB, duas orientações por página levam a OOM, testado a 150 e a
100 dpi. Por isso a sonda **não foi para o código**.

Efeito prático: página girada sai com o texto certo, fora de ordem e sem tabela
— e ainda assim os part numbers são recuperados (8 de 8 no trecho testado).

O extractor **estoura em vez de devolver texto vazio**: abaixo de 150 caracteres
por página, e já tendo tentado o caminho por imagem, levanta
`LocalExtractionFailed` com os scores. Texto vazio chegando no LLM vira invenção
— foi o que vimos o LlamaExtract fazer nas colunas que não existiam no
documento.

## O que o modo local não faz

Não há confiança por palavra nem span por palavra — o Docling pontua por página
(`layout_score`, `ocr_score`, `table_score`, `parse_score`). Logo **a confiança
por campo não funciona neste modo**. O `quality` devolvido marca isso com
`word_confidence_available: false`.

## Como remover por completo

```bash
git rm function/pipeline/extractor_local.py \
       function/pipeline/structurer_local.py \
       function/requirements-local.txt \
       docs/modo-local.md
```

E tirar:

- as quatro linhas de exclusão do `function/.funcignore`;
- os dois blocos marcados como desenvolvimento local em
  `doc_worker.build_extractor()` e `build_structurer()`;
- `use_local_extractor`, `local_extractor_force_ocr`, `use_local_structurer` e
  as três `openrouter_*` em `shared/shared/config.py`;
- `.env.local` de `model_config` no mesmo arquivo, se não houver outro uso;
- a seção correspondente no `STRUCTURE.md`.

Fica no lugar, de propósito, o `self._max_tokens` em `AzureOpenAIStructurer`:
é atributo em vez de literal para a subclasse local poder ajustar sem duplicar
`structure()`, e sem ela o comportamento é idêntico ao de antes (16000).
