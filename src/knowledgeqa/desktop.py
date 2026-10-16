from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import webview

from knowledgeqa.answer import AnswerService
from knowledgeqa.api.auth import AuthGuard
from knowledgeqa.api.app import create_app
from knowledgeqa.backup import BackupService, RestoreService
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.db.connection import connect
from knowledgeqa.db.migrations import apply_migrations, current_version
from knowledgeqa.docker_control import DockerController
from knowledgeqa.embedding import FastEmbedEmbedder
from knowledgeqa.instance_lock import InstanceLock
from knowledgeqa.lifecycle import ExitChoice, ExitCoordinator, ExitDecision
from knowledgeqa.logging_setup import configure_logging
from knowledgeqa.milvus.store import MilvusStore
from knowledgeqa.providers.manager import ProviderManager
from knowledgeqa.providers.openai_compatible import OpenAICompatibleProvider
from knowledgeqa.repository import Repository
from knowledgeqa.security.secret_store import WindowsSecretStore
from knowledgeqa.security.sessions import SessionManager
from knowledgeqa.server import ServerRunner
from knowledgeqa.services.ingestion import IngestionService
from knowledgeqa.services.email_ingestion import EmailIngestionService
from knowledgeqa.services.search import SearchService
from knowledgeqa.status import StatusService
from knowledgeqa.tray import TrayController


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
    db_schema_version: Callable[[], int] = lambda: 2,
) -> dict[str, object]:
    return StatusService(
        settings=settings,
        docker_available=docker_available,
        docker_running=docker_running,
        milvus_available=milvus_available,
        db_schema_version=db_schema_version,
        jobs_running=jobs_running,
    ).snapshot()


def request_exit(
    window,
    jobs_running: Callable[[], int],
    choice_provider: Callable[[], ExitChoice] | None = None,
) -> bool:
    coordinator = ExitCoordinator(jobs_running=jobs_running)
    decision = coordinator.decide(
        choice_provider=choice_provider
        or (lambda: ExitChoice.STOP_AND_EXIT)
    )
    if decision in (ExitDecision.EXIT, ExitDecision.STOP_AND_EXIT):
        window.destroy()
        return True
    return False


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

    configure_logging(paths.log_dir)

    lock = InstanceLock(paths.data_dir / "app.lock")
    if not lock.try_acquire():
        return 0

    repository = Repository(paths.db_path)
    settings = Settings.from_env()
    lan_enabled = repository.get_setting("lan_enabled", "0") == "1"
    settings = replace(
        settings,
        host="0.0.0.0" if lan_enabled else settings.host,
        lan_enabled=lan_enabled,
    )
    controller = docker_controller or DockerController(root / "docker-compose.yml")
    embedder = FastEmbedEmbedder()
    milvus_store = MilvusStore(settings.milvus_uri)
    email_ingestion_service = EmailIngestionService(
        repository,
        embedder,
        milvus_store,
    )
    ingestion_service = IngestionService(
        repository,
        embedder,
        milvus_store,
        email_ingestion_service=email_ingestion_service,
    )
    search_service = SearchService(repository, embedder, milvus_store)
    secret_store = WindowsSecretStore()
    fallback_provider = None
    if settings.llm_base_url and settings.llm_api_key:
        fallback_provider = OpenAICompatibleProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    provider_manager = ProviderManager(
        repository=repository,
        secret_store=secret_store,
        fallback_provider=fallback_provider,
        fallback_model=settings.llm_model,
    )
    answer_service = AnswerService(
        repository=repository,
        search_service=search_service,
        provider=fallback_provider,
        model_name=settings.llm_model,
        provider_resolver=provider_manager.active,
    )
    auth_guard = AuthGuard(
        repository=repository,
        sessions=SessionManager(),
    )
    backup_service = BackupService(
        db_path=paths.db_path,
        data_dir=paths.data_dir,
        backup_dir=paths.backup_dir,
        schema_version=schema_version,
    )
    restore_service = RestoreService(
        target_data_dir=paths.data_dir,
        schema_version=schema_version,
    )
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
        repository=repository,
        ingestion_service=ingestion_service,
        search_service=search_service,
        answer_service=answer_service,
        provider_manager=provider_manager,
        secret_store=secret_store,
        auth_guard=auth_guard,
        backup_service=backup_service,
        restore_service=restore_service,
        docker_controller=controller,
    )
    runner = ServerRunner(app, settings)
    tray = None

    try:
        runner.start()
        if not runner.wait_until_ready():
            return 1
        window = webview.create_window(
            "KnowledgeQA",
            f"http://{settings.host}:{settings.port}",
            width=1180,
            height=780,
            min_size=(920, 620),
        )
        if hasattr(window, "events"):
            window.events.closing += lambda: (window.hide(), False)[1]
        tray = TrayController(
            on_show=window.show,
            on_quit=lambda: request_exit(
                window,
                jobs_running=lambda: 0,
            ),
        )
        tray.start()
        webview.start()
    finally:
        if tray is not None:
            tray.stop()
        runner.stop()
        lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
