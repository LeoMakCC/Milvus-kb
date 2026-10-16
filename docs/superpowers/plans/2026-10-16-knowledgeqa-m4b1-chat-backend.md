# KnowledgeQA M4B1 Chat Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OpenAI-compatible and Azure OpenAI chat providers, conversation persistence, prompt construction, streaming answer generation, and an SSE chat endpoint.

**Architecture:** Providers expose one chat interface for blocking and streaming calls. `AnswerService` retrieves hits, builds a citation prompt, streams provider tokens, and persists conversation messages. FastAPI exposes the stream as server-sent events.

**Tech Stack:** httpx, FastAPI StreamingResponse, SQLite conversation tables, pytest.

---

### Task 1: Provider Interfaces And OpenAI-Compatible Provider

**Files:**
- Create: `src/knowledgeqa/providers/base.py`
- Create: `src/knowledgeqa/providers/openai_compatible.py`
- Create: `src/knowledgeqa/providers/__init__.py`
- Test: `tests/unit/test_providers.py`

- [ ] **Step 1: Write failing tests**

Cover:

- non-streaming `chat` parses `choices[0].message.content`.
- streaming `stream_chat` parses `data:` SSE lines and stops at `[DONE]`.
- request includes model, messages, temperature, and stream flag.

- [ ] **Step 2: Implement models**

```python
@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatRequest:
    messages: list[ChatMessage]
    model: str | None = None
    temperature: float = 0.3


@dataclass(frozen=True)
class ChatChunk:
    text: str
    done: bool = False


@dataclass(frozen=True)
class ChatResponse:
    text: str
    usage: dict | None = None
```

- [ ] **Step 3: Implement OpenAI-compatible provider**

Use `httpx.Client` by default and accept an injected client for tests.

URL: `{base_url}/chat/completions`.

Headers: `Authorization: Bearer <api_key>`.

- [ ] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_providers.py -v
```

---

### Task 2: Azure OpenAI Provider

**Files:**
- Create: `src/knowledgeqa/providers/azure.py`
- Modify: `tests/unit/test_providers.py`

- [ ] **Step 1: Write failing test**

Assert URL:

```text
{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=...
```

Assert header `api-key` is used instead of `Authorization`.

- [ ] **Step 2: Implement**

Reuse the same request/stream parsing helpers where practical.

- [ ] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_providers.py -v
```

---

### Task 3: Conversation Repository

**Files:**
- Modify: `src/knowledgeqa/repository.py`
- Test: `tests/unit/test_repository.py`

- [ ] **Step 1: Write failing tests**

Cover:

```python
conversation = repo.create_conversation(kb_ids=["kb1"], model_name="test")
repo.add_message(conversation["id"], "user", "问题")
repo.add_message(conversation["id"], "assistant", "回答", citations_json="[]")
assert repo.list_conversations()[0]["id"] == conversation["id"]
assert [message["role"] for message in repo.list_messages(conversation["id"])] == ["user", "assistant"]
```

- [ ] **Step 2: Implement**

Methods:

```python
create_conversation(kb_ids, provider_name=None, model_name=None) -> dict
list_conversations() -> list[dict]
get_conversation(conversation_id) -> dict | None
add_message(conversation_id, role, content, citations_json=None) -> dict
list_messages(conversation_id) -> list[dict]
```

- [ ] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_repository.py -v
```

---

### Task 4: Prompt Builder And Answer Service

**Files:**
- Create: `src/knowledgeqa/answer.py`
- Test: `tests/unit/test_answer.py`

- [ ] **Step 1: Write failing tests**

Cover:

- no hits returns a fixed “没有找到足够依据” answer without calling the provider;
- hits are numbered in the prompt;
- provider stream chunks become `token` events;
- final assistant message is persisted;
- multi-turn rewrite hook is used when conversation history exists;
- provider failure yields an `error` event.

- [ ] **Step 2: Implement**

```python
class AnswerService:
    def stream_answer(
        self,
        kb_ids: list[str],
        query: str,
        conversation_id: str | None = None,
    ) -> Iterator[dict]: ...
```

Event types:

```text
status
retrieval
token
done
error
```

Prompt rules:

- answer only from provided snippets;
- cite snippets as `[1]`, `[2]`;
- if snippets are insufficient, say so;
- include source path in each snippet.

- [ ] **Step 3: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_answer.py -v
```

---

### Task 5: SSE Chat API

**Files:**
- Create: `src/knowledgeqa/api/routes/chat.py`
- Modify: `src/knowledgeqa/api/app.py`
- Modify: `src/knowledgeqa/desktop.py`
- Modify: `src/knowledgeqa/config.py`
- Test: `tests/integration/test_chat_api.py`

- [ ] **Step 1: Write failing tests**

Cover:

- `POST /api/v1/chat/stream` returns `text/event-stream`;
- events include `retrieval`, `token`, `done`;
- conversations list and message history endpoints work.

- [ ] **Step 2: Implement SSE**

Event format:

```text
event: token
data: {"text":"..."}

```

- [ ] **Step 3: Wire desktop provider**

Add environment settings:

```text
KB_LLM_BASE_URL
KB_LLM_API_KEY
KB_LLM_MODEL
```

If base URL and API key are present, construct `OpenAICompatibleProvider` and `AnswerService`. Otherwise omit chat routes and keep the app usable.

- [ ] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_chat_api.py -v
```

---

### Task 6: Live Mock Provider Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run all tests**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

- [ ] **Step 2: Start a local mock OpenAI-compatible server**

The mock streams `付款条件是验收后30日内付款。[1]`.

- [ ] **Step 3: Start the app with `KB_LLM_BASE_URL` pointing to the mock**

Call `/api/v1/chat/stream` and verify streamed tokens and a final `done` event.
