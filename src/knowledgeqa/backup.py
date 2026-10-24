from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from knowledgeqa.process_utils import hidden_window_kwargs

APP_VERSION = "0.1.0"
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BackupService:
    def __init__(
        self,
        db_path: Path,
        data_dir: Path,
        backup_dir: Path,
        schema_version: int,
        docker_runner=subprocess.run,
        milvus_volume: str = "knowledgeqa_milvus-data",
    ) -> None:
        self._db_path = db_path
        self._data_dir = data_dir
        self._backup_dir = backup_dir
        self._schema_version = schema_version
        self._docker_runner = docker_runner
        self._milvus_volume = milvus_volume

    def create_backup(
        self,
        include_milvus: bool = True,
        target_dir: Path | str | None = None,
    ) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        output_dir = (
            Path(target_dir).expanduser()
            if target_dir
            else self._backup_dir
        )
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"无法写入备份目录: {output_dir}") from exc
        if not output_dir.is_dir():
            raise ValueError(f"备份目录不可用: {output_dir}")

        self._backup_dir.mkdir(parents=True, exist_ok=True)
        work_dir = self._backup_dir / f"backup-{stamp}"
        work_dir.mkdir(parents=True, exist_ok=False)

        snapshot = work_dir / "metadata.db"
        source = sqlite3.connect(self._db_path)
        destination = sqlite3.connect(snapshot)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        milvus_included = (
            self._backup_milvus(work_dir) if include_milvus else False
        )
        manifest = {
            "app_version": APP_VERSION,
            "created_at": _utc_now(),
            "schema_version": self._schema_version,
            "embedding_model": EMBEDDING_MODEL,
            "milvus_included": milvus_included,
            "files": {},
        }
        for path in sorted(work_dir.iterdir()):
            if path.is_file():
                manifest["files"][path.name] = _sha256(path)
        (work_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        archive = output_dir / f"knowledgeqa-backup-{stamp}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(work_dir.iterdir()):
                if path.is_file():
                    zf.write(path, path.name)
        shutil.rmtree(work_dir, ignore_errors=True)
        return archive

    def _backup_milvus(self, work_dir: Path) -> bool:
        archive = work_dir / "milvus-data.tar"
        archive.write_bytes(b"")
        args = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{self._milvus_volume}:/data",
            "-v",
            f"{work_dir.resolve()}:/backup",
            "alpine",
            "sh",
            "-c",
            "tar -czf /backup/milvus-data.tar -C /data .",
        ]
        result = self._docker_runner(
            args,
            capture_output=True,
            text=True,
            timeout=600,
            **hidden_window_kwargs(),
        )
        if result.returncode == 0 and archive.exists():
            return True
        archive.unlink(missing_ok=True)
        return False

    def list_backups(self) -> list[dict]:
        if not self._backup_dir.exists():
            return []
        items = []
        for path in sorted(
            self._backup_dir.glob("knowledgeqa-backup-*.zip"),
            reverse=True,
        ):
            items.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "created_at": datetime.fromtimestamp(
                        path.stat().st_mtime,
                        tz=timezone.utc,
                    ).isoformat(timespec="milliseconds"),
                }
            )
        return items


class RestoreService:
    def __init__(self, target_data_dir: Path, schema_version: int) -> None:
        self._target_data_dir = target_data_dir
        self._schema_version = schema_version

    def restore(self, archive_path: Path) -> dict:
        with zipfile.ZipFile(archive_path) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            if int(manifest.get("schema_version", 0)) > self._schema_version:
                raise ValueError("Backup schema is newer than this application")
            with tempfile.TemporaryDirectory(
                prefix="knowledgeqa-restore-",
                dir=self._target_data_dir,
            ) as temp:
                temp_dir = Path(temp)
                zf.extractall(temp_dir)
                safety_dir = self._target_data_dir / "backups"
                safety_dir.mkdir(parents=True, exist_ok=True)
                safety = None
                current_db = self._target_data_dir / "metadata.db"
                if current_db.exists():
                    stamp = datetime.now(timezone.utc).strftime(
                        "%Y%m%d-%H%M%S-%f"
                    )
                    safety = safety_dir / f"pre-restore-{stamp}.db"
                    shutil.copy2(current_db, safety)

                extracted_db = temp_dir / "metadata.db"
                if extracted_db.exists():
                    shutil.copy2(extracted_db, current_db)
                for name in ("config.json", "milvus-data.tar"):
                    source = temp_dir / name
                    if source.exists():
                        shutil.copy2(source, self._target_data_dir / name)

        return {
            "restored": True,
            "manifest": manifest,
            "safety_backup": str(safety) if safety else None,
        }
