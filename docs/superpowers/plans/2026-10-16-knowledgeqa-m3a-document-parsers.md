# KnowledgeQA M3A Document Parsers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Extend ingestion from Markdown-only to common document formats with page and section metadata.

**Architecture:** Introduces a parser registry and a richer parsed document model with sections and page numbers. Existing Markdown/ingestion APIs remain compatible. Ingestion becomes format-agnostic through `sync_documents`.

**Tech Stack:** Python 3.12, PyMuPDF, python-docx, openpyxl, python-pptx, beautifulsoup4, pytest.

---

### Task 1: Extend Parsed Models And Chunking

**Files:**
- Modify: `src/knowledgeqa/ingestion/models.py`
- Modify: `src/knowledgeqa/ingestion/chunking.py`
- Modify: `tests/unit/test_markdown_ingestion.py`

- [x] **Step 1: Add failing assertions**

Assert `DocumentChunk.page_no` defaults to `-1`, and a parsed document with two sections produces chunks preserving each section's `page_no`.

- [x] **Step 2: Implement**

Add:

```python
@dataclass(frozen=True)
class ParsedSection:
    text: str
    section: str | None = None
    page_no: int = -1


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    text: str
    doc_type: str
    sections: list[ParsedSection] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentChunk:
    chunk_index: int
    text: str
    section: str | None = None
    page_no: int = -1
```

`chunk_document` uses `document.sections` when present, otherwise builds a synthetic section from `document.text`.

- [x] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_markdown_ingestion.py -v
```

Expected: all pass.

---

### Task 2: Parser Registry And Text-Like Parsers

**Files:**
- Create: `src/knowledgeqa/parsers/base.py`
- Create: `src/knowledgeqa/parsers/plain_text.py`
- Create: `src/knowledgeqa/parsers/html.py`
- Create: `src/knowledgeqa/parsers/csv_doc.py`
- Create: `src/knowledgeqa/parsers/registry.py`
- Test: `tests/unit/test_document_parsers.py`

- [x] **Step 1: Write failing tests**

Cover:

- `.txt` and `.py` use plain-text parser.
- `.html` strips tags and keeps text.
- `.csv` turns rows into readable lines.
- unknown extension raises `UnsupportedDocumentError`.

- [x] **Step 2: Implement parser interface**

```python
class DocumentParser(Protocol):
    extensions: set[str]

    def parse(self, path: Path) -> ParsedDocument: ...
```

Registry API:

```python
def parse_document(path: Path) -> ParsedDocument: ...
def supported_extensions() -> set[str]: ...
```

- [x] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_document_parsers.py -v
```

Expected: all pass.

---

### Task 3: PDF, DOCX, XLSX And PPTX Parsers

**Files:**
- Modify: `pyproject.toml`
- Create: `src/knowledgeqa/parsers/pdf.py`
- Create: `src/knowledgeqa/parsers/docx.py`
- Create: `src/knowledgeqa/parsers/xlsx.py`
- Create: `src/knowledgeqa/parsers/pptx.py`
- Modify: `src/knowledgeqa/parsers/registry.py`
- Test: `tests/unit/test_office_parsers.py`

- [x] **Step 1: Add dependencies**

```toml
"PyMuPDF>=1.24,<2",
"python-docx>=1.1,<2",
"openpyxl>=3.1,<4",
"python-pptx>=1.0,<2",
"beautifulsoup4>=4.12,<5",
```

- [x] **Step 2: Write failing tests**

Create temporary files in tests and assert extracted text:

- PDF page text and `page_no`.
- DOCX paragraph text.
- XLSX sheet and row text.
- PPTX slide text.
- Scanned PDF without extractable text raises `OcrRequiredError`.

- [x] **Step 3: Implement parsers**

Each parser returns a `ParsedDocument` with `sections`.

- PDF: one section per page; page number is one-based.
- DOCX: one section per paragraph group.
- XLSX: one section per sheet, rows joined as `header: value`.
- PPTX: one section per slide.

- [x] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/unit/test_office_parsers.py -v
```

Expected: all pass.

---

### Task 4: Format-Agnostic Ingestion

**Files:**
- Modify: `src/knowledgeqa/services/ingestion.py`
- Modify: `src/knowledgeqa/api/routes/kbs.py`
- Modify: `tests/unit/test_ingestion_service.py`
- Modify: `tests/integration/test_kb_api.py`

- [x] **Step 1: Write failing tests**

Assert:

- `sync_documents` ingests a `.txt` file.
- `sync_markdown` still only processes `.md`.
- chunk rows carry parser `page_no` and `doc_type`.
- API `/sync` calls `sync_documents`.

- [x] **Step 2: Implement**

`IngestionService`:

```python
def sync_documents(self, kb_id: str, directory: Path) -> SyncResult: ...
def sync_markdown(self, kb_id: str, directory: Path) -> SyncResult: ...
```

`sync_documents` walks supported extensions via `supported_extensions()`. `sync_markdown` filters `.md` only.

The sync route calls `sync_documents` when available, otherwise falls back to `sync_markdown`.

- [x] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ingestion_service.py tests/integration/test_kb_api.py -v
```

Expected: all pass.

---

### Task 5: UI And Live Verification

**Files:**
- Modify: `src/knowledgeqa/web/index.html`
- Modify: `src/knowledgeqa/web/app.js`
- Modify: `README.md`

- [x] **Step 1: Change directory field copy**

Change UI placeholder from “Markdown 目录” to “文档目录”.

- [x] **Step 2: Run full tests**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: all pass.

- [x] **Step 3: Restart 8788 and run real document ingestion**

Create a temporary folder containing one `.txt`, one `.csv`, and one `.docx` file. Use the live API to create a KB, sync the folder, and search. Confirm hits include `source_path`, `page_no`, and text.

- [x] **Step 4: Clean up temporary Milvus collection and SQLite rows**

Use the same cleanup pattern as the M2A live check.
