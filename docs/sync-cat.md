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

CI/CD da aplicação, configuração dos App Services e o poison handler. 7 arquivos.
**Substitui a leva `fix/poison-handler-marks-document-error`**, que nunca chegou
a ser aplicada: este patch contém o conteúdo dela mais o resto.

**O que vai:**

- `function/doc_worker.py`, `function_app.py` — `mark_failed()` fecha no banco o
  documento cujo worker morreu; só sobrescreve `received` e `processing`. Mais o
  `NameError` do caminho de `document_id` ausente e uma docstring partida.
- `bicep/main.bicep` — grupo A do change request: runtime (`NODE|20-lts` e
  `PYTHON|3.14`), `AlwaysOn: 'true'` como String, `healthCheckPath: '/health'`
  só no fastapi. Os três valores conferidos contra os serviços.
- `shared/pyproject.toml`, `function/pyproject.toml` — piso `>=3.11`. O backend
  fica em `>=3.14`: a assimetria é intencional, porque o `shared` vai para as
  duas aplicações e a function roda 3.11.
- `workflows/app-ci.yml`, `workflows/app-deploy.yml` — **novos**.

**Primeira leva que carrega `aiagent-documentreader-infrastructure-azure/`.** A
tabela do `CLAUDE.md` foi atualizada na mesma leva: o diretório existe igual dos
dois lados, então espelha por caminho. Mas os workflows **precisam ser copiados
para `.github/workflows/`** do lado de lá para rodar — espelhar o arquivo não é
ativá-lo.

**Transporte:** base64 (`p2.b64`, 39822 bytes,
`be20360210d22bbf82dd44f48811b26b4a53231f34567aa4edf4f1fc9c71f282`); o
`cat2.patch` que sai dele é
`428436cbd6a170201e7495a4c856a65f3e58dfae6fd61214998a551aaeabcfa5`. Conferido
com `git apply --check` num worktree no baseline `74916ef`, e os 7 arquivos
reproduzem o HEAD byte a byte.

**Conferido aqui:** `import function_app` num venv 3.11 real; `check_rules.py`
25/25; `import app.main` num venv 3.14; YAML válido nos dois workflows e
`bash -n` limpo nos 27 blocos de `run`; filtro de paths testado em 10 cenários;
verificador de settings testado contra o estado real da produção. O
`check_structurer.py` **não rodou** — depende do `raw-civ-cap.json`, que não
está nesta máquina. Rodar na VM.

**Decidido por sondagem, não por suposição:** a migração não entra no CD. O
`POST /api/command` do SCM executa no container do Kudu (`exec: alembic: not
found`, exit 127), e o `wwwroot` que ele enxerga tem `output.tar.zst`, não a
aplicação. O job `migrate` falha de propósito e imprime o comando para o webssh.

**Estado:** patch pronto, PR ainda não aberto.

---

## 2026-09-21 — `fix/poison-handler-marks-document-error` · **aguardando PR**

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

**Estado:** **substituída** pela leva acima, que a contém. Este patch nunca foi
aplicado; não aplique o `p.b64` desta entrada.

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

A leva `feat/app-cicd-and-appservice-config`, no topo: o patch está pronto e
conferido, falta transportar para a VM, copiar os workflows para
`.github/workflows/` e abrir o PR.

Para conferir se algo escapou, compare os diretórios que espelham (ver a tabela
no `CLAUDE.md`) contra o último ponto espelhado.
