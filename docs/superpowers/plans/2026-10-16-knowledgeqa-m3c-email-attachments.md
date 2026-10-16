# KnowledgeQA M3C Email Attachments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Index supported email attachment content, deduplicate attachments by content hash, and preserve email/attachment parent-child relationships.

**Architecture:** Email ingestion writes each supported attachment to a temporary file, parses it with the existing parser registry, and indexes it as a child document. Attachment content hashes are reused across emails, so duplicate attachments share one document and one vector set. The `email_attachments` table records every occurrence.

**Tech Stack:** Existing SQLite, parser registry, FastEmbed, Milvus, email parsers, pytest.

---

### Task 1: Schema And Repository Relationships

**Files:**
- Create: `src/knowledgeqa/db/migrations/002_email_attachments.sql`
- Modify: `src/knowledgeqa/repository.py`
- Test: `tests/unit/test_db_migrations.py`
- Test: `tests/unit/test_repository.py`

- [ ] **Step 1: Add failing migration test**

Apply migrations and assert:

```python
assert current_version(conn) == 2
columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
assert "parent_document_id" in columns
tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
assert "email_attachments" in tables
```

- [ ] **Step 2: Implement migration**

```sql
ALTER TABLE documents ADD COLUMN parent_document_id TEXT;
CREATE INDEX IF NOT EXISTS idx_documents_parent ON documents(parent_document_id);

CREATE TABLE IF NOT EXISTS email_attachments (
    id TEXT PRIMARY KEY,
    email_document_id TEXT NOT NULL,
    attachment_document_id TEXT,
    file_name TEXT NOT NULL,
    content_type TEXT,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (email_document_id) REFERENCES documents(id),
    FOREIGN KEY (attachment_document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_email_attachments_email
    ON email_attachments(email_document_id);
CREATE INDEX IF NOT EXISTS idx_email_attachments_hash
    ON email_attachments(content_hash);
```

- [ ] **Step 3: Extend repository**

Add:

```python
def get_document_by_source_hash(self, kb_id: str, source_hash: str) -> dict | None: ...
def upsert_email_attachment(
    self,
    email_document_id: str,
    attachment_document_id: str | None,
    file_name: str,
    content_type: str,
    content_hash: str,
) -> dict: ...
def list_email_attachments(self, email_document_id: str) -> list[dict]: ...
def list_email_thread(self, kb_id: str, thread_id: str) -> list[dict]: ...
```

`upsert_document` must accept `parent_document_id: str | None = None`.

- [ ] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_db_migrations.py tests/unit/test_repository.py -v
```

Expected: all pass.

---

### Task 2: Index Supported Attachments

**Files:**
- Modify: `src/knowledgeqa/ingestion/models.py`
- Modify: `src/knowledgeqa/services/email_ingestion.py`
- Test: `tests/unit/test_email_ingestion.py`

- [ ] **Step 1: Extend SyncResult**

Add defaults:

```python
attachments_inserted: int = 0
attachments_reused: int = 0
```

- [ ] **Step 2: Write failing attachment tests**

Cover:

- email with a `.txt` attachment indexes both email and attachment;
- searching or inspecting rows finds attachment text;
- attachment document has `parent_document_id` equal to email document ID;
- same attachment in a second email reuses the first attachment document;
- `attachments_inserted == 1` and `attachments_reused == 1` in that scenario.

- [ ] **Step 3: Implement attachment ingestion**

For each `EmailAttachment`:

- compute `content_hash = sha256(payload).hexdigest()`;
- if extension is unsupported, record metadata only;
- if a document with the same `source_hash` exists, link to it and count reused;
- otherwise write payload to a temporary file with the original suffix, parse with `parse_document`, chunk, embed, insert into Milvus, create a child document with `parent_document_id`, and count inserted;
- always call `upsert_email_attachment`.

Child rows use:

```python
source_type="email_attachment"
source_path=f"{path.name}::{attachment.file_name}"
page_no=chunk.page_no
```

- [ ] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_email_ingestion.py -v
```

Expected: all pass.

---

### Task 3: Attachment Counts In API And UI

**Files:**
- Modify: `src/knowledgeqa/api/routes/kbs.py`
- Modify: `src/knowledgeqa/web/app.js`
- Modify: `tests/integration/test_kb_api.py`

- [ ] **Step 1: Update API test**

Assert sync response contains:

```json
{
  "scanned": 2,
  "inserted": 1,
  "skipped": 1,
  "failed": 0,
  "attachments_inserted": 1,
  "attachments_reused": 0
}
```

- [ ] **Step 2: Update UI result line**

Display:

```text
扫描 X | 邮件/文档 Y | 跳过 Z | 附件新增 A | 附件复用 B | 失败 F
```

- [ ] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_kb_api.py -v
```

Expected: all pass.

---

### Task 4: Thread Aggregation

**Files:**
- Modify: `src/knowledgeqa/api/routes/kbs.py`
- Test: `tests/integration/test_kb_api.py`

- [ ] **Step 1: Write failing API test**

Add `GET /api/v1/kbs/{kb_id}/threads/{thread_id}`. The route calls `repository.list_email_thread`.

- [ ] **Step 2: Implement route**

Return:

```json
{
  "thread_id": "<thread@example.com>",
  "messages": [...]
}
```

Messages are ordered by `sent_at`.

- [ ] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_kb_api.py -v
```

Expected: all pass.

---

### Task 5: Live Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run the full suite**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: all pass.

- [ ] **Step 2: Restart 8788**

Restart the desktop process so it loads M3C.

- [ ] **Step 3: Create two `.eml` files sharing one `.txt` attachment**

Use the live API to sync. Confirm:

- two emails are inserted;
- one attachment is inserted and the second is reused;
- searching attachment text returns a result with `doc_type="txt"` and a source path containing the attachment name;
- email thread endpoint returns the related messages.

- [ ] **Step 4: Clean up temporary collection and SQLite rows.**
