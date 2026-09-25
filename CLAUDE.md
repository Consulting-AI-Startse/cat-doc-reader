# CLAUDE.md

Leia isto antes de mexer no repo. O resto do contexto está no `README.md`
(o que o sistema faz), `STRUCTURE.md` (por que está assim), `BACKLOG.md`
(o que vem a seguir), `docs/ambiente.md` (o que precisa estar instalado) e
`docs/sync-cat.md` (o que já foi espelhado para a CAT).

## A regra central: este repo espelha o da Caterpillar

Existem **dois repositórios**, com históricos independentes — não dá para dar
merge entre eles:

| | |
|---|---|
| `Consulting-AI-Startse/cat-doc-reader` | repo de desenvolvimento da StartSe |
| `AICOE_AIagent_DocumentReader_POV` (org da CAT) | **de onde sai o deploy**, na infraestrutura da Caterpillar |

**Toda mudança de fluxo ou de regra de negócio feita aqui tem de ser espelhada
para lá**, e o repo da CAT é a referência do que está em produção. Se os dois
divergirem, quem manda é o de lá.

O repo da CAT está clonado na VM Windows em:

```
C:\Users\souzal1\repos\AICOE_AIagent_DocumentReader_POV
```

É contra esse caminho que os comandos de aplicação do patch são escritos (passo
4 do fluxo), e é de lá que sai o deploy do `DEPLOY.md`.

O espelhamento é por **patch escopado**, não por merge: `git diff` restrito aos
diretórios de aplicação, conferido com `git apply --check` antes de aplicar. Como
o patch chega até lá e quem abre o PR está na seção seguinte.

### O que espelha e o que nunca espelha

| espelha para a CAT | nunca espelha |
|---|---|
| `backend/`, `frontend/` | `function/pipeline/extractor_local.py` |
| `shared/shared/` | `function/pipeline/structurer_local.py` |
| `function/pipeline/structurer.py`, `extractor.py` | `function/doc_worker_local.py` |
| `function/doc_worker.py`¹, `function_app.py` | `function/requirements-local.txt` |
| `check_rules.py`, `check_structurer.py` | `start-local.sh`, `stop-local.sh` |
| `backend/alembic/versions/`, `db/db-setup-v2.sql` | `docs/modo-local.md`, `docs/cat-cd/` |
| `aiagent-documentreader-infrastructure-azure/` | `.env.local`, `.local/` |
| | as linhas locais do `.funcignore` |

¹ **O `doc_worker.py` já divergiu dos dois lados, e a divergência está sendo
encerrada.** Os blocos de modo local moravam nele, só existiam aqui, e faziam o
contexto ter ~24 linhas a mais — nenhum `git diff` do arquivo aplicava lá, o que
custou uma leva inteira. Foram extraídos para `function/doc_worker_local.py`,
que nunca espelha; o que sobrou no `doc_worker.py` é um `import` protegido por
`try/except ModuleNotFoundError`.

**Esse gancho é código que espelha** — são 14 linhas, e é justamente elas que
tornam os dois arquivos idênticos. Do lado da CAT ele é inerte: o módulo não
existe lá, o `import` levanta `ModuleNotFoundError`, sobra `_local = None` e o
caminho de produção segue direto. A extração não eliminou a divergência sozinha;
ela a **reduziu de 24 para 14 linhas e a tornou espelhável**, porque as 24 nunca
poderiam ir para lá e as 14 podem:

```
antes da extracao:   nosso = CAT + 24 linhas de modo local
depois da extracao:  nosso = CAT + 14 linhas de gancho
depois da leva:      nosso = CAT
```

A identidade só vale **depois que a leva `feat/app-cicd-and-appservice-config`
for aplicada na CAT**; até lá, o arquivo ainda difere e a base de lá não é
nenhum estado commitado aqui. **Se algum dia voltar a aparecer código de modo
local dentro deste arquivo, a divergência volta junto.**

Três armadilhas de espelhamento, todas capazes de quebrar a produção:

- **A ausência de `.github/` aqui é deliberada** (os workflows de infraestrutura
  foram para `docs/cat-cd/` como referência). Propagar isso **apaga o CD da
  CAT**. Lá eles precisam continuar em `.github/workflows/`.
- **Os workflows de aplicação são a exceção que espelha.** `app-ci.yml` e
  `app-deploy.yml` moram em
  `aiagent-documentreader-infrastructure-azure/workflows/`, diretório que existe
  igual dos dois lados — então vão no patch, por caminho. Mas **o Actions só
  executa workflow de `.github/workflows/`**: do lado da CAT eles precisam ser
  copiados para lá. Espelhar o arquivo não é o mesmo que ativá-lo.
- **Workflow novo confere autenticação e nomes de variável contra
  `docs/cat-cd/`.** Os workflows de aplicação nasceram pedindo um
  `secrets.AZURE_SUBSCRIPTION_ID` que não existe lá; o `azure/login` recebeu
  string vazia e falhou com `Ensure 'subscription-id' is supplied`, erro que não
  diz que o problema é a convenção. A CAT lê o valor de `.github/variables/*.env`
  para o `GITHUB_ENV` num passo dedicado e usa `env.AZURESUBSCRIPTIONID` — é o
  que os três workflows de infraestrutura já faziam, no repo, desde sempre. O
  mesmo vale para `RESOURCEGROUPNAME`. **A referência está em `docs/cat-cd/`:
  leia antes de escrever, não depois de o run falhar.**
- **`.github/variables/*.env` foi removido do histórico deste repo** — carregava
  subscription ID, object ID de grupo AAD e client IDs da Caterpillar. Não
  recriar aqui, e não propagar a remoção para lá.

## Os artefatos do cliente não estão no repo — peça

As planilhas e os PDFs que sustentam quase toda decisão deste projeto **não são
versionados**: são dados do cliente (part numbers, preços, condições comerciais
de fornecedores). Ficam fora, na máquina de quem está trabalhando.

| artefato | o que é |
|---|---|
| `SUBIR_FATURA_GA.xlsx` | contrato de 22 campos, premissas e plano de aceitação |
| `PN Liberados.xlsx` | 206.769 part numbers liberados, com descrição |
| `Gabarito_DocReader.xlsx` | a única verdade legível por máquina: 38 linhas, 16 faturas |
| corpus de 28 PDFs | faturas reais de onde saíram todas as regras de formato |
| `CIV MRKU6295556.PDF` | o documento difícil: 35 páginas, 16 delas giradas |
| `raw-civ-cap.json` | extração do CIV; o `check_structurer.py` depende dela |

**Se precisar de um destes e ele não estiver na máquina, peça ao Luis.** Não
invente caminho, não reconstrua de memória e não conclua que o arquivo não
existe. O `raw-civ-cap.json` em particular pode ser regerado na hora pela VM,
então não tem por que trabalhar com uma versão velha.

## Registre toda leva espelhada

`docs/sync-cat.md` é o log do que já foi para o repo da CAT. **Toda leva nova
entra lá**, no topo, com data, o que mudou, como foi transportada, o nome da
branch e o estado do PR — e o estado é atualizado quando o PR for merjado.

Sem esse arquivo não dá para saber o que já foi espelhado: os dois repos têm
históricos independentes, então o git não responde essa pergunta.

## Mantenha `docs/ambiente.md` atualizado

Versão de ferramenta, pacote novo, porta nova, passo de setup — tudo isso entra
em `docs/ambiente.md` na mesma leva da mudança. É o arquivo que responde "o que
preciso ter instalado para isto rodar", e ele só serve se estiver certo.

## O fluxo de trabalho

```
1. desenvolve aqui, commitando na main deste repo
2. a mudanca e de teste local?  -> fica aqui, fim
   a mudanca e feature de verdade? -> tem de ir para a VM da CAT
3. transporte: e-mail, no arquivo mais leve possivel (.txt com o diff)
4. na VM (C:\Users\souzal1\repos\AICOE_AIagent_DocumentReader_POV):
   comandos de prompt do Windows para aplicar o diff
5. o Luis cria a branch e abre o PR la
```

**Neste repo nao se abre branch nem PR.** Commit direto na `main` e o normal; o
PR existe do lado da CAT, e quem abre e o Luis. O passo 5 e dele, nao nosso.

### O que entregar no passo 3

Para cada leva de mudancas que precisa ir para a VM, produza **quatro coisas**:

1. **O diff em `.txt`**, escopado so ao que espelha (ver a tabela acima). Nunca
   incluir os arquivos do modo local.
2. **O SHA-256 do `.b64` e do `.zip`**, para conferir o transporte. O do `.b64`
   e o que importa: conferido antes de decodificar, separa "chegou corrompido"
   de um erro cifrado do `certutil` meia hora depois. **E o blob SHA-1 do git
   de cada arquivo da leva, em duas colunas** -- base e depois -- para conferir
   o repo. SHA-256 de arquivo nao serve para isso: o CRLF do checkout do
   Windows garante que nunca bata (ver a secao acima).
3. **Um script autocontido que aplica, confere e testa sozinho** -- nao um
   LEIA-ME com comandos para colar e saidas para conferir a olho. Ele roda a
   partir de `Downloads` (nada de transporte entra no repo, ver abaixo) e nao
   depende de `python` no PATH (na VM nao esta; usar
   `.\function\.venv\Scripts\python.exe`).

   **Autocontido quer dizer:** todo valor esperado -- SHA-256, tamanho, blob
   base, blob depois -- esta embutido no proprio script, que compara a saida de
   cada passo e **para na primeira divergencia**. Nada de "confira se bate com
   a tabela": se sobrou conferencia para o operador, o script esta incompleto.

   Formato: o script viaja em **base64**, com extensao `.b64` -- e um dos
   poucos tipos que passam no e-mail da CAT. Do lado de la o `certutil -decode`
   devolve um `.txt`, que roda por um comando. **Nao mandar `.ps1`**, que nao
   passa. E o `.txt` decodificado tem de ser executavel de ponta a ponta:
   qualquer prosa vai em comentario `#`, porque texto solto quebra a execucao.

   Rodar um `.txt` exige `Invoke-Expression`; o `-File` e o dot-source do
   PowerShell so aceitam `.ps1`:

   ```powershell
   cd $env:USERPROFILE\Downloads
   certutil -decode .\aplicar-<leva>.b64 .\aplicar-<leva>.txt
   powershell -ExecutionPolicy Bypass -Command "Invoke-Expression (Get-Content -Raw .\aplicar-<leva>.txt)"
   ```

   Tres armadilhas medidas ao escrever o primeiro deles:

   - **So ASCII.** O PowerShell 5.1 le arquivo sem BOM como ANSI, entao acento
     vira lixo. O `certutil -decode` nao poe BOM.
   - **`$ErrorActionPreference = 'Stop'` mata o script no lugar errado.** O
     `git` escreve em stderr em situacao normal (`rev-parse` de caminho que
     ainda nao existe no HEAD), e o PowerShell promove isso a erro terminante
     -- `2>$null` nao segura. Chame o `git` por um wrapper que afrouxa a
     preferencia e decide pelo codigo de saida.
   - **A mensagem de erro tem de dizer se a arvore foi escrita.** Uma flag que
     vira `true` antes do `Expand-Archive` e a diferenca entre "o repo nao foi
     tocado" e "pode estar pela metade, desfaca assim".

   **Teste o script antes de mandar.** Reconstrua a arvore da CAT a partir dos
   blobs que ela reportou (`git cat-file -p <blob>` monta cada arquivo), rode o
   script contra esse repo de teste e confira os tres caminhos: aplica limpo,
   detecta leva ja aplicada, e para sem escrever quando um arquivo diverge.
4. **Nome de branch e descricao de PR sugeridos**, prontos para o Luis usar.
   Branch no padrao `fix/...` ou `feat/...`, descricao dizendo o que muda, por
   que, e como conferir.

### Mande arquivo pronto, não diff

Um `git diff` exige que o outro lado esteja exatamente onde você pensa que está,
e essa suposição já falhou duas vezes seguidas: uma pela leva anterior já ter
sido aplicada lá, outra pelos blocos de modo local do `doc_worker.py`. O
diagnóstico custou mais que o transporte.

Então: **transporte é zip dos arquivos finais, em base64**, com o SHA-256 do
`.b64` e do `.zip`. Sem contexto para casar, sem CRLF para negociar. O `git
diff` continua sendo como se revisa aqui; só deixou de ser o formato de envio.

E antes de sobrescrever qualquer arquivo que já existe lá, **confira o que está
lá** contra o que você usou de base. Se não bater, pare: pode haver trabalho que
só existe do lado da CAT, e lá é a referência.

**Mas não confira por SHA-256 de arquivo — confira pelo blob do git.** O repo
não tem `.gitattributes`, então o checkout do Windows grava CRLF e todo arquivo
de texto no disco da VM tem bytes diferentes dos daqui. Um SHA-256 calculado
aqui **nunca** bate lá, e o alarme falso se lê exatamente como "há trabalho só
do lado da CAT, pare" — que é o oposto do que está acontecendo. Já custou uma
leva: os três hashes que chegaram a sair na VM estavam todos certos, e só se
revelaram certos depois de converter a base para CRLF.

O blob SHA-1 do git é calculado sobre o conteúdo normalizado em LF, então é
igual nos dois repos apesar dos históricos independentes:

```bash
git rev-parse HEAD:<caminho>     # o que o commit tem (os dois lados)
git hash-object -- <caminho>     # o que o arquivo na árvore tem
```

Mande as duas colunas no LEIA-ME: o blob da **base** (o que tem de estar lá
antes) e o blob **depois** da leva. A segunda coluna paga por si: um arquivo que
já está no valor "depois" foi aplicado numa tentativa anterior, que é
precisamente o diagnóstico que custou a leva 2.

**Não preveja a base a partir do nosso histórico — peça ao outro lado.** Para
qualquer arquivo tocado por um commit que não espelha, o blob da CAT não existe
em lugar nenhum daqui, e não há como derivá-lo de um `git log`. Foi o que
aconteceu com o `doc_worker.py`: entre `Refine OCR extraction` e o poison
handler ele recebeu quatro commits de modo local, nenhum deles espelhado, então
a base real da CAT era "o nosso HEAD menos o gancho de modo local" — um estado
que nunca foi commitado aqui. A previsão deu um falso "DIVERGE" e parou a leva.

O barato é inverter a ordem: **antes de montar o pacote, peça os blobs da VM**
(`git rev-parse HEAD:<caminho>`, um por arquivo da leva) e monte a coluna "base"
com o que voltou. Um comando, uma resposta, e a conferência passa a valer
alguma coisa — prevista, ela só testa a nossa suposição contra ela mesma.

O SHA-256 continua valendo para o `.b64` e o `.zip` — ali o que se confere é o
transporte, byte a byte, e não há checkout no meio.

### O transporte tem de preservar os bytes

Diff cru em `.txt` **nao sobrevive ao e-mail**: o filtro de links reescreve URLs
e nomes terminados em `.py` (`.py` e TLD do Paraguai), e isso ja corrompeu os
proprios cabecalhos `diff --git`, deixando o patch inaplicavel.

Entao, na pratica: gere o diff, **codifique em base64** e mande o `.txt` do
base64. Nao sobra nada que o filtro reconheca.

**Isto vale para o arquivo de instrucoes tambem, nao so para o patch.** A leva
do poison handler mandou o LEIA-ME em texto puro e o filtro reescreveu os nomes
dos arquivos dentro dele (`function/doc_worker` + a extensao virou um link do
urldefense). O patch, em base64, chegou intacto ao lado.

### Nada de transporte entra no repo

O `.b64`, o `.patch` e o LEIA-ME **ficam em `Downloads` na VM e nunca sao
copiados para dentro do repo**. Decodifique e confira ali; aplique de fora para
dentro, com caminho absoluto. Um arquivo de transporte deixado na arvore e
esquecido sobe para o repo da CAT -- ja aconteceu com o `cat-fixes.patch`, que
precisou de `git rm --cached` + amend antes do PR.

```powershell
cd $env:USERPROFILE\Downloads
(Get-Item .\p.b64).Length                                    # confere o b64 ANTES
(Get-FileHash .\p.b64 -Algorithm SHA256).Hash.ToLower()      # de decodificar
certutil -decode .\p.b64 .\cat.patch
(Get-FileHash .\cat.patch -Algorithm SHA256).Hash.ToLower()  # tem de bater

cd <raiz do repo da CAT>
git apply --check "$env:USERPROFILE\Downloads\cat.patch"
git apply "$env:USERPROFILE\Downloads\cat.patch"
git status --short   # so os arquivos modificados; nenhum '??'
```

Conferir o hash do proprio `.b64` antes de decodificar e o que separa "chegou
corrompido" de um erro cifrado do `certutil` ou do `git apply` depois.

## Rodar e testar

```bash
./start-local.sh          # azurite, function, backend, frontend
./start-local.sh --status
./stop-local.sh

python check_rules.py        # 75/75
python check_structurer.py   # 14/14
cd function && python -c "import function_app"

# o unico check que precisa de banco (migrado, e APAGA os documentos dele)
DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/documentreader \
    python check_dedupe.py   # 12/12
```

O `import function_app` **antes de qualquer publish**. Já subimos um módulo que
compilava mas não importava (cinco funções indentadas 4 espaços a mais viraram
métodos de uma classe; `py_compile` passa porque nome se resolve em tempo de
chamada) e a function respondeu 404 em produção até alguém rodar isso.

O modo local de IA — Docling no lugar do Document Intelligence, OpenRouter no
lugar do Azure OpenAI — está em `docs/modo-local.md`, com a matriz de settings.

## Convenções

- **Identificadores em inglês, prosa e comentários em português.** Vale para
  código, docstrings, mensagens de commit e chaves de JSON.
- **Comentário explica o porquê, não o quê.** O padrão do repo é registrar a
  evidência: qual documento quebrou, qual número apareceu. Um comentário que
  repete a linha de código abaixo dele é ruído.
- **Marcar, nunca descartar.** Linha com problema recebe nota em `validation` e
  o documento vai para `needs_review`. Um filtro que apagava linha sem sete
  dígitos destruía os itens de dois dos quatro documentos de teste, porque
  `674-8657` é part number legítimo.
- **Documento gravado sem explicação é bug.** Ou estoura, ou deixa nota. Já
  tivemos documento salvo vazio e tela em branco para o revisor, sem uma pista.

## Armadilhas que já custaram tempo

**Arquivo de texto não sobrevive intacto ao e-mail corporativo.** O filtro de
links reescreve URLs e também nomes terminados em `.py` (`.py` é o TLD do
Paraguai), então o conteúdo chega diferente do que saiu. Já corrompeu: o escopo
do token do Azure OpenAI, o `start-local.ps1` (`--blobHost http://127.0.0.1`,
que não é host válido), um manifesto de sync inteiro, docstrings de dois scripts
de teste e, uma vez, os próprios cabeçalhos de um patch — que por isso não
aplicou.

Duas consequências práticas:

- No código, monte URLs e nomes de arquivo em pedaços
  (`("azurewebsites","net") -join "."`), para que uma reescrita não quebre o
  valor.
- Para transportar patch ou script, use um formato que preserve os bytes
  (base64 ou zip) e **confira o SHA-256 na chegada** antes de aplicar. Conferir
  o hash é o que transforma "chegou corrompido" de bug misterioso em erro na
  hora certa.

**Nunca edite `backend/shared/` nem `function/shared/`.** São geradas por
`scripts/build.sh` a partir de `shared/shared/`. Editar a cópia funciona até o
próximo build sobrescrever em silêncio.

**O `shared/` roda em 3.11, mesmo com o backend em 3.14.** A Function App está
em 3.11 (a 3.14 ainda não chegou lá) e o `shared` é implantado nas duas
aplicações: sintaxe que só exista em 3.14 passa no backend e **quebra no import
da function**. Por isso `shared/pyproject.toml` declara `>=3.11` enquanto
`backend/pyproject.toml` declara `>=3.14` — a assimetria é intencional, e o piso
do `shared` é sempre o menor dos dois runtimes. O `shared` nunca é instalado
como pacote: é vendorizado por `scripts/build.sh`, que é o que o deploy faz.

**Confiança auto-reportada pelo modelo não vale nada.** Um documento voltou com
`confidence: 0.95` e quatro defeitos. Confiança útil vem do OCR (confiança por
palavra) ou da aritmética (soma das linhas contra o total impresso).

**`temperature=0` não é determinismo.** A mesma fatura, no mesmo modelo, deu
`total 22944.02` numa rodada e `22.94` na seguinte. Medir acurácia com uma
rodada só é medir ruído.

**Confira por `length(value)`, não a olho.** O `az ... -o table` reflui valores
longos, e isso nos fez diagnosticar um `FUNCTION_URL` truncado como ausente. O
mesmo vale para migração: confira `information_schema.columns`, não o
`alembic current` — uma migração pode estar carimbada sem estar aplicada.

**Um run de infraestrutura pode apagar as app settings.** O `functions.json`
monta `siteConfig.appSettings` como um `concat(...)` fechado, então reprovisionar
zera o que foi configurado por fora. Depois de qualquer run de infra, reconfira
as settings — `DATABASE_URL` sumiu assim uma vez.

## Onde ficam as coisas

```
shared/shared/       fonte unica: config, db, models, storage
backend/app/api/     rotas (documents, dashboard)
function/            function_app.py (3 gatilhos) + doc_worker.py + pipeline/
frontend/src/        paginas em pages/, rotas inline em main.tsx
backend/alembic/     migracoes; db/db-setup-v2.sql e gerado delas
docs/ambiente.md     ferramentas e versoes do ambiente local
docs/modo-local.md   modo local de IA
docs/sync-cat.md     log do que ja foi espelhado para a CAT
docs/cat-cd/         CD de infraestrutura da CAT, so referencia -- nao roda daqui
aiagent-documentreader-infrastructure-azure/
  bicep/             main.bicep e rbac.bicep (espelham)
  workflows/         app-ci.yml e app-deploy.yml (espelham; ativar em .github/)
```
