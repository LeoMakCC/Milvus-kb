from pathlib import Path

from knowledgeqa.config import AppPaths, Settings


def test_app_paths_default_to_portable_data_directory(portable_root: Path) -> None:
    paths = AppPaths(portable_root=portable_root)

    assert paths.data_dir == portable_root / "data"
    assert paths.db_path == portable_root / "data" / "metadata.db"
    assert paths.log_dir == portable_root / "data" / "logs"
    assert paths.model_dir == portable_root / "data" / "models"
    assert paths.backup_dir == portable_root / "data" / "backups"


def test_app_paths_support_custom_data_root(portable_root: Path, tmp_path: Path) -> None:
    custom = tmp_path / "custom-data"
    paths = AppPaths(portable_root=portable_root, data_root=custom)

    assert paths.data_dir == custom
    assert paths.db_path == custom / "metadata.db"


def test_settings_default_host_and_port() -> None:
    settings = Settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8787
    assert settings.lan_enabled is False
