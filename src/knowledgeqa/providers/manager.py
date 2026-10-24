from __future__ import annotations

from knowledgeqa.providers.azure import AzureOpenAIProvider
from knowledgeqa.providers.openai_compatible import OpenAICompatibleProvider


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderManager:
    def __init__(
        self,
        repository,
        secret_store,
        fallback_provider=None,
        fallback_model: str | None = None,
    ) -> None:
        self._repository = repository
        self._secret_store = secret_store
        self._fallback_provider = fallback_provider
        self._fallback_model = fallback_model

    def _api_key(self, config: dict, api_key: str | None) -> str:
        if api_key:
            return api_key
        encrypted = config.get("encrypted_secret")
        if encrypted:
            return self._secret_store.unprotect(bytes(encrypted))
        return ""

    def build(self, config: dict, api_key: str | None = None):
        """按配置构造 provider，返回 (provider, model_name)。

        ``api_key`` 显式传入时优先使用（用于未保存表单的连通性测试），
        否则使用配置中已保存的密钥。
        """
        provider_type = config.get("provider_type") or ""
        model_name = config.get("model_name") or ""
        resolved_key = self._api_key(config, api_key)
        if provider_type == "openai_compatible":
            return (
                OpenAICompatibleProvider(
                    base_url=config.get("base_url") or "",
                    api_key=resolved_key,
                    model=model_name,
                ),
                model_name,
            )
        if provider_type == "azure_openai":
            return (
                AzureOpenAIProvider(
                    endpoint=config.get("base_url") or "",
                    deployment=model_name,
                    api_version=config.get("api_version") or "",
                    api_key=resolved_key,
                ),
                model_name,
            )
        raise ProviderNotConfigured(
            f"Unsupported provider type: {provider_type or 'unknown'}"
        )

    def for_id(self, provider_id: str):
        config = self._repository.get_provider_config(provider_id)
        if config is None:
            raise ProviderNotConfigured(f"Provider not found: {provider_id}")
        return self.build(config)

    def active(self):
        config = self._repository.get_active_provider_config()
        if config and int(config.get("enabled", 0)) == 1:
            return self.build(config)
        if self._fallback_provider is not None:
            return self._fallback_provider, self._fallback_model or ""
        raise ProviderNotConfigured("No active chat provider is configured")
