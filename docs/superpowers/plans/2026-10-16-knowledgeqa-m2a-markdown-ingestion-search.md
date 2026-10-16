# KnowledgeQA M2A Markdown Ingestion And Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add the first vertical slice: create a knowledge base, ingest Markdown files, generate local embeddings, write vectors to Milvus, and return dense retrieval results.

**Architecture:** Keep parsing, chunking, embedding, persistence, and retrieval as separate modules with small interfaces. SQLite remains the authoritative metadata store. Milvus operations go through a store adapter. Services are injected into FastAPI so unit tests use fakes and do not require Docker or model downloads.

**Tech Stack:** Python 3.12, pymilvus 2.5, fastembed, sqlite3, FastAPI, pytest.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/knowledgeqa/ingestion/models.py` | `ParsedDocument`, `DocumentChunk`, `SyncResult` |
| `src/knowledgeqa/parsers/markdown.py` | Markdown file parser |
| `src/knowledgeqa/ingestion/chunking.py` | Markdown-aware chunking |
| `src/knowledgeqa/embedding.py` | Embedder protocol and FastEmbed implementation |
| `src/knowledgeqa/repository.py` | SQLite knowledge base and document persistence |
| `src/knowledgeqa/milvus/store.py` | Milvus collection, insert, delete, search |
| `src/knowledgeqa/services/ingestion.py` | Markdown sync orchestration |
| `src/knowledgeqa/services/search.py` | Query embedding and dense retrieval |
| `src/knowledgeqa/api/routes/kbs.py` | Knowledge base and sync endpoints |
| `src/knowledgeqa/api/routes/search.py` | Search endpoint |

---

### Task 1: Align pymilvus and Auto ID

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/knowledgeqa/milvus/schema.py`
- Modify: `tests/unit/test_milvus_schema.py`

- [x] **Step 1: Update the schema test to require auto_id**

Add:

```python
assert client.schema_kwargs["auto_id"] is True
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_milvus_schema.py -v
```

Expected: FAIL because `auto_id` is currently `False`.

- [x] **Step 3: Pin pymilvus to 2.5 and enable auto_id**

In `pyproject.toml`, change:

```toml
  "pymilvus>=2.5,<2.6",
```

In `src/knowledgeqa/milvus/schema.py`, change:

```python
schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
```

- [x] **Step 4: Reinstall and run**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/unit/test_milvus_schema.py -v
```

Expected: 2 passed.

---

### Task 2: Markdown Parser And Chunker

**Files:**
- Create: `src/knowledgeqa/ingestion/__init__.py`
- Create: `src/knowledgeqa/ingestion/models.py`
- Create: `src/knowledgeqa/parsers/__init__.py`
- Create: `src/knowledgeqa/parsers/markdown.py`
- Create: `src/knowledgeqa/ingestion/chunking.py`
- Test: `tests/unit/test_markdown_ingestion.py`

- [x] **Step 1: Write the failing tests**

Test behavior:

```python
def test_markdown_parser_uses_first_h1_as_title(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# 合同说明\n\n付款条件...", encoding="utf-8")
    document = parse_markdown(path)
    assert document.title == "合同说明"
    assert document.text.startswith("# 合同说明")


def test_chunker_splits_long_markdown_and_preserves_section():
    document = ParsedDocument(
        title="doc",
        text="# A\n" + "甲" * 1200 + "\n# B\n" + "乙" * 1200,
    )
    chunks = chunk_document(document, max_chars=500, overlap=80)
    assert len(chunks) >= 4
    assert chunks[0].section == "# A"
    assert chunks[-1].section == "# B"
```

- [x] **Step 2: Run tests to verify they fail**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_markdown_ingestion.py -v
```

Expected: import failures for `knowledgeqa.parsers.markdown`.

- [x] **Step 3: Implement minimal models, parser, and chunker**

Interfaces:

```python
@dataclass(frozen=True)
class ParsedDocument:
    title: str
    text: str
    doc_type: str = "markdown"


@dataclass(frozen=True)
class DocumentChunk:
    chunk_index: int
    text: str
    section: str | None = None


def parse_markdown(path: Path) -> ParsedDocument: ...


def chunk_document(
    document: ParsedDocument,
    max_chars: int = 1000,
    overlap: int = 120,
) -> list[DocumentChunk]: ...
```

- [x] **Step 4: Run tests to verify they pass**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_markdown_ingestion.py -v
```

Expected: 2 passed.

---

### Task 3: Embedding Adapter

**Files:**
- Modify: `pyproject.toml`
- Create: `src/knowledgeqa/embedding.py`
- Test: `tests/unit/test_embedding.py`

- [x] **Step 1: Write the failing test**

Use a fake backend:

```python
class FakeBackend:
    def embed(self, texts, batch_size):
        return [[float(len(text)), 1.0] for text in texts]


def test_fastembed_embedder_uses_injected_backend():
    embedder = FastEmbedEmbedder(backend=FakeBackend())
    vectors = embedder.embed(["abc", "de"])
    assert vectors == [[3.0, 1.0], [2.0, 1.0]]
```

- [x] **Step 2: Run test to verify it fails**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_embedding.py -v
```

Expected: `ModuleNotFoundError`.

- [x] **Step 3: Implement adapter**

Add dependency:

```toml
  "fastembed>=0.4,<1",
```

Implementation:

```python
class FastEmbedEmbedder:
    def __init__(self, model_name="BAAI/bge-small-zh-v1.5", backend=None):
        self._model_name = model_name
        self._backend = backend

    def _get_backend(self):
        if self._backend is None:
            from fastembed import TextEmbedding
            self._backend = TextEmbedding(self._model_name)
        return self._backend

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._get_backend().embed(texts, batch_size=64)
        return [vector.tolist() for vector in vectors]
```

- [x] **Step 4: Run test to verify it passes**

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/unit/test_embedding.py -v
```

Expected: 1 passed.

---

### Task 4: SQLite Repository

**Files:**
- Create: `src/knowledgeqa/repository.py`
- Test: `tests/unit/test_repository.py`

- [x] **Step 1: Write failing tests**

Cover:

```python
def test_create_and_list_knowledge_base(tmp_path):
    repo = Repository(tmp_path / "meta.db")
    repo.initialize()
    kb = repo.create_knowledge_base(name="项目A", dimension=512)
    assert repo.list_knowledge_bases()[0]["id"] == kb["id"]


def test_upsert_document_and_replace_chunks(tmp_path):
    repo = Repository(tmp_path / "meta.db")
    repo.initialize()
    kb = repo.create_knowledge_base(name="项目A", dimension=512)
    document = repo.upsert_document(
        kb_id=kb["id"],
        canonical_path="a.md",
        file_name="a.md",
        doc_type="markdown",
        source_type="local_file",
        source_hash="hash",
        index_status="indexed",
    )
    repo.replace_chunks(document["id"], [{"chunk_index": 0, "chunk_hash": "c1", "milvus_id": 1}])
    assert repo.list_documents(kb["id"])[0]["file_name"] == "a.md"
```

- [x] **Step 2: Run tests to verify they fail**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_repository.py -v
```

Expected: `ModuleNotFoundError`.

- [x] **Step 3: Implement repository**

Methods:

```python
class Repository:
    def initialize(self) -> None: ...
    def create_knowledge_base(self, name: str, dimension: int, embedding_model: str = "BAAI/bge-small-zh-v1.5") -> dict: ...
    def list_knowledge_bases(self) -> list[dict]: ...
    def get_knowledge_base(self, kb_id: str) -> dict | None: ...
    def get_document_by_path(self, kb_id: str, canonical_path: str) -> dict | None: ...
    def upsert_document(self, **fields) -> dict: ...
    def replace_chunks(self, document_id: str, chunks: list[dict]) -> None: ...
    def list_documents(self, kb_id: str) -> list[dict]: ...
```

Use UUID4 strings for business IDs and UTC ISO timestamps.

- [x] **Step 4: Run tests to verify they pass**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_repository.py -v
```

Expected: 2 passed.

---

### Task 5: Milvus Store Adapter

**Files:**
- Create: `src/knowledgeqa/milvus/store.py`
- Test: `tests/unit/test_milvus_store.py`

- [x] **Step 1: Write failing tests**

Cover:

- `ensure_collection` calls `has_collection` then `create_knowledge_base_collection`.
- `delete_document` calls delete with `document_id == "doc-1"`.
- `insert_chunks` calls insert and returns primary keys.
- `search` calls client.search with `COSINE` and returns dictionaries.

- [x] **Step 2: Run tests to verify they fail**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_milvus_store.py -v
```

Expected: `ModuleNotFoundError`.

- [x] **Step 3: Implement store**

Interface:

```python
class MilvusStore:
    def __init__(self, uri: str, client=None): ...
    def ensure_collection(self, kb_id: str, dimension: int) -> None: ...
    def delete_document(self, kb_id: str, document_id: str) -> None: ...
    def insert_chunks(self, kb_id: str, rows: list[dict]) -> list[int]: ...
    def search(self, kb_id: str, vector: list[float], limit: int = 5) -> list[dict]: ...
```

Search output fields:

```python
["text", "document_id", "chunk_id", "page_no", "doc_type", "source_type"]
```

- [x] **Step 4: Run tests to verify they pass**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_milvus_store.py -v
```

Expected: all tests pass.

---

### Task 6: Ingestion And Search Services

**Files:**
- Create: `src/knowledgeqa/services/__init__.py`
- Create: `src/knowledgeqa/services/ingestion.py`
- Create: `src/knowledgeqa/services/search.py`
- Test: `tests/unit/test_ingestion_service.py`
- Test: `tests/unit/test_search_service.py`

- [x] **Step 1: Write failing ingestion test**

Use fake repository, embedder, and Milvus store. Assert:

- new Markdown file is parsed, chunked, embedded, inserted, and saved;
- unchanged file is skipped;
- return value counts inserted and skipped files.

- [x] **Step 2: Write failing search test**

Use fake repository, embedder, and Milvus store. Assert:

- query is embedded;
- Milvus search is called with the selected KB;
- hits are returned unchanged.

- [x] **Step 3: Run tests to verify they fail**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ingestion_service.py tests/unit/test_search_service.py -v
```

Expected: import failures.

- [x] **Step 4: Implement services**

Interfaces:

```python
class IngestionService:
    def sync_markdown(self, kb_id: str, directory: Path) -> SyncResult: ...


class SearchService:
    def search(self, kb_id: str, query: str, limit: int = 5) -> list[dict]: ...
```

- [x] **Step 5: Run tests to verify they pass**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ingestion_service.py tests/unit/test_search_service.py -v
```

Expected: all tests pass.

---

### Task 7: API and Desktop Wiring

**Files:**
- Create: `src/knowledgeqa/api/routes/kbs.py`
- Create: `src/knowledgeqa/api/routes/search.py`
- Modify: `src/knowledgeqa/api/app.py`
- Modify: `src/knowledgeqa/desktop.py`
- Create: `tests/integration/test_kb_api.py`

- [x] **Step 1: Write failing API tests**

Cover:

- `GET /api/v1/kbs` returns an empty list.
- `POST /api/v1/kbs` creates a knowledge base.
- `POST /api/v1/kbs/{id}/sync` calls the injected ingestion service.
- `POST /api/v1/search` calls the injected search service.

- [x] **Step 2: Run tests to verify they fail**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_kb_api.py -v
```

Expected: 404 for new endpoints.

- [x] **Step 3: Implement routers and app wiring**

Extend `create_app` with optional service parameters:

```python
def create_app(
    settings,
    paths,
    status_provider,
    kb_service=None,
    search_service=None,
) -> FastAPI: ...
```

Only include KB and search routers when the services are provided.

- [x] **Step 4: Wire desktop**

Desktop creates:

```python
repository = Repository(paths.db_path)
embedder = FastEmbedEmbedder()
milvus_store = MilvusStore(settings.milvus_uri)
ingestion_service = IngestionService(repository, embedder, milvus_store)
search_service = SearchService(repository, embedder, milvus_store)
```

Pass them into `create_app`.

- [x] **Step 5: Run all tests**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: all tests pass.

---

## Self-Review

### Spec Coverage

- Markdown parsing: Task 2.
- Chunking: Task 2.
- Local embedding: Task 3.
- SQLite metadata persistence: Task 4.
- Milvus insert/delete/search: Task 5.
- Incremental sync: Task 6.
- Dense retrieval: Task 6.
- API and desktop wiring: Task 7.

### Deferred

- BM25 and hybrid search.
- Multi-format parsing.
- Background jobs and cancellation.
- File deletion and missing-file cleanup.
- Full UI pages.
- Rerank and LLM answer generation.
