# Log de espelhamento para o repo da CAT

Registro de tudo que saiu daqui para o `AICOE_AIagent_DocumentReader_POV`.
**Toda leva nova entra aqui**, no topo, assim que o PR for aberto — e o estado
atualizado quando ele for merjado.

Existe porque os dois repos têm históricos independentes: sem este arquivo não
há como saber, olhando o git, o que já foi espelhado e o que ainda não foi.

Formato de cada entrada: data, o que foi, como foi transportado, a branch e o
estado do PR.

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

Nada no momento. As mudanças posteriores a esta leva são todas de modo local ou
documentação, que por definição não sobem.

Para conferir se algo escapou, compare os diretórios que espelham (ver a tabela
no `CLAUDE.md`) contra o último ponto espelhado.
