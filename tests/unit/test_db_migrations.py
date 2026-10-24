import shutil
from pathlib import Path

from knowledgeqa.db.connection import connect
from knowledgeqa.db.migrations import (
    apply_migrations,
    current_version,
    migrations_dir,
)


def test_apply_migrations_creates_core_tables(tmp_path: Path) -> None:
    conn = connect(tmp_path / "meta.db")
    try:
        applied = apply_migrations(conn)

        assert applied == [1, 2, 3, 4]
        assert current_version(conn) == 4
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
        assert apply_migrations(conn) == [1, 2, 3, 4]
        assert apply_migrations(conn) == []
    finally:
        conn.close()


def test_title_backfill_migration(tmp_path: Path) -> None:
    staging = tmp_path / "migrations"
    staging.mkdir()
    source = migrations_dir()
    for name in ("001_initial.sql", "002_email_attachments.sql"):
        shutil.copy(source / name, staging / name)

    conn = connect(tmp_path / "meta.db")
    try:
        assert apply_migrations(conn, staging) == [1, 2]
        conn.execute(
            """
            INSERT INTO conversations(id, title, kb_ids, created_at, updated_at)
            VALUES ('c1', '新会话', '["kb1"]', '2026-10-22', '2026-10-22')
            """
        )
        conn.execute(
            """
            INSERT INTO messages(
                id, conversation_id, role, content, created_at
            ) VALUES (
                'm1', 'c1', 'user',
                '请详细说明这份合同里关于付款条件和验收标准的全部条款',
                '2026-10-22 10:00:00'
            )
            """
        )
        conn.commit()

        shutil.copy(source / "003_conversation_titles.sql", staging)
        assert apply_migrations(conn, staging) == [3]

        title = conn.execute(
            "SELECT title FROM conversations WHERE id = 'c1'"
        ).fetchone()[0]
        assert title == "请详细说明这份合同里关于付款条件和验收标准的全部…"
        assert len(title) == 25
    finally:
        conn.close()
