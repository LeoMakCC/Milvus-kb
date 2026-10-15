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
    }


def test_main_starts_window_and_stops_server(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    class FakeRunner:
        def __init__(self, app, settings) -> None:
            self.app = app
            self.settings = settings

        def start(self) -> None:
            calls.append("server_start")

        def wait_until_ready(self, timeout: float = 10.0) -> bool:
            calls.append("server_ready")
            return True

        def stop(self) -> None:
            calls.append("server_stop")

    class FakeWebview:
        @staticmethod
        def create_window(*args, **kwargs) -> None:
            calls.append("window")

        @staticmethod
        def start() -> None:
            calls.append("webview_start")

    monkeypatch.setattr(desktop, "portable_root", lambda: tmp_path)
    monkeypatch.setattr(desktop, "ServerRunner", FakeRunner)
    monkeypatch.setattr(desktop, "webview", FakeWebview)

    assert desktop.main() == 0
    assert calls == [
        "server_start",
        "server_ready",
        "window",
        "webview_start",
        "server_stop",
    ]
