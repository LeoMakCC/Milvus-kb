from pathlib import Path

import pytest


@pytest.fixture
def portable_root(tmp_path: Path) -> Path:
    root = tmp_path / "KnowledgeQA"
    root.mkdir()
    return root
