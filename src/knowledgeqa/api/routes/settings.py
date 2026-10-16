from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from knowledgeqa.security.passwords import hash_password


class SettingsUpdate(BaseModel):
    lan_enabled: bool | None = None
    shared_password: str | None = None


def create_settings_router(repository, settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def current() -> dict:
        lan_enabled = repository.get_setting("lan_enabled", "0") == "1"
        restart_required = (
            repository.get_setting("lan_restart_required", "0") == "1"
        )
        return {
            "lan_enabled": lan_enabled,
            "api_port": settings.port,
            "access_url": (
                f"http://127.0.0.1:{settings.port}"
                if not lan_enabled
                else f"http://<本机局域网IP>:{settings.port}"
            ),
            "restart_required": restart_required,
        }

    @router.get("/settings")
    def get_settings():
        return current()

    @router.put("/settings")
    def update_settings(request: SettingsUpdate):
        if request.lan_enabled is not None:
            repository.set_setting(
                "lan_enabled",
                "1" if request.lan_enabled else "0",
            )
            repository.set_setting("lan_restart_required", "1")
        if request.shared_password:
            repository.set_setting(
                "shared_password_hash",
                hash_password(request.shared_password),
            )
        return current()

    return router
