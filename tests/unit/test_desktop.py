import asyncio

import httpx

from knowledgeqa.config import Settings
from knowledgeqa import desktop


def test_build_status_reports_defaults() -> None:
    settings = Settings()

    status = desktop.build_status(settings, jobs_running=lambda: 2)

    assert status == {
        "milvus": "disconnected",
        "embedding_model": "BAAI/bge-small-zh-v1.5",
        "jobs_running": 2,
        "lan_enabled": False,
        "docker_available": False,
        "docker_running": False,
        "db_schema_version": 2,
        "api_port": 8787,
    }


def test_main_starts_window_and_stops_server(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    class FakeRunner:
        def __init__(self, app, settings) -> None:
            self.app = app
            self.settings = settings
            captured_apps.append(app)

        def start(self) -> None:
            calls.append("server_start")

        def wait_until_ready(self, timeout: float = 10.0) -> bool:
            calls.append("server_ready")
            return True

        def stop(self) -> None:
            calls.append("server_stop")

    class FakeWebview:
        @staticmethod
        def create_window(*args, **kwargs) -> None:
            calls.append("window")

        @staticmethod
        def start() -> None:
            calls.append("webview_start")

    monkeypatch.setattr(desktop, "portable_root", lambda: tmp_path)
    monkeypatch.setattr(desktop, "ServerRunner", FakeRunner)
    monkeypatch.setattr(desktop, "webview", FakeWebview)

    class FakeDockerController:
        def is_available(self) -> bool:
            return False

        def is_running(self) -> bool:
            return False

    captured_apps = []

    assert desktop.main(docker_controller=FakeDockerController()) == 0
    assert calls == [
        "server_start",
        "server_ready",
        "window",
        "webview_start",
        "server_stop",
    ]

    async def fetch_status():
        transport = httpx.ASGITransport(app=captured_apps[0])
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/status")

    status = asyncio.run(fetch_status()).json()
    assert status["db_schema_version"] == 2
    assert status["docker_available"] is False
