from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter


def create_health_router(
    status_provider: Callable[[], dict[str, object]],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/status")
    def status() -> dict[str, object]:
        return status_provider()

    return router
