import pytest

from knowledgeqa.providers.azure import AzureOpenAIProvider
from knowledgeqa.providers.manager import ProviderManager, ProviderNotConfigured
from knowledgeqa.providers.openai_compatible import OpenAICompatibleProvider


class FakeRepository:
    def __init__(self, config=None) -> None:
        self.config = config

    def get_active_provider_config(self):
        return self.config


class FakeSecretStore:
    def unprotect(self, value: bytes) -> str:
        return "decrypted-key"


def test_provider_manager_builds_openai_compatible_provider() -> None:
    manager = ProviderManager(
        FakeRepository(
            {
                "provider_type": "openai_compatible",
                "base_url": "http://127.0.0.1:8899/v1",
                "model_name": "mock",
                "encrypted_secret": b"encrypted",
                "enabled": 1,
            }
        ),
        FakeSecretStore(),
    )

    provider, model_name = manager.active()

    assert isinstance(provider, OpenAICompatibleProvider)
    assert model_name == "mock"


def test_provider_manager_builds_azure_provider() -> None:
    manager = ProviderManager(
        FakeRepository(
            {
                "provider_type": "azure_openai",
                "base_url": "https://example.openai.azure.com",
                "model_name": "deployment",
                "api_version": "2024-02-15-preview",
                "encrypted_secret": b"encrypted",
                "enabled": 1,
            }
        ),
        FakeSecretStore(),
    )

    provider, model_name = manager.active()

    assert isinstance(provider, AzureOpenAIProvider)
    assert model_name == "deployment"


def test_provider_manager_raises_when_not_configured() -> None:
    manager = ProviderManager(FakeRepository(None), FakeSecretStore())

    with pytest.raises(ProviderNotConfigured):
        manager.active()


def test_provider_manager_uses_fallback() -> None:
    fallback = object()
    manager = ProviderManager(
        FakeRepository(None),
        FakeSecretStore(),
        fallback_provider=fallback,
        fallback_model="fallback-model",
    )

    assert manager.active() == (fallback, "fallback-model")
