# KnowledgeQA M4B2B Chat And Model UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build the desktop chat experience and model provider settings page, including streaming answers, conversation history, citations, and provider management.

**Architecture:** The existing static frontend becomes a four-tab single-page workspace: `问答`, `检索`, `知识库`, `模型`. It talks only to local FastAPI endpoints. The chat stream uses `fetch` plus `ReadableStream` to parse server-sent events from `POST /api/v1/chat/stream`.

**Tech Stack:** Vanilla HTML/CSS/JavaScript, local Lucide icons, FastAPI APIs, pytest.

---

### Task 1: UI Contract Tests

**Files:**
- Modify: `tests/integration/test_health_api.py`

- [x] **Step 1: Add failing IDs**

Assert root HTML contains:

```text
id="chatMessages"
id="chatInput"
id="sendButton"
id="stopButton"
id="providerForm"
id="providerList"
```

- [x] **Step 2: Verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_health_api.py -v
```

---

### Task 2: UI Shell And Navigation

**Files:**
- Replace: `src/knowledgeqa/web/index.html`
- Replace: `src/knowledgeqa/web/styles.css`

Required structure:

```text
topbar: KnowledgeQA + API/Milvus/Embedding status
sidebar:
  - knowledge base list
  - conversation list in 问答 tab
main:
  - 问答 tab
  - 检索 tab
  - 知识库 tab
  - 模型 tab
```

Chat panel:

- knowledge base selector
- message list
- input
- send and stop buttons

Model panel:

- provider list
- create/edit form
- provider type, base URL, model or deployment, API version, API key
- test, activate, delete actions

No marketing copy, no instructional paragraphs, no card-in-card layout.

---

### Task 3: Chat JavaScript

**Files:**
- Replace: `src/knowledgeqa/web/app.js`

Required behavior:

- load status, knowledge bases, conversations, providers;
- switch tabs;
- create a new conversation;
- load historical messages;
- send a question to `POST /api/v1/chat/stream`;
- parse SSE events `status`, `retrieval`, `token`, `done`, `error`;
- append streamed tokens to the current assistant message;
- render citation list under the assistant message;
- click a citation to reveal the retrieved source text;
- stop generation with `AbortController`;
- preserve current conversation ID from the `done` event.

---

### Task 4: Model Settings JavaScript

**Files:**
- Modify: `src/knowledgeqa/web/app.js`

Required behavior:

- list providers from `GET /api/v1/providers`;
- create/update provider via `POST /api/v1/providers`;
- activate provider via `POST /api/v1/providers/{id}/activate`;
- test provider via `POST /api/v1/providers/{id}/test`;
- delete provider via `DELETE /api/v1/providers/{id}`;
- never render `api_key` or `encrypted_secret`;
- leave API key blank when editing to keep the existing secret.

---

### Task 5: Verification

**Files:**
- Modify: `README.md`

- [x] **Step 1: Run full tests**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

- [x] **Step 2: Check JavaScript syntax**

```powershell
node --check src\knowledgeqa\web\app.js
```

- [x] **Step 3: Restart 8788 and smoke check**

Confirm root page, static assets, status, KBs, providers, and conversation endpoints all return expected responses.

- [x] **Step 4: Live chat check**

Use the active local mock provider to send a question through the UI stream endpoint and confirm tokens plus `done`.
