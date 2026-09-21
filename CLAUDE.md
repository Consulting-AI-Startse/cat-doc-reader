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

O espelhamento é por **patch escopado**, não por merge: `git diff` restrito aos
diretórios de aplicação, conferido com `git apply --check` antes de aplicar. Como
o patch chega até lá e quem abre o PR está na seção seguinte.

### O que espelha e o que nunca espelha

| espelha para a CAT | nunca espelha |
|---|---|
| `backend/`, `frontend/` | `function/pipeline/extractor_local.py` |
| `shared/shared/` | `function/pipeline/structurer_local.py` |
| `function/pipeline/structurer.py`, `extractor.py` | `function/requirements-local.txt` |
| `function/doc_worker.py`, `function_app.py` | `start-local.sh`, `stop-local.sh` |
| `backend/alembic/versions/`, `db/db-setup-v2.sql` | `docs/modo-local.md`, `docs/cat-cd/` |
| `check_rules.py`, `check_structurer.py` | `.env.local`, `.local/` |
| | as linhas locais do `.funcignore` |

Duas armadilhas de espelhamento, ambas capazes de quebrar a produção:

- **A ausência de `.github/` aqui é deliberada** (os workflows foram para
  `docs/cat-cd/` como referência). Propagar isso **apaga o CD da CAT**. Lá eles
  precisam continuar em `.github/workflows/`.
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
4. na VM: comandos de prompt do Windows para aplicar o diff
5. o Luis cria a branch e abre o PR la
```

**Neste repo nao se abre branch nem PR.** Commit direto na `main` e o normal; o
PR existe do lado da CAT, e quem abre e o Luis. O passo 5 e dele, nao nosso.

### O que entregar no passo 3

Para cada leva de mudancas que precisa ir para a VM, produza **quatro coisas**:

1. **O diff em `.txt`**, escopado so ao que espelha (ver a tabela acima). Nunca
   incluir os arquivos do modo local.
2. **O SHA-256 do arquivo**, para conferir na chegada. E o que separa "chegou
   corrompido" de um erro cifrado do `git apply` meia hora depois.
3. **Os comandos de Windows/PowerShell** para aplicar, conferir e testar --
   prontos para colar, sem depender de `python` no PATH (na VM nao esta; usar
   `.\function\.venv\Scripts\python.exe`).
4. **Nome de branch e descricao de PR sugeridos**, prontos para o Luis usar.
   Branch no padrao `fix/...` ou `feat/...`, descricao dizendo o que muda, por
   que, e como conferir.

### O transporte tem de preservar os bytes

Diff cru em `.txt` **nao sobrevive ao e-mail**: o filtro de links reescreve URLs
e nomes terminados em `.py` (`.py` e TLD do Paraguai), e isso ja corrompeu os
proprios cabecalhos `diff --git`, deixando o patch inaplicavel.

Entao, na pratica: gere o diff, **codifique em base64** e mande o `.txt` do
base64. Nao sobra nada que o filtro reconheca, e a decodificacao na VM e uma
linha:

```powershell
certutil -decode .\p.b64 .\cat.patch
(Get-FileHash .\cat.patch -Algorithm SHA256).Hash.ToLower()   # tem de bater
```

## Rodar e testar

```bash
./start-local.sh          # azurite, function, backend, frontend
./start-local.sh --status
./stop-local.sh

python check_rules.py        # 25/25
python check_structurer.py   # 14/14
cd function && python -c "import function_app"
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

**`shared/pyproject.toml` pede Python >= 3.14, mas a Function App roda 3.11.**
Só não quebra porque o deploy vendoriza os arquivos em vez de instalar o pacote.
Num venv local de 3.11 o `uv pip install -e ../shared` falha — use
`scripts/build.sh`, que é o que o deploy faz.

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
docs/cat-cd/         CD da CAT, so referencia -- nao roda daqui
```
