import asyncio

import httpx

from knowledgeqa.config import Settings
from knowledgeqa import desktop


def test_build_status_reports_defaults() -> None:
    settings = Settings()

    status = desktop.build_status(settings, jobs_running=lambda: 2)

    assert status == {
        "milvus": "disconnected",
        "embedding_model": "BAAI/bge-small-zh-v1.5",
        "jobs_running": 2,
        "lan_enabled": False,
        "docker_available": False,
        "docker_running": False,
        "db_schema_version": 2,
        "api_port": 8787,
    }


def test_main_starts_window_and_stops_server(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    class FakeRunner:
        def __init__(self, app, settings) -> None:
            self.app = app
            self.settings = settings
            captured_apps.append(app)

        def start(self) -> None:
            calls.append("server_start")

        def wait_until_ready(self, timeout: float = 10.0) -> bool:
            calls.append("server_ready")
            return True

        def stop(self) -> None:
            calls.append("server_stop")

    class FakeWebview:
        @staticmethod
        def create_window(*args, **kwargs):
            calls.append("window")
            return FakeWindow()

        @staticmethod
        def start() -> None:
            calls.append("webview_start")

    class FakeWindow:
        def show(self) -> None:
            pass

        def hide(self) -> None:
            pass

        def destroy(self) -> None:
            pass

    class FakeTray:
        def __init__(self, on_show, on_quit) -> None:
            calls.append("tray_create")

        def start(self) -> None:
            calls.append("tray_start")

        def stop(self) -> None:
            calls.append("tray_stop")

    monkeypatch.setattr(desktop, "portable_root", lambda: tmp_path)
    monkeypatch.setattr(desktop, "ServerRunner", FakeRunner)
    monkeypatch.setattr(desktop, "webview", FakeWebview)
    monkeypatch.setattr(desktop, "TrayController", FakeTray)

    class FakeDockerController:
        def is_available(self) -> bool:
            return False

        def is_running(self) -> bool:
            return False

    class FakeMilvusStore:
        def __init__(self, uri: str) -> None:
            self.uri = uri

        def is_available(self) -> bool:
            return False

    monkeypatch.setattr(desktop, "MilvusStore", FakeMilvusStore)
    captured_apps = []

    assert desktop.main(docker_controller=FakeDockerController()) == 0
    assert calls == [
        "server_start",
        "server_ready",
        "window",
        "tray_create",
        "tray_start",
        "webview_start",
        "tray_stop",
        "server_stop",
    ]

    async def fetch_status():
        transport = httpx.ASGITransport(app=captured_apps[0])
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/status")

    status = asyncio.run(fetch_status()).json()
    assert status["db_schema_version"] == 4
    assert status["docker_available"] is False
    assert status["milvus"] == "disconnected"


def test_desktop_api_forwards_selected_folder(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_select_folder(title: str = "", initial: str = "") -> str:
        calls.append((title, initial))
        return "D:\\docs"

    monkeypatch.setattr(desktop, "select_folder", fake_select_folder)

    assert desktop.DesktopApi().select_directory("D:\\start") == "D:\\docs"
    assert calls == [("选择文档目录", "D:\\start")]


def test_desktop_api_selects_backup_file(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []

    def fake_pick_files(title: str = "", initial: str = "", file_filter: str = ""):
        calls.append((title, initial, file_filter))
        return ["D:\\backups\\demo.zip"]

    monkeypatch.setattr(desktop, "pick_files", fake_pick_files)

    selected = desktop.DesktopApi().select_backup_file("D:\\backups")

    assert selected == "D:\\backups\\demo.zip"
    assert calls[0][0] == "选择备份文件"
    assert calls[0][1] == "D:\\backups"
    assert "*.zip" in calls[0][2]


def test_cached_probe_reuses_value_within_ttl() -> None:
    now = [0.0]
    hits: list[int] = []

    def probe() -> bool:
        hits.append(1)
        return True

    cached = desktop.cached_probe(probe, ttl=10.0, clock=lambda: now[0])

    assert cached() is True
    assert cached() is True
    assert len(hits) == 1

    now[0] = 11.0
    assert cached() is True
    assert len(hits) == 2


def test_request_exit_destroys_window_when_no_jobs() -> None:
    class FakeWindow:
        destroyed = False

        def destroy(self) -> None:
            self.destroyed = True

    window = FakeWindow()

    assert desktop.request_exit(window, jobs_running=lambda: 0) is True
    assert window.destroyed is True


def test_request_exit_can_keep_running_with_jobs() -> None:
    class FakeWindow:
        destroyed = False

        def destroy(self) -> None:
            self.destroyed = True

    window = FakeWindow()
    decision = desktop.request_exit(
        window,
        jobs_running=lambda: 1,
        choice_provider=lambda: desktop.ExitChoice.KEEP_RUNNING,
    )

    assert decision is False
    assert window.destroyed is False
