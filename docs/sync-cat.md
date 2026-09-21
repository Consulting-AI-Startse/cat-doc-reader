# Log de espelhamento para o repo da CAT

Registro de tudo que saiu daqui para o `AICOE_AIagent_DocumentReader_POV`.
**Toda leva nova entra aqui**, no topo, assim que o PR for aberto — e o estado
atualizado quando ele for merjado.

Existe porque os dois repos têm históricos independentes: sem este arquivo não
há como saber, olhando o git, o que já foi espelhado e o que ainda não foi.

Formato de cada entrada: data, o que foi, como foi transportado, a branch e o
estado do PR.

---

## 2026-09-21 — `feat/app-cicd-and-appservice-config` · **aguardando PR**

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

**Estado:** pacote pronto, PR ainda não aberto.

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
