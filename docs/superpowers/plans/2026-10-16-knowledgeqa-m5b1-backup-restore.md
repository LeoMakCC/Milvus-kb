# KnowledgeQA M5B1 Backup Restore And Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add manual backup and restore with version manifests, SQLite online backup, optional Milvus data backup, and rolling logs.

**Architecture:** Backup and restore live in a dedicated service with an injectable Docker runner for testability. Backups are zip files containing a manifest, SQLite snapshot, configuration, model metadata, and optional Milvus archive. Restore validates the manifest, protects the current data, then restores files.

**Tech Stack:** sqlite3 backup API, zipfile, Docker command runner, logging.handlers, FastAPI, pytest.

---

### Task 1: Backup Manifest And ZIP

**Files:**
- Create: `src/knowledgeqa/backup.py`
- Test: `tests/unit/test_backup.py`

- [x] **Step 1: Write failing tests**

Create a temporary SQLite DB, call `BackupService.create_backup`, and assert:

```python
zip_path.exists()
manifest["app_version"] == "0.1.0"
manifest["schema_version"] == 2
manifest["embedding_model"] == "BAAI/bge-small-zh-v1.5"
"metadata.db" in manifest["files"]
```

- [x] **Step 2: Implement**

`BackupService.create_backup()`:

- use SQLite backup API to create a consistent snapshot;
- collect config/model/version metadata;
- write `manifest.json`;
- zip `metadata.db`, `manifest.json`, optional config, logs summary;
- record SHA-256 for files.

---

### Task 2: Milvus Backup Hook

**Files:**
- Modify: `src/knowledgeqa/backup.py`
- Test: `tests/unit/test_backup.py`

- [x] **Step 1: Write failing test**

Use a fake Docker runner and assert `BackupService` calls:

```text
docker run --rm -v knowledgeqa_milvus-data:/data ...
```

and records `milvus_included=True` when the command succeeds.

- [x] **Step 2: Implement**

`_backup_milvus()` writes a temporary archive path and returns a bool. Failures are recorded in the manifest but do not abort SQLite backup.

---

### Task 3: Restore

**Files:**
- Modify: `src/knowledgeqa/backup.py`
- Test: `tests/unit/test_backup.py`

- [x] **Step 1: Write failing tests**

Cover:

- backup zip can be restored into a target data directory;
- incompatible schema version raises an error;
- restore creates a safety backup of the current `metadata.db`.

- [x] **Step 2: Implement**

`RestoreService.restore()`:

1. validate manifest;
2. copy current `metadata.db` to `backups/pre-restore-<timestamp>.db`;
3. extract and replace supported files;
4. return a summary.

---

### Task 4: Logging

**Files:**
- Create: `src/knowledgeqa/logging_setup.py`
- Test: `tests/unit/test_logging_setup.py`

- [x] **Step 1: Write failing test**

Configure logging into a temp directory and assert:

```python
(log_dir / "knowledgeqa.log").exists()
```

Log a secret-like value and confirm the formatter does not include request bodies by default.

- [x] **Step 2: Implement**

Use `RotatingFileHandler` with 5 MB max size and 3 backups. Expose `configure_logging(log_dir, debug=False)`.

---

### Task 5: Backup API And Settings UI

**Files:**
- Create: `src/knowledgeqa/api/routes/backup.py`
- Modify: `src/knowledgeqa/api/app.py`
- Modify: `src/knowledgeqa/web/index.html`
- Modify: `src/knowledgeqa/web/app.js`
- Test: `tests/integration/test_backup_api.py`
- Modify: `tests/integration/test_health_api.py`

- [x] **Step 1: Write failing tests**

Cover:

```text
POST /api/v1/backup
GET  /api/v1/backup
POST /api/v1/restore
```

Add UI contract IDs:

```text
id="createBackupButton"
id="restoreBackupButton"
id="backupStatus"
```

- [x] **Step 2: Implement**

Settings page includes:

- create backup button;
- backup status/list;
- restore button using a path input;
- log directory link/summary.

- [x] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest
node --check src\knowledgeqa\web\app.js
```
