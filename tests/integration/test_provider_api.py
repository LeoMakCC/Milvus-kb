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
    def __init__(self, ok: bool = True, message: str = "ok") -> None:
        self.ok = ok
        self.message = message

    def test_connection(self):
        return self.ok, self.message


class FakeProviderManager:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.built = []
        self.requested_ids = []

    def active(self):
        return FakeProvider(self.ok), "mock"

    def build(self, config, api_key=None):
        self.built.append((dict(config), api_key))
        return FakeProvider(self.ok), config.get("model_name") or ""

    def for_id(self, provider_id):
        self.requested_ids.append(provider_id)
        return FakeProvider(self.ok), "saved-model"


async def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def make_app(portable_root, repository, provider_manager=None):
    return create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=lambda: {"milvus": "disconnected"},
        repository=repository,
        provider_manager=provider_manager or FakeProviderManager(),
        secret_store=FakeSecretStore(),
    )


def test_test_endpoint_uses_unsaved_form_values(portable_root) -> None:
    repository = Repository(portable_root / "meta.db")
    repository.initialize()
    manager = FakeProviderManager()
    app = make_app(portable_root, repository, provider_manager=manager)

    response = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/providers/test",
            json={
                "provider_type": "openai_compatible",
                "base_url": "https://api.example.com/v1",
                "model_name": "example-chat",
                "api_key": "sk-test",
            },
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["model"] == "example-chat"
    config, api_key = manager.built[0]
    assert config["base_url"] == "https://api.example.com/v1"
    assert api_key == "sk-test"


def test_test_endpoint_reuses_saved_key_when_input_empty(portable_root) -> None:
    repository = Repository(portable_root / "meta.db")
    repository.initialize()
    manager = FakeProviderManager()
    app = make_app(portable_root, repository, provider_manager=manager)

    created = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/providers",
            json={
                "name": "saved",
                "provider_type": "openai_compatible",
                "base_url": "https://api.example.com/v1",
                "model_name": "model-a",
                "api_key": "sk-saved",
                "enabled": True,
            },
        )
    ).json()

    response = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/providers/test",
            json={
                "provider_id": created["id"],
                "provider_type": "openai_compatible",
                "base_url": "https://api.example.com/v1",
                "model_name": "model-a",
            },
        )
    )

    assert response.status_code == 200
    config, api_key = manager.built[0]
    assert api_key is None
    assert config["encrypted_secret"] == b"enc:sk-saved"


def test_test_endpoint_requires_base_url(portable_root) -> None:
    repository = Repository(portable_root / "meta.db")
    repository.initialize()
    app = make_app(portable_root, repository)

    response = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/providers/test",
            json={"provider_type": "openai_compatible", "model_name": "m"},
        )
    )

    assert response.status_code == 400


def test_test_endpoint_reports_provider_failure(portable_root) -> None:
    repository = Repository(portable_root / "meta.db")
    repository.initialize()
    manager = FakeProviderManager(ok=False)
    app = make_app(portable_root, repository, provider_manager=manager)

    response = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/providers/test",
            json={
                "provider_type": "openai_compatible",
                "base_url": "https://api.example.com/v1",
                "model_name": "model-a",
                "api_key": "sk-bad",
            },
        )
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_provider_crud_and_test_connection(portable_root) -> None:
    repository = Repository(portable_root / "meta.db")
    repository.initialize()
    manager = FakeProviderManager()
    app = make_app(portable_root, repository, provider_manager=manager)

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
    payload = tested.json()
    assert payload["ok"] is True
    assert payload["message"] == "ok"
    assert payload["model"] == "saved-model"
    assert isinstance(payload["latency_ms"], int)
    assert manager.requested_ids == [body["id"]]

    listed = asyncio.run(request(app, "GET", "/api/v1/providers"))
    assert listed.json()[0]["active"] is True

    deleted = asyncio.run(
        request(app, "DELETE", f"/api/v1/providers/{body['id']}")
    )
    assert deleted.status_code == 200
    assert repository.get_provider_config(body["id"]) is None
