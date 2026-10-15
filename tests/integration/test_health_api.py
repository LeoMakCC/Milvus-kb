import asyncio

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings


def status_provider() -> dict[str, object]:
    return {
        "milvus": "disconnected",
        "embedding_model": "BAAI/bge-small-zh-v1.5",
        "jobs_running": 0,
        "lan_enabled": False,
    }


async def get(app, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_health_endpoint(portable_root) -> None:
    app = create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=status_provider,
    )
    response = asyncio.run(get(app, "/api/v1/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_endpoint(portable_root) -> None:
    app = create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=status_provider,
    )
    response = asyncio.run(get(app, "/api/v1/status"))

    assert response.status_code == 200
    assert response.json() == status_provider()
