# KnowledgeQA M5A LAN Access And Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional LAN access with a shared password and session tokens, plus a settings API and desktop settings page.

**Architecture:** Password hashes and session tokens are handled by a dedicated security layer. Settings are persisted in `app_settings`. FastAPI middleware allows local requests without login and requires a valid session token for remote requests when LAN mode is enabled. LAN binding is decided at startup and requires restart after changing the setting.

**Tech Stack:** Python hashlib/secrets, FastAPI middleware, SQLite app_settings, vanilla settings UI, pytest.

---

### Task 1: Password Hashing And Session Tokens

**Files:**
- Create: `src/knowledgeqa/security/passwords.py`
- Create: `src/knowledgeqa/security/sessions.py`
- Test: `tests/unit/test_auth_security.py`

- [ ] **Step 1: Write failing tests**

Cover:

```python
hashed = hash_password("secret")
assert verify_password("secret", hashed) is True
assert verify_password("wrong", hashed) is False
```

And session manager:

```python
sessions = SessionManager(ttl_seconds=60)
token = sessions.create()
assert sessions.validate(token) is True
sessions.revoke(token)
assert sessions.validate(token) is False
```

- [ ] **Step 2: Implement**

Use `hashlib.scrypt` and `secrets.token_urlsafe`. Store the salt with the hash.

---

### Task 2: Settings Repository

**Files:**
- Modify: `src/knowledgeqa/repository.py`
- Test: `tests/unit/test_repository.py`

- [ ] **Step 1: Write failing tests**

Cover:

```python
repo.set_setting("lan_enabled", "1")
assert repo.get_setting("lan_enabled") == "1"
repo.set_setting("shared_password_hash", "hash")
assert repo.get_app_settings()["shared_password_hash"] == "hash"
```

- [ ] **Step 2: Implement**

Methods:

```python
get_setting(key, default=None)
set_setting(key, value, encrypted=False)
get_app_settings() -> dict
```

---

### Task 3: Authentication Middleware And Routes

**Files:**
- Create: `src/knowledgeqa/api/auth.py`
- Modify: `src/knowledgeqa/api/app.py`
- Test: `tests/integration/test_auth_api.py`

- [ ] **Step 1: Write failing tests**

Cover:

- LAN disabled: remote request allowed.
- LAN enabled: remote request without token returns 401.
- `POST /api/v1/auth/login` with correct password returns token.
- Remote request with token is allowed.
- Local request bypasses login.

Use `httpx.ASGITransport(..., client=("1.2.3.4", 1234))` to simulate remote clients.

- [ ] **Step 2: Implement**

Middleware rules:

```text
/api/v1/health and /api/v1/auth/login are public
local client addresses bypass authentication
when lan_enabled=1, remote requests require Bearer token
```

Routes:

```text
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/session
```

---

### Task 4: Settings API

**Files:**
- Create: `src/knowledgeqa/api/routes/settings.py`
- Modify: `src/knowledgeqa/api/app.py`
- Test: `tests/integration/test_settings_api.py`

- [ ] **Step 1: Write failing tests**

Cover:

```text
GET  /api/v1/settings
PUT  /api/v1/settings
```

Response fields:

```json
{
  "lan_enabled": false,
  "api_port": 8788,
  "access_url": null,
  "restart_required": false
}
```

Password is accepted only on write and never returned.

- [ ] **Step 2: Implement**

On password change, hash and store `shared_password_hash`.

---

### Task 5: Desktop Settings UI

**Files:**
- Modify: `src/knowledgeqa/web/index.html`
- Modify: `src/knowledgeqa/web/styles.css`
- Modify: `src/knowledgeqa/web/app.js`
- Modify: `tests/integration/test_health_api.py`

- [ ] **Step 1: Add UI contract IDs**

```text
id="settingsPanel"
id="lanEnabled"
id="sharedPassword"
id="saveSettingsButton"
```

- [ ] **Step 2: Implement**

Add a `设置` tab with:

- LAN enabled toggle
- shared password input
- save button
- access URL
- restart-required message

The API helper must attach the bearer token when one is stored locally.

---

### Task 6: Startup Binding And Verification

**Files:**
- Modify: `src/knowledgeqa/desktop.py`
- Modify: `README.md`

- [ ] **Step 1: Read LAN setting at startup**

If `lan_enabled` is true in SQLite, bind FastAPI to `0.0.0.0`; otherwise bind to `127.0.0.1`.

- [ ] **Step 2: Run full tests**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

- [ ] **Step 3: Live verification**

Use 8788. Confirm local requests bypass login, settings save, and the restart-required state is visible.
