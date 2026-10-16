from knowledgeqa.config import Settings
from knowledgeqa.status import StatusService


def test_status_snapshot_aggregates_dependencies() -> None:
    service = StatusService(
        settings=Settings(host="127.0.0.1", port=8788, lan_enabled=True),
        docker_available=lambda: True,
        docker_running=lambda: True,
        milvus_available=lambda: False,
        db_schema_version=lambda: 1,
        jobs_running=lambda: 3,
    )

    status = service.snapshot()

    assert status == {
        "milvus": "disconnected",
        "embedding_model": "BAAI/bge-small-zh-v1.5",
        "jobs_running": 3,
        "lan_enabled": True,
        "docker_available": True,
        "docker_running": True,
        "db_schema_version": 1,
        "api_port": 8788,
    }
