# Testes do structurer, do offline ao end-to-end.
# Rode da raiz do repo:  .\run-tests.ps1
# Para so os offline:    .\run-tests.ps1 -SkipDeploy

param([switch]$SkipDeploy)

$ErrorActionPreference = "Stop"

# Caminhos absolutos: o $PY relativo quebrava depois de qualquer cd
# $PSScriptRoot fica vazio quando o conteudo roda fora de um arquivo
# (ex.: via [scriptblock]::Create), entao caimos no diretorio atual.
$REPO = $PSScriptRoot
if (-not $REPO) { $REPO = (Get-Location).Path }
# Nomes de arquivo montados em pedacos: '.py' e um TLD de verdade (Paraguai),
# e o filtro de email reescreve esses nomes como se fossem enderecos.
$PYEXT = "py"
$T_RULES = "check_rules." + $PYEXT
$T_STRUCT = "check_structurer." + $PYEXT
$PY   = Join-Path $REPO "function\.venv\Scripts\python.exe"
$FUNC = Join-Path $REPO "function"
$DL   = Join-Path $env:USERPROFILE "Downloads"
# Montado em pedacos de proposito: o filtro de email reescreve enderecos
# literais e corrompe o valor. Nao junte isto numa string unica.
$SITE = "aiagent-documentreader-pov-fastapi-appservice"
$DOM  = ("azurewebsites", "net") -join "."
$BASE = ("https", "//" + $SITE + "." + $DOM) -join ":"
$APP  = "aiagent-documentreader-pov-backend-function"

if (-not (Test-Path $PY)) { throw "python do venv nao encontrado em $PY" }

function Wait-Doc($id) {
    # sai em qualquer status terminal, nao so em needs_review
    for ($i = 0; $i -lt 60; $i++) {
        $s = (curl.exe -s "$BASE/documents/$id" | ConvertFrom-Json).status
        Write-Host ("  {0} {1}" -f (Get-Date -f HH:mm:ss), $s)
        if ($s -notin @("received", "processing")) { return $s }
        Start-Sleep 15
    }
    return "timeout"
}

function Send-Doc($path, $label) {
    # copia para nome sem espaco: o -F do curl quebra no espaco do caminho
    $tmp = Join-Path $env:TEMP "$label.pdf"
    Copy-Item $path $tmp -Force
    $r = curl.exe -s -X POST -F "file=@$tmp" "$BASE/documents/upload"
    $id = ($r | ConvertFrom-Json).id
    if (-not $id) { throw "upload de $label falhou: $r" }
    Write-Host "  id $id"
    return $id
}

Write-Host "`n=== 1. regras puras (_num, PART_NUMBER_RE) ===" -ForegroundColor Cyan
& $PY (Join-Path $REPO $T_RULES)
if ($LASTEXITCODE -ne 0) { throw "check_rules falhou" }

Write-Host "`n=== 2. structurer contra o gabarito ===" -ForegroundColor Cyan
& $PY (Join-Path $REPO $T_STRUCT)
if ($LASTEXITCODE -ne 0) { throw "check_structurer falhou" }

Write-Host "`n=== 3. import do function_app ===" -ForegroundColor Cyan
Push-Location $FUNC
& $PY -c "import function_app; print('import ok')"
$importOk = $LASTEXITCODE
Pop-Location
if ($importOk -ne 0) { throw "import do function_app falhou -- nao publique" }

if ($SkipDeploy) { Write-Host "`nofflines ok, deploy pulado" -ForegroundColor Green; return }

Write-Host "`n=== 4. sessao do az ===" -ForegroundColor Cyan
az account show -o tsv --query name
if ($LASTEXITCODE -ne 0) { throw "az sem sessao -- rode 'az login' e chame de novo" }

Write-Host "`n=== 5. publish ===" -ForegroundColor Cyan
Push-Location $FUNC
func azure functionapp publish $APP --build remote
$pubOk = $LASTEXITCODE
Pop-Location
if ($pubOk -ne 0) { throw "publish falhou" }

Write-Host "`n=== 6. regressao: fatura europeia (espera EUR 22944.02) ===" -ForegroundColor Cyan
$id = Send-Doc (Join-Path $DL "Maritimo Europa\1090257290_en_2026RFM04490.pdf") "eu1"
Wait-Doc $id | Out-Null
curl.exe -s "$BASE/documents/$id/raw" -o (Join-Path $DL "raw-eu-v2.json")
& $PY -c @"
import json
s = json.load(open(r'$DL\raw-eu-v2.json', encoding='utf-8-sig'))['raw_extraction']['structured']
for i in s['invoices']:
    print(' ', i['currency'], i['total'], '| freight', i.get('freight'), '| pack', i.get('packaging_cost'))
    for l in i['line_items']:
        print('   ', l['part_number'], l['part_number_normalised'], l['part_number_status'], l['quantity'], l['unit_price'], l['amount'])
"@

Write-Host "`n=== 7. CIV: 6 invoices, 8 materiais, rateio de embalagem ===" -ForegroundColor Cyan
$id2 = Send-Doc (Join-Path $DL "CIV MRKU6295556.PDF") "civ"
Wait-Doc $id2 | Out-Null
curl.exe -s "$BASE/documents/$id2/raw" -o (Join-Path $DL "raw-civ-v2.json")
& $PY -c @"
import json
GAB = {'6637238','6064986','4638344','4638343','4638341','3649717','5617001','3215765'}
r = json.load(open(r'$DL\raw-civ-v2.json', encoding='utf-8-sig'))['raw_extraction']
s = r['structured']
norm = set()
for n, i in enumerate(s['invoices']):
    print(' invoice[%d]' % n, i.get('invoice_number'), '| total', i.get('total'),
          '| freight', i.get('freight'), '| pack', i.get('packaging_cost'))
    for l in i['line_items']:
        norm.add(l['part_number_normalised'])
        print('   ', l['part_number'], l['part_number_normalised'], l['part_number_status'],
              '| unit', l.get('unit_price'), '-> landed', l.get('unit_price_landed'))
print()
print(' materiais do gabarito cobertos:', len(GAB & norm), '/ 8')
print(' faltando:', sorted(GAB - norm) or 'nenhum')
print()
for v in r['validation']:
    print('  -', v)
"@

Write-Host "`nfim" -ForegroundColor Green
