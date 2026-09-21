# docs/cat-cd — o CD da Caterpillar, como referência

Cópia dos workflows que fazem o deploy do POV. **Eles não rodam a partir deste
repositório**, e estão aqui de propósito, fora de `.github/workflows/`, para
que isso fique explícito.

Três motivos pelos quais não rodam daqui:

1. Leem `.github/variables/*.env`, que carregam identificadores da Caterpillar
   e foram removidos de todo o histórico deste repo. Ver `variables.md` para as
   chaves esperadas.
2. Dependem de secrets da org da CAT: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` e
   `ARTIFACTORY_ACCESS_TOKEN`.
3. Baixam os templates ARM governados do JFrog interno, inalcançável de fora da
   rede da Caterpillar.

O deploy de verdade acontece pelo repo `AICOE_AIagent_DocumentReader_POV`, na
org da Caterpillar. Alterar qualquer coisa aqui não muda nada lá.

## Para que servem então

São a referência de como o ambiente é provisionado, e a base do documento de
change-request que pedimos ao Cloud COE. Ler junto de
`aiagent-documentreader-infrastructure-azure/bicep/`, que continua no lugar
original porque não é executável por si só.

| arquivo | o que faz |
|---|---|
| `aiagent-documentreader-infra-provision.yml` | baixa os templates governados do JFrog, monta os artefatos e chama o deploy |
| `aiagent-documentreader-infra-deploy.yml` | aplica `main.bicep` e `rbac.bicep` no resource group |
| `deploy-model.yml` | publica deployments de modelo no Azure OpenAI (`modelVersionPairs`) |
| `app-ci.yml` | **novo** — portão de testes da aplicação; não publica nada |
| `app-deploy.yml` | **novo** — publica só o serviço que mudou, e reaplica as settings |
| `variables.md` | chaves esperadas dos três `.env`, sem valores |

## Os dois workflows de aplicação

Três cadências separadas, de propósito:

| workflow | dispara | faz |
|---|---|---|
| `app-ci.yml` | PR e push na `main` | testa; não publica |
| `app-deploy.yml` | push na `main`, por path | publica o que mudou e reaplica as settings |
| `...infra-provision.yml` | **só `workflow_dispatch`** | provisiona — e apaga as settings ao passar |

O provisionamento não pode disparar sozinho num push. Todo run dele substitui a
coleção inteira de application settings da function (o `functions.json` monta
`siteConfig.appSettings` como um `concat(...)` fechado), e mal configurada aqui
quer dizer **silenciosamente mockada**: `use_real_services` tem default `False`
em `shared/config.py`.

### O que o CI roda, e o que não roda

Roda: `import function_app` em 3.11, `check_rules.py`, `import app.main` em
3.14, `alembic upgrade head` contra um Postgres de serviço (conferido por
`information_schema`, não pelo stamp) e `npm run build`.

**Não roda `check_structurer.py`**: ele depende do `raw-civ-cap.json`, que é
artefato de cliente e não é versionado. Fica como passo manual na VM, onde o
arquivo existe.

### Deploy por path

```
frontend/**                   -> frontend
backend/**                    -> backend
function/**                   -> function
shared/shared/**              -> backend E function
backend/alembic/versions/**   -> migracao (alem do backend)
```

`shared/shared/` dispara os dois porque é a fonte única do domínio: subir um
sem o outro deixa backend e function em versões diferentes do mesmo código.

### B1 e B2 são passos do deploy, não IaC

O change request pedia `appCommandLine` e `additionalAppSettings` nos templates
governados. Como não haverá versão nova, os dois viram passos pós-publicação —
que é a alternativa que o próprio documento classifica como *strictly weaker*.

A fraqueza é específica e vale ter em mente: **o que esses passos aplicam morre
no próximo run de provisionamento**, inclusive um disparado por *policy
remediation* em vez de por nós. Por isso o job `settings` também é chamável
sozinho (`workflow_dispatch` → `settings-only`), para rodar depois de qualquer
run de infraestrutura sem republicar código.

### As dez settings, não nove

O apêndice do change request lista nove. São **dez**: falta `AZURE_DOCINTEL_HIGH_RES`,
que está em produção com `false` enquanto o default em `config.py` é `True`.
Se ela sumir, o OCR passa a rodar em alta resolução sem ninguém pedir — mais
lento e mais caro, sem erro nenhum.

Duas das dez mudam comportamento em silêncio quando apagadas:

| setting | default em `config.py` | efeito de sumir |
|---|---|---|
| `USE_REAL_SERVICES` | `False` | a function volta a rodar **mockada** |
| `AZURE_DOCINTEL_HIGH_RES` | `True` | OCR em alta resolução, mais lento e mais caro |

E uma está **ausente hoje**: `AZURE_OPENAI_API_VERSION`, que cai no default
`2024-10-21` do código. O job `settings` passa a gravá-la.

O passo de verificação confere por `length(value)`, nunca a olho — o
`az ... -o table` reflui valores longos, e isso já nos fez diagnosticar um
`FUNCTION_URL` truncado como ausente.

### O que ainda não está de pé

O job `migrate` precisa de duas coisas que hoje não existem:

1. **caminho de rede até o Postgres.** A allow-list do firewall tem os IPs de
   saída do Function App, não as faixas dos runners do GitHub.
2. **o service principal do CD como principal no Postgres**, com direito de DDL.

Até os dois existirem, aponte a variável `DB_RUNNER_LABEL` para um runner dentro
da rede da CAT. Sem isso o job falha no connect e a migração segue manual na VM.

### Variáveis e secrets que os dois esperam

| nome | tipo | usado em |
|---|---|---|
| `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | secret | login OIDC |
| `RESOURCEGROUPNAME` | variable | todos os comandos `az` |
| `PIP_INDEX_URL` | variable (opcional) | Artifactory, se PyPI estiver bloqueado |
| `DB_RUNNER_LABEL` | variable (opcional) | runner com acesso ao Postgres |

## Ao sincronizar com o repo da CAT

Nunca propague esta movimentação para lá. Lá os arquivos têm de continuar em
`.github/workflows/`, senão o CD para de existir. A sincronização deve ficar
restrita a `backend/`, `frontend/`, `function/` e `shared/`.
