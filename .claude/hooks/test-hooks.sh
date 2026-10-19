#!/usr/bin/env bash
# Matriz de teste dos hooks. Literais perigosos montados em pedaços para o
# proprio guarda nao recusar o teste.
cd /home/luisf/projects/Caterpillar/cat-doc-reader
pass=0; fail=0
t() { # t <deny|ok> <hook> <json>
  out=$(printf '%s' "$3" | bash .claude/hooks/$2 2>/dev/null; echo "rc=$?")
  if [ "$1" = deny ]; then ok=$([[ "$out" == *'"deny"'* ]] && echo 1 || echo 0)
  else ok=$([[ "$out" == "rc=0" ]] && echo 1 || echo 0); fi
  if [ $ok = 1 ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL ($1): ${3:0:120} -> ${out:0:160}"; fi
}
j() { python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.argv[1]}}))' "$1"; }
w() { python3 -c 'import json,sys; print(json.dumps({"tool_input":{"file_path":sys.argv[1],"content":sys.argv[2]}}))' "$1" "$2"; }
RM="r""m"; MK="mk""fs"; FP="--for""ce"; DB="drop"" database"; DD="drop""db"
KEY="AZURE_OPENAI""_KEY"; AK="AKIA""ABCDEFGHIJKLMNOP"; SK="sk-""ant-aaaaaaaaaaaaaaaaaaaaaaaaaa"
for c in "$RM -rf /" "$RM -rf /*" "$RM -r -f /" "$RM -rf \"\$HOME\"" "$RM -rf / --no-preserve-root" "$RM -rf \$FOO/" "$RM -rf ~" "$MK.ext4 /dev/sda" "git push $FP origin main" "git push origin +main" "git push -f origin main" "git push $FP main" "git push --force-with-lease origin main" "git push -f origin HEAD:main" "psql -c \"$DB x\"" "$DD x" "cat > a.py <<EOF
$KEY=abcdefghijklmnop1234
EOF" "echo 'postgresql://u:secretpw@prod.example.com/db' > README.md"; do t deny guard-command.sh "$(j "$c")"; done
for c in 'ls' "$RM -rf build/" "$RM -rf ./dist" "$RM -rf \$FOO/bar" "$RM -rf \"\$tmp\"" "git push $FP origin feat/main-page" 'git push -u origin ci/x' "echo '{\"command\":\"git push $FP origin main\"}' | bash hook" "echo \"$MK.ext4 /dev/sda\"" "gh pr create --body \"nunca rode $DB\"" 'DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/dedupe_test python check_parts.py' 'export AzureWebJobsStorage=UseDevelopmentStorage=true' 'git commit -m x'; do t ok guard-command.sh "$(j "$c")"; done
t deny guard-secrets.sh "$(w "$PWD/shared/shared/config.py" "$KEY=abcdefghijklmnop1234")"
t deny guard-secrets.sh "$(w "$PWD/README.md" 'postgresql://u:secretpw@prod.example.com/db')"
t ok   guard-secrets.sh "$(w "$PWD/CLAUDE.md" 'DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/dedupe_test')"
t ok   guard-secrets.sh "$(w "$PWD/.env.local" "$KEY=abcdefghijklmnop1234")"
t ok   guard-secrets.sh "$(w "/tmp/claude-1000/x/fixture.py" "$SK")"
t ok   guard-secrets.sh "$(w "$PWD/start-local.sh" 'AzureWebJobsStorage=UseDevelopmentStorage=true')"
bigjson=$(mktemp); python3 -c "import json,sys; print(json.dumps({'tool_input':{'file_path':sys.argv[1],'content':'x'*300000+sys.argv[2]}}))" "$PWD/backend/app/config.py" "$AK" > "$bigjson"
out=$(bash .claude/hooks/guard-secrets.sh < "$bigjson"); [[ "$out" == *deny* ]] && pass=$((pass+1)) || { fail=$((fail+1)); echo "FAIL big payload: $out"; }; rm -f "$bigjson"
# clone na main: commit simples nega; checkout -b && commit passa
tmp=$(mktemp -d); git clone -q . "$tmp/c"; git -C "$tmp/c" checkout -q main; cp -r .claude "$tmp/c/"
( cd "$tmp/c" && out=$(printf '%s' "$(j 'git commit -m x')" | bash .claude/hooks/guard-command.sh); [[ "$out" == *deny* ]] && echo "PASS main-commit deny" || echo "FAIL main-commit"
  out=$(printf '%s' "$(j 'git checkout -b feat/x && git commit -m x')" | bash .claude/hooks/guard-command.sh); [ -z "$out" ] && echo "PASS checkout-b+commit ok" || echo "FAIL checkout-b: $out" )
rm -rf "$tmp"
nopy=$(mktemp -d); for b in bash dirname grep git cat; do ln -s "$(command -v $b)" "$nopy/$b"; done
echo '{"tool_input":{"command":"ls"}}' | PATH="$nopy" bash .claude/hooks/guard-command.sh; rc=$?; echo "rc sem python3=$rc (esperado 2)"; [ $rc = 2 ] && pass=$((pass+1)) || fail=$((fail+1)); rm -rf "$nopy"
echo "pass=$pass fail=$fail"
