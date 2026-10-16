from pathlib import Path

from knowledgeqa.services.ingestion import IngestionService


class FakeRepository:
    def __init__(self) -> None:
        self.knowledge_base = {"id": "kb1", "dimension": 2}
        self.documents_by_path = {}
        self.chunks = {}
        self.next_document = 1

    def get_knowledge_base(self, kb_id: str):
        return self.knowledge_base if kb_id == "kb1" else None

    def get_document_by_path(self, kb_id: str, canonical_path: str):
        return self.documents_by_path.get(canonical_path)

    def upsert_document(self, **fields):
        path = fields["canonical_path"]
        existing = self.documents_by_path.get(path)
        document = dict(existing or {})
        document.update(fields)
        document["id"] = existing["id"] if existing else f"doc{self.next_document}"
        if not existing:
            self.next_document += 1
        self.documents_by_path[path] = document
        return document

    def replace_chunks(self, document_id: str, chunks: list[dict]) -> None:
        self.chunks[document_id] = chunks


class FakeEmbedder:
    def __init__(self) -> None:
        self.inputs = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.inputs.append(texts)
        return [[float(len(text)), 1.0] for text in texts]


class FakeMilvusStore:
    def __init__(self) -> None:
        self.ensured = []
        self.deleted = []
        self.inserted = []

    def ensure_collection(self, kb_id: str, dimension: int) -> None:
        self.ensured.append((kb_id, dimension))

    def delete_document(self, kb_id: str, document_id: str) -> None:
        self.deleted.append((kb_id, document_id))

    def insert_chunks(self, kb_id: str, rows: list[dict]) -> list[int]:
        self.inserted.append((kb_id, rows))
        return list(range(1, len(rows) + 1))

    def search(self, kb_id, vector, limit=5):
        return []


def test_sync_markdown_inserts_new_file_then_skips_unchanged(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# A\n付款条件", encoding="utf-8")
    repository = FakeRepository()
    embedder = FakeEmbedder()
    store = FakeMilvusStore()
    service = IngestionService(repository, embedder, store)

    first = service.sync_markdown("kb1", tmp_path)
    second = service.sync_markdown("kb1", tmp_path)

    assert first.scanned == 1
    assert first.inserted == 1
    assert first.skipped == 0
    assert second.inserted == 0
    assert second.skipped == 1
    assert store.ensured == [("kb1", 2)]
    assert len(store.inserted) == 1
    assert store.inserted[0][1][0]["page_no"] == -1
    assert store.inserted[0][1][0]["source_path"] == "a.md"
    assert repository.chunks["doc1"][0]["milvus_id"] == 1


def test_sync_documents_ingests_supported_formats(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# A\nMarkdown", encoding="utf-8")
    (tmp_path / "b.txt").write_text("Plain text", encoding="utf-8")
    repository = FakeRepository()
    embedder = FakeEmbedder()
    store = FakeMilvusStore()
    service = IngestionService(repository, embedder, store)

    result = service.sync_documents("kb1", tmp_path)

    assert result.scanned == 2
    assert result.inserted == 2
    inserted_types = {
        row["doc_type"]
        for _, rows in store.inserted
        for row in rows
    }
    assert inserted_types == {"markdown", "txt"}
