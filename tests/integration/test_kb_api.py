import asyncio

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.ingestion.models import FileSyncResult, SyncResult


class FakeRepository:
    def __init__(self) -> None:
        self.items = []
        self.created = []
        self.documents = []
        self.deleted = []

    def delete_knowledge_base(self, kb_id: str) -> bool:
        self.deleted.append(kb_id)
        return True

    def list_knowledge_bases(self):
        return self.items

    def get_knowledge_base(self, kb_id: str):
        return next(
            (item for item in self.items if item["id"] == kb_id),
            None,
        )

    def list_documents_with_chunk_counts(self, kb_id: str):
        return self.documents

    def create_knowledge_base(self, name: str, dimension: int):
        item = {"id": f"kb{len(self.items) + 1}", "name": name, "dimension": dimension}
        self.created.append(item)
        self.items.append(item)
        return item

    def list_email_thread(self, kb_id: str, thread_id: str):
        return [
            {
                "message_id": "<one@example.com>",
                "thread_id": thread_id,
                "subject": "付款条件",
            }
        ]


class FakeIngestionService:
    def __init__(self) -> None:
        self.calls = []

    def sync_documents(self, kb_id: str, directory):
        self.calls.append((kb_id, str(directory)))
        return SyncResult(scanned=2, inserted=1, skipped=1, failed=0)

    def sync_markdown(self, kb_id: str, directory):
        raise AssertionError("sync_markdown should not be called when sync_documents exists")

    def sync_files(self, kb_id: str, paths):
        self.calls.append((kb_id, [str(path) for path in paths]))
        return FileSyncResult(
            scanned=len(paths),
            inserted=len(paths),
            skipped=0,
            failed=0,
            errors=[],
        )


class FakeSearchService:
    def __init__(self) -> None:
        self.calls = []

    def search(
        self,
        kb_id: str,
        query: str,
        limit: int = 5,
        expand_context: bool = False,
    ):
        self.calls.append((kb_id, query, limit))
        return [{"id": 1, "score": 0.9, "text": "付款条件"}]


async def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def make_app(
    portable_root,
    repository=None,
    ingestion_service=None,
    search_service=None,
    milvus_store=None,
):
    return create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=lambda: {"milvus": "disconnected"},
        repository=repository,
        ingestion_service=ingestion_service,
        search_service=search_service,
        milvus_store=milvus_store,
    )


def test_kb_routes_are_absent_without_services(portable_root) -> None:
    app = make_app(portable_root)

    response = asyncio.run(request(app, "GET", "/api/v1/kbs"))

    assert response.status_code == 404


def test_create_and_list_knowledge_base(portable_root) -> None:
    repository = FakeRepository()
    app = make_app(portable_root, repository=repository)

    created = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/kbs",
            json={"name": "项目A", "dimension": 512},
        )
    )
    listed = asyncio.run(request(app, "GET", "/api/v1/kbs"))

    assert created.status_code == 200
    assert created.json()["name"] == "项目A"
    assert listed.json() == [created.json()]


def test_delete_knowledge_base_drops_collection(portable_root) -> None:
    repository = FakeRepository()
    repository.items.append({"id": "kb1", "name": "项目A", "dimension": 512})

    class FakeMilvusStore:
        def __init__(self) -> None:
            self.dropped = []

        def drop_collection(self, kb_id: str) -> bool:
            self.dropped.append(kb_id)
            return True

    store = FakeMilvusStore()
    app = make_app(portable_root, repository, milvus_store=store)

    response = asyncio.run(request(app, "DELETE", "/api/v1/kbs/kb1"))

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "milvus_dropped": True}
    assert store.dropped == ["kb1"]
    assert repository.deleted == ["kb1"]


def test_delete_unknown_knowledge_base(portable_root) -> None:
    app = make_app(portable_root, repository=FakeRepository())

    response = asyncio.run(request(app, "DELETE", "/api/v1/kbs/missing"))

    assert response.status_code == 404


def test_list_documents_reports_status_and_chunks(portable_root) -> None:
    repository = FakeRepository()
    repository.items.append({"id": "kb1", "name": "项目A", "dimension": 512})
    repository.documents = [
        {
            "id": "d1",
            "file_name": "contract.md",
            "doc_type": "markdown",
            "source_type": "local_file",
            "index_status": "indexed",
            "chunk_count": 3,
            "size_bytes": 120,
            "indexed_at": "2026-10-22T01:00:00.000Z",
            "last_error": None,
        },
        {
            "id": "d2",
            "file_name": "scan.pdf",
            "doc_type": "pdf",
            "source_type": "local_file",
            "index_status": "failed",
            "chunk_count": 0,
            "size_bytes": 2048,
            "indexed_at": None,
            "last_error": "需要 OCR",
        },
    ]

    class FakeMilvusStore:
        def count_entities(self, kb_id: str) -> int:
            return 3

    app = make_app(portable_root, repository, milvus_store=FakeMilvusStore())

    response = asyncio.run(request(app, "GET", "/api/v1/kbs/kb1/documents"))

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {
        "documents": 2,
        "indexed": 1,
        "failed": 1,
        "chunks": 3,
        "milvus_entities": 3,
    }
    assert body["documents"][0]["file_name"] == "contract.md"
    assert body["documents"][0]["chunk_count"] == 3
    assert body["documents"][1]["last_error"] == "需要 OCR"


def test_list_documents_unknown_knowledge_base(portable_root) -> None:
    app = make_app(portable_root, repository=FakeRepository())

    response = asyncio.run(request(app, "GET", "/api/v1/kbs/missing/documents"))

    assert response.status_code == 404


def test_sync_calls_ingestion_service(portable_root) -> None:
    ingestion = FakeIngestionService()
    app = make_app(
        portable_root,
        repository=FakeRepository(),
        ingestion_service=ingestion,
    )

    response = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/kbs/kb1/sync",
            json={"directory": "D:/docs"},
        )
    )

    assert response.status_code == 200
    assert response.json() == {
        "scanned": 2,
        "inserted": 1,
        "skipped": 1,
        "failed": 0,
        "attachments_inserted": 0,
        "attachments_reused": 0,
    }
    assert ingestion.calls == [("kb1", "D:\\docs")]


def test_add_documents_calls_ingestion_service(portable_root) -> None:
    ingestion = FakeIngestionService()
    app = make_app(
        portable_root,
        repository=FakeRepository(),
        ingestion_service=ingestion,
    )

    response = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/kbs/kb1/documents",
            json={"paths": ["D:/docs/a.md", "D:/docs/b.pdf"]},
        )
    )

    assert response.status_code == 200
    assert response.json() == {
        "scanned": 2,
        "inserted": 2,
        "skipped": 0,
        "failed": 0,
        "errors": [],
    }
    assert ingestion.calls == [("kb1", ["D:\\docs\\a.md", "D:\\docs\\b.pdf"])]


def test_add_documents_rejects_empty_paths(portable_root) -> None:
    app = make_app(
        portable_root,
        repository=FakeRepository(),
        ingestion_service=FakeIngestionService(),
    )

    response = asyncio.run(
        request(app, "POST", "/api/v1/kbs/kb1/documents", json={"paths": []})
    )

    assert response.status_code == 400


def test_search_calls_search_service(portable_root) -> None:
    search = FakeSearchService()
    app = make_app(
        portable_root,
        repository=FakeRepository(),
        search_service=search,
    )

    response = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/search",
            json={"kb_id": "kb1", "query": "付款条件", "limit": 3},
        )
    )

    assert response.status_code == 200
    assert response.json()["hits"] == [
        {"id": 1, "score": 0.9, "text": "付款条件"}
    ]
    assert search.calls == [("kb1", "付款条件", 3)]


def test_email_thread_endpoint(portable_root) -> None:
    app = make_app(portable_root, repository=FakeRepository())

    response = asyncio.run(
        request(app, "GET", "/api/v1/kbs/kb1/threads/%3Cthread%40example.com%3E")
    )

    assert response.status_code == 200
    assert response.json() == {
        "thread_id": "<thread@example.com>",
        "messages": [
            {
                "message_id": "<one@example.com>",
                "thread_id": "<thread@example.com>",
                "subject": "付款条件",
            }
        ],
    }
