# KnowledgeQA M4A Hybrid Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add Milvus dense + BM25 hybrid retrieval with RRF and an optional rerank hook.

**Architecture:** `MilvusStore` exposes a hybrid search method using `AnnSearchRequest` and `RRFRanker`. `SearchService` uses hybrid retrieval when available and falls back to dense search. Reranking is a separate, optional interface with a no-op default.

**Tech Stack:** pymilvus 2.5, Milvus BM25 function, RRF, pytest.

---

### Task 1: Milvus Hybrid Search

**Files:**
- Modify: `src/knowledgeqa/milvus/store.py`
- Modify: `tests/unit/test_milvus_store.py`

- [x] **Step 1: Write failing test**

Assert `hybrid_search`:

```python
client.calls contains a hybrid_search call
two AnnSearchRequest objects are sent
dense request uses anns_field="vector"
sparse request uses anns_field="sparse"
ranker is RRFRanker
```

- [x] **Step 2: Implement**

```python
from pymilvus import AnnSearchRequest, RRFRanker

def hybrid_search(
    self,
    kb_id: str,
    dense_vector: list[float],
    query_text: str,
    limit: int = 20,
) -> list[dict]: ...
```

The method calls `client.hybrid_search(collection_name, reqs=[dense_req, sparse_req], ranker=RRFRanker(60), limit=limit, output_fields=[...])`.

- [x] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_milvus_store.py -v
```

---

### Task 2: Search Service Uses Hybrid Search

**Files:**
- Modify: `src/knowledgeqa/services/search.py`
- Modify: `tests/unit/test_search_service.py`

- [x] **Step 1: Write failing test**

Fake store defines `hybrid_search` and asserts it is called with the embedded query and raw query text.

- [x] **Step 2: Implement**

Prefer `store.hybrid_search(kb_id, vector, query, limit=limit)`. Fall back to `store.search(...)` when hybrid search is unavailable.

- [x] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_search_service.py -v
```

---

### Task 3: Optional Rerank Hook

**Files:**
- Create: `src/knowledgeqa/rerank.py`
- Test: `tests/unit/test_rerank.py`
- Modify: `src/knowledgeqa/services/search.py`
- Modify: `tests/unit/test_search_service.py`

- [x] **Step 1: Write failing tests**

Cover:

- `NoopReranker.rerank` returns the first `top_k` hits.
- `HttpReranker` sends query and documents to an injected HTTP client and sorts by returned score.
- `SearchService` applies reranker only when configured.
- Reranker failure falls back to the original hit order.

- [x] **Step 2: Implement**

```python
class Reranker(Protocol):
    def rerank(self, query: str, hits: list[dict], top_k: int) -> list[dict]: ...


class NoopReranker:
    def rerank(...): return hits[:top_k]


class HttpReranker:
    def __init__(self, endpoint: str, api_key: str = "", client=None): ...
```

Request:

```json
{
  "model": "rerank-model",
  "query": "...",
  "documents": ["hit text"],
  "top_n": 5
}
```

Response contract:

```json
{
  "results": [
    {"index": 2, "relevance_score": 0.91}
  ]
}
```

- [x] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_rerank.py tests/unit/test_search_service.py -v
```

---

### Task 4: Live Hybrid Verification

**Files:**
- Modify: `README.md`

- [x] **Step 1: Run all tests**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

- [x] **Step 2: Restart 8788**

- [x] **Step 3: Ingest a document containing an exact identifier and a semantic phrase**

Use:

```text
合同 HT-2024-013：验收后30日内付款。
```

Search for `HT-2024-013` and for `验收后付款`, confirming both return the same source.

- [x] **Step 4: Clean up the temporary collection and SQLite rows.**
