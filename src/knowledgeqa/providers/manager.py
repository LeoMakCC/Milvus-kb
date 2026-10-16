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

    def active(self):
        config = self._repository.get_active_provider_config()
        if config and int(config.get("enabled", 0)) == 1:
            encrypted = config.get("encrypted_secret")
            api_key = (
                self._secret_store.unprotect(bytes(encrypted))
                if encrypted
                else ""
            )
            provider_type = config.get("provider_type")
            model_name = config.get("model_name") or ""
            if provider_type == "openai_compatible":
                return (
                    OpenAICompatibleProvider(
                        base_url=config.get("base_url") or "",
                        api_key=api_key,
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
                        api_key=api_key,
                    ),
                    model_name,
                )
        if self._fallback_provider is not None:
            return self._fallback_provider, self._fallback_model or ""
        raise ProviderNotConfigured("No active chat provider is configured")
