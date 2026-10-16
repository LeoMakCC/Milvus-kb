import asyncio

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.repository import Repository


class FakeSecretStore:
    def protect(self, value: str) -> bytes:
        return b"enc:" + value.encode("utf-8")

    def unprotect(self, value: bytes) -> str:
        return value.removeprefix(b"enc:").decode("utf-8")


class FakeProvider:
    def test_connection(self):
        return True, "ok"


class FakeProviderManager:
    def active(self):
        return FakeProvider(), "mock"


async def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def make_app(portable_root, repository):
    return create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=lambda: {"milvus": "disconnected"},
        repository=repository,
        provider_manager=FakeProviderManager(),
        secret_store=FakeSecretStore(),
    )


def test_provider_crud_and_test_connection(portable_root) -> None:
    repository = Repository(portable_root / "meta.db")
    repository.initialize()
    app = make_app(portable_root, repository)

    created = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/providers",
            json={
                "name": "local",
                "provider_type": "openai_compatible",
                "base_url": "http://127.0.0.1:8899/v1",
                "model_name": "mock",
                "api_key": "key",
                "enabled": True,
            },
        )
    )
    assert created.status_code == 200
    body = created.json()
    assert "api_key" not in body
    assert "encrypted_secret" not in body
    stored = repository.get_provider_config(body["id"])
    assert stored["encrypted_secret"] == b"enc:key"

    activated = asyncio.run(
        request(app, "POST", f"/api/v1/providers/{body['id']}/activate")
    )
    assert activated.status_code == 200
    assert repository.get_active_provider_config()["id"] == body["id"]

    tested = asyncio.run(
        request(app, "POST", f"/api/v1/providers/{body['id']}/test")
    )
    assert tested.json() == {"ok": True, "message": "ok"}

    listed = asyncio.run(request(app, "GET", "/api/v1/providers"))
    assert listed.json()[0]["active"] is True

    deleted = asyncio.run(
        request(app, "DELETE", f"/api/v1/providers/{body['id']}")
    )
    assert deleted.status_code == 200
    assert repository.get_provider_config(body["id"]) is None
