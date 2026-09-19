from collections.abc import Generator

from sqlalchemy.orm import Session

from shared.db import SessionLocal
from shared.storage import BlobStorage, get_blob_storage


def get_db() -> Generator[Session, None, None]:
    """Sessão por request.

    PARA AZURE: isto NÃO muda. A sessão sai do mesmo SessionLocal (shared/db.py);
    o que muda é apenas como o engine se autentica no Postgres da Azure (token do
    Entra via Managed Identity), e isso está anotado no bloco PARA AZURE de
    shared/db.py. A camada de rotas continua intacta.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_storage() -> BlobStorage:
    # Azurite em dev, Blob real com Managed Identity no Azure. Quem escolhe é a
    # config (azure_storage_account_url); a interface e as rotas não mudam.
    return get_blob_storage()
