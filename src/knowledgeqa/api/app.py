from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from knowledgeqa.api.routes.chat import create_chat_router
from knowledgeqa.api.routes.health import create_health_router
from knowledgeqa.api.routes.kbs import create_kbs_router
from knowledgeqa.api.routes.providers import create_providers_router
from knowledgeqa.api.routes.search import create_search_router
from knowledgeqa.config import AppPaths, Settings


def create_app(
    settings: Settings,
    paths: AppPaths,
    status_provider: Callable[[], dict[str, object]],
    repository=None,
    ingestion_service=None,
    search_service=None,
    answer_service=None,
    provider_manager=None,
    secret_store=None,
) -> FastAPI:
    app = FastAPI(title="KnowledgeQA", version="0.1.0")
    app.include_router(create_health_router(status_provider))
    if repository is not None:
        app.include_router(create_kbs_router(repository, ingestion_service))
    if search_service is not None:
        app.include_router(create_search_router(search_service))
    if answer_service is not None and repository is not None:
        app.include_router(create_chat_router(answer_service, repository))
    if (
        provider_manager is not None
        and secret_store is not None
        and repository is not None
    ):
        app.include_router(
            create_providers_router(
                repository,
                secret_store,
                provider_manager,
            )
        )

    web_dir = Path(__file__).resolve().parents[1] / "web"
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    return app
