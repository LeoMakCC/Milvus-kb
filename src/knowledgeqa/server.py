from __future__ import annotations

import threading
import time

import httpx
import uvicorn

from knowledgeqa.config import Settings


class ServerRunner:
    def __init__(self, app, settings: Settings) -> None:
        self._settings = settings
        config = uvicorn.Config(
            app,
            host=settings.host,
            port=settings.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    @property
    def is_running(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        self._thread.start()

    def wait_until_ready(self, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        url = f"http://{self._settings.host}:{self._settings.port}/api/v1/health"
        while time.monotonic() < deadline:
            if self._server.started:
                try:
                    response = httpx.get(url, timeout=0.5)
                    if response.status_code == 200:
                        return True
                except httpx.HTTPError:
                    pass
            time.sleep(0.05)
        return False

    def stop(self) -> None:
        self._server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=5)
