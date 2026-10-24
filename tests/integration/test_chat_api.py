import asyncio

import httpx

from knowledgeqa.api.app import create_app
from knowledgeqa.config import AppPaths, Settings


class FakeRepository:
    def __init__(self) -> None:
        self.archived: dict[str, bool] = {}

    def list_conversations(self, only_archived: bool = False):
        if only_archived:
            return (
                [{"id": "conv1", "title": "已归档"}]
                if self.archived.get("conv1")
                else []
            )
        return (
            []
            if self.archived.get("conv1")
            else [{"id": "conv1", "title": "新会话"}]
        )

    def set_conversation_archived(
        self,
        conversation_id: str,
        archived: bool,
    ):
        if conversation_id != "conv1":
            return None
        self.archived[conversation_id] = archived
        return {"id": conversation_id}

    def get_conversation(self, conversation_id: str):
        if conversation_id == "conv1":
            return {"id": "conv1", "title": "新会话"}
        return None

    def list_messages(self, conversation_id: str):
        return [{"id": "m1", "role": "user", "content": "问题"}]


class FakeAnswerService:
    def stream_answer(self, kb_ids, query, conversation_id=None):
        yield {"type": "status", "message": "正在检索"}
        yield {
            "type": "retrieval",
            "hits": [{"id": 1, "text": "片段", "source_path": "a.md"}],
        }
        yield {"type": "token", "text": "答"}
        yield {"type": "token", "text": "案"}
        yield {
            "type": "done",
            "conversation_id": "conv1",
            "message_id": "m2",
        }


async def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def make_app(portable_root, answer_service=None, repository=None):
    return create_app(
        settings=Settings(),
        paths=AppPaths(portable_root=portable_root),
        status_provider=lambda: {"milvus": "disconnected"},
        repository=repository,
        answer_service=answer_service,
    )


def test_chat_stream_returns_sse_events(portable_root) -> None:
    app = make_app(
        portable_root,
        answer_service=FakeAnswerService(),
        repository=FakeRepository(),
    )

    response = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/chat/stream",
            json={"kb_ids": ["kb1"], "query": "付款条件"},
        )
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: retrieval" in response.text
    assert "event: token" in response.text
    assert '"text": "答"' in response.text
    assert "event: done" in response.text


def test_conversation_endpoints(portable_root) -> None:
    app = make_app(
        portable_root,
        answer_service=FakeAnswerService(),
        repository=FakeRepository(),
    )

    listed = asyncio.run(request(app, "GET", "/api/v1/conversations"))
    detail = asyncio.run(
        request(app, "GET", "/api/v1/conversations/conv1")
    )

    assert listed.json()[0]["id"] == "conv1"
    assert detail.json()["conversation"]["id"] == "conv1"
    assert detail.json()["messages"][0]["content"] == "问题"


def test_archive_and_unarchive_conversation(portable_root) -> None:
    repository = FakeRepository()
    app = make_app(
        portable_root,
        answer_service=FakeAnswerService(),
        repository=repository,
    )

    archived = asyncio.run(
        request(app, "POST", "/api/v1/conversations/conv1/archive")
    )
    assert archived.json() == {"ok": True, "archived": True}
    assert repository.archived["conv1"] is True

    active_list = asyncio.run(request(app, "GET", "/api/v1/conversations"))
    assert active_list.json() == []

    archived_list = asyncio.run(
        request(app, "GET", "/api/v1/conversations?archived=true")
    )
    assert archived_list.json()[0]["id"] == "conv1"

    restored = asyncio.run(
        request(app, "POST", "/api/v1/conversations/conv1/unarchive")
    )
    assert restored.json() == {"ok": True, "archived": False}
    assert repository.archived["conv1"] is False


def test_archive_unknown_conversation_returns_404(portable_root) -> None:
    app = make_app(
        portable_root,
        answer_service=FakeAnswerService(),
        repository=FakeRepository(),
    )

    response = asyncio.run(
        request(app, "POST", "/api/v1/conversations/missing/archive")
    )

    assert response.status_code == 404
