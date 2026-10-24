from __future__ import annotations

import json
from urllib.parse import urlparse

import httpx

from knowledgeqa.providers.base import (
    ChatChunk,
    ChatRequest,
    ChatResponse,
)

HTTP_HINTS = {
    400: "请求格式被拒绝",
    401: "API Key 无效或缺失",
    403: "无权访问该模型",
    404: "接口不存在，请检查 Base URL",
    429: "请求过于频繁或额度不足",
    500: "模型服务端错误",
    502: "网关错误",
    503: "服务暂不可用",
}


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
            host = (urlparse(self._base_url).hostname or "").lower()
            local = host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
            # 本地模型服务不应该被系统代理接管
            self._client = httpx.Client(trust_env=not local)
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
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("模型返回内容为空")
        message = choices[0].get("message") or {}
        return ChatResponse(
            text=message.get("content") or "",
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
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                # 兼容服务常在结尾补发只带 usage 的块（choices 为空），
                # 直接取 choices[0] 会抛 IndexError
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    yield ChatChunk(text=text)
        yield ChatChunk(text="", done=True)

    def _models_probe(self):
        return self._get_client().get(
            f"{self._base_url}/models",
            headers=self._request_headers(),
            timeout=15,
        )

    def test_connection(self):
        try:
            response = self._models_probe()
        except httpx.RequestError:
            # TLS 提前关闭等网络抖动很常见，重试一次再判定失败
            try:
                response = self._models_probe()
            except Exception as exc:  # noqa: BLE001
                return False, self._describe(exc)
        except Exception as exc:  # noqa: BLE001
            return False, self._describe(exc)

        if response.status_code in (404, 405):
            return self._probe_chat()
        try:
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return False, self._describe(exc)
        return True, "ok"

    def _probe_chat(self):
        """部分兼容服务不提供 /models，用一次极小对话验证连通性。"""
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "stream": False,
        }
        try:
            response = self._get_client().post(
                self._url(),
                headers=self._request_headers(),
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            return True, "ok（chat 探针）"
        except Exception as exc:  # noqa: BLE001
            return False, self._describe(exc)

    def _describe(self, exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            response = exc.response
            hint = HTTP_HINTS.get(response.status_code, "")
            try:
                body = (response.text or "").strip()[:160]
            except Exception:  # noqa: BLE001
                body = ""
            message = f"HTTP {response.status_code}"
            if hint:
                message = f"{message} {hint}"
            if body:
                message = f"{message}：{body}"
            return message
        if isinstance(exc, httpx.RequestError):
            return f"无法连接 {self._base_url}：{exc}"
        return str(exc)
