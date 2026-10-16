from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from knowledgeqa.config import Settings


@dataclass(frozen=True)
class StatusService:
    settings: Settings
    docker_available: Callable[[], bool]
    docker_running: Callable[[], bool]
    milvus_available: Callable[[], bool]
    db_schema_version: Callable[[], int]
    jobs_running: Callable[[], int]

    def snapshot(self) -> dict[str, object]:
        return {
            "milvus": "connected" if self.milvus_available() else "disconnected",
            "embedding_model": "BAAI/bge-small-zh-v1.5",
            "jobs_running": self.jobs_running(),
            "lan_enabled": self.settings.lan_enabled,
            "docker_available": self.docker_available(),
            "docker_running": self.docker_running(),
            "db_schema_version": self.db_schema_version(),
            "api_port": self.settings.port,
        }
