---
name: operar-azure-cat
description: Armadilhas de operar os recursos Azure da CAT - az CLI, nomes de resource group, webssh e token do Entra, migracao de schema, restricao de rede do App Service, run de infra que apaga app settings. Use antes de diagnosticar deploy, rodar migracao ou mexer em recurso da CAT.
---

# Operar o Azure da CAT

Complementa o `DEPLOY.md`.

**Confira por `length(value)`, não a olho.** O `az ... -o table` reflui valores
longos, e isso nos fez diagnosticar um `FUNCTION_URL` truncado como ausente. O
mesmo vale para migração: confira `information_schema.columns`, não o
`alembic current` — uma migração pode estar carimbada sem estar aplicada.

**Nome de recurso da CAT se descobre, nao se deriva.** O resource group real e
`aicoe_aiagent_documentreader_pov`, nao o `<projeto>-<ambiente>` que os
workflows usam como rede de seguranca — o valor de verdade vem de
`.github/variables/*.env`, que nao existe deste lado. Derivar custou duas
rodadas, e o sintoma nao ajuda: `az` com o RG errado nao acha o servidor, e a
falha se parece com "nao consegui descobrir o admin". Descubra com
`az postgres flexible-server list --query "[].{n:name,g:resourceGroup}" -o tsv`
e afins, ou peca. O mesmo vale para nome de subcomando do `az`: `ad-admin`
virou `microsoft-entra-admin`, e `execute` precisa da extensao
`rdbms-connect`, ausente na VM.

**O webssh trunca a entrada em 4095 caracteres.** Um token do Entra tem ~4500,
entao colar de uma vez corta a assinatura do JWT e o servidor responde
`The access token has invalid format`. Vai em duas metades. Confira contando as
partes: `printf '%s' "$T" | awk -F. '{print NF}'` tem de dar **3**.

**Migracao de schema nao roda como a Managed Identity.** Ver a secao propria no
`DEPLOY.md`. A MI tem so DML por desenho; quem e dono das tabelas e o grupo
admin do Entra. E a VM nao alcanca o Postgres (fora da allow-list), entao o
unico caminho e o webssh com token de administrador.

**Roteiro da migracao que funcionou (0007, 01/10), e os quatro tropecos dele:**

- o usuario do banco e o **grupo admin do Entra**, `CATIT-GenAICOE-DocumentReaderPOV-Developer`
  (sai de `az postgres flexible-server microsoft-entra-admin list ... --query "[0].principalName"`),
  nunca o nome do servidor. Com o servidor no lugar do usuario o erro e
  `password authentication failed for user "...postgres.database."`;
- o host nao precisa ser procurado: o container tem o `DATABASE_URL` da MI em
  `/proc/1/environ` (`tr '\0' '\n' < /proc/1/environ | grep '^DATABASE_URL='`);
  o servidor e `aiagent-documentreader-pov-postgresql-server`;
- o token do admin vale ~1 h. Gere **na hora de colar**: metades de um token
  antigo dao `The access token has expired`, depois de toda a montagem certa;
- reabrir o webssh zera as variaveis (`H`, `PGPASSWORD`). Conferir com
  `echo "H=[$H] token=${#PGPASSWORD}"` antes do `alembic current`;
- a aplicacao esta em `/tmp/<hash>` (`find /tmp /home -name alembic.ini`), com
  o venv em `antenv/`;
- **instrucao com marcador (`SERVIDOR`, `GRUPO-ADMIN`) e colada literalmente.**
  Para a VM, mande o valor ja preenchido ou um comando que o descubra -- nunca
  um placeholder no meio de uma linha que se cola inteira.

**O App Service so aceita as redes da CAT, e o runner do GitHub nao e uma
delas.** Acao padrao `Deny`; as `Allow` sao Cat_Amsterdam, Cat_Chicago,
Cat_Dublin, Cat_Peoria_Firewall, Cat_Plano, Cat_Singapore e os ExpressRoute
NAT. O `/health` do runner devolve 403 com a pagina "blocked your access" --
que e a restricao, nao a aplicacao. Isso derrubou o deploy do backend por dias
com um app saudavel, e gerou um diagnostico falso ("cold start de 5 minutos")
porque o curl manual de conferencia saia da rede da CAT. **O SCM nao herda
essas regras**, e e por isso que publicar funciona e verificar nao: sao portas
diferentes. Ver a secao propria no `DEPLOY.md`.

**Um run de infraestrutura pode apagar as app settings.** O `functions.json`
monta `siteConfig.appSettings` como um `concat(...)` fechado, então reprovisionar
zera o que foi configurado por fora. Depois de qualquer run de infra, reconfira
as settings — `DATABASE_URL` sumiu assim uma vez.

**O papel da function no OpenAI e uma tag, e a tag pode sumir.** O RBAC da CAT
e declarado como tag `roleAssignments1` no recurso (`rbac.bicep`), e um robo da
plataforma a transforma em atribuicao de papel alguns minutos depois. Em 25/09
a `cloud-coe-automation-new` regravou as tags da conta do OpenAI 13 min depois
do nosso RBAC, deixou so as de governanca (`automationtype`, `templateVersion`,
`validateNetworking`) e a atribuicao nunca foi criada; o DocIntel, que nao teve
tags regravadas, manteve a dele. O sintoma veio em 30/09, quando a function
voltou a rodar: `401 PermissionDenied` sem a data action
`.../OpenAI/deployments/chat/completions/action`, com o Document Intelligence
respondendo 202 na mesma execucao. O documento vai para `error` com a mensagem
em `error_message` -- o `concluido` no log do worker so diz que ele terminou.
Conferir: `az resource show --ids <conta> --query tags` e `az role assignment
list --scope <conta> --assignee <MI>`. Corrigir: `az tag update --operation
Merge` com a mesma tag do `rbac.bicep` (nao apaga as outras); o papel apareceu
em minutos, depois `az functionapp restart`. Reprovisionar o RBAC tambem
resolve, mas o run de infra zera as app settings.

**PowerShell 5.1 nao enumera o que sai do `ConvertFrom-Json` num pipe.** A
lista inteira vira um objeto so, e `ForEach-Object { $_.campo }` imprime todos
os valores numa linha. Atribua a uma variavel antes do pipe. E o `az` do
Windows passa pelo `cmd.exe`: parenteses na `--query` quebram com
`} was unexpected at this time` -- use `-o json | ConvertFrom-Json`.

**Colar bloco longo na VM perde caracteres.** Um script de 90 linhas chegou com
pedacos de linha faltando (`-match` sem o operando, `a taolor Red`) e o parser
acusou `Missing closing '}'`. Script de mais de umas poucas linhas vai como
`.b64` por e-mail, com o SHA-256 conferido no proprio comando que o executa.
