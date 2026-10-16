import logging
from pathlib import Path

from knowledgeqa.logging_setup import configure_logging


def test_configure_logging_writes_rolling_file(tmp_path: Path) -> None:
    handler = configure_logging(tmp_path)
    logger = logging.getLogger("knowledgeqa.test")
    logger.info("test message")
    handler.flush()

    log_file = tmp_path / "knowledgeqa.log"
    assert log_file.exists()
    assert "test message" in log_file.read_text(encoding="utf-8")
