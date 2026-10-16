import asyncio

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.repository import Repository
from knowledgeqa.security.passwords import verify_password


async def request(app, method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def make_app(portable_root, repository):
    return create_app(
        settings=Settings(port=8788),
        paths=AppPaths(portable_root=portable_root),
        status_provider=lambda: {"milvus": "disconnected"},
        repository=repository,
    )


def test_get_and_update_settings(portable_root) -> None:
    repository = Repository(portable_root / "meta.db")
    repository.initialize()
    app = make_app(portable_root, repository)

    initial = asyncio.run(request(app, "GET", "/api/v1/settings"))
    updated = asyncio.run(
        request(
            app,
            "PUT",
            "/api/v1/settings",
            json={"lan_enabled": True, "shared_password": "secret"},
        )
    )

    assert initial.json()["lan_enabled"] is False
    assert updated.json()["lan_enabled"] is True
    assert updated.json()["restart_required"] is True
    assert "shared_password" not in updated.json()
    assert verify_password(
        "secret",
        repository.get_setting("shared_password_hash"),
    )
