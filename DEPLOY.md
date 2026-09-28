# DEPLOY.md: subir o cat-doc-reader nos App Services da Caterpillar

Guia de deploy por linha de comando (`az`), para rodar **da VM Windows da CAT**, com
o repo da CAT (`AICOE_AIagent_DocumentReader_POV`) já clonado na VM. Foco: **frontend** e
**backend FastAPI**, cada um no seu App Service. O **Function App** entra como terceiro
passo, porque o backend chama a function por HTTP (arquitetura separada, como planejado).

Modelo de trabalho: você roda estes comandos na VM; se algo falhar, cola o erro que eu ajusto.

---

## 0. Pré-requisitos (uma vez por sessão na VM)

- Repo da CAT na VM: `C:\Users\souzal1\repos\AICOE_AIagent_DocumentReader_POV`.
  O deploy sai dele, nao deste repo de desenvolvimento (ver `CLAUDE.md`).
- **Node 20+** e **npm** (para buildar o frontend).
- **az CLI** logado: `az login` (subscription IA COE Gen AI POV).
- Para os passos que tocam o Postgres (principal da Managed Identity): portal
  **`fwauth.corp.cat.com`** autenticado e aba aberta, mais o token Entra (ver seção 4).
- **Extensão de deploy** já vem no az. Para o Function App, é bom ter o **Azure Functions
  Core Tools** (`func`); há alternativa por `az` (zip) se não tiver.

### Variáveis (PowerShell)

```powershell
$RG     = "aicoe_aiagent_documentreader_pov"
$FRONT  = "aiagent-documentreader-pov-frontend-appservice"
$APP    = "aiagent-documentreader-pov-fastapi-appservice"
$FUNC   = "aiagent-documentreader-pov-backend-function"
$PG     = "aiagent-documentreader-pov-postgresql-server"
$ST     = "aiagentdocumentreaderpov"
$GROUP  = "CATIT-GenAICOE-DocumentReaderPOV-Developer"
$PGHOST = "aiagent-documentreader-pov-postgresql-server.postgres.database.azure.com"
$repo   = "C:\Users\souzal1\repos\AICOE_AIagent_DocumentReader_POV"
```

### Ordem

O banco (schema v2) precisa estar aplicado antes do backend funcionar de verdade
(ver `db-setup-v2.sql`, Fase 0 do plano). Para o deploy do código, faço **frontend
primeiro** (retorno visual mais rápido). O único porém: a UI só passa a responder de
verdade quando o backend estiver no ar. Se preferir ver tudo funcionando de primeira,
inverta e faça o backend (seção 2) antes do frontend (seção 1).

---

## 1. Frontend (App Service estático)

O `.env.production` já aponta o build para a URL do backend
(`https://aiagent-documentreader-pov-fastapi-appservice.azurewebsites.net`), então o
`npm run build` já embute o endpoint certo.

### 1.1 Conferir o runtime do App Service (deve ser Linux + Node)

```powershell
az webapp config show -g $RG -n $FRONT --query "{linux:linuxFxVersion, win:windowsFxVersion}" -o jsonc
```
Se não vier um `NODE|...` em `linuxFxVersion`, me avise (o mecanismo de servir estático
muda). Para setar Node (se você tiver permissão):
```powershell
az webapp config set -g $RG -n $FRONT --linux-fx-version "NODE|20-lts"
```

### 1.2 Build

```powershell
cd $repo\frontend
npm install
npm run build          # gera dist/ com a URL do backend embutida
```

### 1.3 Deploy do dist/ + fallback de SPA (React Router)

```powershell
Compress-Archive -Path dist\* -DestinationPath $repo\frontend\dist.zip -Force
az webapp deploy -g $RG -n $FRONT --src-path $repo\frontend\dist.zip --type zip
az webapp config set -g $RG -n $FRONT --startup-file "pm2 serve /home/site/wwwroot --no-daemon --spa"
az webapp restart -g $RG -n $FRONT
```
> `pm2 serve ... --spa` faz qualquer rota cair no `index.html` (necessário para o React
> Router). O `pm2` já vem nas imagens Node do App Service Linux.

### 1.4 Conferir

```powershell
start https://aiagent-documentreader-pov-frontend-appservice.azurewebsites.net
```
A UI deve carregar. Erros de API no console são esperados até o backend subir.

---

## 2. Backend FastAPI (App Service)

O App Service deve ter stack **Python (Linux)**. O deploy usa build no servidor (Oryx
roda `pip install` do `requirements.txt`).

### 2.1 App Settings

```powershell
az webapp config appsettings set -g $RG -n $APP --settings `
  SCM_DO_BUILD_DURING_DEPLOYMENT=true `
  DB_USE_ENTRA_TOKEN=true `
  DATABASE_URL="postgresql+psycopg://$APP@$PGHOST`:5432/documentreader?sslmode=require" `
  AZURE_STORAGE_ACCOUNT_URL="https://$ST.blob.core.windows.net" `
  BLOB_CONTAINER_NAME=invoices `
  USE_REAL_SERVICES=true `
  CORS_ORIGINS="https://$FRONT.azurewebsites.net" `
  FUNCTION_URL="https://$FUNC.azurewebsites.net/api/process_document"
```
> Notas: a `DATABASE_URL` NÃO leva senha (o usuário é a Managed Identity, com o nome do
> App Service); `DB_USE_ENTRA_TOKEN=true` liga a injeção do token do Entra no código
> (`shared/db.py`). O `` `: `` no meio da URL é só o escape do `:` no PowerShell.
> `FUNCTION_KEY` a gente preenche na seção 3.4, depois que a function existir.

### 2.2 Deploy do código

```powershell
cd $repo\backend
Compress-Archive -Path * -DestinationPath $repo\backend.zip -Force
az webapp deploy -g $RG -n $APP --src-path $repo\backend.zip --type zip
az webapp config set -g $RG -n $APP --startup-file "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
az webapp restart -g $RG -n $APP
```

### 2.3 Smoke test do "no ar" (não depende de banco)

```powershell
curl https://aiagent-documentreader-pov-fastapi-appservice.azurewebsites.net/health
```
Esperado: `{"status":"ok"}`. Se falhar, logs: `az webapp log tail -g $RG -n $APP`.

> Se o Oryx não achar os pacotes (PyPI bloqueado), aponte o pip para o Artifactory da CAT:
> `az webapp config appsettings set -g $RG -n $APP --settings PIP_INDEX_URL="<feed JFrog>"`
> e refaça o deploy.

### 2.4 Ligar a Managed Identity no Postgres (self-serve, como grupo admin)

```powershell
az webapp identity assign -g $RG -n $APP
$mi = (az webapp identity show -g $RG -n $APP --query principalId -o tsv)

# precisa do portal Check Point aberto + token Entra:
$token = (az account get-access-token --resource https://ossrdbms-aad.database.windows.net --query accessToken -o tsv).Trim()

$create = "SELECT * FROM pgaadauth_create_principal_with_oid('$APP','$mi','service',false,false);"
az postgres flexible-server execute -n $PG -u $GROUP -p $token -d documentreader --querytext $create

$grants = "GRANT USAGE ON SCHEMA public TO ""$APP""; GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO ""$APP""; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO ""$APP""; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO ""$APP""; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO ""$APP"";"
az postgres flexible-server execute -n $PG -u $GROUP -p $token -d documentreader --querytext $grants
```
> Se o `pgaadauth_create_principal_with_oid` não existir nessa versão do servidor, me
> cole o erro: algumas versões usam `pgaadauth_create_principal('<nome-da-MI>', false, false)`.

Depois: `az webapp restart -g $RG -n $APP` e teste um endpoint de banco:
```powershell
curl https://aiagent-documentreader-pov-fastapi-appservice.azurewebsites.net/dashboard/metrics
```

### 2.5 Ligar o Blob na Managed Identity

```powershell
$scope = (az storage account show -g $RG -n $ST --query id -o tsv)
az role assignment create --assignee $mi --role "Storage Blob Data Contributor" --scope $scope
```
> Isto exige `roleAssignments/write`, que você provavelmente NÃO tem (mesmo tipo de
> permissão que faltou no firewall). Se der `AuthorizationFailed`, é **pedido à
> plataforma**: "conceder à MI do App Service `$APP` (principalId `$mi`) o papel
> *Storage Blob Data Contributor* na conta `$ST`". Sem isso, `/health`, listagem e
> dashboard funcionam; o upload de PDF só fecha quando o papel sair.

---

## 3. Function App (worker de IA, chamado pelo backend)

O backend chama `https://<func>.azurewebsites.net/api/process_document`. Sem a function
no ar, o upload cria o documento e guarda o PDF, mas não processa. Deploy do worker:

### 3.1 App Settings da function

```powershell
az functionapp config appsettings set -g $RG -n $FUNC --settings `
  DB_USE_ENTRA_TOKEN=true `
  DATABASE_URL="postgresql+psycopg://$FUNC@$PGHOST`:5432/documentreader?sslmode=require" `
  AZURE_STORAGE_ACCOUNT_URL="https://$ST.blob.core.windows.net" `
  BLOB_CONTAINER_NAME=invoices `
  USE_REAL_SERVICES=true
```

### 3.2 Deploy do código

Opção A (recomendada, Azure Functions Core Tools):
```powershell
cd $repo\function
func azure functionapp publish aiagent-documentreader-pov-backend-function --python
```
Opção B (só com az, build no servidor):
```powershell
az functionapp config appsettings set -g $RG -n $FUNC --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true ENABLE_ORYX_BUILD=true
cd $repo\function
Compress-Archive -Path * -DestinationPath $repo\function.zip -Force
az functionapp deployment source config-zip -g $RG -n $FUNC --src $repo\function.zip
```

### 3.3 MI da function no Postgres + Blob (mesmo padrão do backend)

```powershell
az functionapp identity assign -g $RG -n $FUNC
$mifunc = (az functionapp identity show -g $RG -n $FUNC --query principalId -o tsv)
$createF = "SELECT * FROM pgaadauth_create_principal_with_oid('$FUNC','$mifunc','service',false,false);"
az postgres flexible-server execute -n $PG -u $GROUP -p $token -d documentreader --querytext $createF
$grantsF = "GRANT USAGE ON SCHEMA public TO ""$FUNC""; GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO ""$FUNC""; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO ""$FUNC""; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO ""$FUNC""; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO ""$FUNC"";"
az postgres flexible-server execute -n $PG -u $GROUP -p $token -d documentreader --querytext $grantsF
# Blob (mesma ressalva de permissão da seção 2.5):
$scope = (az storage account show -g $RG -n $ST --query id -o tsv)
az role assignment create --assignee $mifunc --role "Storage Blob Data Contributor" --scope $scope
```
> A allow-list do firewall do Postgres já inclui os IPs de saída do Function App
> (registrado nos aprendizados), então a rede function -> banco já está liberada.

### 3.4 Conectar o backend na function (chave)

```powershell
$fkey = (az functionapp function keys list -g $RG -n $FUNC --function-name process_document --query default -o tsv)
az webapp config appsettings set -g $RG -n $APP --settings FUNCTION_KEY=$fkey
az webapp restart -g $RG -n $APP
```

---

## 4. Teste ponta a ponta

1. Abra a UI: `https://aiagent-documentreader-pov-frontend-appservice.azurewebsites.net`
2. "Novo documento", suba um PDF.
3. Ele entra como **Recebido**, o backend chama a function, e em alguns segundos vira
   **Para revisar** com os invoices e as linhas de part number (Document Intelligence + Azure OpenAI).
4. Edite e **aprove** (aprovação por documento, human-in-the-loop).

---

## Resumo do que cada serviço precisa

| Serviço | Deploy | Depende de |
|---|---|---|
| Frontend | `az webapp deploy` (dist do Vite) + `pm2 serve --spa` | URL do backend no build (já configurada) |
| Backend FastAPI | `az webapp deploy` (zip) + Oryx | schema v2 aplicado; MI no Postgres (self-serve); Blob na MI (plataforma); `FUNCTION_URL/KEY` |
| Function App | `func publish` ou `az ...config-zip` | MI no Postgres; Blob na MI; App Settings |

## Migração de schema: roda como administrador, no webssh

Aplicado assim em 25/09, com a `0004`. Os três caminhos mais óbvios não
funcionam, e cada um falha com uma mensagem que não diz o porquê:

| caminho | o que acontece |
|---|---|
| `alembic upgrade head` no webssh | `must be owner of table invoices` — a MI só tem DML |
| conectar da VM | `connection timeout` — o IP da VM não está na allow-list do firewall |
| `az postgres flexible-server execute` | `'execute' is misspelled` — falta a extensão `rdbms-connect` |

A rede passa do **container**; o privilégio é do **administrador**. A saída é
juntar os dois: rodar no webssh, autenticando com o token do admin.

**Na VM**, o token sai em duas metades porque o webssh trunca a entrada em
**4095 caracteres** e o token tem ~4500:

```powershell
$t = (az account get-access-token --resource https://ossrdbms-aad.database.windows.net --query accessToken -o tsv).Trim()
$h = [math]::Ceiling($t.Length/2)
$p1 = $t.Substring(0,$h); $p2 = $t.Substring($h)
"total: $($t.Length)  p1: $($p1.Length)  p2: $($p2.Length)"
Set-Clipboard -Value $p1
# depois de colar a primeira metade no webssh:
Set-Clipboard -Value $p2
```

O nome do grupo admin sai daqui (o subcomando antigo era `ad-admin`):

```powershell
az postgres flexible-server microsoft-entra-admin list -g <rg> -s <servidor> --query "[0].principalName" -o tsv
```

**No webssh do fastapi**, no diretório que tem o `alembic.ini`:

```bash
export DATABASE_URL="postgresql+psycopg://<grupo-admin>@<servidor>.postgres.database.azure.com:5432/documentreader?sslmode=require"
read -rs P1      # cola a 1a metade
read -rs P2      # cola a 2a metade
PGPASSWORD=$(printf '%s%s' "$P1" "$P2" | tr -d '\r\n '); export PGPASSWORD; unset P1 P2
echo "${#PGPASSWORD} $(printf '%s' "$PGPASSWORD" | awk -F. '{print NF}')"   # 4515 e 3
alembic current        # tem de imprimir a revisao ANTERIOR, sem erro
alembic upgrade head
```

O `read -rs` não ecoa e não deixa o token no histórico. O `tr -d` tira o `\r`
que o clipboard do Windows cola junto — com ele o servidor responde
`The access token has invalid format`, que não diz nada sobre isso. O
`awk -F.` conta as partes do JWT: **3** significa inteiro, **2** significa que a
colagem foi truncada.

Confira pelo catálogo, nunca por `alembic current`, e reinicie o
fastapi e a function depois — eles carregaram o modelo antigo na memória.

**Depois de toda migração que cria tabela, confira os privilégios das MIs.**
Em 28/09, depois da `0005`, as duas Managed Identities estavam **sem nenhum
privilégio** em `released_part_numbers`, `serial_rules` e
`serial_rules_id_seq`. O `pg_default_acl` de produção estava **vazio**: o
`ALTER DEFAULT PRIVILEGES` das seções 2.4 e 3.3 nunca vigorou. Todas as
tabelas têm o mesmo dono (o grupo admin), então não era papel trocado. As
antigas tinham acesso só porque o `GRANT ... ON ALL TABLES` pegou o que
existia na hora.

O sintoma não aponta para a causa: o `doc_worker` consulta
`released_part_numbers` a cada documento, então **todo documento processado
entre o deploy da leva 6 e o `GRANT` falhou** com `permission denied`, e a tela
de part numbers também. A migração em si passou limpa.

Corrigido rodando, como admin, para cada MI (é idempotente):

```sql
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO "<mi>";
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO "<mi>";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO "<mi>";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO "<mi>";
```

Sem `FOR ROLE`, o privilégio padrão vale para o que o papel **atual** criar,
por isso tem de rodar como o mesmo grupo admin que roda o `alembic upgrade`.
Depois disso o `pg_default_acl` mostra uma linha `r` (`arwd`) e uma `S` (`rU`)
para o grupo, e a próxima tabela já nasce acessível. Conferir sempre:

```sql
SELECT pg_get_userbyid(defaclrole), defaclobjtype, defaclacl FROM pg_default_acl;
```

`has_table_privilege(r, t, 'SELECT,INSERT')` devolve verdadeiro se houver
**qualquer um** dos privilégios listados — conferir um por vez.

**O `alembic/env.py` não injeta token de propósito.** É o que deixa o
`PGPASSWORD` valer. Se alguém "corrigir" isso copiando o listener do
`shared/db.py`, a migração volta a conectar como a MI e a falhar.

---

## O App Service só aceita as redes da Caterpillar

Medido em 27/09, nos dois App Services:

```
ipSecurityRestrictionsDefaultAction: Deny
```

As regras `Allow` são as redes corporativas — `Cat_Amsterdam`, `Cat_Chicago`,
`Cat_Dublin`, `Cat_Peoria_Firewall`, `Cat_Plano`, `Cat_Singapore`,
`Cat_ExpressRoute_NAT`, `MS_ExpressRoute_NAT` — mais uma `Deny all` explícita.
O backend tem 32 regras a mais, `aiagent-documentreader-pov-fr-*`, que são os
IPs de saída do App Service do frontend, para ele alcançar o backend.

**Consequência prática: o runner do GitHub não alcança `/health`.** Ele recebe
403 com a página `Web App - Unavailable / blocked your access`, que é a
restrição respondendo — não a aplicação. Isso derrubou o job de deploy do
backend durante dias, com dez minutos de espera inútil, enquanto a aplicação
estava perfeitamente de pé: da VM o mesmo `/health` devolve 200.

O diagnóstico anterior — "5 minutos não bastam para o cold start" — era falso
pelo mesmo motivo: o `curl` manual que respondia 200 logo depois saía da rede
da CAT, não do runner.

**O SCM não herda essas regras** (`scmIpSecurityRestrictionsUseMain: false`), e
é por isso que o `az webapp deploy` funciona do runner enquanto o site público
não responde. Publicar e verificar passam por portas diferentes.

Para verificar o backend, de dentro da rede da CAT:

```powershell
curl.exe -s -o NUL -w "%{http_code}" https://aiagent-documentreader-pov-fastapi-appservice.azurewebsites.net/health
```

Easy Auth está **desligado** nos dois apps, então 403 nunca é autenticação.

## Troubleshooting rápido

- **Logs backend:** `az webapp log tail -g $RG -n $APP`
- **Logs function:** `az functionapp log tail -g $RG -n $FUNC` (ou App Insights)
- **PyPI bloqueado:** App Setting `PIP_INDEX_URL` apontando para o Artifactory/JFrog.
- **Erro de auth no Postgres:** regenere o `$token` (validade ~1h) e confira o portal
  Check Point aberto; confirme que a MI virou principal (seção 2.4 / 3.3).
- **`must be owner of table ...`:** você conectou como a Managed Identity. Ela
  tem só DML (seção 2.4) e nunca poderá fazer DDL. Migração roda como
  administrador — ver a seção abaixo.
- **`The access token has invalid format`:** o token veio com o `\r` que o
  clipboard do Windows cola junto. Limpe com `tr -d '\r\n '`.
- **`'ad-admin' is misspelled`:** o subcomando virou
  `az postgres flexible-server microsoft-entra-admin`.
- **`'execute' is misspelled`:** `az postgres flexible-server execute` precisa da
  extensão `rdbms-connect`, que não está instalada na VM.
- **403 com "blocked your access":** é a restrição de rede, não a aplicação.
  Ver a seção acima. Do runner do GitHub é o esperado.
- **`az webapp deploy` sem permissão:** confirme os direitos Web; você já tem
  `az webapp ssh`, deploy costuma vir junto. Se faltar, é pedido à plataforma.

---

## Passo obrigatorio (pos-reestruturacao): vendorizar o shared

O repo passou a ter um `shared/` unico na raiz. **Antes de empacotar o backend (secao 2.2)
e a function (secao 3.2)**, rode o vendoring, que copia `shared/shared/` pra dentro de cada
servico (`backend/shared` e `function/shared` sao gitignored e geradas por aqui):

Windows (VM):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

Linux/macOS:
```bash
bash scripts/build.sh
```

Sem esse passo, um clone novo nao tem `backend/shared` nem `function/shared` (sao
gitignored), o zip sobe sem o dominio compartilhado e o import quebra no boot.
