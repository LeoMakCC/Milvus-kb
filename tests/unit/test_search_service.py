from knowledgeqa.services.search import SearchService


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

    def search(self, kb_id: str, vector: list[float], limit: int = 5):
        self.calls.append((kb_id, vector, limit))
        return [{"id": 1, "score": 0.9, "text": "付款条件"}]


def test_search_embeds_query_and_delegates_to_milvus() -> None:
    repository = FakeRepository()
    embedder = FakeEmbedder()
    store = FakeMilvusStore()
    service = SearchService(repository, embedder, store)

    hits = service.search("kb1", "付款条件", limit=3)

    assert hits == [{"id": 1, "score": 0.9, "text": "付款条件"}]
    assert embedder.inputs == [["付款条件"]]
    assert store.calls == [("kb1", [0.1, 0.2], 3)]
