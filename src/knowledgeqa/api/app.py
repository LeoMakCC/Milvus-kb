from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI

from knowledgeqa.api.routes.health import create_health_router
from knowledgeqa.config import AppPaths, Settings


def create_app(
    settings: Settings,
    paths: AppPaths,
    status_provider: Callable[[], dict[str, object]],
) -> FastAPI:
    app = FastAPI(title="KnowledgeQA", version="0.1.0")
    app.include_router(create_health_router(status_provider))
    return app
