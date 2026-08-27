from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from shared.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


if settings.db_use_entra_token:
    from azure.identity import DefaultAzureCredential

    _credential = DefaultAzureCredential()
    _TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

    @event.listens_for(engine, "do_connect")
    def _inject_entra_token(dialect, conn_rec, cargs, cparams):
        cparams["password"] = _credential.get_token(_TOKEN_SCOPE).token
