import asyncio

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings
from knowledgeqa.ingestion.models import SyncResult


class FakeRepository:
    def __init__(self) -> None:
        self.items = []
        self.created = []

    def list_knowledge_bases(self):
        return self.items

    def create_knowledge_base(self, name: str, dimension: int):
        item = {"id": f"kb{len(self.items) + 1}", "name": name, "dimension": dimension}
        self.created.append(item)
        self.items.append(item)
        return item


class FakeIngestionService:
    def __init__(self) -> None:
        self.calls = []

    def sync_documents(self, kb_id: str, directory):
        self.calls.append((kb_id, str(directory)))
        return SyncResult(scanned=2, inserted=1, skipped=1, failed=0)

    def sync_markdown(self, kb_id: str, directory):
        raise AssertionError("sync_markdown should not be called when sync_documents exists")


class FakeSearchService:
    def __init__(self) -> None:
        self.calls = []

    def search(self, kb_id: str, query: str, limit: int = 5):
        self.calls.append((kb_id, query, limit))
        return [{"id": 1, "score": 0.9, "text": "付款条件"}]


async def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def make_app(portable_root, repository=None, ingestion_service=None, search_service=None):
    return create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=lambda: {"milvus": "disconnected"},
        repository=repository,
        ingestion_service=ingestion_service,
        search_service=search_service,
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
    }
    assert ingestion.calls == [("kb1", "D:\\docs")]


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
