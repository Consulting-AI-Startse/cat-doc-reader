# Hooks — guardrails de desenvolvimento assistido

Dois scripts que o Claude Code executa antes de uma ferramenta rodar,
registrados em [`../settings.json`](../settings.json). Vieram do
`cat-freight-poc` em 19/10, adaptados. São **garantias**, não pedidos: um
pedido em prosa some no meio de uma conversa longa; um hook roda sempre.

| Evento | Script | O que faz |
|---|---|---|
| `PreToolUse` · `Bash` | `guard-command.sh` | recusa comando destrutivo, e `git commit` / `git push` com a `main` em checkout |
| `PreToolUse` · `Write\|Edit` | `guard-secrets.sh` | recusa segredo em arquivo versionado (`.env.local` e o resto do gitignore passam) |

`_hooklib.sh` não é hook — é a biblioteca que os outros carregam. É Python e
não `jq` porque o `jq` não está instalado nas máquinas de desenvolvimento, e um
hook que falha calado é pior que nenhum.

O que **não** foi trazido, e por quê: o hook de `Stop` daquele repo roda lint e
testes no fim do turno. Aqui não há `ruff`, e dos quatro `check_*.py` dois
apagam dados do banco e um depende do `raw-civ-cap.json` estar na máquina.
Quando houver um check rápido e sem dependência externa, ele entra.

```bash
# testar à mão, com o payload que o hook recebe de verdade
echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}' | bash .claude/hooks/guard-command.sh

# desligar temporariamente (settings.local.json é pessoal, não vai para o git)
#   "disableAllHooks": true
```

**Depois de editar `settings.json`, abra `/hooks` uma vez** — sem isso a
mudança só vale na sessão seguinte.
