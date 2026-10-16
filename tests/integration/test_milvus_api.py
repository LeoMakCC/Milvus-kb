import asyncio

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings


class FakeDockerController:
    def __init__(self) -> None:
        self.calls = []

    def is_available(self) -> bool:
        return True

    def is_running(self) -> bool:
        return True

    def compose_up(self):
        self.calls.append("up")
        return type("Result", (), {"returncode": 0})()

    def compose_down(self):
        self.calls.append("down")
        return type("Result", (), {"returncode": 0})()


async def request(app, method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def test_milvus_lifecycle_api(portable_root) -> None:
    controller = FakeDockerController()
    app = create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=lambda: {"milvus": "disconnected"},
        docker_controller=controller,
    )

    status = asyncio.run(request(app, "GET", "/api/v1/milvus/status"))
    start = asyncio.run(request(app, "POST", "/api/v1/milvus/start"))
    stop = asyncio.run(request(app, "POST", "/api/v1/milvus/stop"))

    assert status.json() == {
        "available": True,
        "running": True,
        "compose_status": "ok",
    }
    assert start.json()["returncode"] == 0
    assert stop.json()["returncode"] == 0
    assert controller.calls == ["up", "down"]
