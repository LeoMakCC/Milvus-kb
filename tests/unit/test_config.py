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
    assert settings.milvus_uri == "http://localhost:19530"


def test_settings_from_env_overrides_runtime_values() -> None:
    settings = Settings.from_env(
        {
            "KB_HOST": "0.0.0.0",
            "KB_PORT": "8788",
            "KB_LAN_ENABLED": "1",
            "KB_MILVUS_URI": "http://127.0.0.1:19531",
        }
    )

    assert settings.host == "0.0.0.0"
    assert settings.port == 8788
    assert settings.lan_enabled is True
    assert settings.milvus_uri == "http://127.0.0.1:19531"
