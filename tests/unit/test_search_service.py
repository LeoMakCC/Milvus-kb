from knowledgeqa.services.search import SearchService, merge_chunks


class FakeRepository:
    def get_knowledge_base(self, kb_id: str):
        return {"id": kb_id} if kb_id == "kb1" else None


class FakeEmbedder:
    def __init__(self) -> None:
        self.inputs = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.inputs.append(texts)
        return [[0.1, 0.2]]


class FakeMilvusStore:
    def __init__(self) -> None:
        self.calls = []

    def hybrid_search(
        self,
        kb_id: str,
        dense_vector: list[float],
        query_text: str,
        limit: int = 20,
    ):
        self.calls.append(("hybrid", kb_id, dense_vector, query_text, limit))
        return [
            {"id": 1, "score": 0.9, "text": "付款条件"},
            {"id": 2, "score": 0.8, "text": "第二结果"},
        ]

    def search(self, kb_id: str, vector: list[float], limit: int = 5):
        self.calls.append(("dense", kb_id, vector, limit))
        return [{"id": 2, "score": 0.8, "text": "稠密结果"}]


class DenseOnlyStore:
    def __init__(self) -> None:
        self.calls = []

    def search(self, kb_id: str, vector: list[float], limit: int = 5):
        self.calls.append((kb_id, vector, limit))
        return [{"id": 2, "score": 0.8, "text": "稠密结果"}]


def test_search_embeds_query_and_delegates_to_milvus() -> None:
    repository = FakeRepository()
    embedder = FakeEmbedder()
    store = FakeMilvusStore()
    service = SearchService(repository, embedder, store)

    hits = service.search("kb1", "付款条件", limit=3)

    assert hits[0] == {"id": 1, "score": 0.9, "text": "付款条件"}
    assert embedder.inputs == [["付款条件"]]
    assert store.calls == [("hybrid", "kb1", [0.1, 0.2], "付款条件", 3)]


def test_search_falls_back_to_dense_when_hybrid_is_unavailable() -> None:
    store = DenseOnlyStore()
    service = SearchService(FakeRepository(), FakeEmbedder(), store)

    hits = service.search("kb1", "付款条件", limit=3)

    assert hits == [{"id": 2, "score": 0.8, "text": "稠密结果"}]
    assert store.calls == [("kb1", [0.1, 0.2], 3)]


class ReversingReranker:
    def rerank(self, query: str, hits: list[dict], top_k: int):
        return list(reversed(hits))[:top_k]


class FailingReranker:
    def rerank(self, query: str, hits: list[dict], top_k: int):
        raise RuntimeError("rerank failed")


def test_search_applies_reranker_when_configured() -> None:
    service = SearchService(
        FakeRepository(),
        FakeEmbedder(),
        FakeMilvusStore(),
        reranker=ReversingReranker(),
    )

    hits = service.search("kb1", "付款条件", limit=1)

    assert hits == [{"id": 2, "score": 0.8, "text": "第二结果"}]


def test_search_falls_back_when_reranker_fails() -> None:
    service = SearchService(
        FakeRepository(),
        FakeEmbedder(),
        FakeMilvusStore(),
        reranker=FailingReranker(),
    )

    hits = service.search("kb1", "付款条件", limit=1)

    assert hits == [{"id": 1, "score": 0.9, "text": "付款条件"}]


class ChunkStore(FakeMilvusStore):
    def __init__(self) -> None:
        super().__init__()
        self.chunk_calls: list[list[str]] = []
        self.rows = {
            "doc1:0": {
                "chunk_id": "doc1:0",
                "text": "# 付款条件\n验收后30日内付款。",
                "page_no": -1,
            },
            "doc1:1": {
                "chunk_id": "doc1:1",
                "text": "# 付款条件\n逾期按日万分之五计息。",
                "page_no": -1,
            },
            "doc1:2": {
                "chunk_id": "doc1:2",
                "text": "# 付款条件\n验收标准见附件。",
                "page_no": -1,
            },
        }

    def hybrid_search(self, kb_id, dense_vector, query_text, limit=20):
        self.calls.append(("hybrid", kb_id, dense_vector, query_text, limit))
        return [
            {
                "id": 1,
                "score": 0.9,
                "chunk_id": "doc1:1",
                "text": "# 付款条件\n逾期按日万分之五计息。",
            }
        ]

    def chunks_by_ids(self, kb_id: str, chunk_ids: list[str]):
        self.chunk_calls.append(list(chunk_ids))
        return [self.rows[item] for item in chunk_ids if item in self.rows]


def test_search_expands_context_with_neighbor_chunks() -> None:
    store = ChunkStore()
    service = SearchService(
        FakeRepository(),
        FakeEmbedder(),
        store,
        context_window=1,
    )

    hits = service.search("kb1", "逾期", limit=3, expand_context=True)

    hit = hits[0]
    assert hit["chunk_span"] == [0, 2]
    assert "验收后30日内付款" in hit["text"]
    assert "逾期按日万分之五计息" in hit["text"]
    assert "验收标准见附件" in hit["text"]
    assert hit["text"].count("# 付款条件") == 1
    assert store.chunk_calls == [["doc1:0", "doc1:1", "doc1:2"]]


def test_search_without_expand_keeps_single_chunk() -> None:
    store = ChunkStore()
    service = SearchService(FakeRepository(), FakeEmbedder(), store)

    hits = service.search("kb1", "逾期", limit=3)

    assert store.chunk_calls == []
    assert "chunk_span" not in hits[0]
    assert hits[0]["text"] == "# 付款条件\n逾期按日万分之五计息。"


class OverlappingStore(ChunkStore):
    def hybrid_search(self, kb_id, dense_vector, query_text, limit=20):
        return [
            {
                "id": 1,
                "score": 0.9,
                "document_id": "doc1",
                "chunk_id": "doc1:0",
                "text": "# 付款条件\n验收后30日内付款。",
            },
            {
                "id": 2,
                "score": 0.8,
                "document_id": "doc1",
                "chunk_id": "doc1:1",
                "text": "# 付款条件\n逾期按日万分之五计息。",
            },
        ]


def test_overlapping_hits_are_merged_into_one() -> None:
    store = OverlappingStore()
    service = SearchService(
        FakeRepository(),
        FakeEmbedder(),
        store,
        context_window=1,
    )

    hits = service.search("kb1", "付款", limit=5, expand_context=True)

    assert len(hits) == 1
    hit = hits[0]
    assert hit["chunk_span"] == [0, 2]
    assert hit["merged_count"] == 2
    assert "验收标准见附件" in hit["text"]
    assert hit["text"].count("# 付款条件") == 1


def test_merge_respects_max_chunk_limit() -> None:
    store = OverlappingStore()
    service = SearchService(
        FakeRepository(),
        FakeEmbedder(),
        store,
        context_window=1,
        max_merged_chunks=2,
    )

    hits = service.search("kb1", "付款", limit=5, expand_context=True)

    assert len(hits) == 2


def test_merge_chunks_removes_overlap() -> None:
    assert merge_chunks(["一二三四五六", "五六七八九十"]) == "一二三四五六七八九十"
