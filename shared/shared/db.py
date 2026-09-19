from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from shared.config import settings

# Engine único por processo. pool_pre_ping evita conexões mortas.
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

# Fábrica de sessões. Backend abre uma por request; a function abre a sua.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# PARA AZURE (CAT): o Postgres é Entra-only (sem senha). O resto do app NÃO muda;
# muda só COMO a conexão se autentica: a DATABASE_URL não leva senha (só o usuário
# = Managed Identity) e, antes de cada conexão, injeta-se um token do Entra como
# "senha". A MI do App Service/Function precisa ser principal no Postgres (via o
# grupo admin do Entra) -- isso é permissão na Azure, não código.
if settings.db_use_entra_token:
    from azure.identity import DefaultAzureCredential

    _credential = DefaultAzureCredential()
    _TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

    @event.listens_for(engine, "do_connect")
    def _inject_entra_token(dialect, conn_rec, cargs, cparams):
        cparams["password"] = _credential.get_token(_TOKEN_SCOPE).token
