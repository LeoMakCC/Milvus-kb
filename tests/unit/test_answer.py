import json

from knowledgeqa.answer import AnswerService, build_messages
from knowledgeqa.providers.base import ChatChunk, ChatMessage, ChatResponse


class FakeRepository:
    def __init__(self) -> None:
        self.conversation = {
            "id": "conv1",
            "title": "新会话",
            "kb_ids": '["kb1"]',
            "provider_name": "fake",
            "model_name": "fake-model",
        }
        self.messages = []

    def get_conversation(self, conversation_id):
        return self.conversation if conversation_id == "conv1" else None

    def create_conversation(
        self,
        kb_ids,
        provider_name=None,
        model_name=None,
        title=None,
    ):
        self.conversation["title"] = title or "新会话"
        return self.conversation

    def update_conversation_title(self, conversation_id, title):
        self.conversation["title"] = title

    def list_messages(self, conversation_id):
        return list(self.messages)

    def add_message(self, conversation_id, role, content, citations_json=None):
        message = {
            "id": f"m{len(self.messages) + 1}",
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "citations_json": citations_json,
        }
        self.messages.append(message)
        return message


class FakeSearchService:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, kb_id, query, limit=5):
        self.calls.append((kb_id, query, limit))
        return self.hits


class FakeProvider:
    def __init__(self) -> None:
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        return ChatResponse(text="改写后的问题")

    def stream_chat(self, request):
        self.requests.append(request)
        yield ChatChunk(text="答")
        yield ChatChunk(text="案")
        yield ChatChunk(text="", done=True)


def sample_hits():
    return [
        {
            "id": 1,
            "score": 0.9,
            "text": "验收后30日内付款。",
            "source_path": "contract.md",
            "document_id": "doc1",
            "chunk_id": "chunk1",
        }
    ]


def test_build_messages_numbers_context_sources() -> None:
    messages = build_messages(
        history=[],
        hits=sample_hits(),
        query="付款条件",
    )

    assert isinstance(messages[0], ChatMessage)
    assert "[1]" in messages[-1].content
    assert "contract.md" in messages[-1].content
    assert "付款条件" in messages[-1].content


def test_no_hits_returns_fixed_answer_without_provider_call() -> None:
    repository = FakeRepository()
    provider = FakeProvider()
    service = AnswerService(
        repository=repository,
        search_service=FakeSearchService([]),
        provider=provider,
    )

    events = list(service.stream_answer(["kb1"], "没有答案的问题"))

    tokens = "".join(
        event["text"] for event in events if event["type"] == "token"
    )
    assert "没有找到足够依据" in tokens
    assert provider.requests == []
    assert repository.messages[-1]["role"] == "assistant"


def test_stream_answer_emits_tokens_and_persists_assistant_message() -> None:
    repository = FakeRepository()
    provider = FakeProvider()
    service = AnswerService(
        repository=repository,
        search_service=FakeSearchService(sample_hits()),
        provider=provider,
    )

    events = list(service.stream_answer(["kb1"], "付款条件"))

    tokens = [
        event["text"] for event in events if event["type"] == "token"
    ]
    assert tokens == ["答", "案"]
    assert events[-1]["type"] == "done"
    assert repository.messages[-1]["role"] == "assistant"
    assert repository.messages[-1]["content"] == "答案"
    assert json.loads(repository.messages[-1]["citations_json"])[0]["index"] == 1


def test_query_rewriter_is_used_for_follow_up() -> None:
    repository = FakeRepository()
    repository.messages.append(
        {"role": "user", "content": "第一轮问题"},
    )
    search = FakeSearchService(sample_hits())
    service = AnswerService(
        repository=repository,
        search_service=search,
        provider=FakeProvider(),
        query_rewriter=lambda history, query: "独立问题",
    )

    list(service.stream_answer(["kb1"], "它呢？", conversation_id="conv1"))

    assert search.calls[0][1] == "独立问题"


def test_first_question_becomes_conversation_title() -> None:
    repository = FakeRepository()
    service = AnswerService(
        repository=repository,
        search_service=FakeSearchService(sample_hits()),
        provider=FakeProvider(),
    )

    list(service.stream_answer(["kb1"], "合同里的付款条件是什么？"))

    assert repository.conversation["title"] == "合同里的付款条件是什么？"


def test_long_question_title_is_truncated_with_ellipsis() -> None:
    repository = FakeRepository()
    service = AnswerService(
        repository=repository,
        search_service=FakeSearchService(sample_hits()),
        provider=FakeProvider(),
    )

    question = "请详细说明这份合同里关于付款条件、验收标准以及违约责任的全部条款"
    list(service.stream_answer(["kb1"], question))

    title = repository.conversation["title"]
    assert title.endswith("…")
    assert len(title) <= 25
    assert question.startswith(title[:-1])


def test_existing_title_is_not_overwritten() -> None:
    repository = FakeRepository()
    repository.conversation["title"] = "旧标题"
    service = AnswerService(
        repository=repository,
        search_service=FakeSearchService(sample_hits()),
        provider=FakeProvider(),
    )

    list(service.stream_answer(["kb1"], "新问题", conversation_id="conv1"))

    assert repository.conversation["title"] == "旧标题"


def test_deleted_knowledge_base_is_skipped() -> None:
    class FlakySearchService:
        def search(self, kb_id, query, limit=5):
            if kb_id == "gone":
                raise ValueError(f"Knowledge base not found: {kb_id}")
            return sample_hits()

    repository = FakeRepository()
    service = AnswerService(
        repository=repository,
        search_service=FlakySearchService(),
        provider=FakeProvider(),
    )

    events = list(service.stream_answer(["gone", "kb1"], "付款条件"))

    retrieval = next(
        event for event in events if event["type"] == "retrieval"
    )
    assert len(retrieval["hits"]) == 1
    assert events[-1]["type"] == "done"


class FailingProvider:
    def __init__(self) -> None:
        self.requests = []

    def stream_chat(self, request):
        self.requests.append(request)
        yield ChatChunk(text="部分")
        raise RuntimeError("list index out of range")


def test_provider_failure_keeps_partial_answer_and_marks_error() -> None:
    repository = FakeRepository()
    service = AnswerService(
        repository=repository,
        search_service=FakeSearchService(sample_hits()),
        provider=FailingProvider(),
    )

    events = list(service.stream_answer(["kb1"], "付款条件"))

    errors = [event for event in events if event["type"] == "error"]
    assert errors and "模型服务调用失败" in errors[0]["message"]
    assert repository.messages[-1]["role"] == "assistant"
    assert repository.messages[-1]["content"] == "部分"


def test_provider_resolver_overrides_constructor_provider() -> None:
    repository = FakeRepository()
    resolved_provider = FakeProvider()
    service = AnswerService(
        repository=repository,
        search_service=FakeSearchService(sample_hits()),
        provider=object(),
        provider_resolver=lambda: (resolved_provider, "resolved-model"),
    )

    list(service.stream_answer(["kb1"], "付款条件"))

    assert resolved_provider.requests[0].model == "resolved-model"
