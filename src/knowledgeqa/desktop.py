from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import webview

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.instance_lock import InstanceLock
from knowledgeqa.server import ServerRunner


def portable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def build_status(
    settings: Settings,
    jobs_running: Callable[[], int],
) -> dict[str, object]:
    return {
        "milvus": "disconnected",
        "embedding_model": "BAAI/bge-small-zh-v1.5",
        "jobs_running": jobs_running(),
        "lan_enabled": settings.lan_enabled,
    }


def main() -> int:
    root = portable_root()
    paths = AppPaths(portable_root=root)
    paths.ensure()

    lock = InstanceLock(paths.data_dir / "app.lock")
    if not lock.try_acquire():
        return 0

    settings = Settings()
    app = create_app(
        settings=settings,
        paths=paths,
        status_provider=lambda: build_status(settings, jobs_running=lambda: 0),
    )
    runner = ServerRunner(app, settings)

    try:
        runner.start()
        if not runner.wait_until_ready():
            return 1
        webview.create_window(
            "KnowledgeQA",
            f"http://{settings.host}:{settings.port}",
            width=1180,
            height=780,
            min_size=(920, 620),
        )
        webview.start()
    finally:
        runner.stop()
        lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
