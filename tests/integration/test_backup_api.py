import asyncio

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.backup import BackupService, RestoreService
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.db.connection import connect
from knowledgeqa.db.migrations import apply_migrations


async def request(app, method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def test_backup_and_restore_api(portable_root) -> None:
    data_dir = portable_root / "data"
    data_dir.mkdir()
    db_path = data_dir / "metadata.db"
    conn = connect(db_path)
    try:
        apply_migrations(conn)
    finally:
        conn.close()
    backup = BackupService(
        db_path=db_path,
        data_dir=data_dir,
        backup_dir=data_dir / "backups",
        schema_version=2,
    )
    restore = RestoreService(target_data_dir=data_dir, schema_version=2)
    app = create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=lambda: {"milvus": "disconnected"},
        backup_service=backup,
        restore_service=restore,
    )

    created = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/backup",
            json={"include_milvus": False},
        )
    )
    listed = asyncio.run(request(app, "GET", "/api/v1/backup"))
    restored = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/restore",
            json={"path": created.json()["path"]},
        )
    )

    assert created.status_code == 200
    assert listed.json()[0]["name"] == created.json()["name"]
    assert restored.json()["restored"] is True
