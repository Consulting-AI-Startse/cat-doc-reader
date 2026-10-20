"""Aplica as migracoes e confere o banco contra o modelo, num comando so.

Roda no webssh do fastapi, como o grupo admin do Entra, com o DATABASE_URL e o
PGPASSWORD do roteiro do DEPLOY.md:

    python migrar.py

Existe porque o roteiro da leva 14 tinha passos demais (alembic current,
alembic upgrade head e um python -c com as colunas daquela migracao) e o
cat-freight-poc fazia o mesmo com um script. A conferencia e contra o
shared/models.py inteiro, nao contra uma lista de colunas: nao ha o que
atualizar a cada migracao, e uma coluna que o codigo usa e o banco nao tem
aparece aqui, e nao como erro 500 em producao.

Confere pelo catalogo, nunca pelo carimbo do alembic: uma migracao pode estar
carimbada sem estar aplicada. No fim mostra o pg_default_acl, que ja esteve
vazio em producao e deixou as Managed Identities sem acesso a tabela nova.
"""
import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from shared.models import Base


def _revision(conn) -> str:
    try:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar() or "(vazio)"
    except SQLAlchemyError:
        conn.rollback()
        return "(sem alembic_version)"


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL nao definido: cole o export do admin (DEPLOY.md, migracao)")
        return 2
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "alembic"))

    engine = create_engine(url)
    with engine.connect() as conn:
        before = _revision(conn)

    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        after = _revision(conn)
        present = set(conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'")).fetchall())
        acl = conn.execute(text(
            "SELECT pg_get_userbyid(defaclrole), defaclobjtype, defaclacl::text "
            "FROM pg_default_acl")).fetchall()

    expected = [(t.name, c.name) for t in Base.metadata.sorted_tables for c in t.columns]
    missing = [pair for pair in expected if pair not in present]

    print("revisao: %s -> %s" % (before, after))
    print("schema: %d colunas do modelo, %d faltando no banco" % (len(expected), len(missing)))
    for table, column in missing:
        print("  FALTA %s.%s" % (table, column))
    print("pg_default_acl (tem de haver uma linha r e uma S para o grupo admin):")
    for role, kind, privileges in acl:
        print("  %s %s %s" % (role, kind, privileges))
    if not acl:
        print("  VAZIO -- tabela nova nasce sem acesso para as Managed Identities (DEPLOY.md)")

    if missing:
        return 1
    print("tudo certo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
