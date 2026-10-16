from knowledgeqa.milvus import store as store_module
from knowledgeqa.milvus.store import MilvusStore


class FakeMilvusClient:
    def __init__(self) -> None:
        self.calls = []
        self.collections = {"kb_abc"}

    def has_collection(self, name: str) -> bool:
        self.calls.append(("has_collection", name))
        return name in self.collections

    def delete(self, name: str, filter: str):
        self.calls.append(("delete", name, filter))
        return {"delete_count": 1}

    def insert(self, name: str, rows: list[dict]):
        self.calls.append(("insert", name, rows))
        return {"ids": [101, 102]}

    def load_collection(self, name: str) -> None:
        self.calls.append(("load_collection", name))

    def search(self, name, data, limit, output_fields, search_params):
        self.calls.append(
            ("search", name, data, limit, output_fields, search_params)
        )
        return [
            [
                {
                    "id": 101,
                    "distance": 0.91,
                    "entity": {
                        "text": "付款条件",
                        "document_id": "doc-1",
                        "chunk_id": "chunk-1",
                        "page_no": None,
                        "doc_type": "markdown",
                        "source_type": "local_file",
                    },
                }
            ]
        ]

    def list_collections(self):
        self.calls.append(("list_collections",))
        return list(self.collections)


def test_ensure_collection_creates_missing_collection(monkeypatch) -> None:
    client = FakeMilvusClient()
    client.collections.clear()
    created = []
    monkeypatch.setattr(
        store_module,
        "create_knowledge_base_collection",
        lambda client, kb_id, dimension: created.append((kb_id, dimension)),
    )
    store = MilvusStore("http://localhost:19530", client=client)

    store.ensure_collection("abc", 512)

    assert created == [("abc", 512)]


def test_delete_document_uses_document_filter() -> None:
    client = FakeMilvusClient()
    store = MilvusStore("http://localhost:19530", client=client)

    store.delete_document("abc", "doc-1")

    assert ("delete", "kb_abc", 'document_id == "doc-1"') in client.calls


def test_insert_chunks_returns_primary_keys() -> None:
    client = FakeMilvusClient()
    store = MilvusStore("http://localhost:19530", client=client)

    ids = store.insert_chunks("abc", [{"vector": [1.0], "text": "x"}])

    assert ids == [101, 102]


def test_search_returns_normalized_hits() -> None:
    client = FakeMilvusClient()
    store = MilvusStore("http://localhost:19530", client=client)

    hits = store.search("abc", [0.1, 0.2], limit=3)

    assert hits == [
        {
            "id": 101,
            "score": 0.91,
            "text": "付款条件",
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "page_no": None,
            "doc_type": "markdown",
            "source_type": "local_file",
        }
    ]
    search_call = next(call for call in client.calls if call[0] == "search")
    assert search_call[3] == 3
