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
| `check_rules.py`, `check_structurer.py`, `check_dedupe.py`, `check_parts.py` | `start-local.sh`, `stop-local.sh` |
| `DEPLOY.md`, `scripts/` | |
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

**A divergência foi encerrada em 25/09, com o merge da leva 4.** O blob do
`doc_worker.py` da CAT foi conferido antes de enviar e batia com `c70c235`, o
commit da extração; a leva levou o nosso `HEAD` por cima, e agora os dois
arquivos são idênticos, gancho de modo local incluído. **Se algum dia voltar a
aparecer código de modo local dentro deste arquivo, a divergência volta junto.**

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

**A tabela já esteve incompleta duas vezes, e o sintoma é sempre o mesmo:** um
arquivo que existe dos dois lados, nunca foi espelhado, e só aparece quando
alguém confere os blobs. Aconteceu com `backend/app/api/documents.py` e
`frontend/src/pages/DocumentDetail.tsx` na leva 4, e com o `DEPLOY.md` na leva
5 — os três estavam na versão de 27/08, do `init`. O `DEPLOY.md` de lá ainda
mandava configurar `USE_REAL_SERVICES=false`, que é o que faz a function rodar
mockada sem emitir erro. **Conferir a árvore inteira com `git ls-tree -r HEAD`
custa um comando e responde isso de uma vez.**

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

### Leva para a CAT: o que nao se negocia

O passo a passo de montar a leva (o que entregar, script autocontido,
conferencia por blob, transporte) esta na skill `.claude/skills/leva-cat/` --
carregue antes de montar qualquer pacote. O que vale sempre:

- **Nunca incluir os arquivos do modo local** (tabela acima) no pacote.
- **Transporte e zip dos arquivos finais em base64** (`.b64`), com SHA-256 do
  `.b64` e do `.zip`. Nunca diff cru nem instrucoes em texto puro: o filtro de
  e-mail reescreve URLs e nomes `.py`. **Nunca `.ps1`**, que nao passa.
- **Confira pelo blob do git** (`git rev-parse HEAD:<caminho>`), nunca por
  SHA-256 de arquivo: o CRLF do checkout da VM faz o hash nunca bater.
- **Nao preveja a base pelo nosso historico** -- peca os blobs a VM antes.
- **Nada de transporte entra no repo**: fica em `Downloads` na VM.
- **Teste o script antes de mandar**, contra uma arvore reconstruida dos blobs.

## Rodar e testar

```bash
./start-local.sh          # azurite, function, backend, frontend
./start-local.sh --status
./stop-local.sh

python check_rules.py        # 75/75
python check_structurer.py   # 14/14
cd function && python -c "import function_app"

# os dois que precisam de banco migrado -- e que APAGAM dados dele:
# o check_dedupe apaga os documentos, o check_parts apaga a lista de PN.
# Aponte para uma base de teste, nunca para a de desenvolvimento.
DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/dedupe_test \
    python check_dedupe.py   # 12/12
DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/dedupe_test \
    python check_parts.py    # 25/25
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

  **A exceção, decidida em 25/09: linha que não é código sai de `line_items`.**
  Só `not_a_code` e `missing` — nunca `other_code`, que é código de fornecedor
  (`15.1301.466`) e é item real, e nunca "não está na lista de PN liberados",
  que apagaria as faturas de fornecedor inteiras. E não é descarte de verdade:
  a linha vai para `discarded_lines` com o motivo, e aparece na tela.

  O filtro roda **antes da conferência aritmética**, de propósito. Na fatura de
  motor 93872204 a nota `END USE` vinha como item com o preço do motor e
  estourava o total; sem ela a soma fecha. E a recíproca é a rede de segurança:
  **se o filtro derrubar uma linha legítima, a soma para de fechar e o
  documento vai para revisão sozinho.** É o que separa um filtro auditável de
  um filtro cego — tem teste travando isso (`check_structurer.py`, seção 10d).
- **Rejeitar quer dizer "esta leitura não presta, vou subir de novo".** Não é
  decisão de negócio sobre a fatura. Por isso documento `rejected` (e `error`)
  não serve de referência para duplicata: se servisse, o reenvio corrigido
  voltaria marcado como cópia do scan que acabou de ser descartado. E como a
  marca é calculada na gravação, rejeitar **depois** exige reavaliar quem
  apontava para ele — é o que o `reresolve_dependents` faz no endpoint.

- **Nota que o revisor não vê não é explicação.** As notas de `validation`
  moravam só no `raw_extraction` e nos eventos, e a tela de revisão não
  mostrava nenhuma — o documento aparecia em "Revisar" sem dizer por quê. Isso
  passou a ser defeito quando o filtro começou a remover linhas: `validation` e
  `discarded_lines` agora saem no payload do documento e têm painel próprio.

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

**E por serem geradas, elas não viajam na leva — ficam velhas do outro lado.**
Toda leva que toca `shared/shared/` tem de rodar o build na CAT logo depois de
aplicar, antes de qualquer teste: lá é `scripts/build.ps1`, o equivalente
Windows. A leva 4 aprendeu isso do jeito ruim — o `check_rules.py` passou a
importar `shared.dedupe`, o `function/shared/` da VM era de antes e não tinha
esse módulo, e o `ModuleNotFoundError` não diz nada sobre vendorização. O
script de aplicação faz esse passo desde então.

**A venv local tem dependencia que o CI da CAT nao tem.** Ela e montada do
`pyproject.toml` e arrasta o modo local junto -- `openai`, Docling, e o que eles
puxam. O CI instala so o `requirements.txt`. Um `import` que funciona aqui pode
nao existir la, e o erro so aparece no run deles. Aconteceu com o `httpx`, que
o `TestClient` do FastAPI exige: o `check_parts.py` passava aqui e quebraria no
CI. **Teste de logica nao sobe HTTP** -- a funcao pura vai para o `shared` e o
check chama direto. Para conferir antes de mandar, monte uma venv limpa com
`python -m venv` + `pip install -r backend/requirements.txt` e rode os checks
nela; e o unico jeito de ver o que o CI ve.

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

**Operacao no Azure da CAT** (`az`, webssh, migracao, App Service, run de
infra): as armadilhas estao na skill `.claude/skills/operar-azure-cat/` --
carregue antes de diagnosticar ou mexer em recurso da CAT.

**`db/db-setup-v2.sql` e gerado das migracoes do alembic** -- nao editar a mao.
