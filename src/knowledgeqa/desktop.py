from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import webview

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.db.connection import connect
from knowledgeqa.db.migrations import apply_migrations, current_version
from knowledgeqa.docker_control import DockerController
from knowledgeqa.instance_lock import InstanceLock
from knowledgeqa.server import ServerRunner
from knowledgeqa.status import StatusService


def portable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def build_status(
    settings: Settings,
    jobs_running: Callable[[], int],
    docker_available: Callable[[], bool] = lambda: False,
    docker_running: Callable[[], bool] = lambda: False,
    milvus_available: Callable[[], bool] = lambda: False,
    db_schema_version: Callable[[], int] = lambda: 1,
) -> dict[str, object]:
    return StatusService(
        settings=settings,
        docker_available=docker_available,
        docker_running=docker_running,
        milvus_available=milvus_available,
        db_schema_version=db_schema_version,
        jobs_running=jobs_running,
    ).snapshot()


def main(docker_controller: DockerController | None = None) -> int:
    root = portable_root()
    paths = AppPaths(portable_root=root)
    paths.ensure()

    conn = connect(paths.db_path)
    try:
        apply_migrations(conn)
        schema_version = current_version(conn)
    finally:
        conn.close()

    lock = InstanceLock(paths.data_dir / "app.lock")
    if not lock.try_acquire():
        return 0

    settings = Settings()
    controller = docker_controller or DockerController(root / "docker-compose.yml")
    app = create_app(
        settings=settings,
        paths=paths,
        status_provider=lambda: build_status(
            settings,
            jobs_running=lambda: 0,
            docker_available=controller.is_available,
            docker_running=controller.is_running,
            milvus_available=lambda: False,
            db_schema_version=lambda: schema_version,
        ),
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
