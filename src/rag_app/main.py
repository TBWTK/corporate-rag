from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from rag_app.api.routes import router
from rag_app.config import Settings, get_settings
from rag_app.db.session import create_database_engine, create_session_factory, initialize_database
from rag_app.providers.factory import create_provider


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved_settings.data_dir.mkdir(parents=True, exist_ok=True)
        engine = create_database_engine(resolved_settings)
        initialize_database(engine)
        provider = create_provider(resolved_settings, engine=engine)
        app.state.settings = resolved_settings
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.provider = provider
        yield
        close = getattr(provider, "close", None)
        if callable(close):
            close()
        engine.dispose()

    app = FastAPI(
        title="Corporate RAG API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.include_router(router)

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app


app = create_app()
