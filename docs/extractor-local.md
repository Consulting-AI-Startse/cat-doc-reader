# Extractor local (Docling) — só para desenvolvimento

## A decisão

Existe um terceiro modo de extração, além de `mock` e Document Intelligence:
um extractor local baseado em [Docling](https://github.com/docling-project/docling),
que converte o PDF em markdown na máquina do desenvolvedor.

**Ele nunca vai para a VM da Caterpillar nem para o repo da CAT.** Não é uma
alternativa de produção e não deve ser tratada como tal. Serve para uma coisa
só: exercitar o structurer — prompt, parsing, regras de part number, rateio de
embalagem — com texto real de documento, sem gastar chamada paga do Document
Intelligence e sem depender de rede da CAT.

## Como é garantido que fica fora do deploy

Três barreiras independentes, para que esquecer uma não vaze nada:

| barreira | onde | efeito |
|---|---|---|
| dependência separada | `function/requirements-local.txt` | o build remoto do Oryx lê `requirements.txt`, nunca este |
| exclusão do pacote | `function/.funcignore` | o módulo e o requirements não entram no zip |
| import condicional | `doc_worker.build_extractor()` | só importa com `USE_LOCAL_EXTRACTOR=true`, setting que não existe no Function App |

## Como ligar, localmente

```bash
# torch pelo indice de CPU: a resolucao padrao puxa a stack CUDA inteira (varios GB)
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
uv pip install -r function/requirements-local.txt
```

No `.env` local:

```
USE_LOCAL_EXTRACTOR=true
LOCAL_EXTRACTOR_FORCE_OCR=false
USE_REAL_SERVICES=true      # ver a matriz abaixo
```

`LOCAL_EXTRACTOR_FORCE_OCR=true` ignora a camada de texto e OCRa a página
inteira. Ajuda quando a camada de texto é ruim; atrapalha quando é boa.

### A matriz que importa

`USE_LOCAL_EXTRACTOR` decide **só o extractor**, e tem precedência sobre
`USE_REAL_SERVICES`. Quem escolhe o structurer continua sendo
`USE_REAL_SERVICES`:

| `USE_LOCAL_EXTRACTOR` | `USE_REAL_SERVICES` | extractor | structurer | serve para |
|---|---|---|---|---|
| false | false | Mock | Mock | subir a UI com dados de mentira |
| false | true | Document Intelligence | Azure OpenAI | produção |
| true | **true** | **Docling** | **Azure OpenAI** | **testar parsing do LLM com texto real** |
| true | false | Docling | Mock | quase inútil, ver abaixo |

A última linha é uma armadilha: o `MockStructurer` monta os invoices a partir
de `extraction["invoices"]`, e o Docling devolve essa lista vazia porque não tem
modelo de invoice. O documento sai sem nenhuma linha. Se a ideia é testar
parsing, ligue os dois.

Custo local: ~1,5 GB de venv com torch CPU, mais ~500 MB de modelos em
`~/.cache/huggingface` (uma vez só).

## O que foi medido

Tudo abaixo é medição no corpus real, não estimativa.

| documento | resultado |
|---|---|
| Fatura turca (1 pág., PDF nativo) | **ótimo**. Tabela de itens em markdown, `7G-5837`, `9G-9180`, `473-7719`, decimais europeus (`6.398,88`) intactos. 14 s |
| CIV, páginas 1–3 (escaneadas, de pé) | **ótimo**. `ocr_score` 0.997, 7 dos 8 part numbers. 22 s |
| CIV, páginas 4–6 (escaneadas, giradas −179.8°) | **falha total**. RapidOCR devolve vazio: 62 caracteres, 0 part numbers |
| CIV inteiro (35 pág.), sem forçar OCR | 4.670 chars e 1 tabela, contra **83.641 chars e 98 tabelas** do Document Intelligence |

A causa é rotação de página, não qualidade de scan — as páginas de pé do mesmo
documento saem perfeitas. O Document Intelligence rotaciona sozinho e não perde
nada: das 35 páginas do CIV, 11 estão a 180° e 4 a 90°, e a confiança média por
palavra fica igual (0.9747 nas de pé, 0.9734 nas invertidas). O Docling não faz
isso.

Por isso o extractor **estoura em vez de devolver texto vazio**: abaixo de 150
caracteres por página ele levanta `LocalExtractionFailed` com os scores. Texto
vazio chegando no LLM vira invenção, e foi exatamente o que vimos o LlamaExtract
fazer nas colunas que não existiam no documento.

## O que este modo não faz

Não há confiança por palavra nem span por palavra — o Docling pontua por
página (`layout_score`, `ocr_score`, `table_score`, `parse_score`). Logo **a
confiança por campo não funciona neste modo**. O `quality` devolvido marca isso
explicitamente com `word_confidence_available: false`.

`invoices` volta vazio: o Docling não tem modelo de invoice, então não há
pre-pass. O structurer já trata lista vazia.

## Como remover por completo

```bash
git rm function/pipeline/extractor_local.py function/requirements-local.txt docs/extractor-local.md
```

E tirar:

- as duas linhas do `function/.funcignore`;
- o bloco de três linhas em `doc_worker.build_extractor()` (está comentado como
  bloco de desenvolvimento local);
- `use_local_extractor` e `local_extractor_force_ocr` em `shared/shared/config.py`;
- a seção correspondente no `STRUCTURE.md`.

Nada mais depende dele.
