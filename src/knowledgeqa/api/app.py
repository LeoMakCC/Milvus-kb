from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from knowledgeqa.api.routes.health import create_health_router
from knowledgeqa.config import AppPaths, Settings


def create_app(
    settings: Settings,
    paths: AppPaths,
    status_provider: Callable[[], dict[str, object]],
) -> FastAPI:
    app = FastAPI(title="KnowledgeQA", version="0.1.0")
    app.include_router(create_health_router(status_provider))

    web_dir = Path(__file__).resolve().parents[1] / "web"
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    return app
