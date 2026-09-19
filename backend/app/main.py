from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dashboard import router as dashboard_router
from app.api.documents import router as documents_router
from app.deps import get_storage
from shared.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Garante o container de blobs no boot (idempotente; no-op no Azure).
    get_storage().ensure_container()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="CAT Document Reader", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.include_router(documents_router)
    app.include_router(dashboard_router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
