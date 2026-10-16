# KnowledgeQA M3B Email Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Index `.eml`, `.mbox`, and `.msg` email files with headers, bodies, thread fields, and deduplication.

**Architecture:** Email parsing produces a normalized `ParsedEmail` model. Email ingestion creates normal document/chunk/vector rows and an `emails` metadata row. Deduplication happens before document creation using `Message-ID` first and a normalized hash as fallback.

**Tech Stack:** Python 3.12 stdlib `email`/`mailbox`, `extract-msg`, existing SQLite/Milvus/Embedding pipeline, pytest.

---

### Task 1: Email Models And Repository Support

**Files:**
- Create: `src/knowledgeqa/email_models.py`
- Modify: `src/knowledgeqa/repository.py`
- Test: `tests/unit/test_repository.py`

- [x] **Step 1: Write failing tests**

Cover:

```python
def test_upsert_email_and_find_by_message_id(tmp_path):
    repo = Repository(tmp_path / "meta.db")
    repo.initialize()
    kb = repo.create_knowledge_base(name="邮件", dimension=2)
    document = repo.upsert_document(
        kb_id=kb["id"],
        canonical_path="mail#1",
        file_name="mail.eml",
        doc_type="email",
        source_type="email_file",
        source_hash="hash",
        index_status="indexed",
    )
    repo.upsert_email(
        document_id=document["id"],
        message_id="<abc@example.com>",
        thread_id="<thread@example.com>",
        subject="付款条件",
        from_addr="a@example.com",
        to_addr="b@example.com",
        cc_addr="",
        sent_at="2026-10-16T00:00:00Z",
        message_hash="mh1",
    )
    assert repo.get_email_by_message_id(kb["id"], "<abc@example.com>")["subject"] == "付款条件"
    assert repo.get_email_by_hash(kb["id"], "mh1")["document_id"] == document["id"]
```

- [x] **Step 2: Implement models**

```python
@dataclass(frozen=True)
class EmailAttachment:
    file_name: str
    content_type: str
    payload: bytes


@dataclass(frozen=True)
class ParsedEmail:
    message_id: str | None
    thread_id: str | None
    subject: str
    from_addr: str
    to_addr: str
    cc_addr: str
    sent_at: str
    body_text: str
    message_hash: str
    source_path: str
    attachments: list[EmailAttachment] = field(default_factory=list)
```

- [x] **Step 3: Implement repository methods**

Add `upsert_email`, `get_email_by_message_id`, `get_email_by_hash`, and `get_email_by_document_id` using the existing `emails` table.

- [x] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_repository.py -v
```

Expected: all pass.

---

### Task 2: EML And MBOX Parsers

**Files:**
- Create: `src/knowledgeqa/parsers/email_parser.py`
- Test: `tests/unit/test_email_parsers.py`

- [x] **Step 1: Write failing tests**

Cover:

- `.eml` parses subject, from, to, date, body, message ID.
- `.mbox` returns one `ParsedEmail` per message.
- duplicate `Message-ID` is preserved by the parser; dedup happens in ingestion.
- attachment names are appended as an `附件: name` section.
- `Thread-Index` or `References` becomes `thread_id`.

- [x] **Step 2: Implement**

Functions:

```python
def parse_eml(path: Path) -> list[ParsedEmail]: ...
def parse_mbox(path: Path) -> list[ParsedEmail]: ...
def parse_email_file(path: Path) -> list[ParsedEmail]: ...
```

Use stdlib `email` policies for header decoding. For `.mbox`, use `mailbox.mbox`.

Compute `message_hash` from normalized subject, from, to, date, and plain-text body.

- [x] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_email_parsers.py -v
```

Expected: all pass.

---

### Task 3: MSG Parser

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/knowledgeqa/parsers/email_parser.py`
- Test: `tests/unit/test_email_parsers.py`

- [x] **Step 1: Add dependency**

```toml
"extract-msg>=0.50,<1",
```

- [x] **Step 2: Write a mocked failing test**

Patch `extract_msg.Message` to return an object with:

```text
subject, sender, to, cc, date, messageId, body, attachments
```

Assert one `ParsedEmail` is produced with the expected fields.

- [x] **Step 3: Implement**

`parse_msg(path)` reads fields defensively and converts `date` to ISO 8601 when possible. Attachment objects expose `longFilename` or `shortFilename`, `mimetype`, and `data`.

- [x] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/unit/test_email_parsers.py -v
```

Expected: all pass.

---

### Task 4: Email Ingestion And Dedup

**Files:**
- Create: `src/knowledgeqa/services/email_ingestion.py`
- Modify: `src/knowledgeqa/services/ingestion.py`
- Test: `tests/unit/test_email_ingestion.py`

- [x] **Step 1: Write failing tests**

Cover:

- new `.eml` is indexed;
- unchanged duplicate `Message-ID` is skipped;
- same message in two files is skipped;
- chunk rows use `doc_type="email"`;
- body and attachment names are searchable text.

- [x] **Step 2: Implement**

`EmailIngestionService.sync_emails(kb_id, directory) -> SyncResult`:

- walk `.eml`, `.mbox`, `.msg`;
- parse each message;
- dedup via `get_email_by_message_id` then `get_email_by_hash`;
- use `canonical_path = f"{path}::{message_hash}"`;
- create document, chunks, embeddings, Milvus rows, and `emails` row.

Update `IngestionService.sync_all` to combine document and email results.

`synced` counts:

- scanned means messages discovered, not files.
- inserted means unique messages indexed.
- skipped means duplicate messages.

- [x] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_email_ingestion.py -v
```

Expected: all pass.

---

### Task 5: API Integration And Live Verification

**Files:**
- Modify: `src/knowledgeqa/api/routes/kbs.py`
- Modify: `README.md`

- [x] **Step 1: Change sync route preference**

Call `sync_all` first, then `sync_documents`, then `sync_markdown`.

- [x] **Step 2: Run full tests**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: all pass.

- [x] **Step 3: Live verification**

Create a temporary folder with one `.eml` and one `.mbox` containing duplicate `Message-ID`. Sync through 8788 and confirm:

- duplicate message is indexed once;
- email body is searchable;
- result includes `source_path`;
- result includes `doc_type="email"`.

Clean up the temporary Milvus collection and SQLite rows.
