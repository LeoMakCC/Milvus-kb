import socket

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.server import ServerRunner


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_server_runner_starts_and_stops(portable_root) -> None:
    port = free_port()
    settings = Settings(host="127.0.0.1", port=port)
    paths = AppPaths(portable_root=portable_root)
    app = create_app(
        settings=settings,
        paths=paths,
        status_provider=lambda: {"milvus": "disconnected"},
    )
    runner = ServerRunner(app, settings)

    runner.start()
    try:
        assert runner.wait_until_ready(timeout=5)
        response = httpx.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=2)
        assert response.json() == {"status": "ok"}
    finally:
        runner.stop()

    assert runner.is_running is False
