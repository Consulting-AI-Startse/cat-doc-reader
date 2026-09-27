"""Lista de part numbers e regra de serial, contra Postgres de verdade.

Precisa de banco migrado e APAGA a tabela released_part_numbers dele. Aponte
para uma base de teste:

    DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/dedupe_test \\
        python check_parts.py

Os numeros vem da PN Liberados.xlsx real, medidos em 25/09: 206.769 pecas,
'ENGINE' casa 910 e 'ENGINE AR' casa 588.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared"))

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from shared import parts
from shared.models import ReleasedPartNumber, SerialRules

URL = os.environ.get("DATABASE_URL")
if not URL:
    sys.exit("DATABASE_URL nao definida -- este check precisa de banco")

falhas = []


def check(label, got, expected):
    ok = got == expected
    print(("  OK   " if ok else "  FALHA") + f" {label:<52} -> {got!r}   esperado {expected!r}")
    if not ok:
        falhas.append(label)


# Amostra fiel da planilha: os dois motores conhecidos, os acessorios que o
# substring solto pegaria por engano, os tres ENGINE GP de fronteira, e a linha
# de nome vazio que existe de verdade (6834334) e que ja abortou um recompute
# inteiro por causa de NULL ILIKE.
AMOSTRA = [
    ("6511308", "ENGINE AR-COMPL"),
    ("6522586", "ENGINE AR-COMPL"),
    ("1234567", "ENGINE AR-PRIM"),
    ("7654321", "ENGINE AR-74.4KW"),
    ("2P1467", "SUPPORT-ENGINE"),
    ("5P1175", "FILM-ENGINE OIL"),
    ("5Y0601", "CHART-ENGINE"),
    ("2Y2168", "PLATE-ENGINE S/N"),
    ("6526886", "ENGINE GP"),
    ("6526888", "ENGINE GP"),
    ("6822798", "ENGINE GP"),
    ("6637238", "PUMP GP-LUB"),
    ("7G5837", "HUB-SPROCKET"),
    ("5P1465", "HOSE BK"),
    ("6834334", None),
]

print("=== normalise_part_number: uma chave so para as duas grafias ===")
for v, e in [("463-8344", "4638344"), ("4638344", "4638344"), ("5P-1465", "5P1465"),
             ("663-7238~00", "663723800"), ("  6511308  ", "6511308"),
             ("", None), (None, None), ("---", None)]:
    check(f"normalise_part_number({v!r})", parts.normalise_part_number(v), e)

engine = create_engine(URL)
with Session(engine) as db:
    db.execute(delete(ReleasedPartNumber))
    regras = parts.get_rules(db)
    regras.substrings = []
    regras.manual_part_numbers = []
    db.add_all([ReleasedPartNumber(part_number=pn, name=nome) for pn, nome in AMOSTRA])
    db.commit()

    print("=== preview: nao grava, so conta ===")
    p = parts.preview(db, ["ENGINE"], [])
    check("'ENGINE' casa acessorio junto", p["marcadas"], 11)  # 4 motores + 4 acessorios + 3 ENGINE GP
    p = parts.preview(db, ["ENGINE AR"], [])
    check("'ENGINE AR' casa so motor", p["marcadas"], 4)
    check(
        "e nenhum acessorio entra",
        sorted(x["name"] for x in p["exemplos"]),
        ["ENGINE AR-74.4KW", "ENGINE AR-COMPL", "ENGINE AR-COMPL", "ENGINE AR-PRIM"],
    )
    marcadas_no_banco = db.scalar(
        select(func.count()).select_from(ReleasedPartNumber)
        .where(ReleasedPartNumber.requires_serial)
    )
    check("preview nao gravou nada", marcadas_no_banco, 0)

    print("=== preview: caixa nao importa ===")
    check("minuscula casa igual", parts.preview(db, ["engine ar"], [])["marcadas"], 4)

    print("=== recompute: substring + lista manual ===")
    n = parts.recompute(db, ["ENGINE AR"], ["6526886", "6526888", "6822798"])
    db.commit()
    check("4 por substring + 3 manuais", n, 7)
    # A linha de nome vazio e o caso que abortava o UPDATE inteiro: NULL ILIKE
    # devolve NULL e viola o NOT NULL da coluna.
    vazio = db.get(ReleasedPartNumber, "6834334")
    check("linha de nome vazio nao derruba o recompute", vazio.requires_serial, False)

    print("=== recompute: lista manual aceita a forma impressa ===")
    n = parts.recompute(db, [], ["463-8344", "5P-1465"])
    db.commit()
    check("'5P-1465' casa a chave normalizada", db.get(ReleasedPartNumber, "5P1465").requires_serial, True)
    check("so os dois manuais", n, 1)  # 463-8344 nao esta na amostra

    print("=== recompute: regra vazia desmarca tudo ===")
    n = parts.recompute(db, [], [])
    db.commit()
    check("nenhuma marcada", n, 0)

    print("=== lookup: uma consulta, e quem nao esta na lista nao volta ===")
    parts.recompute(db, ["ENGINE AR"], [])
    db.commit()
    r = parts.lookup(db, ["6511308", "463-8344", "5P-1465", "0V3456", "QIPP27001", None, ""])
    check("so os que existem", sorted(r), ["5P1465", "6511308"])
    check("motor exige serial", r["6511308"].requires_serial, True)
    check("nao-motor nao exige", r["5P1465"].requires_serial, False)
    check("lista vazia nao consulta", parts.lookup(db, []), {})

    print("=== get_rules: a linha unica existe e persiste ===")
    regras = parts.get_rules(db)
    regras.substrings = ["ENGINE AR"]
    db.commit()
    check("substrings gravadas", parts.get_rules(db).substrings, ["ENGINE AR"])
    check("id e sempre 1", db.scalar(select(func.count()).select_from(SerialRules)), 1)

    db.execute(delete(ReleasedPartNumber))
    regras = parts.get_rules(db)
    regras.substrings = []
    regras.manual_part_numbers = []
    db.commit()

print("=== o relatorio de import fecha: recebidas = gravadas + duplicadas + erros ===")
# Numero sem explicacao e o mesmo defeito de documento gravado sem nota: a
# primeira versao dizia "3 ignoradas" e listava 2 erros, e a terceira era uma
# duplicata que sumia calada.
#
# Testado direto na funcao pura, sem TestClient: ele exige httpx, que nao esta
# no requirements.txt do backend e nao vai estar -- e dependencia de teste, nao
# de producao. No CI da CAT o import do TestClient derrubava este check.
CSV = "\n".join([
    "PECA,NOME",
    "6511308,ENGINE AR-COMPL",
    "2P1467,SUPPORT-ENGINE",
    "6511308,ENGINE AR-COMPL",      # duplicata dentro do arquivo
    ",SEM PART NUMBER",             # sem chave
    "X" * 40 + ",LONGO DEMAIS",     # chave acima de 32 caracteres
])
r = parts.parse_csv(CSV)
check("recebidas", r["recebidas"], 5)
check("validas", len(r["validas"]), 2)
check("duplicadas contadas", r["duplicadas"], 1)
check("erros listados", len(r["erros"]), 2)
check("a conta fecha", len(r["validas"]) + r["duplicadas"] + len(r["erros"]), r["recebidas"])
check("a chave sai normalizada", r["validas"][0], ("6511308", "ENGINE AR-COMPL"))

print("=== cabecalho e opcional, e so pula titulo conhecido ===")
# Pular por heuristica apagaria a primeira peca de um arquivo sem cabecalho.
sem = parts.parse_csv("6511308,ENGINE AR-COMPL\n2P1467,SUPPORT-ENGINE")
check("sem cabecalho, nenhuma linha perdida", len(sem["validas"]), 2)
check("arquivo vazio e sinalizado", parts.parse_csv("")["vazio"], True)

print("=== decode_csv aguenta o que o Excel do Windows salva ===")
# encode('utf-8-sig') ja POE o BOM; passar uma string que ja comeca com \ufeff
# gera dois, e o decode tira so um.
check("utf-8 com BOM", parts.decode_csv("6511308,MOTOR".encode("utf-8-sig")).split(",")[0], "6511308")
check("latin-1", parts.decode_csv("6511308,CORREIA DE TRANSMISS\xc3O".encode("latin-1")).split(",")[0], "6511308")

print()
if falhas:
    print(f"{len(falhas)} FALHA(S): {falhas}")
    sys.exit(1)
print("tudo certo")
