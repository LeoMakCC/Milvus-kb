import json
import zipfile
from pathlib import Path
from subprocess import CompletedProcess

from knowledgeqa.backup import BackupService, RestoreService
from knowledgeqa.db.connection import connect
from knowledgeqa.db.migrations import apply_migrations


def make_db(path: Path) -> None:
    conn = connect(path)
    try:
        apply_migrations(conn)
    finally:
        conn.close()


def test_create_backup_contains_manifest_and_database(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "metadata.db"
    db_path.parent.mkdir()
    make_db(db_path)
    service = BackupService(
        db_path=db_path,
        data_dir=db_path.parent,
        backup_dir=tmp_path / "backups",
        schema_version=2,
    )

    archive = service.create_backup(include_milvus=False)

    assert archive.exists()
    with zipfile.ZipFile(archive) as zf:
        assert "metadata.db" in zf.namelist()
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["schema_version"] == 2
    assert manifest["milvus_included"] is False
    assert manifest["embedding_model"] == "BAAI/bge-small-zh-v1.5"
    assert "metadata.db" in manifest["files"]


def test_create_backup_writes_to_custom_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "metadata.db"
    db_path.parent.mkdir()
    make_db(db_path)
    target = tmp_path / "external"
    service = BackupService(
        db_path=db_path,
        data_dir=db_path.parent,
        backup_dir=tmp_path / "backups",
        schema_version=2,
    )

    archive = service.create_backup(include_milvus=False, target_dir=target)

    assert archive.parent == target
    assert archive.exists()
    assert service.list_backups() == []


def test_milvus_backup_hook_records_success(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "metadata.db"
    db_path.parent.mkdir()
    make_db(db_path)

    calls = []

    def runner(args, capture_output, text, timeout, **kwargs):
        calls.append(args)
        return CompletedProcess(args, 0, stdout="", stderr="")

    service = BackupService(
        db_path=db_path,
        data_dir=db_path.parent,
        backup_dir=tmp_path / "backups",
        schema_version=2,
        docker_runner=runner,
    )

    archive = service.create_backup(include_milvus=True)

    with zipfile.ZipFile(archive) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        assert "milvus-data.tar" in zf.namelist()
    assert manifest["milvus_included"] is True
    assert calls[0][:2] == ["docker", "run"]


def test_restore_replaces_database_and_creates_safety_backup(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    db_path = source / "metadata.db"
    make_db(db_path)
    service = BackupService(
        db_path=db_path,
        data_dir=source,
        backup_dir=source / "backups",
        schema_version=2,
    )
    archive = service.create_backup(include_milvus=False)

    target = tmp_path / "target"
    target.mkdir()
    target_db = target / "metadata.db"
    target_db.write_bytes(b"old database")
    restore = RestoreService(target_data_dir=target, schema_version=2)

    result = restore.restore(archive)

    assert result["restored"] is True
    assert target_db.read_bytes() != b"old database"
    assert any((target / "backups").glob("pre-restore-*.db"))
