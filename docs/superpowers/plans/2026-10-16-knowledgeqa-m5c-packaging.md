# KnowledgeQA M5C Tray And Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add tray behavior and exit protection, expose Docker lifecycle actions, and produce a portable PyInstaller build with a SHA-256 release manifest.

**Architecture:** Tray behavior is isolated in `tray.py` and integrated into the desktop entry point. Docker lifecycle stays behind `DockerController`. PyInstaller builds the desktop entry point into an onedir bundle; a PowerShell script creates the portable zip and release manifest.

**Tech Stack:** pystray, Pillow, pywebview, PyInstaller, PowerShell, Docker Compose.

---

### Task 1: Tray Controller

**Files:**
- Create: `src/knowledgeqa/tray.py`
- Test: `tests/unit/test_tray.py`

- [x] **Step 1: Write failing tests**

Use fake icon and menu factories and assert:

- menu contains `显示主窗口` and `退出`;
- callbacks call the injected show/quit callbacks;
- `stop` calls the icon stop method.

- [x] **Step 2: Implement**

```python
class TrayController:
    def __init__(self, on_show, on_quit, icon_factory=None, menu_factory=None): ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

Use pystray and Pillow by default.

---

### Task 2: Desktop Tray And Exit Protection

**Files:**
- Modify: `src/knowledgeqa/desktop.py`
- Test: `tests/unit/test_desktop.py`

- [x] **Step 1: Write failing tests**

Cover:

- closing the window hides it instead of destroying it;
- tray quit destroys the window;
- exit with running jobs asks for confirmation;
- exit without jobs proceeds.

- [x] **Step 2: Implement**

Create the webview window as a variable, attach a closing handler, start the tray controller, and stop the tray in `finally`.

---

### Task 3: Docker Lifecycle Actions

**Files:**
- Modify: `src/knowledgeqa/docker_control.py`
- Test: `tests/unit/test_docker_control.py`
- Create: `src/knowledgeqa/api/routes/milvus.py`
- Modify: `src/knowledgeqa/api/app.py`
- Modify: `src/knowledgeqa/web/index.html`
- Modify: `src/knowledgeqa/web/app.js`
- Test: `tests/integration/test_milvus_api.py`

- [x] **Step 1: Write failing tests**

Cover:

```text
GET  /api/v1/milvus/status
POST /api/v1/milvus/start
POST /api/v1/milvus/stop
```

Use a fake Docker controller.

- [x] **Step 2: Implement**

Return:

```json
{
  "available": true,
  "running": true,
  "compose_status": "ok"
}
```

Settings page gets `启动 Milvus`、`停止 Milvus`、`刷新状态`.

---

### Task 4: PyInstaller Spec

**Files:**
- Modify: `pyproject.toml`
- Create: `build/pyinstaller/KnowledgeQA.spec`
- Create: `scripts/build_portable.ps1`

- [x] **Step 1: Add build dependency**

```toml
"pyinstaller>=6.10,<7",
```

- [x] **Step 2: Implement spec**

Include:

- `src/knowledgeqa/web`
- `src/knowledgeqa/db/migrations`
- `docker-compose.yml`
- `fastembed`
- `onnxruntime`
- `pymilvus`
- `webview`
- `pystray`
- `PIL`

Output: `dist/KnowledgeQA/KnowledgeQA.exe`, `console=False`.

---

### Task 5: Portable Release

**Files:**
- Create: `scripts/make_release.ps1`
- Create: `scripts/release_manifest.py`
- Modify: `README.md`

- [x] **Step 1: Implement release script**

The script:

1. runs PyInstaller;
2. copies `docker-compose.yml` and README into the bundle;
3. zips `dist/KnowledgeQA`;
4. writes `.sha256`;
5. writes `manifest.json` with version, build time, and hashes.

- [x] **Step 2: Verify**

```powershell
.\scripts\make_release.ps1
```

Expected:

```text
dist\KnowledgeQA\KnowledgeQA.exe
dist\KnowledgeQA-portable.zip
dist\KnowledgeQA-portable.zip.sha256
dist\manifest.json
```

- [x] **Step 3: Smoke test**

Run `KnowledgeQA.exe` with `KB_PORT=8790`, verify the window opens and `/api/v1/health` responds.
