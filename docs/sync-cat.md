# Log de espelhamento para o repo da CAT

Registro de tudo que saiu daqui para o `AICOE_AIagent_DocumentReader_POV`.
**Toda leva nova entra aqui**, no topo, assim que o PR for aberto — e o estado
atualizado quando ele for merjado.

Existe porque os dois repos têm históricos independentes: sem este arquivo não
há como saber, olhando o git, o que já foi espelhado e o que ainda não foi.

Formato de cada entrada: data, o que foi, como foi transportado, a branch e o
estado do PR.

---

## 2026-10-01 — leva 11: confiança por campo e página por fornecedor · **pronta**, base conferida

Itens 5 e 8 do `BACKLOG.md` numa leva só: o 8 depende das colunas do 5, e uma
leva evita duas rodadas de migração e deploy. 21 arquivos (13 modificados, 8
novos), por ZIP em base64 + script autocontido. Branch sugerida:
`feat/confianca-por-campo`.

**Base conferida pelos blobs que a VM reportou (`origin/main`)**, com uma
ressalva: dois arquivos vieram na base da leva 10, embora o PR #30 já estivesse
merjado. O `origin/main` da VM estava velho -- o `git fetch -q` pedia
autenticação no navegador e falhou calado. Os outros 19 arquivos o #30 não
toca, então a conferência deles vale. O script aceita as duas bases para
`structurer.py` e `check_structurer.py`, o que cobre os dois casos.

**Antes de pedir blob à VM, `git fetch` sem `-q`**, e conferir que não pediu
autenticação: um fetch que falha calado faz o `rev-parse` responder com a
referência antiga, e a conclusão errada parece um fato.

- confiança por campo medida no OCR: palavra fraca (pior ocorrência), gêmeo
  confundível impresso no texto, valor não localizado. A do modelo deixa de
  decidir; limite 0.85, a calibrar com o gabarito em produção
- migração `0007`: `field_confidence` JSONB na invoice e na linha, agregados em
  coluna na invoice. Só colunas: sem `GRANT` novo
- `db-setup-v2.sql` regerado na head `0007` (estava na `0003`)
- página `/fornecedores` e `GET /suppliers/confidence` (+ `/detail`)

**Ordem em produção, que importa:** o `alembic upgrade` roda no webssh do
fastapi, com o código publicado lá, e a `0007` só chega com o deploy do
backend. Então: backend → migração → restart do fastapi → function →
frontend. Entre o backend e a migração a tela de revisão dá erro; a function
antiga segue gravando, porque as colunas novas são nulas.

O script confere, antes de escrever, que o `raw-civ-cap.json` da VM não é o do
CIV gravado com o bug do serial (`cc02235d-...`): com ele a seção 12 do
`check_structurer.py` falha com razão.

Script testado com PowerShell 5.1 e git do Windows, checkout CRLF, `build.ps1`
de verdade: aplica limpo (sem e com a leva 10 na base), já aplicada, arquivo
modificado só do lado da CAT, arquivo novo já existente, CIV com o bug, CIV
ausente, `.b64` corrompido.

| | |
|---|---|
| SHA-256 do `aplicar-leva11.b64` | `7cebe7c1d19f6119c12d34c38110af677a3ecf206d79ac52c256a4d444e8a50d` |
| SHA-256 do `leva11-arquivos.b64` | `cefbbf16961d8c8b465faca1dd56245c53684939804a41c094ec5f187591f9ad` |
| SHA-256 do `leva11-arquivos.zip` | `da2643efad8e79d0e8b781f0424c66ed64bb1082c741f770470f01dcf96ad3ad` |

---

## 2026-10-01 — leva 10: serial só expande peça que exige · **merjado** (PR #30)

**Merjada e em produção em 01/10.** A base foi conferida na VM antes do envio
(`origin/main`, os dois blobs como previstos). O CIV reenviado
(`3dce38ec-05bf-45a2-b72f-3f3e829ab4db`) saiu com a Bosch em **1 linha de 128
peças**, e o código da palete só na nota. O documento antigo
(`cc02235d-...`) segue gravado com os 18 registros errados.

2 arquivos, por ZIP em base64 + script autocontido. Branch sugerida:
`fix/serial-so-peca-que-exige`. Base: os dois blobs são o "depois" da leva 6,
a última que tocou os dois arquivos.

O CIV reextraído em 01/10 (`cc02235d-d981-455a-9baf-54bbaf8b7d01`) gravou a
fatura Bosch 9028078388 com **18 registros de 1 peça** no lugar das 128 de
`561-7001`, com seriais `3`, `3`, `6`... O modelo devolveu o código da palete
(`336624491166044672`) como **string** em `serial_numbers`, e o
`_expand_serials` a percorria letra a letra. A expansão também rodava para
peça que não exige serial pela lista, e a conferência aritmética não acusou,
porque soma a linha impressa antes de expandir.

- Expansão só quando a lista de PN exige serial; fora disso o valor devolvido
  pelo modelo vai para `notes` e a linha fica como impressa.
- String em `serial_numbers` é um valor só.
- `check_structurer.py`: seção 9g com o caso da Bosch; a remontagem do CIV
  gravado junta os registros expandidos de volta na linha impressa; o teste do
  gabarito confere a normalização, não qual código o modelo escolheu na rodada.

Não toca `shared/shared/`, então não precisa de `build.ps1`. Depois do merge:
`app-deploy → function` e reprocessar o CIV.

Script testado com PowerShell 5.1 e git do Windows, checkout CRLF, nos quatro
caminhos: aplica limpo (com `import function_app`, `check_rules.py` e
`check_structurer.py`), já aplicada, diverge sem escrever (em qualquer dos dois
arquivos), `.b64` corrompido.

| | |
|---|---|
| SHA-256 do `aplicar-leva10.b64` | `13294e0a045c8ad067b69611eb4347783a1e2032101d355803a00b39b95e7fd2` |
| SHA-256 do `leva10-arquivos.b64` | `17f844b943a8803efae34c59d20a63c6031261cd077bf0ee60471363a3aa4386` |
| SHA-256 do `leva10-arquivos.zip` | `3e0073a567c8b8a6744631d362f52fd5284ef64bcabcbce2f50ab59cdfd35613` |

| arquivo | base | depois |
|---|---|---|
| `function/pipeline/structurer.py` | `f4f965a50fef` | `f2b158993860` |
| `check_structurer.py` | `9eaa4c8bd8b1` | `482be0b3b574` |

---

## 2026-10-01 — papel da function no Azure OpenAI · **aplicado** (não é leva)

Operação na VM, sem código. Depois da leva 9 a function voltou a rodar e o
próximo erro foi `401 PermissionDenied` no OpenAI para a MI
`cd1b90fa-7e33-4036-b49c-bc9593dca99d`. A tag `roleAssignments1` do
`rbac.bicep` não estava na conta: a `cloud-coe-automation-new` regravou as
tags dela em 25/09 19:38 UTC, 13 min depois do nosso RBAC. Recolocada por
`az tag update --operation Merge`; a automação criou o papel em minutos,
function reiniciada, documento processado de ponta a ponta. Diagnóstico e
comandos na skill `operar-azure-cat`.

---

## 2026-09-30 — leva 9: wheels da function para a glibc do host · **merjado**

**Merjada e publicada em 30/09** (`app-deploy → function`). A function voltou
a indexar e processar: o Document Intelligence respondeu 202, e o user-agent
do host confirma `glibc2.31` — o teto de 2.28 tem folga. O próximo erro já é
de outra camada: `401 PermissionDenied` no Azure OpenAI para a MI da function
(`cd1b90fa-7e33-4036-b49c-bc9593dca99d`), sem a data action
`.../OpenAI/deployments/chat/completions/action`. É RBAC, não código.

1 arquivo em 2 lugares, por ZIP em base64 + script autocontido. Branch
sugerida: `fix/function-wheels-host-glibc`. Base conferida pelos blobs que a VM
reportou (`origin/main`): os dois caminhos em `0850d866`, o "depois" da leva 8.

**O 404 voltou com o pacote cheio.** A leva 8 instalava as dependências no
`ubuntu-latest`, e o pip escolheu o wheel `manylinux_2_34` do `cryptography`;
o container da function não tem `GLIBC_2.33`, o import quebrava no
`azure.identity` e o host subia com `No job functions found`. Diagnóstico pelo
Application Insights (`Worker failed to index functions`) — o estado
`Running`, o `wwwroot` e o `import` de conferência no runner estavam todos
certos.

- `pip install` com `--platform manylinux_2_28_x86_64` /
  `manylinux2014_x86_64`, `--python-version 3.11`, `--only-binary=:all:`.
  Mesmas versões de pacote; só o wheel do cryptography muda
  (`manylinux_2_34` → `manylinux_2_28`).
- Passo novo `Conferir a glibc das extensoes nativas`: lê a GLIBC exigida por
  cada `.so` do pacote e cai acima de 2.28. Controle negativo: o pacote de
  30/09 cai em `cryptography/hazmat/bindings/_rust.abi3.so` (GLIBC_2.34).

Depois do merge: `app-deploy → function`, e reenviar os documentos que caíram
com o 404 (entre eles `e7b3542f-e883-4a46-b020-1a1e1565177b`).

Script testado com PowerShell 5.1 e git do Windows, checkout CRLF, nos quatro
caminhos: aplica limpo, já aplicada, diverge sem escrever, `.b64` corrompido.

| | |
|---|---|
| SHA-256 do `aplicar-leva9.b64` | `93f38e3c92e4cc22694485ecd57c707223bd6d5b803e60739fd82ec3e8fe65ea` |
| SHA-256 do `leva9-arquivos.b64` | `bbab35f365ca67b2590c6a6654eeffc5d54deda6b047a82fb24e06665e376ab5` |
| SHA-256 do `leva9-arquivos.zip` | `a3ab5e33343a77dda6c98b0bc4066c42f4cf52f50e6c03f42490df5358770bc3` |

| arquivo | base | depois |
|---|---|---|
| `aiagent-documentreader-infrastructure-azure/workflows/app-deploy.yml` | `0850d8667f7d` | `83e8263501fc` |
| `.github/workflows/app-deploy.yml` (só lá) | `0850d8667f7d` | `83e8263501fc` |

---

## 2026-09-29 — leva 8: a function publicava sem dependências · **merjado** (regressão: ver abaixo)

**Merjada e publicada, e o 404 voltou** (30/09). Conferido na VM:
`origin/main:.github/workflows/app-deploy.yml` = `0850d866`, e o `wwwroot` tem
`.python_packages` completo. Desta vez quem denunciou foi o Application
Insights: `Worker failed to index functions` / `No job functions found`, com
`ImportError: ... GLIBC_2.33 not found` em
`cryptography/hazmat/bindings/_rust.abi3.so`, pela cadeia
`function_app → doc_worker → shared/db → azure.identity`. O `pip install` no
`ubuntu-latest` escolheu o wheel `manylinux_2_34` do cryptography, que o
container da function não carrega; o `import` de conferência passou porque
roda na glibc do runner. Correção na leva seguinte.

1 arquivo em 2 lugares, por ZIP em base64 + script autocontido. Branch
sugerida: `fix/function-deps-in-package`. Base conferida pelos blobs que a VM
reportou: os dois caminhos em `85db9a0f`, o "depois" da leva 7.

**Todo upload caía com `HTTP Error 404` ao acionar a function** (29/09), e
nenhum documento era processado desde 27/09. O host estava `Running`, com
`errors: null`, e a lista de funções do ARM mostrava as três — os dois
enganam: a lista é a do último sync, e o host sobe "saudável" com zero
funções quando o worker não consegue importar o `function_app`. Quem
denunciou foi o `wwwroot`, lido pelo SCM: **sem `.python_packages`**.

O deploy da leva 6 (27/09 17:53) foi um `rsync` de 28 arquivos, 1 segundo,
sem `pip install`. O `scm-do-build-during-deployment: true` do workflow só
tem efeito com a app setting `SCM_DO_BUILD_DURING_DEPLOYMENT`, que não existe
entre as 17 da function — e que todo run de infraestrutura apagaria.

- As dependências passam a ser instaladas **no runner, dentro do pacote**
  (`pip install --target function/.python_packages/lib/site-packages`), e o
  build remoto é desligado. Não depende mais de setting nenhuma.
- O `import function_app` de conferência usa só o que vai no pacote
  (`python -S`); antes ele importava do site-packages do runner e passava com
  o pacote vazio. Controle negativo: sem o pacote, `No module named 'azure'`.
- Depois do publish, o `wwwroot` é conferido pelo SCM (que não herda a
  restrição de rede) e o job cai se faltar `.python_packages`.

**Ponte até o merge:** criar `SCM_DO_BUILD_DURING_DEPLOYMENT=true` e
`ENABLE_ORYX_BUILD=true` na function e rodar `app-deploy → function`. Apagar
as duas depois da leva 8. Documentos que caíram com o 404 ficaram em `error`
e precisam ser reenviados.

Script testado com PowerShell 5.1 e git do Windows, checkout CRLF, nos quatro
caminhos: aplica limpo, já aplicada, diverge sem escrever, `.b64` corrompido.

| | |
|---|---|
| SHA-256 do `aplicar-leva8.b64` | `f1a4d21426e96f72b0c7977e2fe7a4df1ab998a30b07a4e3a23cb91326ba310b` |
| SHA-256 do `leva8-arquivos.b64` | `7d1b5a5a2d69228b32cbfa0cacfe495bbf4998133e3222edd24309fbe8664d31` |
| SHA-256 do `leva8-arquivos.zip` | `15437afc038fb107298b458c69fdfed433a1f4738bcb71bbcf4e386942e95590` |

| arquivo | base | depois |
|---|---|---|
| `aiagent-documentreader-infrastructure-azure/workflows/app-deploy.yml` | `85db9a0f99cb` | `0850d8667f7d` |
| `.github/workflows/app-deploy.yml` (só lá) | `85db9a0f99cb` | `0850d8667f7d` |

**Continua pendente** (fora desta leva, de propósito): a correção do
`DEPLOY.md` (`6f9e277`, `d5d5290`), o `--clean true` no deploy do frontend e
o rollback no `except` do `lookup_parts`.

---

## 2026-09-28 — migração 0005 + 0006 em produção, e o GRANT que faltava · **aplicado**

Não é leva de código: é a operação no banco que a leva 6 deixou pendente (o
job `migrate` falha de propósito). Três roteiros em base64, rodados pelo
webssh do fastapi com token de administrador (`migrar-0006-v2`,
`grant-0006`, `fechar-0006`). Todo código Python foi como uma linha de
base64 com SHA-256 conferido antes de executar: a primeira versão, em texto,
chegou ao webssh sem indentação, sem `*` e sem `#` — passou por algo que a
leu como Markdown.

- `alembic upgrade head`: `0004 -> 0005 -> 0006`, limpo.
- **As duas MIs ficaram sem nenhum privilégio** em `released_part_numbers`,
  `serial_rules` e `serial_rules_id_seq`. O `pg_default_acl` de produção
  estava **vazio**: o `ALTER DEFAULT PRIVILEGES` do `DEPLOY.md` nunca vigorou.
  Todas as tabelas têm o mesmo dono, o grupo admin. Corrigido com `GRANT ...
  ON ALL TABLES/SEQUENCES` e `ALTER DEFAULT PRIVILEGES` para tabelas e
  sequences, como o grupo admin; o `pg_default_acl` agora tem as linhas `r`
  (`arwd`) e `S` (`rU`) para as duas MIs. Conferência pelo catálogo: `TUDO OK`.
- **Nenhum documento afetado:** nenhum foi atualizado desde 27/09, então nada
  passou pelo `doc_worker` enquanto a lista estava inacessível.

**Pendente para a próxima leva:** a correção do `DEPLOY.md` (commits `6f9e277`
e `d5d5290`) e o `--clean true` no deploy do frontend. E, a reproduzir antes:
o `except` em volta do `lookup_parts` no `doc_worker` não faz rollback, e no
Postgres um comando que falha aborta a transação — a próxima falha da
consulta derrubaria o documento adiante, em vez de seguir sem serial.

---

## 2026-09-28 — leva 7: o frontend morria no boot · **merjado**

5 caminhos (1 renomeado, 3 modificados), por ZIP em base64 + script
autocontido. Branch: `fix/frontend-boot-cjs`, aberta da `main` depois do merge
da leva 6 (`a30b9d1`, PR #26). Base conferida pelos blobs que a VM reportou
(HEAD `6be7006`), e de novo na `main` antes do `stash pop`; os quatro bateram.

**Conferido em produção em 28/09.** O primeiro deploy com a correção falhou
mesmo assim, com o site de pé: o container imprimiu `serving dist on 8080` e a
plataforma registrou `Site started` às 14:15:04, 30 s depois do publish, mas o
`az webapp deploy` seguiu em "Starting the site..." até estourar os 10 minutos
com `FailedInstances: 1`. Todas as linhas de status carregavam
`LastError: ContainerStartupFailure` de 13:45 — a última queda do `server.js`
antigo. Depois de um restart manual (que troca o `LastError` por
`SiteStartupCancelled`), o deploy seguinte passou. A leitura, **não
confirmada**, é que o acompanhamento do deploy conta o `LastError` velho como
falha: o primeiro deploy depois de uma sequência de quedas pode falhar com o
site saudável. Se acontecer, restart e rodar de novo.

**O deploy do frontend caía por timeout de 10 minutos** ("the site failed to
start within 10 mins"), sem pista de causa. O zip leva o `package.json`, que
declara `"type": "module"` para o Vite; com ele do lado, o Node 20 carregava o
`server.js` como ESM e morria no primeiro `require` (`require is not defined
in ES module scope`). Defeito desde que o workflow foi escrito — o deploy
manual do `DEPLOY.md` escapava por subir só o `dist/` e servir com `pm2`.

- `frontend/server.js` → `server.cjs`, que o Node lê como CommonJS
  independente do `package.json`. Conteúdo idêntico (mesmo blob).
- No `app-deploy.yml`, o startup command passa a rodar **antes** do publish: o
  deploy espera o site subir com o startup vigente, e o antigo apontaria para
  um `server.js` que o zip novo não traz.
- O workflow vai **nos dois lugares** do lado da CAT: o diretório de
  infraestrutura e `.github/workflows/`, que é o que o Actions executa. Os
  dois estavam no mesmo blob.

O script também sobe o `server.cjs` com o `package.json` do lado, que é a
condição exata da falha, e para se o processo não ficar de pé. Testado aqui nos
três caminhos (aplica limpo, já aplicada, diverge sem escrever), com checkout
CRLF e Node 20 no Windows; o controle negativo, o arquivo antigo no mesmo
lugar, reproduz o `ReferenceError`.

| | |
|---|---|
| SHA-256 do `aplicar-leva7.b64` | `8543049187e8436ebc699905a202157c79da15b6f16002bbdfcbcd54ea317d9f` |
| SHA-256 do `leva7-arquivos.b64` | `23dcfeb6b331dec6409bcaf22aaa31dcb122385136570e493d72664995448aab` |
| SHA-256 do `leva7-arquivos.zip` | `2567da5fad1067966a05c2dd473d655473633964dca2c41628cab79bff245065` |

| arquivo | base | depois |
|---|---|---|
| `frontend/server.js` | `3546e19ecc79` | **removido** |
| `frontend/server.cjs` | **novo** | `3546e19ecc79` |
| `aiagent-documentreader-infrastructure-azure/workflows/app-deploy.yml` | `9dae22a744b0` | `85db9a0f99cb` |
| `.github/workflows/app-deploy.yml` (só lá) | `9dae22a744b0` | `85db9a0f99cb` |
| `aiagent-documentreader-infrastructure-azure/bicep/main.bicep` | `b2ba489a5e80` | `ad041bb624ca` |

---

## 2026-09-27 — leva 6: lista de PN, serial number e conserto do CD · **merjado** (PR #26)

26 arquivos (8 novos), por ZIP em base64 + script autocontido. Branch:
`feat/part-numbers-and-serial`, merjada na `main` como `a30b9d1` (PR #26).

**O que vai:**

- **Lista de PN liberados** — tabela, import CSV e tela de configuração com a
  regra de quem exige serial. Medido: 206.769 linhas em 18 MB, consulta em
  0,43 ms, recálculo em 0,81 s. `ENGINE` casaria 910 peças (quase todas
  acessório); `ENGINE AR` casa 588 sem falso positivo — por isso a tela mostra
  prévia antes de salvar.
- **Serial number** — um registro por serial, com quantidade 1 e
  `amount` = `unit_price`, o que preserva a soma contra o total impresso.
  Verificado contra o modelo, 3 rodadas sobre a fatura de motor 93872204: 3/3
  com os sete seriais.
- **Gate de linhas sem part number**, antes da conferência aritmética, com as
  descartadas preservadas e visíveis na tela.
- **Defeito separado de registro de cálculo** — nota de rateio não derruba mais
  o documento para `needs_review`. E a embalagem entrou na conferência: um
  falso positivo que estava travado por teste.
- **Documento rejeitado deixa de valer como referência de duplicata.**
- **Conserto do CD** (ver abaixo).

**O smoke test batia numa restrição de rede.** Os dois App Services têm
`ipSecurityRestrictionsDefaultAction: Deny` e liberam só as redes da
Caterpillar; o runner do GitHub não está em nenhuma. O `/health` de lá devolve
403 com a página "blocked your access" — a restrição, não a aplicação. O job
gastava 10 minutos nisso e derrubava o deploy de um backend saudável: da VM o
mesmo `/health` dá 200. O diagnóstico anterior ("cold start de 5 minutos") era
falso pelo mesmo motivo. Agora o 403 é reconhecido na primeira tentativa,
explicado no resumo do job, e não derruba o deploy; erro real continua
derrubando. **O SCM não herda essas regras**, e é por isso que publicar
funciona e verificar não.

**O `check_parts.py` teria quebrado o CI.** Ele testava o relatório de import
pelo `TestClient` do FastAPI, que exige `httpx` — presente aqui porque a venv
arrasta o modo local, ausente no `requirements.txt` do backend. A leitura do
CSV virou função pura em `shared/parts.py` e o teste chama direto. Conferido
numa venv limpa com apenas o `requirements.txt`.

**Atenção: `rbac.bicep` diverge.** A VM tem `6a925b49…`, que não existe em
commit nenhum deste repo — é trabalho feito direto lá. **Não está nesta leva**,
então não há risco de sobrescrita, mas a nossa cópia está velha e precisa ser
trazida de lá antes que alguém a edite aqui.

**Atenção no deploy:** traz **duas** migrações (`0005` e `0006`). O job
`migrate` falha de propósito; rodar como administrador do Entra pelo webssh.

| | |
|---|---|
| SHA-256 do `.b64` | `fcc26c8f0a6c9f448c7764fbb53c3f68b3ea9b7ae8f5b24979e507799d9c5ddb` |
| SHA-256 do `.zip` | `3c3a91d575b5a665a3a95b9de5ab42a6dbf45fe1410845d2fcfaf7959cd32ba7` |

| arquivo | base | depois |
|---|---|---|
| `DEPLOY.md` | `b900994db7c9` | `7ef20d49e42f` |
| `aiagent-documentreader-infrastructure-azure/workflows/app-ci.yml` | `67e193ed5711` | `4bcaa0bd3ed8` |
| `aiagent-documentreader-infrastructure-azure/workflows/app-deploy.yml` | `463773b96950` | `9dae22a744b0` |
| `backend/alembic/versions/0002_packaging_text.py` | `dffb9c3bb07a` | `74ab9ad54cd4` |
| `backend/alembic/versions/0005_released_part_numbers.py` | **novo** | `95de84b6e57e` |
| `backend/alembic/versions/0006_serial_number_on_item.py` | **novo** | `e4605b137a6b` |
| `backend/app/api/documents.py` | `21d2d882ee1f` | `97ef00df3bb9` |
| `backend/app/api/parts.py` | **novo** | `efe85da4ca8f` |
| `backend/app/main.py` | `1752971b4d13` | `ac4f10de8b2d` |
| `check_dedupe.py` | `d96bf376a54b` | `28c8599da713` |
| `check_parts.py` | **novo** | `6ad902b84a22` |
| `check_structurer.py` | `cd7809898c18` | `9eaa4c8bd8b1` |
| `frontend/src/api/client.ts` | `fa50a9057233` | `4516ed6a85ab` |
| `frontend/src/api/parts.ts` | **novo** | `22fc74500fcc` |
| `frontend/src/components/AppShell.tsx` | `dd493504af4a` | `715e9f3d73c6` |
| `frontend/src/components/FileUpload.tsx` | `9b15e9513883` | `ae2d7ef2536a` |
| `frontend/src/main.tsx` | `3be1b15f2b73` | `f3292e4890a1` |
| `frontend/src/pages/DocumentDetail.tsx` | `e6c5434e18ab` | `96c5170b670e` |
| `frontend/src/pages/PartNumbers.tsx` | **novo** | `5284ef354cc1` |
| `frontend/src/types/document.ts` | `6ed2264de618` | `dcdfaa893f71` |
| `frontend/src/types/parts.ts` | **novo** | `b0184e2ee729` |
| `function/doc_worker.py` | `799befdd6d8a` | `e9e2fe9f1539` |
| `function/pipeline/structurer.py` | `65fcea67e15e` | `f4f965a50fef` |
| `shared/shared/dedupe.py` | `3ef88c95396a` | `af7646b6ddd4` |
| `shared/shared/models.py` | `531a1f7e0856` | `f2214a63412e` |
| `shared/shared/parts.py` | **novo** | `bd6ff2dd6030` |

---

## 2026-09-25 — leva 5: a instrução de migração estava errada · **merjado**

3 arquivos, por ZIP em base64 + script autocontido. Branch sugerida:
`docs/migration-runs-as-admin`.

**Aplicar a `0004` em produção custou cinco tentativas, e as três instruções
que o repo dava levavam para o caminho que não funciona.** Os três erros, com a
mensagem que cada um dá:

| caminho | mensagem | por quê |
|---|---|---|
| `alembic upgrade head` no webssh | `must be owner of table invoices` | a MI tem só DML pela seção 2.4 do `DEPLOY.md` |
| conectar da VM | `connection timeout` | o IP da VM não está na allow-list do firewall |
| `az postgres flexible-server execute` | `'execute' is misspelled` | falta a extensão `rdbms-connect` |

A rede passa do **container** e o privilégio é do **administrador**. O caminho é
o webssh com token de admin, colado em **duas metades** — o webssh trunca a
entrada em 4095 caracteres e o token tem ~4500. Colar inteiro corta a assinatura
do JWT e o servidor responde `The access token has invalid format`, que não diz
nada sobre truncamento.

**O `env.py` não deve ser "corrigido".** Ele não injeta o token do Entra, e
parece faltar simetria com o `shared/db.py`. Copiar o listener para lá põe o
token da **Managed Identity** como senha, descarta o `PGPASSWORD` do admin e
quebra exatamente o que passou a funcionar. A ausência agora está comentada
como deliberada.

**O `DEPLOY.md` da CAT era de 27/08**, do `init` — mesma história do
`documents.py` na leva 4. Ainda mandava configurar `USE_REAL_SERVICES=false`,
que é o que faz a function rodar mockada sem emitir erro, e apontava para o
caminho antigo do repo. Entrou na leva, e `DEPLOY.md` e `scripts/` foram
acrescentados à tabela de espelhamento do `CLAUDE.md`, onde nunca estiveram.

Nenhum código executável muda: dois documentos e um comentário. O script não
vendoriza nem roda os checks; confere o YAML do workflow e para por aí.

| | |
|---|---|
| SHA-256 do `.b64` | `75678d5db4760a570e708499018b0b00184e3f8b01c63e4aefaa7fcd990c4861` |
| SHA-256 do `.zip` | `6da7a8f582b5c2f89b39edebf9a6380af601951dfc94afc900225d8655b65863` |

| arquivo | base | depois |
|---|---|---|
| `DEPLOY.md` | `11305cd34d6edaf09e6fcbbb285a7ae97730fa2f` | `b900994d` |
| `aiagent-documentreader-infrastructure-azure/workflows/app-deploy.yml` | `995da844d4c71aa5cf48fc5347e3829e2a7a477c` | `463773b9` |
| `backend/alembic/env.py` | `3d367a891e570f1a5455f6912e83d136a000494d` | `db4bf56d` |

---

## 2026-09-25 — leva 4: duplicatas, regra 6 do prompt e catch-up · **merjado**

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

**Duas correções no script depois da primeira tentativa na VM**, que chegou
verde até o passo 7 e quebrou no 8:

- **Faltava vendorizar o `shared`.** `function/shared/` é gerado e gitignored,
  então não viaja na leva; o da VM era de antes e não tinha o `dedupe.py` que o
  `check_rules.py` desta leva passou a importar. O script agora roda o
  `scripts/build.ps1` antes dos testes.
- **O wrapper de comando nativo valia só para o `git`.** O `python` também
  escreve em stderr (traceback), e sob `ErrorActionPreference='Stop'` o
  PowerShell não só aborta como **engole a mensagem** — da VM só voltou a linha
  `Traceback (most recent call last):`, sem o erro. Agora todo executável passa
  pelo mesmo wrapper e a saída é impressa quando falha.

**Encerra a divergência do `doc_worker.py`.** O blob da CAT batia com
`c70c235` antes de aplicar; agora os dois lados têm o mesmo arquivo, gancho de
modo local incluído.

**Atenção no deploy:** traz migração. **Aplicada em produção em 25/09**, como
administrador do Entra pelo webssh — ver a leva 5, que documenta o procedimento
depois de as instruções antigas falharem cinco vezes.

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
