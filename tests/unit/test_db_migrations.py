from pathlib import Path

from knowledgeqa.db.connection import connect
from knowledgeqa.db.migrations import apply_migrations, current_version


def test_apply_migrations_creates_core_tables(tmp_path: Path) -> None:
    conn = connect(tmp_path / "meta.db")
    try:
        applied = apply_migrations(conn)

        assert applied == [1, 2]
        assert current_version(conn) == 2
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {
            "app_settings",
            "knowledge_bases",
            "document_roots",
            "documents",
            "emails",
            "chunks",
            "jobs",
            "job_items",
            "conversations",
            "messages",
            "provider_configs",
            "email_attachments",
        }.issubset(tables)
        document_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(documents)")
        }
        assert "parent_document_id" in document_columns
    finally:
        conn.close()


def test_apply_migrations_is_idempotent(tmp_path: Path) -> None:
    conn = connect(tmp_path / "meta.db")
    try:
        assert apply_migrations(conn) == [1, 2]
        assert apply_migrations(conn) == []
    finally:
        conn.close()
