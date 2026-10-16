# KnowledgeQA M4B2A Provider Settings Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store model provider settings in SQLite, encrypt API keys with Windows DPAPI, expose provider configuration APIs, and resolve the active provider at chat time.

**Architecture:** Provider configuration is persisted in `provider_configs`. API keys are encrypted before storage and decrypted only when constructing a provider. `ProviderManager` builds chat providers from SQLite and supplies the active provider to `AnswerService` through a resolver callable.

**Tech Stack:** SQLite, Windows DPAPI, OpenAI-compatible/Azure providers, FastAPI, pytest.

---

### Task 1: DPAPI Secret Store

**Files:**
- Create: `src/knowledgeqa/security/__init__.py`
- Create: `src/knowledgeqa/security/secret_store.py`
- Test: `tests/unit/test_secret_store.py`

- [ ] **Step 1: Write failing test**

```python
def test_secret_round_trip():
    store = WindowsSecretStore()
    protected = store.protect("sk-test")
    assert protected != b"sk-test"
    assert store.unprotect(protected) == "sk-test"
```

- [ ] **Step 2: Implement**

Use `win32crypt.CryptProtectData` and `CryptUnprotectData`. Raise a clear `RuntimeError` when the platform is not Windows.

- [ ] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_secret_store.py -v
```

---

### Task 2: Provider Config Repository

**Files:**
- Modify: `src/knowledgeqa/repository.py`
- Test: `tests/unit/test_repository.py`

- [ ] **Step 1: Write failing tests**

Cover:

```python
provider = repo.upsert_provider_config(
    name="local",
    provider_type="openai_compatible",
    base_url="http://127.0.0.1:8899/v1",
    model_name="mock",
    encrypted_secret=b"secret",
    enabled=True,
)
assert repo.get_provider_config(provider["id"])["name"] == "local"
assert repo.list_provider_configs()[0]["id"] == provider["id"]
assert repo.get_active_provider_config()["id"] == provider["id"]
repo.set_active_provider(provider["id"])
```

- [ ] **Step 2: Implement**

Methods:

```python
upsert_provider_config(...) -> dict
list_provider_configs() -> list[dict]
get_provider_config(provider_id) -> dict | None
get_provider_config_by_name(name) -> dict | None
set_active_provider(provider_id) -> None
get_active_provider_config() -> dict | None
delete_provider_config(provider_id) -> None
```

Store active provider name in `app_settings` using key `active_provider`.

- [ ] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_repository.py -v
```

---

### Task 3: Provider Manager

**Files:**
- Create: `src/knowledgeqa/providers/manager.py`
- Test: `tests/unit/test_provider_manager.py`

- [ ] **Step 1: Write failing tests**

Cover:

- OpenAI-compatible config creates `OpenAICompatibleProvider`.
- Azure config creates `AzureOpenAIProvider`.
- Disabled or missing active config raises `ProviderNotConfigured`.
- Environment fallback is used when no SQLite provider is active.

- [ ] **Step 2: Implement**

```python
class ProviderNotConfigured(RuntimeError):
    pass


class ProviderManager:
    def __init__(self, repository, secret_store, fallback_provider=None, fallback_model=None): ...
    def active(self) -> tuple[object, str]: ...
```

- [ ] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_provider_manager.py -v
```

---

### Task 4: Answer Service Provider Resolver

**Files:**
- Modify: `src/knowledgeqa/answer.py`
- Test: `tests/unit/test_answer.py`

- [ ] **Step 1: Write failing test**

Pass `provider_resolver=lambda: (fake_provider, "resolved-model")` and assert the resolved provider/model are used.

- [ ] **Step 2: Implement**

`AnswerService` accepts optional `provider_resolver`. If present, call it once per stream request:

```python
provider, model_name = self._provider_resolver()
```

Fall back to constructor provider/model when no resolver is configured.

- [ ] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_answer.py -v
```

---

### Task 5: Provider Configuration API

**Files:**
- Create: `src/knowledgeqa/api/routes/providers.py`
- Modify: `src/knowledgeqa/api/app.py`
- Test: `tests/integration/test_provider_api.py`

- [ ] **Step 1: Write failing tests**

Cover:

- `GET /api/v1/providers` returns safe fields only, never plaintext keys.
- `POST /api/v1/providers` stores encrypted secret.
- `POST /api/v1/providers/{id}/activate` sets active provider.
- `POST /api/v1/providers/{id}/test` calls `provider.test_connection`.
- `DELETE /api/v1/providers/{id}` removes config.

- [ ] **Step 2: Implement**

Request model:

```json
{
  "name": "local",
  "provider_type": "openai_compatible",
  "base_url": "http://127.0.0.1:8899/v1",
  "model_name": "mock",
  "api_key": "mock",
  "api_version": null,
  "deployment": null,
  "enabled": true
}
```

Responses must never include `api_key` or `encrypted_secret`.

- [ ] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_provider_api.py -v
```

---

### Task 6: Desktop Wiring And Live Verification

**Files:**
- Modify: `src/knowledgeqa/desktop.py`
- Modify: `README.md`

- [ ] **Step 1: Wire**

Desktop creates:

```python
secret_store = WindowsSecretStore()
provider_manager = ProviderManager(repository, secret_store, fallback_provider=env_provider, fallback_model=settings.llm_model)
answer_service = AnswerService(repository, search_service, provider=env_provider, provider_resolver=provider_manager.active)
```

Chat routes are included even when no provider is configured; calling chat without a configured model returns an `error` event.

- [ ] **Step 2: Run all tests**

```powershell
\.\.venv\Scripts\python.exe -m pytest
```

- [ ] **Step 3: Live verification**

Restart 8788 without LLM environment variables. Use the provider API to add the local mock provider on `8899`, activate it, ingest a Markdown file, call `/api/v1/chat/stream`, and confirm tokens and `done`.
