from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    portable_root: Path
    data_root: Path | None = None

    @property
    def data_dir(self) -> Path:
        return self.data_root if self.data_root is not None else self.portable_root / "data"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "metadata.db"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def model_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "temp"

    def ensure(self) -> None:
        for path in (
            self.data_dir,
            self.log_dir,
            self.model_dir,
            self.backup_dir,
            self.temp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8787
    lan_enabled: bool = False
    milvus_uri: str = "http://localhost:19530"
