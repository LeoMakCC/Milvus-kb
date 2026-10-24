from __future__ import annotations

from knowledgeqa.providers.openai_compatible import OpenAICompatibleProvider


class AzureOpenAIProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        endpoint: str,
        deployment: str,
        api_version: str,
        api_key: str,
        headers: dict[str, str] | None = None,
        timeout: float = 120.0,
        client=None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._deployment = deployment
        self._api_version = api_version
        super().__init__(
            base_url=(
                f"{self._endpoint}/openai/deployments/{self._deployment}"
            ),
            api_key=api_key,
            model=deployment,
            headers=headers,
            timeout=timeout,
            client=client,
        )

    def _url(self) -> str:
        return (
            f"{self._base_url}/chat/completions"
            f"?api-version={self._api_version}"
        )

    def _request_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "api-key": self._api_key,
            **self._headers,
        }

    def test_connection(self):
        # Azure OpenAI 不提供 /models，直接用一次极小对话验证部署是否可用
        return self._probe_chat()
