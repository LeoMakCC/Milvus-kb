from __future__ import annotations

import time

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


class ProviderTestRequest(BaseModel):
    provider_id: str | None = None
    provider_type: str = "openai_compatible"
    base_url: str | None = None
    model_name: str | None = None
    api_version: str | None = None
    api_key: str | None = None


def _safe_config(config: dict, active_id: str | None) -> dict:
    return {
        key: value
        for key, value in config.items()
        if key != "encrypted_secret"
    } | {"active": config.get("id") == active_id}


def _test_result(provider, model_name: str) -> dict:
    started = time.perf_counter()
    try:
        result = provider.test_connection()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "message": str(exc),
            "model": model_name,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    if isinstance(result, tuple):
        ok, message = result
    else:
        ok, message = bool(result), ""
    return {
        "ok": bool(ok),
        "message": str(message),
        "model": model_name,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


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

    @router.post("/providers/test")
    def test_provider_payload(request: ProviderTestRequest):
        """直接测试表单里填写的配置，允许未保存时验证连通性。"""
        saved = (
            repository.get_provider_config(request.provider_id)
            if request.provider_id
            else None
        )
        config = dict(saved) if saved else {}
        for field in ("provider_type", "base_url", "model_name", "api_version"):
            value = getattr(request, field)
            if value:
                config[field] = value
        if not config.get("base_url"):
            raise HTTPException(400, "Base URL 不能为空")
        if not config.get("model_name"):
            raise HTTPException(400, "模型名称不能为空")
        try:
            provider, model_name = provider_manager.build(
                config,
                api_key=request.api_key or None,
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "message": str(exc),
                "model": config.get("model_name") or "",
                "latency_ms": 0,
            }
        return _test_result(provider, model_name)

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
            provider, model_name = provider_manager.for_id(provider_id)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "message": str(exc),
                "model": "",
                "latency_ms": 0,
            }
        return _test_result(provider, model_name)

    @router.delete("/providers/{provider_id}")
    def delete_provider(provider_id: str):
        if repository.get_provider_config(provider_id) is None:
            raise HTTPException(404, "Provider not found")
        repository.delete_provider_config(provider_id)
        return {"ok": True}

    return router
