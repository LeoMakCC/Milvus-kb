from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Migration:
    version: int
    path: Path


def migrations_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def discover_migrations(directory: Path | None = None) -> list[Migration]:
    root = directory or migrations_dir()
    migrations: list[Migration] = []
    for path in root.glob("[0-9][0-9][0-9]_*.sql"):
        version = int(path.name[:3])
        migrations.append(Migration(version=version, path=path))
    return sorted(migrations, key=lambda item: item.version)


def _ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def current_version(conn: sqlite3.Connection) -> int:
    _ensure_migration_table(conn)
    row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    return int(row[0])


def apply_migrations(
    conn: sqlite3.Connection,
    directory: Path | None = None,
) -> list[int]:
    _ensure_migration_table(conn)
    version = current_version(conn)
    applied: list[int] = []
    for migration in discover_migrations(directory):
        if migration.version <= version:
            continue
        sql = migration.path.read_text(encoding="utf-8")
        try:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
                (migration.version,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        applied.append(migration.version)
    return applied
