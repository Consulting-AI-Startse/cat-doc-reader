---
name: leva-cat
description: Montar uma leva para o repo da CAT (AICOE_AIagent_DocumentReader_POV) - o que entregar, o script autocontido de aplicacao em .b64, conferencia por blob do git e transporte por e-mail. Use sempre que for empacotar mudancas para a VM da CAT ou escrever o script aplicar-*.
---

# Montar uma leva para a CAT

Complementa o `CLAUDE.md` (a tabela do que espelha, o fluxo de 5 passos e as
regras que nao se negociam ficam la). "A tabela acima" e "a secao acima" abaixo
se referem ao `CLAUDE.md`.

## O que entregar no passo 3

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

   **Entregar o `.b64` sem o comando de rodar nao e entrega.** Junto dos
   arquivos vao sempre: os comandos exatos, **com os nomes reais desta leva**
   (nunca `<leva>` generico), e em **qual maquina** rodam -- a VM da CAT
   (`souzal1`), nao a maquina de desenvolvimento (`luisf`). Os dois `.b64` vao
   por e-mail e ficam em `Downloads` do lado de la; o script acha o zip sozinho.

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

## Mande arquivo pronto, não diff

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

## O transporte tem de preservar os bytes

Diff cru em `.txt` **nao sobrevive ao e-mail**: o filtro de links reescreve URLs
e nomes terminados em `.py` (`.py` e TLD do Paraguai), e isso ja corrompeu os
proprios cabecalhos `diff --git`, deixando o patch inaplicavel.

Entao, na pratica: gere o diff, **codifique em base64** e mande o `.txt` do
base64. Nao sobra nada que o filtro reconheca.

**Isto vale para o arquivo de instrucoes tambem, nao so para o patch.** A leva
do poison handler mandou o LEIA-ME em texto puro e o filtro reescreveu os nomes
dos arquivos dentro dele (`function/doc_worker` + a extensao virou um link do
urldefense). O patch, em base64, chegou intacto ao lado.

## Nada de transporte entra no repo

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
