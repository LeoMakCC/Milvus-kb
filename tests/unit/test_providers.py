import json

import httpx
import pytest

from knowledgeqa.providers.base import ChatMessage, ChatRequest
from knowledgeqa.providers.azure import AzureOpenAIProvider
from knowledgeqa.providers.openai_compatible import OpenAICompatibleProvider


class FakeResponse:
    def __init__(
        self,
        payload=None,
        lines=None,
        status_code: int = 200,
        text: str = "",
    ) -> None:
        self._payload = payload
        self._lines = lines or []
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://test.local")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=request,
                response=httpx.Response(
                    self.status_code,
                    request=request,
                    text=self.text,
                ),
            )

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
    def __init__(self, response, get_response=None) -> None:
        self.response = response
        self.get_response = get_response or response
        self.calls = []

    def get(self, url, headers, timeout):
        self.calls.append(("get", url, headers, None, timeout))
        return self.get_response

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


def test_test_connection_falls_back_to_chat_when_models_missing() -> None:
    client = FakeClient(
        FakeResponse(payload={"choices": [{"message": {"content": "p"}}]}),
        get_response=FakeResponse(status_code=404, text="not found"),
    )
    provider = OpenAICompatibleProvider(
        base_url="https://api.example/v1",
        api_key="sk-test",
        model="test-model",
        client=client,
    )

    ok, message = provider.test_connection()

    assert ok is True
    assert "chat" in message
    assert [call[0] for call in client.calls] == ["get", "post"]
    assert client.calls[1][3]["max_tokens"] == 1


def test_test_connection_reports_unauthorized_reason() -> None:
    client = FakeClient(
        FakeResponse(),
        get_response=FakeResponse(
            status_code=401,
            text='{"error":"invalid api key"}',
        ),
    )
    provider = OpenAICompatibleProvider(
        base_url="https://api.example/v1",
        api_key="bad",
        model="test-model",
        client=client,
    )

    ok, message = provider.test_connection()

    assert ok is False
    assert "HTTP 401" in message
    assert "API Key" in message
    assert [call[0] for call in client.calls] == ["get"]


def test_test_connection_retries_once_after_network_error() -> None:
    class FlakyClient(FakeClient):
        def __init__(self) -> None:
            super().__init__(FakeResponse())
            self.attempts = 0

        def get(self, url, headers, timeout):
            self.attempts += 1
            self.calls.append(("get", url, headers, None, timeout))
            if self.attempts == 1:
                raise httpx.ConnectError("tls eof")
            return FakeResponse()

    client = FlakyClient()
    provider = OpenAICompatibleProvider(
        base_url="https://api.example/v1",
        api_key="sk-test",
        model="test-model",
        client=client,
    )

    ok, message = provider.test_connection()

    assert ok is True
    assert message == "ok"
    assert client.attempts == 2


def test_local_provider_client_ignores_proxy_env() -> None:
    provider = OpenAICompatibleProvider(
        base_url="http://127.0.0.1:8899/v1",
        api_key="mock",
        model="mock",
    )

    client = provider._get_client()

    assert client.trust_env is False
    client.close()


def test_azure_provider_uses_chat_probe_for_connection_test() -> None:
    client = FakeClient(
        FakeResponse(payload={"choices": [{"message": {"content": "p"}}]})
    )
    provider = AzureOpenAIProvider(
        endpoint="https://example.openai.azure.com",
        deployment="knowledge-chat",
        api_version="2024-02-15-preview",
        api_key="azure-key",
        client=client,
    )

    ok, message = provider.test_connection()

    assert ok is True
    assert [call[0] for call in client.calls] == ["post"]
    assert "api-version=2024-02-15-preview" in client.calls[0][1]


def test_stream_chat_ignores_chunks_without_choices() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"你"}}]}',
        'data: {"choices":[],"usage":{"total_tokens":5}}',
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

    assert [chunk.text for chunk in chunks if not chunk.done] == ["你"]
    assert chunks[-1].done is True


def test_chat_raises_clear_error_when_choices_empty() -> None:
    client = FakeClient(FakeResponse(payload={"choices": []}))
    provider = OpenAICompatibleProvider(
        base_url="https://api.example/v1",
        api_key="sk-test",
        model="test-model",
        client=client,
    )

    with pytest.raises(RuntimeError):
        provider.chat(request())


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
