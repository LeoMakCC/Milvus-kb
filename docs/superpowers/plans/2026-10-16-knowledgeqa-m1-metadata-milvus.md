# KnowledgeQA M1 Metadata And Milvus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add SQLite schema migrations, Milvus collection schema creation, Docker lifecycle control, and a status service wired into the desktop app.

**Architecture:** SQLite remains the authoritative metadata store. Milvus schema creation is isolated behind a small pymilvus adapter. Docker operations use an injectable command runner so unit tests do not require Docker. A status service aggregates database, Docker, Milvus, and job state for the existing `/api/v1/status` endpoint.

**Tech Stack:** Python 3.12, sqlite3, pymilvus, subprocess, pytest, FastAPI.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/knowledgeqa/db/__init__.py` | DB package marker |
| `src/knowledgeqa/db/connection.py` | SQLite connection setup |
| `src/knowledgeqa/db/migrations.py` | Migration discovery and execution |
| `src/knowledgeqa/db/migrations/001_initial.sql` | Initial metadata schema |
| `src/knowledgeqa/milvus/__init__.py` | Milvus package marker |
| `src/knowledgeqa/milvus/schema.py` | Knowledge-base collection schema |
| `src/knowledgeqa/docker_control.py` | Docker and compose command wrapper |
| `src/knowledgeqa/status.py` | Status snapshot service |
| `tests/unit/test_db_connection.py` | SQLite PRAGMA behavior |
| `tests/unit/test_db_migrations.py` | Migration discovery and idempotency |
| `tests/unit/test_milvus_schema.py` | Milvus schema contract |
| `tests/unit/test_docker_control.py` | Docker command behavior |
| `tests/unit/test_status.py` | Status snapshot behavior |

---

### Task 1: SQLite Connection And Migrations

**Files:**
- Create: `src/knowledgeqa/db/__init__.py`
- Create: `src/knowledgeqa/db/connection.py`
- Create: `src/knowledgeqa/db/migrations.py`
- Create: `src/knowledgeqa/db/migrations/001_initial.sql`
- Test: `tests/unit/test_db_connection.py`
- Test: `tests/unit/test_db_migrations.py`
- Modify: `pyproject.toml`

- [x] **Step 1: Write the failing connection test**

Create `tests/unit/test_db_connection.py`:

```python
from pathlib import Path

from knowledgeqa.db.connection import connect


def test_connect_enables_wal_and_foreign_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "meta.db"

    with connect(db_path) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert foreign_keys == 1
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_db_connection.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledgeqa.db'`.

- [x] **Step 3: Implement the SQLite connection**

Create `src/knowledgeqa/db/__init__.py`:

```python
```

Create `src/knowledgeqa/db/connection.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
```

- [x] **Step 4: Run the connection test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_db_connection.py -v
```

Expected: 1 passed.

- [x] **Step 5: Write the failing migration test**

Create `tests/unit/test_db_migrations.py`:

```python
from pathlib import Path

from knowledgeqa.db.connection import connect
from knowledgeqa.db.migrations import apply_migrations, current_version


def test_apply_migrations_creates_core_tables(tmp_path: Path) -> None:
    conn = connect(tmp_path / "meta.db")
    try:
        applied = apply_migrations(conn)

        assert applied == [1]
        assert current_version(conn) == 1
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {
            "app_settings",
            "knowledge_bases",
            "document_roots",
            "documents",
            "emails",
            "chunks",
            "jobs",
            "job_items",
            "conversations",
            "messages",
            "provider_configs",
        }.issubset(tables)
    finally:
        conn.close()


def test_apply_migrations_is_idempotent(tmp_path: Path) -> None:
    conn = connect(tmp_path / "meta.db")
    try:
        assert apply_migrations(conn) == [1]
        assert apply_migrations(conn) == []
    finally:
        conn.close()
```

- [x] **Step 6: Run the migration test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_db_migrations.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledgeqa.db.migrations'`.

- [x] **Step 7: Implement migration runner and initial schema**

Create `src/knowledgeqa/db/migrations.py`:

```python
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
```

Create `src/knowledgeqa/db/migrations/001_initial.sql` with the initial table definitions from `WINDOWS_V1_DESIGN.md`.

At minimum include:

- `schema_migrations`
- `app_settings`
- `knowledge_bases`
- `document_roots`
- `documents`
- `document_aliases`
- `emails`
- `chunks`
- `index_versions`
- `jobs`
- `job_items`
- `conversations`
- `messages`
- `provider_configs`
- `audit_logs`
- all index statements from the design document

- [x] **Step 8: Add migration SQL to package data**

Modify `pyproject.toml`:

```toml
[tool.setuptools.package-data]
knowledgeqa = ["web/*", "db/migrations/*.sql"]
```

- [x] **Step 9: Run migration tests to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_db_connection.py tests/unit/test_db_migrations.py -v
```

Expected: 3 passed.

- [x] **Step 10: Commit**

```powershell
git add pyproject.toml src/knowledgeqa/db tests/unit/test_db_connection.py tests/unit/test_db_migrations.py
git commit -m "feat: add sqlite migrations"
```

---

### Task 2: Milvus Knowledge Base Schema

**Files:**
- Modify: `pyproject.toml`
- Create: `src/knowledgeqa/milvus/__init__.py`
- Create: `src/knowledgeqa/milvus/schema.py`
- Test: `tests/unit/test_milvus_schema.py`

- [x] **Step 1: Add pymilvus dependency**

Modify `pyproject.toml` dependencies by adding:

```toml
  "pymilvus>=2.5,<3",
```

- [x] **Step 2: Write the failing schema test**

Create `tests/unit/test_milvus_schema.py`:

```python
from knowledgeqa.milvus.schema import collection_name, create_knowledge_base_collection


class FakeSchema:
    def __init__(self) -> None:
        self.fields = []
        self.functions = []

    def add_field(self, *args, **kwargs) -> None:
        self.fields.append((args, kwargs))

    def add_function(self, function) -> None:
        self.functions.append(function)


class FakeIndexParams:
    def __init__(self) -> None:
        self.indexes = []

    def add_index(self, **kwargs) -> None:
        self.indexes.append(kwargs)


class FakeClient:
    def __init__(self) -> None:
        self.schema = FakeSchema()
        self.indexes = FakeIndexParams()
        self.collections = []

    def create_schema(self, **kwargs) -> FakeSchema:
        self.schema_kwargs = kwargs
        return self.schema

    def prepare_index_params(self) -> FakeIndexParams:
        return self.indexes

    def create_collection(self, name, schema, index_params) -> None:
        self.collections.append((name, schema, index_params))


def test_collection_name_is_prefixed() -> None:
    assert collection_name("abc") == "kb_abc"


def test_create_knowledge_base_collection_builds_expected_contract() -> None:
    client = FakeClient()

    create_knowledge_base_collection(client, "abc", 512)

    assert client.collections[0][0] == "kb_abc"
    field_names = [field[0][0] for field in client.schema.fields]
    assert field_names == [
        "id",
        "vector",
        "text",
        "sparse",
        "kb_id",
        "document_id",
        "chunk_id",
        "page_no",
        "doc_type",
        "source_type",
    ]
    assert len(client.schema.functions) == 1
    assert client.indexes.indexes[0]["field_name"] == "vector"
    assert client.indexes.indexes[1]["field_name"] == "sparse"
```

- [x] **Step 3: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/unit/test_milvus_schema.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledgeqa.milvus'`.

- [x] **Step 4: Implement the schema builder**

Create `src/knowledgeqa/milvus/__init__.py`:

```python
```

Create `src/knowledgeqa/milvus/schema.py`:

```python
from __future__ import annotations

from pymilvus import DataType, Function, FunctionType


def collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}"


def create_knowledge_base_collection(client, kb_id: str, dim: int) -> None:
    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field(
        "text",
        DataType.VARCHAR,
        max_length=8192,
        enable_analyzer=True,
        analyzer_params={"type": "chinese"},
    )
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field("kb_id", DataType.VARCHAR, max_length=64)
    schema.add_field("document_id", DataType.VARCHAR, max_length=64)
    schema.add_field("chunk_id", DataType.VARCHAR, max_length=64)
    schema.add_field("page_no", DataType.INT64)
    schema.add_field("doc_type", DataType.VARCHAR, max_length=32)
    schema.add_field("source_type", DataType.VARCHAR, max_length=32)
    schema.add_function(
        Function(
            name="bm25",
            function_type=FunctionType.BM25,
            input_field_names=["text"],
            output_field_names=["sparse"],
            params={},
        )
    )

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    index_params.add_index(
        field_name="sparse",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
    )
    client.create_collection(
        collection_name(kb_id),
        schema=schema,
        index_params=index_params,
    )
```

- [x] **Step 5: Run the schema test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_milvus_schema.py -v
```

Expected: 2 passed.

- [x] **Step 6: Commit**

```powershell
git add pyproject.toml src/knowledgeqa/milvus tests/unit/test_milvus_schema.py
git commit -m "feat: add milvus schema builder"
```

---

### Task 3: Docker Controller

**Files:**
- Create: `src/knowledgeqa/docker_control.py`
- Test: `tests/unit/test_docker_control.py`

- [x] **Step 1: Write the failing Docker controller test**

Create `tests/unit/test_docker_control.py`:

```python
from pathlib import Path
from subprocess import CompletedProcess

from knowledgeqa.docker_control import DockerController


class FakeRunner:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.calls = []

    def __call__(self, args, capture_output, text, timeout):
        self.calls.append(args)
        return CompletedProcess(args, self.returncode, stdout="ok", stderr="")


def test_docker_available_uses_version_command(tmp_path: Path) -> None:
    runner = FakeRunner()
    controller = DockerController(tmp_path / "docker-compose.yml", runner=runner)

    assert controller.is_available() is True
    assert runner.calls[0][:2] == ["docker", "version"]


def test_compose_up_uses_project_name_and_file(tmp_path: Path) -> None:
    runner = FakeRunner()
    compose = tmp_path / "docker-compose.yml"
    controller = DockerController(compose, runner=runner)

    result = controller.compose_up()

    assert result.returncode == 0
    assert runner.calls[0] == [
        "docker",
        "compose",
        "-f",
        str(compose),
        "-p",
        "knowledgeqa",
        "up",
        "-d",
    ]
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_docker_control.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledgeqa.docker_control'`.

- [x] **Step 3: Implement the Docker controller**

Create `src/knowledgeqa/docker_control.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path


class DockerController:
    def __init__(
        self,
        compose_file: Path,
        project_name: str = "knowledgeqa",
        runner=subprocess.run,
    ) -> None:
        self._compose_file = compose_file
        self._project_name = project_name
        self._runner = runner

    def _run(self, args: list[str], timeout: int = 60):
        return self._runner(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def is_available(self) -> bool:
        return self._run(["docker", "version"], timeout=10).returncode == 0

    def is_running(self) -> bool:
        return self._run(["docker", "info"], timeout=10).returncode == 0

    def compose_up(self):
        return self._run(
            [
                "docker",
                "compose",
                "-f",
                str(self._compose_file),
                "-p",
                self._project_name,
                "up",
                "-d",
            ]
        )

    def compose_down(self):
        return self._run(
            [
                "docker",
                "compose",
                "-f",
                str(self._compose_file),
                "-p",
                self._project_name,
                "down",
            ]
        )

    def compose_ps(self):
        return self._run(
            [
                "docker",
                "compose",
                "-f",
                str(self._compose_file),
                "-p",
                self._project_name,
                "ps",
            ]
        )
```

- [x] **Step 4: Run the Docker controller tests to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_docker_control.py -v
```

Expected: 2 passed.

- [x] **Step 5: Commit**

```powershell
git add src/knowledgeqa/docker_control.py tests/unit/test_docker_control.py
git commit -m "feat: add docker controller"
```

---

### Task 4: Status Service And Desktop Integration

**Files:**
- Create: `src/knowledgeqa/status.py`
- Modify: `src/knowledgeqa/desktop.py`
- Test: `tests/unit/test_status.py`

- [x] **Step 1: Write the failing status service test**

Create `tests/unit/test_status.py`:

```python
from knowledgeqa.config import Settings
from knowledgeqa.status import StatusService


def test_status_snapshot_aggregates_dependencies() -> None:
    service = StatusService(
        settings=Settings(host="127.0.0.1", port=8788, lan_enabled=True),
        docker_available=lambda: True,
        docker_running=lambda: True,
        milvus_available=lambda: False,
        db_schema_version=lambda: 1,
        jobs_running=lambda: 3,
    )

    status = service.snapshot()

    assert status == {
        "milvus": "disconnected",
        "embedding_model": "BAAI/bge-small-zh-v1.5",
        "jobs_running": 3,
        "lan_enabled": True,
        "docker_available": True,
        "docker_running": True,
        "db_schema_version": 1,
        "api_port": 8788,
    }
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_status.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'knowledgeqa.status'`.

- [x] **Step 3: Implement status service**

Create `src/knowledgeqa/status.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from knowledgeqa.config import Settings


@dataclass(frozen=True)
class StatusService:
    settings: Settings
    docker_available: Callable[[], bool]
    docker_running: Callable[[], bool]
    milvus_available: Callable[[], bool]
    db_schema_version: Callable[[], int]
    jobs_running: Callable[[], int]

    def snapshot(self) -> dict[str, object]:
        return {
            "milvus": "connected" if self.milvus_available() else "disconnected",
            "embedding_model": "BAAI/bge-small-zh-v1.5",
            "jobs_running": self.jobs_running(),
            "lan_enabled": self.settings.lan_enabled,
            "docker_available": self.docker_available(),
            "docker_running": self.docker_running(),
            "db_schema_version": self.db_schema_version(),
            "api_port": self.settings.port,
        }
```

- [x] **Step 4: Run the status service test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_status.py -v
```

Expected: 1 passed.

- [x] **Step 5: Integrate migrations and status into desktop startup**

Modify `src/knowledgeqa/desktop.py`:

- Import `connect`, `apply_migrations`, `current_version`.
- Import `DockerController` and `StatusService`.
- Apply migrations after `paths.ensure()`.
- Create `DockerController(paths.portable_root / "docker-compose.yml")`.
- Build status provider from `StatusService`.

The `milvus_available` callable for M1 remains `lambda: False`; M2 replaces it with a real Milvus probe.

- [x] **Step 6: Update desktop orchestration test**

Modify `tests/unit/test_desktop.py` so `test_main_starts_window_and_stops_server` creates a temporary `docker-compose.yml` and sets:

- `milvus_available` to false
- `db_schema_version` to 1

Use the existing fake runner and fake webview.

- [x] **Step 7: Run all tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: all tests pass.

- [x] **Step 8: Commit**

```powershell
git add src/knowledgeqa/status.py src/knowledgeqa/desktop.py tests/unit/test_status.py tests/unit/test_desktop.py
git commit -m "feat: wire metadata and dependency status"
```

---

## Self-Review

### Spec Coverage

- SQLite schema and migrations: Task 1.
- Milvus collection schema: Task 2.
- Docker lifecycle controller: Task 3.
- Status aggregation: Task 4.
- Desktop integration: Task 4.

### Deferred

- Real per-knowledge-base collection creation from the UI.
- Milvus connectivity probing and collection loading.
- Ingestion jobs and document parsers.
- HTTP calls to Docker operations from the UI.

### Type Consistency

- `StatusService.snapshot()` returns the same status shape used by `/api/v1/status`.
- `DockerController` command runner accepts the `subprocess.run` keyword arguments used in tests.
- `create_knowledge_base_collection` accepts a pymilvus-compatible client and a dimension.
