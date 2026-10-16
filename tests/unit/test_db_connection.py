from pathlib import Path

from knowledgeqa.db.connection import connect


def test_connect_enables_wal_and_foreign_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "meta.db"

    with connect(db_path) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert foreign_keys == 1
