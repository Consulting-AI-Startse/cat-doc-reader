# Log de espelhamento para o repo da CAT

Registro de tudo que saiu daqui para o `AICOE_AIagent_DocumentReader_POV`.
**Toda leva nova entra aqui**, no topo, assim que o PR for aberto — e o estado
atualizado quando ele for merjado.

Existe porque os dois repos têm históricos independentes: sem este arquivo não
há como saber, olhando o git, o que já foi espelhado e o que ainda não foi.

Formato de cada entrada: data, o que foi, como foi transportado, a branch e o
estado do PR.

---

## 2026-09-25 — leva 4: duplicatas, regra 6 do prompt e catch-up · **PR não aberto**

15 arquivos, por ZIP em base64, com **script autocontido** no lugar do LEIA-ME
em prosa (`aplicar-leva4.b64` -> `.txt` -> `Invoke-Expression`). O script traz
todos os valores esperados embutidos e para na primeira divergencia; nao sobra
conferencia para o operador. Testado contra uma reconstrucao da arvore da CAT:
aplica limpo, detecta leva ja aplicada e para **sem escrever** quando um
arquivo diverge. Branch sugerida:
`feat/duplicate-invoices-and-printed-numbers`.

**A conferência de blobs mudou o escopo da leva, e valeu por si.** Pedi os
blobs da VM antes de montar o pacote, como manda o fluxo. Dos 10 que pedi
primeiro, 2 divergiram — e a busca dos hashes no nosso histórico mostrou que
não era trabalho da CAT: os arquivos é que nunca tinham sido espelhados.
`backend/app/api/documents.py` estava na versão de **27/08**, a do
`init: first deployable commit`.

Como a suposição "a CAT == nosso último ponto espelhado" tinha acabado de ser
falsificada, pedi o `git ls-tree -r HEAD` inteiro dos caminhos que espelham.
Resultado dos 63 arquivos: **48 idênticos, 12 atrasados, 3 novos, 0 exclusivos
da CAT**. A leva passou de 13 para 15 arquivos.

O `shared/shared/config.py` foi o caso do `doc_worker.py` de novo: o blob de lá
não existia em commit nenhum daqui porque a versão da CAT é "o nosso HEAD menos
o bloco de modo local", estado que nunca foi commitado. 24 linhas a mais do
nosso lado, 1 modificada, **zero linhas exclusivas de lá**.

Brinde: o blob do `doc_worker.py` bate com `c70c235`, ou seja, a extração do
modo local já chegou lá. Depois desta leva os dois arquivos ficam idênticos e a
divergência que o `CLAUDE.md` acompanha se encerra.

**O que vai:**

- **Duplicatas por (número + fornecedor).** `supplier` sobe de
  `invoice_part_number_items` para `invoices`; chave normalizada em
  `shared/shared/dedupe.py`; só a cópia é marcada, com faixa visual na invoice
  e link para a original; migração `0004`.
- **Regra 6 do prompt.** O modelo copia o número como impresso e o `_num()`
  converte. Medido: o mesmo documento dava `22944.02` em 4 runs e `22.94` em 4.
  Depois da mudança, 5/5 corretos contra o modelo de verdade.
- **Catch-up:** `shared/shared/config.py` e `backend/app/processing.py`, sem
  relação com as duas features — só atraso acumulado.

**Atenção no deploy:** traz migração. O job `migrate` do `app-deploy.yml` falha
de propósito; `alembic upgrade head` é manual, pelo webssh do fastapi.

| | |
|---|---|
| SHA-256 do `.b64` | `96eaf5bbb7ceae479d2ca7fda99b4a8e38363da83d59bfcad73f3da64befbf5a` |
| SHA-256 do `.zip` | `29f04d892ed0a9cebee38730445cf869ccead2569f4d1cf224d65da037806d58` |
| bytes do `.b64` / `.zip` | 61734 / 45698 |

| arquivo | base (tem de estar la) | depois (fica assim) |
|---|---|---|
| `aiagent-documentreader-infrastructure-azure/workflows/app-ci.yml` | `5fa4d59c6bfd17efbcfba0a0cd5048d624c9d16d` | `67e193ed5711805377d2a61ed8736668c0d7f31e` |
| `aiagent-documentreader-infrastructure-azure/workflows/app-deploy.yml` | `4b70c9a8f4ff005e6784b1da9e39e334d8ded363` | `995da844d4c71aa5cf48fc5347e3829e2a7a477c` |
| `backend/alembic/versions/0004_supplier_on_invoice_and_duplicates.py` | `— novo —` | `2f3cbeb55d915d07d0ae26ef1dbc4133a4f815b1` |
| `backend/app/api/documents.py` | `d955c45f9ca86bd4d3b9b8b4d4ab961ffdc8425c` | `21d2d882ee1f22b8377ded62fe4b0f603231d43e` |
| `backend/app/processing.py` | `c9f147646a7b8beee9cc9f4f240034c9133d3c59` | `ba7a926cd478d38bb3a970a37fce1afae19aea00` |
| `check_dedupe.py` | `— novo —` | `d96bf376a54be954f6dd0a241a1c9e1154ae905d` |
| `check_rules.py` | `8a5323e49d54d5234cd130dc4a4ae39acafdd1ee` | `a38555f6a289086a1af9ccb8d4f30d25cc87ab89` |
| `check_structurer.py` | `1c98c949e0dbe8244f9c1f0907c5bb38dcf86a60` | `cd7809898c18c665d4f88b185e582327cc8de6e3` |
| `frontend/src/pages/DocumentDetail.tsx` | `ad1f1bdb1c4b04d20428494adac0e7fbb550578c` | `e6c5434e18abf780145f9322c26e09c7ac04e4ce` |
| `frontend/src/types/document.ts` | `3b96e3238957c1ebf961ab4ee085de4dae3962eb` | `6ed2264de618a8e475d08912d5d50ef43e87dba0` |
| `function/doc_worker.py` | `618767fec7293e74f165df1eeaf4513647ec6a14` | `799befdd6d8a5f5877e27de365e1a2b18bcb9cc0` |
| `function/pipeline/structurer.py` | `efe9af2c22eb1718cb76bb4dcc568875ec754fa4` | `65fcea67e15e71c619644315fccbd6f614406c29` |
| `shared/shared/config.py` | `9165b0ab7715285dd61d00f16e024750d47ddfeb` | `ec472196cc10cd0dac8f5d5bcfff9cfb15291259` |
| `shared/shared/dedupe.py` | `— novo —` | `3ef88c95396a5076c51399e0cfff463f822363e5` |
| `shared/shared/models.py` | `2b376cdf66d4583e6650165d84dbd32f16d8cc4d` | `531a1f7e08562e558ec5aaa30fadb6486c7a6760` |

---

## 2026-09-22 — leva 3: autenticação do deploy · **merjado**

Um arquivo, `app-deploy.yml`, que vai para **dois lugares**: o diretório de
infraestrutura (que espelha) e `.github/workflows/` (que executa).

**O que quebrou.** Primeiro run do deploy depois da leva 2: `azure/login@v2`
falhou com `Ensure 'subscription-id' is supplied or 'allow-no-subscriptions' is
'true'`. Os quatro jobs pediam `secrets.AZURE_SUBSCRIPTION_ID`, que não existe
no repo da CAT — o login recebeu string vazia. Na captura do run, `client-id` e
`tenant-id` saem como `***` e `subscription-id` **não aparece**: ausência do
campo é o sintoma de valor vazio.

**A convenção certa estava no repo o tempo todo.** `docs/cat-cd/` tem os três
workflows de infraestrutura, e os três carregam `.github/variables/*.env` para o
`GITHUB_ENV` num passo dedicado e usam `env.AZURESUBSCRIPTIONID`. Conferido na
VM: `pov.env` traz `AZURESUBSCRIPTIONID` **e** `RESOURCEGROUPNAME` (só os nomes
das chaves foram lidos, nunca os valores).

**O que muda:** passo `Carregar as variaveis` nos quatro jobs,
`env.AZURESUBSCRIPTIONID` no login, `env.RESOURCEGROUPNAME` nos seis `az` (vinha
de `vars.`, e pelo mesmo motivo estava vazio — seria a falha seguinte, num
`az webapp deploy -g ""`), passo de derivação do RG como rede de segurança, e um
`checkout` no job `settings`, que não tinha e portanto não teria os `.env` para
ler.

| | base | depois |
|---|---|---|
| `workflows/app-deploy.yml` | `42ababc3` | `4b70c9a8` |

**Transporte:** `leva3.b64`, 7899 bytes,
`641db7edbb9a385d8d6587cb1be6f1ea4da66bfeb8a3764fce8841d183a81a53`; o `.zip` é
`b3524f8fc03830944ff5148a5c323928cc887a6ad05abcc7dd0ee011fb553556`. LEIA-ME em
base64 à parte: `LEIA-ME-LEVA3.b64`, 6627 bytes,
`d561a208c7aec44c173f3350b2a767b9636aa18abf02b4d3d0abc329b8887ca8`.

**A lição foi para o `CLAUDE.md`:** workflow novo confere autenticação e nomes
de variável contra `docs/cat-cd/` antes de sair, não depois do run falhar.

**Validada contra a Azure em 2026-09-22.** `workflow_dispatch` →
`settings-only` a partir da `main`: `Settings da function (B2)` verde em 26s, os
três jobs de publicação e a migração pulados, como esperado. O verde implica o
`Verificar` com `exit 0` — as dez settings presentes e nenhuma truncada.

Conferido antes de disparar: o `DATABASE_URL` em produção é **idêntico** ao que
o job grava, e `USE_REAL_SERVICES`, `gpt-4.1` e `AZURE_DOCINTEL_HIGH_RES`
também — o run era efetivamente um no-op, que era o ponto. O resource group é
`aicoe_aiagent_documentreader_pov`, **não** o derivado
`aiagent-documentreader-pov`: ler o `pov.env` era mesmo necessário, e o passo de
derivação nunca será usado.

**Estado:** aplicada na VM, merjada na `main` e validada em 2026-09-22.

---

## 2026-09-22 — LEIA-ME refeito da leva 2 · **merjado**

Não é leva nova: é a **segunda tentativa de aplicar a leva abaixo**, que falhou
na VM por dois motivos independentes. O `leva2.b64` não mudou e chegou íntegro;
o que foi reenviado foi só o arquivo de instruções.

**O que falhou:**

1. **O LEIA-ME foi mandado em texto puro.** O filtro de links reescreveu
   `function\doc_worker` + extensão dentro dele (a extensão é TLD do Paraguai),
   virando um `urldefense` no meio do caminho. O PowerShell leu `function\https`
   como nome de drive: `DriveNotFoundException`. **Exatamente a armadilha que a
   leva do poison handler já tinha registrado** — a regra existia, não foi
   seguida. Agora o LEIA-ME também vai em base64, e os nomes de arquivo dentro
   dele são montados em pedaços.
2. **A conferência de hash não podia dar certo.** O LEIA-ME trazia SHA-256 dos
   4 arquivos a sobrescrever, calculados aqui, em LF. O repo não tem
   `.gitattributes`, então o checkout do Windows grava CRLF e nenhum deles
   bateria nunca.

**O que os hashes da VM provaram, depois de convertidos:**

| arquivo | VM | base daqui, em CRLF |
|---|---|---|
| `bicep/main.bicep` | `37b5d393…` | `37b5d393…` ✅ |
| `function/pyproject.toml` | `97922cce…` | `97922cce…` ✅ |
| `shared/pyproject.toml` | `66d5b343…` | `66d5b343…` ✅ |

Ou seja: **a VM está exatamente na base esperada**, sem nenhum trabalho local
nesses arquivos. O alarme era falso — e é o tipo de alarme falso que se lê como
"há trabalho só do lado da CAT, pare", que é o oposto da verdade.

**A correção, agora no `CLAUDE.md`:** conferir pelo **blob SHA-1 do git**
(`git rev-parse HEAD:<caminho>` e `git hash-object -- <caminho>`), que é
calculado sobre o conteúdo normalizado em LF e portanto é igual nos dois repos
apesar dos históricos independentes. Em duas colunas, base e depois — a coluna
"depois" detecta de graça o arquivo que já foi aplicado numa tentativa anterior,
que foi o outro motivo de a leva 2 ter se perdido.

Blobs desta leva:

| arquivo | base | depois |
|---|---|---|
| `bicep/main.bicep` | `cf378540` | `b2ba489a` |
| `workflows/app-ci.yml` | — novo | `5fa4d59c` |
| `workflows/app-deploy.yml` | — novo | `42ababc3` |
| `function/doc_worker` | `63333378` ¹ | `618767fe` |
| `function/pyproject.toml` | `95599ffe` | `ab668d0e` |
| `shared/pyproject.toml` | `be062cec` | `4f4115d3` |

¹ **Corrigido depois de a conferência acusar `DIVERGE` na VM.** Eu tinha
previsto `1f3efcab`, o nosso blob no commit do poison handler. Errado: entre o
`Refine OCR extraction` e aquele commit, o `doc_worker` recebeu quatro commits
de modo local (extractor Docling, structurer OpenRouter, fallback por página,
correção do RapidOCR), **nenhum deles espelhado** — então a CAT nunca passou
por esse estado. A base real de lá é o nosso HEAD **menos o gancho de modo
local**, reconstruída e conferida por hash: dá `63333378…`, exatamente o que a
VM reportou. O `mark_failed` é idêntico dos dois lados.

Não havia trabalho da CAT em risco, e esta leva é justamente o que encerra essa
divergência: depois de aplicada, o arquivo fica idêntico nos dois repos.

A lição foi para o `CLAUDE.md`: **não prever a base a partir do nosso
histórico**. Para arquivo tocado por commit que não espelha, o blob da CAT não
existe aqui. Pedir `git rev-parse HEAD:<caminho>` na VM antes de montar o
pacote — prevista, a conferência só testa a nossa suposição contra ela mesma.

**Transporte do LEIA-ME:** `LEIA-ME-VM.b64`, 14849 bytes,
`31d50fa9d3d5ad27ea3fcaf3efa6f481698e892ec0307cc2d5f032374c958c0f`; o `.txt` que
sai dele é
`3796ceda11302805d5d356eb6d8adfc747a1051f522e0c2b04f77acbbe346bf8`.

**Aplicada na VM em 2026-09-22.** Conferência dos seis blobs: 6/6 OK.
`check_rules.py` 25/25. `import function_app` limpo. Os dois workflows copiados
para `.github/workflows/`, sem tocar no que já estava lá.

**Um susto no caminho, que não era da leva.** O `import function_app` falhou com
`ModuleNotFoundError: No module named 'shared.config'`. Causa: `function/shared/`
é gerada por `scripts/build` e gitignored — na VM ela existia mas estava
**vazia**, só com um `__pycache__` órfão de 17/09. Diretório sem `__init__` vira
namespace package, então `import shared` passa e o erro aponta para o submódulo,
escondendo a causa. `scripts/build.ps1` resolveu. A linha que estourou
(`doc_worker.py:9`) é idêntica antes e depois da leva — conferido por hash antes
de mexer em qualquer coisa. Foi para o `docs/ambiente.md`.

**Estado:** merjada na `main` em 2026-09-22.

---

## 2026-09-21 — `feat/app-cicd-and-appservice-config` · **merjado**

Grupo A do change request e o CI/CD da aplicação. 6 arquivos, 2 deles novos.

**O que vai:**

- `bicep/main.bicep` — runtime (`NODE|20-lts`, `PYTHON|3.14`), `AlwaysOn: 'true'`
  como String, `healthCheckPath: '/health'` só no fastapi. Os três valores
  conferidos contra os serviços, não supostos.
- `function/doc_worker.py` — os blocos de modo local saem para
  `function/doc_worker_local.py`, que não espelha. **Encerra a divergência
  permanente** que fez esta leva falhar: o arquivo volta a ser idêntico nos dois
  repos. Nenhuma mudança de comportamento do lado da CAT.
- `shared/pyproject.toml`, `function/pyproject.toml` — piso `>=3.11`. O backend
  fica em `>=3.14`; a assimetria é intencional.
- `workflows/app-ci.yml`, `workflows/app-deploy.yml` — **novos**.

**Primeira leva que carrega `aiagent-documentreader-infrastructure-azure/`**, e
a primeira transportada como **zip dos arquivos finais em base64, não como
diff** — ver abaixo. Os workflows precisam ser copiados para
`.github/workflows/` do lado de lá: espelhar o arquivo não é ativá-lo.

**Transporte:** `leva2.b64`, 18112 bytes,
`1a35710afaeb7cc5553d86f1b15f60c9f49e6d288d7a797797ccacd57c06301e`; o
`leva2.zip` que sai dele é
`8e2b33077042e1e42ac1ffd43eeb2c5d3c1e86a0058f640c144d2edc776f3db0`. O LEIA-ME
traz os hashes dos 4 arquivos que serão sobrescritos, para conferir **antes** de
descompactar.

**Por que deixou de ser diff.** Duas tentativas falharam, por motivos
diferentes, e o diagnóstico custou mais que o transporte:

1. o patch da leva 2 incluía a leva 1, que já estava aplicada lá;
2. o `doc_worker.py` divergia dos dois lados — os blocos `use_local_extractor` /
   `use_local_structurer` só existiam aqui, então o contexto tinha ~24 linhas a
   mais e nenhum diff desse arquivo aplicava lá.

O segundo **foi resolvido nesta leva**, não só documentado: os blocos saíram
para `doc_worker_local.py`. A nota de rodapé no `CLAUDE.md` agora registra o que
faria a divergência voltar.

**Conferido aqui:** `import function_app` em venv 3.11 real; `check_rules.py`
25/25; YAML válido nos dois workflows e `bash -n` limpo nos 27 blocos de `run`;
filtro de paths em 10 cenários; verificador de settings contra o estado real da
produção. O `check_structurer.py` **não rodou** — depende do `raw-civ-cap.json`.

**Decidido por sondagem:** a migração não entra no CD. O `POST /api/command` do
SCM executa no container do Kudu (`exec: alembic: not found`, exit 127).

**Estado:** merjado na `main` em 2026-09-22, junto da leva 3. O histórico da
tentativa está nas duas entradas acima.

---

## 2026-09-21 — `fix/poison-handler-marks-document-error` · **merjado**

Handler da fila de poison passa a fechar o documento no banco. 2 arquivos de
código (`function/doc_worker.py`, `function/function_app.py`) e o `BACKLOG.md`,
que não espelha.

**O que vai:**

- `doc_worker.mark_failed()` grava `error`, `error_message` e um `DocumentEvent`
  com `actor="poison"`. Só sobrescreve `received` e `processing`: o worker pode
  ter comitado o resultado e morrido depois do commit, e marcar `error` ali
  destruiria extração boa.
- `process_document_poison` chama essa função depois de logar.
- Dois defeitos de tabela no mesmo arquivo: `HttpResponse("missing document_id",
  status)` estourava `NameError` no caminho de erro (`status` não existe, vem do
  commit inicial), e a docstring de `_document_id_from` estava partida por
  reescrita de e-mail.

**Transporte:** base64 (`p.b64`), SHA-256 do `cat.patch`
`b4254da20c8ce5d69ba34aa8293ad30f801616d80878b1d77e061bb30824d289`. O patch foi
conferido com `git apply --check` num worktree no baseline, e a aplicação
reproduz o HEAD byte a byte.

**Conferido aqui:** `import function_app` num venv 3.11 de verdade (não
`py_compile`) e `check_rules.py` 25/25. O `check_structurer.py` **não rodou**:
depende do `raw-civ-cap.json`, que não está nesta máquina. Rodar na VM, onde ele
existe.

**Estado:** **merjado.** Confirmado em 21/09 comparando o `function_app.py` do
repo da CAT com o nosso: idêntico, `mark_failed` incluído.

---

## 2026-09-21 — `fix/mirror-startse-findings` · **merjado**

Primeira leva de correções achadas no ambiente de desenvolvimento. 30 arquivos,
197 inserções, 1028 remoções — número grande porque um terço é remoção de lixo e
outro terço é comentário voltando.

**Código que importa (4 arquivos):**

- `function/pipeline/structurer.py` — separa o sufixo de revisão do part number
  (`663-7238~00` → `6637238`), o que leva os 8 materiais do CIV de seis
  `not_printed` para oito `cat`; e impede gravar documento vazio sem explicação
  quando o modelo devolve `{}` ou `{"invoices": []}`.
- `db/db-setup-v2.sql` — regerado na head 0003. Estava carimbado `0002` com
  `incoterm VARCHAR(16)`, então ambiente novo provisionado por ele nasceria com
  o schema que já estourou em produção.
- `shared/shared/models.py` — sete colunas alinhadas com a migração 0003.
- `start-local.ps1` — conserta `$NOPROXY` e o host do Azurite, ambos quebrados
  lá por reescrita de e-mail.

**Resto:** remoção de 8 arquivos duplicados (`frontendsrc*.ts`, 938 linhas) e do
`sync-para-vm.txt`; 18 comentários de frontend e 22 linhas de docstring que
tinham virado linha em branco; remoção de BOM em `function_app.py` e
`processing.py`; default do deployment para `gpt-4.1`.

**Transporte:** base64 (`cat-patch-b64.txt`), conferido por SHA-256 na chegada.
A primeira tentativa foi com o `.txt` do diff cru e **falhou** — o filtro de
e-mail reescreveu os próprios cabeçalhos `diff --git`. Foi o que estabeleceu a
regra do base64.

**Percalço:** o arquivo `cat-fixes.patch` (a tentativa corrompida) acabou
commitado na branch e precisou ser removido com `git rm --cached` + amend antes
do PR. Daí a regra de que arquivo de comunicação nunca mora no repo.

---

## Pendente de espelhamento

A leva `feat/app-cicd-and-appservice-config`, no topo: o pacote está pronto e
conferido, falta transportar para a VM, copiar os workflows para
`.github/workflows/` e abrir o PR.

Para conferir se algo escapou, compare os diretórios que espelham (ver a tabela
no `CLAUDE.md`) contra o último ponto espelhado.
