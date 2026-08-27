from collections.abc import Generator

from sqlalchemy.orm import Session

from shared.db import SessionLocal
from shared.storage import BlobStorage, get_blob_storage


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_storage() -> BlobStorage:
    return get_blob_storage()
