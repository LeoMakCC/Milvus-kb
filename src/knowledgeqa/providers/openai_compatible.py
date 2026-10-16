from __future__ import annotations

import json

from knowledgeqa.providers.base import (
    ChatChunk,
    ChatRequest,
    ChatResponse,
)


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        headers: dict[str, str] | None = None,
        timeout: float = 120.0,
        client=None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._headers = headers or {}
        self._timeout = timeout
        self._client = client

    def _get_client(self):
        if self._client is None:
            import httpx

            self._client = httpx.Client()
        return self._client

    def _url(self) -> str:
        return f"{self._base_url}/chat/completions"

    def _request_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            **self._headers,
        }

    def _payload(self, request: ChatRequest, stream: bool) -> dict:
        return {
            "model": request.model or self._model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "temperature": request.temperature,
            "stream": stream,
        }

    def chat(self, request: ChatRequest) -> ChatResponse:
        response = self._get_client().post(
            self._url(),
            headers=self._request_headers(),
            json=self._payload(request, stream=False),
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        return ChatResponse(
            text=data["choices"][0]["message"]["content"],
            usage=data.get("usage"),
        )

    def stream_chat(self, request: ChatRequest):
        with self._get_client().stream(
            "POST",
            self._url(),
            headers=self._request_headers(),
            json=self._payload(request, stream=True),
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines():
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    yield ChatChunk(text="", done=True)
                    return
                data = json.loads(payload)
                text = data["choices"][0].get("delta", {}).get("content")
                if text:
                    yield ChatChunk(text=text)
        yield ChatChunk(text="", done=True)

    def test_connection(self):
        try:
            response = self._get_client().get(
                f"{self._base_url}/models",
                headers=self._request_headers(),
                timeout=10,
            )
            response.raise_for_status()
            return True, "ok"
        except Exception as exc:
            return False, str(exc)
