# KnowledgeQA M0 Desktop Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Windows desktop foundation with Python 3.12, FastAPI health/status endpoints, single-instance protection, safe exit coordination, a pywebview shell, and a basic static UI.

**Architecture:** The launcher owns the desktop window and process lifecycle. A threaded Uvicorn server hosts a FastAPI app. SQLite, Milvus, ingestion, and model providers are deliberately deferred to later plans. M0 only proves the shell, API boundary, lifecycle rules, and test harness.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, Pydantic v2, pywebview, portalocker, pytest, httpx, pystray, Pillow.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, runtime dependencies, pytest configuration |
| `.gitignore` | Ignore virtual environment, caches, build output, and portable data |
| `README.md` | Development setup and M0 run instructions |
| `src/knowledgeqa/__init__.py` | Package version |
| `src/knowledgeqa/config.py` | Portable paths and runtime settings |
| `src/knowledgeqa/instance_lock.py` | Single-instance file lock |
| `src/knowledgeqa/lifecycle.py` | Exit decision logic |
| `src/knowledgeqa/server.py` | Uvicorn server thread and health wait |
| `src/knowledgeqa/api/app.py` | FastAPI application factory |
| `src/knowledgeqa/api/routes/health.py` | Health and status endpoints |
| `src/knowledgeqa/desktop.py` | Desktop entry point and pywebview integration |
| `src/knowledgeqa/web/index.html` | M0 desktop page |
| `src/knowledgeqa/web/styles.css` | M0 desktop styling |
| `src/knowledgeqa/web/app.js` | M0 status polling |
| `tests/unit/test_config.py` | Config and path behavior |
| `tests/unit/test_instance_lock.py` | Single-instance lock behavior |
| `tests/unit/test_lifecycle.py` | Exit decision behavior |
| `tests/unit/test_server.py` | Server lifecycle behavior |
| `tests/integration/test_health_api.py` | API health and status contract |

---

### Task 1: Bootstrap Python 3.12 Project

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/knowledgeqa/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create project metadata**

Create `pyproject.toml` with Python 3.12, setuptools, runtime dependencies, dev dependencies, package discovery, and pytest configuration.

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "knowledgeqa"
version = "0.1.0"
description = "Portable local knowledge base QA desktop application"
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi>=0.115,<1",
  "httpx>=0.27,<1",
  "Pillow>=10.4,<12",
  "portalocker>=2.10,<3",
  "pydantic>=2.7,<3",
  "pystray>=0.19,<1",
  "pywebview>=5.3,<6",
  "uvicorn[standard]>=0.30,<1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2,<9",
]

[project.scripts]
knowledgeqa = "knowledgeqa.desktop:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
knowledgeqa = ["web/*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: Create ignore rules and package marker**

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
build/
dist/
*.egg-info/
data/
logs/
backups/
*.db
*.db-wal
*.db-shm
```

Create `src/knowledgeqa/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `tests/conftest.py`:

```python
from pathlib import Path

import pytest


@pytest.fixture
def portable_root(tmp_path: Path) -> Path:
    root = tmp_path / "KnowledgeQA"
    root.mkdir()
    return root
```

- [ ] **Step 3: Create README**

Create `README.md`:

```markdown
# KnowledgeQA

Windows-first portable knowledge base QA desktop application.

## Development

```powershell
& "$env:APPDATA\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

## M0 Run

```powershell
.\.venv\Scripts\python.exe -m knowledgeqa.desktop
```
```

- [ ] **Step 4: Create and install the environment**

Run:

```powershell
& "$env:APPDATA\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Expected: editable install completes and `pytest --version` prints a version.

- [ ] **Step 5: Run test discovery**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: no tests found, exit code 5. This is expected for bootstrap.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml .gitignore README.md src tests docs
git commit -m "chore: bootstrap KnowledgeQA package"
```

---

### Task 2: Portable Configuration and Paths

**Files:**
- Create: `tests/unit/test_config.py`
- Create: `src/knowledgeqa/config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_config.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledgeqa.config'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/knowledgeqa/config.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/knowledgeqa/config.py tests/unit/test_config.py
git commit -m "feat: add portable path configuration"
```

---

### Task 3: Health and Status API

**Files:**
- Create: `tests/integration/test_health_api.py`
- Create: `src/knowledgeqa/api/__init__.py`
- Create: `src/knowledgeqa/api/app.py`
- Create: `src/knowledgeqa/api/routes/__init__.py`
- Create: `src/knowledgeqa/api/routes/health.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_health_api.py`:

```python
from fastapi.testclient import TestClient

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings


def status_provider() -> dict[str, object]:
    return {
        "milvus": "disconnected",
        "embedding_model": "BAAI/bge-small-zh-v1.5",
        "jobs_running": 0,
        "lan_enabled": False,
    }


def test_health_endpoint(portable_root) -> None:
    app = create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=status_provider,
    )
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_endpoint(portable_root) -> None:
    app = create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=status_provider,
    )
    client = TestClient(app)

    response = client.get("/api/v1/status")

    assert response.status_code == 200
    assert response.json() == status_provider()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_health_api.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledgeqa.api'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/knowledgeqa/api/__init__.py`:

```python
```

Create `src/knowledgeqa/api/routes/__init__.py`:

```python
```

Create `src/knowledgeqa/api/routes/health.py`:

```python
from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter


def create_health_router(
    status_provider: Callable[[], dict[str, object]],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/status")
    def status() -> dict[str, object]:
        return status_provider()

    return router
```

Create `src/knowledgeqa/api/app.py`:

```python
from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI

from knowledgeqa.api.routes.health import create_health_router
from knowledgeqa.config import AppPaths, Settings


def create_app(
    settings: Settings,
    paths: AppPaths,
    status_provider: Callable[[], dict[str, object]],
) -> FastAPI:
    app = FastAPI(title="KnowledgeQA", version="0.1.0")
    app.include_router(create_health_router(status_provider))
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_health_api.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/knowledgeqa/api tests/integration/test_health_api.py
git commit -m "feat: add health and status API"
```

---

### Task 4: Single-Instance Lock

**Files:**
- Create: `tests/unit/test_instance_lock.py`
- Create: `src/knowledgeqa/instance_lock.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_instance_lock.py`:

```python
from pathlib import Path

from knowledgeqa.instance_lock import InstanceLock


def test_first_lock_can_be_acquired(tmp_path: Path) -> None:
    lock = InstanceLock(tmp_path / "app.lock")

    assert lock.try_acquire() is True
    lock.release()


def test_second_lock_is_rejected_until_first_releases(tmp_path: Path) -> None:
    first = InstanceLock(tmp_path / "app.lock")
    second = InstanceLock(tmp_path / "app.lock")

    assert first.try_acquire() is True
    assert second.try_acquire() is False

    first.release()

    assert second.try_acquire() is True
    second.release()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_instance_lock.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledgeqa.instance_lock'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/knowledgeqa/instance_lock.py`:

```python
from __future__ import annotations

from pathlib import Path

import portalocker


class InstanceLock:
    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._file = None

    def try_acquire(self) -> bool:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        file = self._lock_path.open("a+", encoding="utf-8")
        try:
            portalocker.lock(file, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.exceptions.LockException:
            file.close()
            return False
        self._file = file
        return True

    def release(self) -> None:
        if self._file is None:
            return
        portalocker.unlock(self._file)
        self._file.close()
        self._file = None
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_instance_lock.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/knowledgeqa/instance_lock.py tests/unit/test_instance_lock.py
git commit -m "feat: add single-instance lock"
```

---

### Task 5: Exit Decision Coordinator

**Files:**
- Create: `tests/unit/test_lifecycle.py`
- Create: `src/knowledgeqa/lifecycle.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_lifecycle.py`:

```python
from knowledgeqa.lifecycle import ExitChoice, ExitCoordinator, ExitDecision


def test_exit_without_jobs_exits_immediately() -> None:
    coordinator = ExitCoordinator(jobs_running=lambda: 0)

    assert coordinator.decide(choice_provider=lambda: ExitChoice.CANCEL) == ExitDecision.EXIT


def test_exit_with_jobs_can_keep_running() -> None:
    coordinator = ExitCoordinator(jobs_running=lambda: 1)

    assert coordinator.decide(choice_provider=lambda: ExitChoice.KEEP_RUNNING) == ExitDecision.KEEP_RUNNING


def test_exit_with_jobs_can_stop_and_exit() -> None:
    coordinator = ExitCoordinator(jobs_running=lambda: 1)

    assert coordinator.decide(choice_provider=lambda: ExitChoice.STOP_AND_EXIT) == ExitDecision.STOP_AND_EXIT


def test_exit_with_jobs_can_cancel_exit() -> None:
    coordinator = ExitCoordinator(jobs_running=lambda: 1)

    assert coordinator.decide(choice_provider=lambda: ExitChoice.CANCEL) == ExitDecision.CANCEL_EXIT
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_lifecycle.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledgeqa.lifecycle'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/knowledgeqa/lifecycle.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from enum import Enum


class ExitChoice(str, Enum):
    KEEP_RUNNING = "keep_running"
    STOP_AND_EXIT = "stop_and_exit"
    CANCEL = "cancel"


class ExitDecision(str, Enum):
    EXIT = "exit"
    KEEP_RUNNING = "keep_running"
    STOP_AND_EXIT = "stop_and_exit"
    CANCEL_EXIT = "cancel_exit"


class ExitCoordinator:
    def __init__(self, jobs_running: Callable[[], int]) -> None:
        self._jobs_running = jobs_running

    def decide(self, choice_provider: Callable[[], ExitChoice]) -> ExitDecision:
        if self._jobs_running() == 0:
            return ExitDecision.EXIT

        choice = choice_provider()
        if choice is ExitChoice.KEEP_RUNNING:
            return ExitDecision.KEEP_RUNNING
        if choice is ExitChoice.STOP_AND_EXIT:
            return ExitDecision.STOP_AND_EXIT
        return ExitDecision.CANCEL_EXIT
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_lifecycle.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/knowledgeqa/lifecycle.py tests/unit/test_lifecycle.py
git commit -m "feat: add exit decision coordinator"
```

---

### Task 6: Uvicorn Server Thread

**Files:**
- Create: `tests/unit/test_server.py`
- Create: `src/knowledgeqa/server.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_server.py`:

```python
import socket

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.server import ServerRunner


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_server_runner_starts_and_stops(portable_root) -> None:
    port = free_port()
    settings = Settings(host="127.0.0.1", port=port)
    paths = AppPaths(portable_root=portable_root)
    app = create_app(
        settings=settings,
        paths=paths,
        status_provider=lambda: {"milvus": "disconnected"},
    )
    runner = ServerRunner(app, settings)

    runner.start()
    try:
        assert runner.wait_until_ready(timeout=5)
        response = httpx.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=2)
        assert response.json() == {"status": "ok"}
    finally:
        runner.stop()

    assert runner.is_running is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_server.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledgeqa.server'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/knowledgeqa/server.py`:

```python
from __future__ import annotations

import threading
import time

import httpx
import uvicorn

from knowledgeqa.config import Settings


class ServerRunner:
    def __init__(self, app, settings: Settings) -> None:
        self._settings = settings
        config = uvicorn.Config(
            app,
            host=settings.host,
            port=settings.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    @property
    def is_running(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        self._thread.start()

    def wait_until_ready(self, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        url = f"http://{self._settings.host}:{self._settings.port}/api/v1/health"
        while time.monotonic() < deadline:
            if self._server.started:
                try:
                    response = httpx.get(url, timeout=0.5)
                    if response.status_code == 200:
                        return True
                except httpx.HTTPError:
                    pass
            time.sleep(0.05)
        return False

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_server.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/knowledgeqa/server.py tests/unit/test_server.py
git commit -m "feat: add uvicorn server runner"
```

---

### Task 7: Minimal Desktop Shell

**Files:**
- Create: `src/knowledgeqa/web/index.html`
- Create: `src/knowledgeqa/web/styles.css`
- Create: `src/knowledgeqa/web/app.js`
- Create: `src/knowledgeqa/desktop.py`
- Modify: `src/knowledgeqa/api/app.py`
- Modify: `tests/integration/test_health_api.py`

- [ ] **Step 1: Write the failing test**

Modify `tests/integration/test_health_api.py` by adding:

```python
def test_root_serves_desktop_page(portable_root) -> None:
    app = create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=status_provider,
    )
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "KnowledgeQA" in response.text
```

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_health_api.py::test_root_serves_desktop_page -v
```

Expected: FAIL with 404 for `/`.

- [ ] **Step 2: Add static page files**

Create `src/knowledgeqa/web/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KnowledgeQA</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <main class="shell">
    <header>
      <h1>KnowledgeQA</h1>
      <span id="health" class="status">检测中</span>
    </header>
    <section class="panel">
      <h2>桌面基础服务</h2>
      <p id="statusLine">正在读取状态...</p>
    </section>
  </main>
  <script src="/static/app.js"></script>
</body>
</html>
```

Create `src/knowledgeqa/web/styles.css`:

```css
:root {
  color-scheme: light;
  --bg: #f5f6f8;
  --panel: #ffffff;
  --text: #1f2329;
  --muted: #6b7078;
  --border: #e4e6ea;
  --accent: #2563eb;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
}
.shell { max-width: 900px; margin: 0 auto; padding: 28px 24px; }
header { display: flex; align-items: center; gap: 14px; margin-bottom: 22px; }
h1 { font-size: 22px; margin: 0; }
.status {
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  font-size: 12px;
  padding: 4px 10px;
}
.status.ok { color: #15803d; border-color: #bbf7d0; background: #f0fdf4; }
.status.bad { color: #b91c1c; border-color: #fecaca; background: #fef2f2; }
.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
}
h2 { font-size: 16px; margin: 0 0 10px; }
p { color: var(--muted); line-height: 1.7; margin: 0; }
```

Create `src/knowledgeqa/web/app.js`:

```javascript
async function refreshStatus() {
  const health = document.getElementById("health");
  const statusLine = document.getElementById("statusLine");
  try {
    const response = await fetch("/api/v1/status");
    const data = await response.json();
    health.textContent = "已运行";
    health.className = "status ok";
    statusLine.textContent = `Milvus: ${data.milvus} | 任务: ${data.jobs_running}`;
  } catch (error) {
    health.textContent = "服务异常";
    health.className = "status bad";
    statusLine.textContent = String(error);
  }
}

refreshStatus();
setInterval(refreshStatus, 5000);
```

- [ ] **Step 3: Modify API app to serve static files**

Replace `src/knowledgeqa/api/app.py` with:

```python
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from knowledgeqa.api.routes.health import create_health_router
from knowledgeqa.config import AppPaths, Settings


def create_app(
    settings: Settings,
    paths: AppPaths,
    status_provider: Callable[[], dict[str, object]],
) -> FastAPI:
    app = FastAPI(title="KnowledgeQA", version="0.1.0")
    app.include_router(create_health_router(status_provider))

    web_dir = Path(__file__).resolve().parents[1] / "web"
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_health_api.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Create desktop entry point**

Create `src/knowledgeqa/desktop.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import webview

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.instance_lock import InstanceLock
from knowledgeqa.lifecycle import ExitChoice, ExitCoordinator, ExitDecision
from knowledgeqa.server import ServerRunner


def portable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def main() -> int:
    root = portable_root()
    paths = AppPaths(portable_root=root)
    paths.ensure()

    lock = InstanceLock(paths.data_dir / "app.lock")
    if not lock.try_acquire():
        return 0

    settings = Settings()
    app = create_app(
        settings=settings,
        paths=paths,
        status_provider=lambda: {
            "milvus": "disconnected",
            "embedding_model": "BAAI/bge-small-zh-v1.5",
            "jobs_running": 0,
            "lan_enabled": settings.lan_enabled,
        },
    )
    runner = ServerRunner(app, settings)

    try:
        runner.start()
        if not runner.wait_until_ready():
            return 1
        webview.create_window(
            "KnowledgeQA",
            f"http://{settings.host}:{settings.port}",
            width=1180,
            height=780,
            min_size=(920, 620),
        )
        webview.start()
    finally:
        runner.stop()
        lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run all tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add src/knowledgeqa tests
git commit -m "feat: add desktop shell and static UI"
```

---

### Task 8: Development Smoke Script

**Files:**
- Create: `scripts/run_dev.ps1`
- Modify: `README.md`

- [ ] **Step 1: Create a smoke script**

Create `scripts/run_dev.ps1`:

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Missing .venv. Follow README development setup first."
}

.\.venv\Scripts\python.exe -m knowledgeqa.desktop
```

- [ ] **Step 2: Update README with smoke instructions**

Append to `README.md`:

```markdown
## Manual Smoke Test

```powershell
.\scripts\run_dev.ps1
```

Expected: a desktop window opens, status shows "已运行", and closing the window exits the backend without leaving the lock file held.
```

- [ ] **Step 3: Verify tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```powershell
git add scripts README.md
git commit -m "docs: add M0 development smoke script"
```

---

## Self-Review

### Spec Coverage

- Desktop shell: Task 7.
- FastAPI local service: Tasks 3 and 6.
- Single-instance lock: Task 4.
- Exit protection decision logic: Task 5.
- Portable data directory: Task 2.
- Web UI foundation: Task 7.
- Test harness: Tasks 2 through 7.
- Git and project baseline: Task 1.

### Deferred to Later Plans

- SQLite schema and migrations.
- Milvus and Docker lifecycle.
- Tray icon and native dialogs.
- Document parsing and ingestion.
- Email parsing and deduplication.
- Model gateway and streaming.
- Multi-knowledge-base UI.
- Backup and release packaging.

### Type Consistency

- `Settings` is defined once in `knowledgeqa.config`.
- `AppPaths` is used by API creation and desktop startup.
- `ExitChoice` and `ExitDecision` are defined together in `lifecycle.py`.
- `ServerRunner` accepts a FastAPI app and `Settings`.
