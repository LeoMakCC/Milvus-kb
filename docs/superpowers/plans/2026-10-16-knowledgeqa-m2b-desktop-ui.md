# KnowledgeQA M2B Desktop UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn the M1 status page into a usable desktop UI for creating knowledge bases, syncing Markdown folders, and searching retrieved chunks.

**Architecture:** Keep the static, dependency-light frontend. Use vanilla HTML/CSS/JavaScript with a vendored Lucide icon runtime. Add `source_path` to Milvus rows so search results can show a human-readable source. The UI talks only to the local FastAPI service.

**Tech Stack:** HTML, CSS, vanilla JavaScript, Lucide 1.57.0, FastAPI, pytest.

---

### Task 1: Add Source Path To Retrieval

**Files:**
- Modify: `src/knowledgeqa/milvus/schema.py`
- Modify: `src/knowledgeqa/milvus/store.py`
- Modify: `src/knowledgeqa/services/ingestion.py`
- Modify: `tests/unit/test_milvus_schema.py`
- Modify: `tests/unit/test_milvus_store.py`
- Modify: `tests/unit/test_ingestion_service.py`

- [x] **Step 1: Write failing assertions**

Add:

```python
# schema test
assert "source_path" in field_names

# store test
assert search_call[4] == [
    "text",
    "document_id",
    "chunk_id",
    "page_no",
    "doc_type",
    "source_type",
    "source_path",
]

# ingestion test
assert store.inserted[0][1][0]["source_path"] == "a.md"
```

- [x] **Step 2: Run to verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_milvus_schema.py tests/unit/test_milvus_store.py tests/unit/test_ingestion_service.py -v
```

Expected: failures for missing `source_path`.

- [x] **Step 3: Implement**

- Add `source_path` to the Milvus schema after `source_type`.
- Include `source_path` in ingestion rows using `path.name`.
- Add `source_path` to search output fields and normalized hit output.

- [x] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_milvus_schema.py tests/unit/test_milvus_store.py tests/unit/test_ingestion_service.py -v
```

Expected: all pass.

---

### Task 2: Define UI Contract Tests

**Files:**
- Modify: `tests/integration/test_health_api.py`

- [x] **Step 1: Add failing UI tests**

Assert:

```python
def test_root_serves_desktop_page(portable_root):
    ...
    assert 'id="kbList"' in response.text
    assert 'id="searchInput"' in response.text
    assert 'id="syncButton"' in response.text


def test_static_assets_are_served(portable_root):
    ...
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/vendor/lucide.min.js").status_code == 200
```

- [x] **Step 2: Run to verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_health_api.py -v
```

Expected: missing UI element IDs or missing vendor file.

---

### Task 3: Build The Desktop UI

**Files:**
- Replace: `src/knowledgeqa/web/index.html`
- Replace: `src/knowledgeqa/web/styles.css`
- Replace: `src/knowledgeqa/web/app.js`

Required UI:

- Header with app name and runtime status.
- Left sidebar with Knowledge Base list and a compact create form.
- Main workspace with two tabs: `检索` and `知识库`.
- Knowledge Base tab:
  - selected knowledge base name
  - directory path input
  - sync button
  - sync result summary
- Search tab:
  - query input
  - result count selector
  - search button
  - results list with source path, score, and chunk text
- No visible instructional paragraphs or marketing copy.
- Use Lucide icons for create, refresh, search, database, and folder actions.
- Keep the layout dense, quiet, and usable at a 920 px minimum width.

---

### Task 4: Vendor Lucide

**Files:**
- Create: `src/knowledgeqa/web/vendor/lucide.min.js`

Download the pinned UMD build:

```powershell
New-Item -ItemType Directory -Force -Path 'src\knowledgeqa\web\vendor' | Out-Null
Invoke-WebRequest -Uri 'https://unpkg.com/lucide@1.57.0/dist/umd/lucide.min.js' -OutFile 'src\knowledgeqa\web\vendor\lucide.min.js'
```

Expected: the file is non-empty and exposes `window.lucide`.

---

### Task 5: Verify And Integrate

**Files:**
- Modify: `README.md`

- [x] **Step 1: Run the full test suite**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: all tests pass.

- [x] **Step 2: Restart the desktop app on 8788**

Use:

```powershell
$env:KB_PORT='8788'
.\.venv\Scripts\python.exe -m knowledgeqa.desktop
```

Expected: a `KnowledgeQA` window opens and `http://127.0.0.1:8788/` serves the new UI.

- [x] **Step 3: Verify live endpoints**

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8788/api/v1/status'
Invoke-RestMethod -Uri 'http://127.0.0.1:8788/api/v1/kbs'
```

Expected: M1 status object and an empty or existing KB list.

- [x] **Step 4: Verify real search flow**

1. Create a knowledge base in the UI.
2. Select a folder containing at least one Markdown file.
3. Click sync.
4. Search for a phrase from the Markdown file.
5. Confirm at least one result shows the source path and chunk text.

---

## Self-Review

### Spec Coverage

- Knowledge base creation: Task 3.
- Knowledge base sync: Task 3.
- Dense retrieval results: Tasks 1 and 3.
- Source path display: Task 1.
- Desktop shell: Task 3.
- Offline icon runtime: Task 4.

### Deferred

- Hybrid retrieval.
- Rerank.
- LLM answer generation.
- Multi-format parsing.
- Knowledge base deletion and rename.
- Background job progress.
