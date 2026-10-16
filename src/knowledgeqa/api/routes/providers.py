from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class ProviderRequest(BaseModel):
    name: str
    provider_type: str
    base_url: str | None = None
    model_name: str | None = None
    api_version: str | None = None
    api_key: str | None = None
    enabled: bool = True


def _safe_config(config: dict, active_id: str | None) -> dict:
    return {
        key: value
        for key, value in config.items()
        if key != "encrypted_secret"
    } | {"active": config.get("id") == active_id}


def create_providers_router(repository, secret_store, provider_manager) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/providers")
    def list_providers():
        active = repository.get_active_provider_config()
        active_id = active["id"] if active else None
        return [
            _safe_config(config, active_id)
            for config in repository.list_provider_configs()
        ]

    @router.post("/providers")
    def upsert_provider(request: ProviderRequest):
        existing = repository.get_provider_config_by_name(request.name)
        if request.api_key:
            encrypted_secret = secret_store.protect(request.api_key)
        elif existing:
            encrypted_secret = existing.get("encrypted_secret")
        else:
            encrypted_secret = None
        config = repository.upsert_provider_config(
            name=request.name,
            provider_type=request.provider_type,
            base_url=request.base_url,
            model_name=request.model_name,
            api_version=request.api_version,
            encrypted_secret=encrypted_secret,
            enabled=request.enabled,
        )
        active = repository.get_active_provider_config()
        return _safe_config(config, active["id"] if active else None)

    @router.post("/providers/{provider_id}/activate")
    def activate_provider(provider_id: str):
        try:
            repository.set_active_provider(provider_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"ok": True}

    @router.post("/providers/{provider_id}/test")
    def test_provider(provider_id: str):
        if repository.get_provider_config(provider_id) is None:
            raise HTTPException(404, "Provider not found")
        try:
            provider, _model_name = provider_manager.active()
            result = provider.test_connection()
        except Exception as exc:
            return {"ok": False, "message": str(exc)}
        if isinstance(result, tuple):
            ok, message = result
        else:
            ok, message = bool(result), ""
        return {"ok": bool(ok), "message": str(message)}

    @router.delete("/providers/{provider_id}")
    def delete_provider(provider_id: str):
        if repository.get_provider_config(provider_id) is None:
            raise HTTPException(404, "Provider not found")
        repository.delete_provider_config(provider_id)
        return {"ok": True}

    return router
