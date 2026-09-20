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

## O que foi medido no extractor

Tudo abaixo é medição no corpus real, não estimativa.

| documento | resultado |
|---|---|
| Fatura turca (1 pág., PDF nativo) | **ótimo**. Tabela de itens em markdown, `7G-5837`, `9G-9180`, `473-7719`, decimais europeus (`6.398,88`) intactos. 14 s |
| CIV, páginas 1–3 (escaneadas, de pé) | **ótimo**. `ocr_score` 0.997, 7 dos 8 part numbers. 22 s |
| CIV, páginas 4–6 (escaneadas, giradas −179.8°) | **falha total**. RapidOCR devolve vazio: 62 caracteres, 0 part numbers |
| CIV inteiro (35 pág.) | 4.670 chars e 1 tabela, contra **83.641 chars e 98 tabelas** do Document Intelligence |

A causa é rotação de página, não qualidade de scan — as páginas de pé do mesmo
documento saem perfeitas. Das 35 páginas do CIV, 11 estão a 180° e 4 a 90°, e o
Document Intelligence rotaciona sozinho sem perder nada (confiança média 0.9747
nas de pé contra 0.9734 nas invertidas). O Docling não faz isso.

Por isso o extractor **estoura em vez de devolver texto vazio**: abaixo de 150
caracteres por página levanta `LocalExtractionFailed` com os scores. Texto vazio
chegando no LLM vira invenção — foi o que vimos o LlamaExtract fazer nas colunas
que não existiam no documento.

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
