import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.deps import get_db
from shared import parts as parts_lib
from shared.models import ReleasedPartNumber

router = APIRouter(prefix="/parts", tags=["parts"])

# 5.000 por lote: 206.769 linhas nao podem virar 206.769 round-trips, e lotes
# muito maiores estouram o limite de parametros do psycopg.
_LOTE = 5000


class RulesIn(BaseModel):
    substrings: list[str] = []
    manual_part_numbers: list[str] = []


def _serialize_rules(regras, marcadas: int, total: int) -> dict:
    return {
        "substrings": list(regras.substrings or []),
        "manual_part_numbers": list(regras.manual_part_numbers or []),
        "updated_at": regras.updated_at,
        "marcadas": marcadas,
        "total_na_lista": total,
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(ReleasedPartNumber)) or 0
    marcadas = db.scalar(
        select(func.count()).select_from(ReleasedPartNumber)
        .where(ReleasedPartNumber.requires_serial)
    ) or 0
    ultimo = db.execute(
        select(ReleasedPartNumber.import_batch, func.max(ReleasedPartNumber.imported_at))
        .group_by(ReleasedPartNumber.import_batch)
        .order_by(func.max(ReleasedPartNumber.imported_at).desc())
        .limit(1)
    ).first()
    return {
        "total": total,
        "requires_serial": marcadas,
        "ultimo_import": None if ultimo is None else {
            "batch": ultimo[0], "em": ultimo[1],
        },
    }


@router.post("/import")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Importa a lista por CSV. Duas colunas: part number e nome.

    Upsert, nao truncate: a lista e cumulativa entre importacoes, e apagar tudo
    antes deixaria a checagem cega caso o arquivo novo viesse quebrado.

    A linha invalida NAO derruba o arquivo -- ela e contada e devolvida na
    resposta. Um CSV de 206 mil linhas com tres defeitos tem de importar as
    206.997 restantes e dizer quais falharam.
    """
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(422, "envie um arquivo .csv")

    bruto = await file.read()
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel no Windows salva CSV em latin-1 com frequencia.
        texto = bruto.decode("latin-1")

    leitor = csv.reader(io.StringIO(texto))
    linhas = list(leitor)
    if not linhas:
        raise HTTPException(422, "arquivo vazio")

    # Cabecalho e opcional: se a primeira celula normalizar para algo que nao
    # parece part number, tratamos como titulo.
    inicio = 0
    primeira = (linhas[0][0] if linhas[0] else "").strip().upper()
    if primeira in ("PECA", "PEÇA", "PART_NUMBER", "PART NUMBER", "PN"):
        inicio = 1

    batch = "%s @ %s" % (
        file.filename, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    )
    recebidas = 0
    duplicadas = 0
    erros: list[str] = []
    vistos: set[str] = set()
    lote: list[dict] = []
    gravadas = 0

    def descarrega():
        nonlocal lote, gravadas
        if not lote:
            return
        stmt = insert(ReleasedPartNumber).values(lote)
        db.execute(stmt.on_conflict_do_update(
            index_elements=["part_number"],
            set_={
                "name": stmt.excluded.name,
                "imported_at": stmt.excluded.imported_at,
                "import_batch": stmt.excluded.import_batch,
            },
        ))
        gravadas += len(lote)
        lote = []

    agora = datetime.now(timezone.utc)
    for n, linha in enumerate(linhas[inicio:], start=inicio + 1):
        if not linha or not any(c.strip() for c in linha):
            continue
        recebidas += 1
        chave = parts_lib.normalise_part_number(linha[0])
        if not chave:
            if len(erros) < 20:
                erros.append("linha %d: part number vazio ou sem caractere util" % n)
            continue
        if len(chave) > 32:
            if len(erros) < 20:
                erros.append("linha %d: part number '%s' tem mais de 32 caracteres" % (n, chave))
            continue
        # Duplicata dentro do proprio arquivo: o upsert em lote reclama de duas
        # linhas com a mesma chave no mesmo comando. Nao e erro, mas e contada
        # -- 'ignoradas' sem explicacao e o mesmo defeito de documento gravado
        # sem nota.
        if chave in vistos:
            duplicadas += 1
            continue
        vistos.add(chave)
        nome = (linha[1].strip() if len(linha) > 1 and linha[1] else None) or None
        lote.append({
            "part_number": chave, "name": nome,
            "imported_at": agora, "import_batch": batch,
        })
        if len(lote) >= _LOTE:
            descarrega()
    descarrega()

    # Sem isto a lista nova ficaria com requires_serial do import anterior --
    # as linhas novas entrariam todas como false, em silencio.
    regras = parts_lib.get_rules(db)
    marcadas = parts_lib.recompute(db, regras.substrings, regras.manual_part_numbers)
    db.commit()

    total = db.scalar(select(func.count()).select_from(ReleasedPartNumber)) or 0
    return {
        "recebidas": recebidas,
        "gravadas": gravadas,
        "ignoradas": recebidas - gravadas,
        # recebidas = gravadas + duplicadas + len(erros), sempre.
        "duplicadas_no_arquivo": duplicadas,
        "total_na_lista": total,
        "requires_serial": marcadas,
        "erros": erros,
    }


@router.get("/serial-rules")
def get_serial_rules(db: Session = Depends(get_db)):
    regras = parts_lib.get_rules(db)
    total = db.scalar(select(func.count()).select_from(ReleasedPartNumber)) or 0
    marcadas = db.scalar(
        select(func.count()).select_from(ReleasedPartNumber)
        .where(ReleasedPartNumber.requires_serial)
    ) or 0
    db.commit()
    return _serialize_rules(regras, marcadas, total)


@router.post("/serial-rules/preview")
def preview_serial_rules(payload: RulesIn, db: Session = Depends(get_db)):
    """Quantas pecas a regra marcaria, sem gravar.

    E o que separa uma regra boa de uma ruim antes do estrago: 'ENGINE' casa
    910 pecas -- 'FILM-ENGINE RUN', 'PLATE-ENGINE SHU', 'SUPPORT-ENGINE' --
    enquanto 'ENGINE AR' casa 588 sem nenhum falso positivo.
    """
    atual = db.scalar(
        select(func.count()).select_from(ReleasedPartNumber)
        .where(ReleasedPartNumber.requires_serial)
    ) or 0
    resultado = parts_lib.preview(db, payload.substrings, payload.manual_part_numbers)
    resultado["marcadas_hoje"] = atual
    return resultado


@router.put("/serial-rules")
def put_serial_rules(payload: RulesIn, db: Session = Depends(get_db)):
    regras = parts_lib.get_rules(db)
    regras.substrings = [s.strip() for s in payload.substrings if s and s.strip()]
    regras.manual_part_numbers = [
        k for k in (parts_lib.normalise_part_number(p) for p in payload.manual_part_numbers) if k
    ]
    marcadas = parts_lib.recompute(db, regras.substrings, regras.manual_part_numbers)
    db.commit()
    db.refresh(regras)
    total = db.scalar(select(func.count()).select_from(ReleasedPartNumber)) or 0
    return _serialize_rules(regras, marcadas, total)
