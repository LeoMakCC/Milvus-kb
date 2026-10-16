import json

from knowledgeqa.providers.base import ChatMessage, ChatRequest
from knowledgeqa.providers.azure import AzureOpenAIProvider
from knowledgeqa.providers.openai_compatible import OpenAICompatibleProvider


class FakeResponse:
    def __init__(self, payload=None, lines=None) -> None:
        self._payload = payload
        self._lines = lines or []

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._payload

    def iter_lines(self):
        return iter(self._lines)


class FakeStreamContext:
    def __init__(self, response) -> None:
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeClient:
    def __init__(self, response) -> None:
        self.response = response
        self.calls = []

    def post(self, url, headers, json, timeout):
        self.calls.append(("post", url, headers, json, timeout))
        return self.response

    def stream(self, method, url, headers, json, timeout):
        self.calls.append(("stream", method, url, headers, json, timeout))
        return FakeStreamContext(self.response)


def request() -> ChatRequest:
    return ChatRequest(messages=[ChatMessage(role="user", content="问题")])


def test_openai_compatible_chat_parses_response() -> None:
    client = FakeClient(
        FakeResponse(
            payload={
                "choices": [{"message": {"content": "回答"}}],
                "usage": {"total_tokens": 12},
            }
        )
    )
    provider = OpenAICompatibleProvider(
        base_url="https://api.example/v1",
        api_key="sk-test",
        model="test-model",
        client=client,
    )

    result = provider.chat(request())

    assert result.text == "回答"
    assert result.usage == {"total_tokens": 12}
    call = client.calls[0]
    assert call[1] == "https://api.example/v1/chat/completions"
    assert call[2]["Authorization"] == "Bearer sk-test"
    assert call[3]["model"] == "test-model"
    assert call[3]["stream"] is False


def test_openai_compatible_stream_parses_sse() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"你"}}]}',
        'data: {"choices":[{"delta":{"content":"好"}}]}',
        "data: [DONE]",
    ]
    client = FakeClient(FakeResponse(lines=lines))
    provider = OpenAICompatibleProvider(
        base_url="https://api.example/v1",
        api_key="sk-test",
        model="test-model",
        client=client,
    )

    chunks = list(provider.stream_chat(request()))

    assert [chunk.text for chunk in chunks if not chunk.done] == ["你", "好"]
    assert chunks[-1].done is True
    call = client.calls[0]
    assert call[0] == "stream"
    assert call[4]["stream"] is True


def test_azure_provider_builds_deployment_url_and_api_key_header() -> None:
    client = FakeClient(
        FakeResponse(
            payload={"choices": [{"message": {"content": "Azure 回答"}}]}
        )
    )
    provider = AzureOpenAIProvider(
        endpoint="https://example.openai.azure.com",
        deployment="knowledge-chat",
        api_version="2024-02-15-preview",
        api_key="azure-key",
        client=client,
    )

    result = provider.chat(request())

    assert result.text == "Azure 回答"
    call = client.calls[0]
    assert call[1] == (
        "https://example.openai.azure.com/openai/deployments/"
        "knowledge-chat/chat/completions?api-version=2024-02-15-preview"
    )
    assert call[2]["api-key"] == "azure-key"
    assert "Authorization" not in call[2]
