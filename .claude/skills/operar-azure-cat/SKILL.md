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
