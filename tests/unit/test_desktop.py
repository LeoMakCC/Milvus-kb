from knowledgeqa.config import Settings
from knowledgeqa.desktop import build_status


def test_build_status_reports_defaults() -> None:
    settings = Settings()

    status = build_status(settings, jobs_running=lambda: 2)

    assert status == {
        "milvus": "disconnected",
        "embedding_model": "BAAI/bge-small-zh-v1.5",
        "jobs_running": 2,
        "lan_enabled": False,
    }
