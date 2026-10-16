const state = {
  kbs: [],
  selectedKbId: null,
  conversations: [],
  currentConversationId: null,
  messages: [],
  providers: [],
  providerId: null,
  activeTab: "chat",
  abortController: null,
  streaming: false,
};

const $ = (id) => document.getElementById(id);

function createIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function setChip(element, text, status) {
  element.textContent = text;
  element.className = "status-chip" + (status ? ` ${status}` : "");
}

function authToken() {
  return localStorage.getItem("knowledgeqa:token") || "";
}

function withAuth(headers = {}) {
  const token = authToken();
  return token
    ? { ...headers, Authorization: `Bearer ${token}` }
    : { ...headers };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: withAuth({
      "Content-Type": "application/json",
      ...(options.headers || {}),
    }),
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) {
      showLogin();
    }
    throw new Error(data.detail || data.message || `HTTP ${response.status}`);
  }
  return data;
}

async function refreshStatus() {
  try {
    const status = await api("/api/v1/status");
    setChip($("apiStatus"), `API ${status.api_port || ""}`.trim(), "ok");
    setChip(
      $("milvusStatus"),
      status.milvus === "connected" ? "Milvus 已连接" : "Milvus 未连接",
      status.milvus === "connected" ? "ok" : "warn",
    );
    setChip($("modelStatus"), "Embedding", status.embedding_model ? "ok" : "warn");
  } catch (error) {
    setChip($("apiStatus"), "API 异常", "bad");
  }
}

function selectedKb() {
  return state.kbs.find((kb) => kb.id === state.selectedKbId) || null;
}

function directoryKey(kbId) {
  return `knowledgeqa:directory:${kbId}`;
}

function renderKnowledgeBases() {
  const list = $("kbList");
  list.replaceChildren();
  if (!state.kbs.length) {
    list.append(emptyNode("暂无知识库"));
  }
  for (const kb of state.kbs) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "kb-item" + (kb.id === state.selectedKbId ? " active" : "");
    const icon = document.createElement("i");
    icon.dataset.lucide = "database";
    const label = document.createElement("span");
    label.textContent = kb.name;
    button.append(icon, label);
    button.addEventListener("click", () => selectKnowledgeBase(kb.id));
    list.append(button);
  }
  renderChatKbOptions();
  createIcons();
}

function renderChatKbOptions() {
  const select = $("chatKbSelect");
  select.replaceChildren();
  for (const kb of state.kbs) {
    const option = document.createElement("option");
    option.value = kb.id;
    option.textContent = kb.name;
    option.selected = kb.id === state.selectedKbId;
    select.append(option);
  }
}

function selectKnowledgeBase(kbId) {
  state.selectedKbId = kbId;
  const kb = selectedKb();
  $("kbTitle").textContent = kb ? kb.name : "未选择知识库";
  $("kbMeta").textContent = kb ? `维度 ${kb.dimension}` : "";
  $("directoryInput").value = localStorage.getItem(directoryKey(kbId)) || "";
  renderKnowledgeBases();
}

async function loadKnowledgeBases() {
  state.kbs = await api("/api/v1/kbs");
  if (!state.selectedKbId && state.kbs.length) {
    state.selectedKbId = state.kbs[0].id;
  }
  if (state.selectedKbId && !selectedKb()) {
    state.selectedKbId = state.kbs[0]?.id || null;
  }
  const kb = selectedKb();
  if (kb) {
    $("kbTitle").textContent = kb.name;
    $("kbMeta").textContent = `维度 ${kb.dimension}`;
    $("directoryInput").value = localStorage.getItem(directoryKey(kb.id)) || "";
  }
  renderKnowledgeBases();
}

async function createKnowledgeBase(event) {
  event.preventDefault();
  const name = $("kbNameInput").value.trim();
  if (!name) return;
  const button = $("createKbButton");
  button.disabled = true;
  try {
    const kb = await api("/api/v1/kbs", {
      method: "POST",
      body: JSON.stringify({ name, dimension: 512 }),
    });
    $("kbNameInput").value = "";
    $("kbForm").classList.add("hidden");
    state.selectedKbId = kb.id;
    await loadKnowledgeBases();
    switchTab("kb");
  } catch (error) {
    window.alert(error.message);
  } finally {
    button.disabled = false;
  }
}

async function syncKnowledgeBase() {
  const kb = selectedKb();
  const directory = $("directoryInput").value.trim();
  if (!kb || !directory) return;
  localStorage.setItem(directoryKey(kb.id), directory);
  const button = $("syncButton");
  button.disabled = true;
  $("syncResult").textContent = "同步中...";
  try {
    const result = await api(`/api/v1/kbs/${encodeURIComponent(kb.id)}/sync`, {
      method: "POST",
      body: JSON.stringify({ directory }),
    });
    $("syncResult").textContent =
      `扫描 ${result.scanned} | 入库 ${result.inserted} | 跳过 ${result.skipped}` +
      ` | 附件新增 ${result.attachments_inserted ?? 0}` +
      ` | 附件复用 ${result.attachments_reused ?? 0}` +
      ` | 失败 ${result.failed}`;
  } catch (error) {
    $("syncResult").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function renderHits(hits) {
  const container = $("searchResults");
  container.replaceChildren();
  if (!hits.length) {
    container.append(emptyNode("未找到结果"));
    return;
  }
  for (const hit of hits) {
    const item = document.createElement("article");
    item.className = "result";
    const meta = document.createElement("div");
    meta.className = "result-meta";
    const score = document.createElement("span");
    score.className = "score";
    score.textContent = Number(hit.score ?? 0).toFixed(4);
    const source = document.createElement("span");
    source.className = "source";
    const page = Number(hit.page_no) > 0 ? ` · 第 ${hit.page_no} 页` : "";
    source.textContent = `${hit.source_path || hit.document_id || "unknown"}${page}`;
    meta.append(score, source);
    const text = document.createElement("div");
    text.className = "result-text";
    text.textContent = hit.text || "";
    item.append(meta, text);
    container.append(item);
  }
}

async function doSearch() {
  const kb = selectedKb();
  const query = $("searchInput").value.trim();
  if (!kb || !query) return;
  const button = $("searchButton");
  button.disabled = true;
  $("searchResults").replaceChildren();
  try {
    const result = await api("/api/v1/search", {
      method: "POST",
      body: JSON.stringify({
        kb_id: kb.id,
        query,
        limit: Number($("searchLimit").value),
      }),
    });
    renderHits(result.hits || []);
  } catch (error) {
    $("searchResults").replaceChildren(errorNode(error.message));
  } finally {
    button.disabled = false;
  }
}

function emptyNode(text) {
  const node = document.createElement("div");
  node.className = "empty-state";
  node.textContent = text;
  return node;
}

function errorNode(text) {
  const node = emptyNode(text);
  node.style.color = "var(--err)";
  return node;
}

function appendMessage(role, content = "") {
  const message = {
    role,
    content,
    citations: [],
    hits: [],
    error: null,
    status: "",
  };
  state.messages.push(message);
  renderMessages();
  return message;
}

function renderMessages() {
  const container = $("chatMessages");
  container.replaceChildren();
  if (!state.messages.length) {
    container.append(emptyNode("选择知识库后开始提问"));
    return;
  }
  for (const message of state.messages) {
    const item = document.createElement("article");
    item.className = `message ${message.role}` + (message.error ? " error" : "");
    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent =
      message.role === "user" ? "你" : message.status || "KnowledgeQA";
    const content = document.createElement("div");
    content.className = "message-content";
    content.textContent = message.error || message.content || "…";
    item.append(meta, content);

    if (message.citations.length) {
      const citations = document.createElement("div");
      citations.className = "citations";
      for (const citation of message.citations) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "citation";
        button.textContent = `[${citation.index}] ${citation.source_path || ""}`;
        button.addEventListener("click", () => {
          const hit = message.hits[citation.index - 1];
          const existing = item.querySelector(".citation-detail");
          if (existing) {
            existing.remove();
            return;
          }
          const detail = document.createElement("div");
          detail.className = "citation-detail";
          detail.textContent = hit?.text || "来源片段不可用";
          item.append(detail);
        });
        citations.append(button);
      }
      item.append(citations);
    }
    container.append(item);
  }
  container.scrollTop = container.scrollHeight;
}

async function loadConversations() {
  state.conversations = await api("/api/v1/conversations");
  renderConversations();
}

function renderConversations() {
  const list = $("conversationList");
  list.replaceChildren();
  if (!state.conversations.length) {
    list.append(emptyNode("暂无会话"));
  }
  for (const conversation of state.conversations) {
    const button = document.createElement("button");
    button.type = "button";
    button.className =
      "conversation-item" +
      (conversation.id === state.currentConversationId ? " active" : "");
    const icon = document.createElement("i");
    icon.dataset.lucide = "message-square";
    const label = document.createElement("span");
    label.textContent = conversation.title || "新会话";
    button.append(icon, label);
    button.addEventListener("click", () => selectConversation(conversation.id));
    list.append(button);
  }
  createIcons();
}

function newConversation() {
  state.currentConversationId = null;
  state.messages = [];
  renderMessages();
  renderConversations();
}

async function selectConversation(conversationId) {
  const data = await api(`/api/v1/conversations/${encodeURIComponent(conversationId)}`);
  state.currentConversationId = conversationId;
  state.messages = (data.messages || []).map((message) => ({
    role: message.role,
    content: message.content,
    citations: message.citations_json
      ? JSON.parse(message.citations_json)
      : [],
    hits: [],
    error: null,
    status: "",
  }));
  renderMessages();
  renderConversations();
  switchTab("chat");
}

function handleChatEvent(assistant, eventType, data) {
  if (eventType === "status") {
    assistant.status = data.message || "处理中";
  } else if (eventType === "retrieval") {
    assistant.hits = data.hits || [];
  } else if (eventType === "token") {
    assistant.content += data.text || "";
  } else if (eventType === "done") {
    assistant.status = "";
    if (data.conversation_id) {
      state.currentConversationId = data.conversation_id;
    }
  } else if (eventType === "error") {
    assistant.error = data.message || "生成失败";
  }
  renderMessages();
}

function parseSseFrame(frame) {
  let eventType = "message";
  const dataLines = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) {
      eventType = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      dataLines.push(line.slice(6));
    }
  }
  if (!dataLines.length) return null;
  return {
    type: eventType,
    data: JSON.parse(dataLines.join("\n")),
  };
}

async function sendChat() {
  const query = $("chatInput").value.trim();
  const kbId = $("chatKbSelect").value;
  if (!query || !kbId || state.streaming) return;
  $("chatInput").value = "";
  appendMessage("user", query);
  const assistant = appendMessage("assistant", "");
  state.streaming = true;
  state.abortController = new AbortController();
  $("sendButton").disabled = true;
  $("stopButton").classList.remove("hidden");

  try {
    const response = await fetch("/api/v1/chat/stream", {
      method: "POST",
      headers: withAuth({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        kb_ids: [kbId],
        query,
        conversation_id: state.currentConversationId,
      }),
      signal: state.abortController.signal,
    });
    if (response.status === 401) {
      showLogin();
      throw new Error("Authentication required");
    }
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = parseSseFrame(frame);
        if (event) {
          handleChatEvent(assistant, event.type, event.data);
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
    await loadConversations();
  } catch (error) {
    if (error.name !== "AbortError") {
      assistant.error = error.message;
    } else {
      assistant.content += "\n\n[已停止]";
    }
    renderMessages();
  } finally {
    state.streaming = false;
    state.abortController = null;
    $("sendButton").disabled = false;
    $("stopButton").classList.add("hidden");
  }
}

function stopChat() {
  if (state.abortController) {
    state.abortController.abort();
  }
}

async function loadProviders() {
  state.providers = await api("/api/v1/providers");
  renderProviders();
}

function renderProviders() {
  const list = $("providerList");
  list.replaceChildren();
  if (!state.providers.length) {
    list.append(emptyNode("暂无模型服务"));
  }
  for (const provider of state.providers) {
    const item = document.createElement("div");
    item.className = "provider-item" + (provider.active ? " active" : "");
    const title = document.createElement("div");
    title.className = "provider-title";
    const icon = document.createElement("i");
    icon.dataset.lucide = provider.active ? "check-circle-2" : "server";
    const name = document.createElement("span");
    name.textContent = provider.name;
    title.append(icon, name);
    const meta = document.createElement("div");
    meta.className = "provider-meta";
    meta.textContent = `${provider.provider_type} · ${provider.model_name || ""}`;
    const actions = document.createElement("div");
    actions.className = "provider-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = "编辑";
    edit.addEventListener("click", () => fillProviderForm(provider));
    const activate = document.createElement("button");
    activate.type = "button";
    activate.textContent = "激活";
    activate.addEventListener("click", () => activateProvider(provider.id));
    const test = document.createElement("button");
    test.type = "button";
    test.textContent = "测试";
    test.addEventListener("click", () => testProvider(provider.id));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "删除";
    remove.addEventListener("click", () => deleteProvider(provider.id));
    actions.append(edit, activate, test, remove);
    item.append(title, meta, actions);
    list.append(item);
  }
  createIcons();
}

function resetProviderForm() {
  state.providerId = null;
  $("providerForm").reset();
  $("providerId").value = "";
  $("providerTestResult").textContent = "";
}

function fillProviderForm(provider) {
  state.providerId = provider.id;
  $("providerId").value = provider.id;
  $("providerName").value = provider.name || "";
  $("providerType").value = provider.provider_type || "openai_compatible";
  $("providerBaseUrl").value = provider.base_url || "";
  $("providerModel").value = provider.model_name || "";
  $("providerApiVersion").value = provider.api_version || "";
  $("providerApiKey").value = "";
  $("providerTestResult").textContent = "";
}

async function saveProvider(event) {
  event.preventDefault();
  const payload = {
    name: $("providerName").value.trim(),
    provider_type: $("providerType").value,
    base_url: $("providerBaseUrl").value.trim(),
    model_name: $("providerModel").value.trim(),
    api_version: $("providerApiVersion").value.trim() || null,
    enabled: true,
  };
  const apiKey = $("providerApiKey").value.trim();
  if (apiKey) {
    payload.api_key = apiKey;
  }
  const result = await api("/api/v1/providers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.providerId = result.id;
  $("providerId").value = result.id;
  await loadProviders();
}

async function activateProvider(providerId) {
  await api(`/api/v1/providers/${encodeURIComponent(providerId)}/activate`, {
    method: "POST",
  });
  await loadProviders();
}

async function testProvider(providerId) {
  const result = await api(
    `/api/v1/providers/${encodeURIComponent(providerId)}/test`,
    { method: "POST" },
  );
  $("providerTestResult").textContent = result.ok
    ? "连接正常"
    : `连接失败: ${result.message}`;
}

async function deleteProvider(providerId) {
  if (!window.confirm("删除该模型服务？")) return;
  await api(`/api/v1/providers/${encodeURIComponent(providerId)}`, {
    method: "DELETE",
  });
  if (state.providerId === providerId) {
    resetProviderForm();
  }
  await loadProviders();
}

async function loadSettings() {
  const settings = await api("/api/v1/settings");
  $("lanEnabled").checked = Boolean(settings.lan_enabled);
  $("settingsResult").textContent = settings.restart_required
    ? `已保存。访问地址：${settings.access_url}，重启应用后生效。`
    : `访问地址：${settings.access_url}`;
}

async function saveSettings(event) {
  event.preventDefault();
  const password = $("sharedPassword").value.trim();
  const result = await api("/api/v1/settings", {
    method: "PUT",
    body: JSON.stringify({
      lan_enabled: $("lanEnabled").checked,
      shared_password: password || null,
    }),
  });
  $("sharedPassword").value = "";
  $("settingsResult").textContent = result.restart_required
    ? `已保存。访问地址：${result.access_url}，重启应用后生效。`
    : `访问地址：${result.access_url}`;
}

function showLogin() {
  $("loginOverlay").classList.remove("hidden");
}

function hideLogin() {
  $("loginOverlay").classList.add("hidden");
  $("loginError").textContent = "";
}

async function submitLogin(event) {
  event.preventDefault();
  const password = $("loginPassword").value;
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!response.ok) {
    $("loginError").textContent = "密码不正确";
    return;
  }
  const data = await response.json();
  localStorage.setItem("knowledgeqa:token", data.token);
  $("loginPassword").value = "";
  hideLogin();
  await refreshStatus();
  await loadKnowledgeBases();
  await loadConversations();
  await loadProviders();
  await loadSettings();
}

function switchTab(tab) {
  state.activeTab = tab;
  const panels = {
    chat: $("chatPanel"),
    search: $("searchPanel"),
    kb: $("kbPanel"),
    models: $("modelsPanel"),
    settings: $("settingsPanel"),
  };
  const tabs = {
    chat: $("tabChat"),
    search: $("tabSearch"),
    kb: $("tabKb"),
    models: $("tabModels"),
    settings: $("tabSettings"),
  };
  for (const [name, panel] of Object.entries(panels)) {
    panel.classList.toggle("hidden", name !== tab);
    tabs[name].classList.toggle("active", name === tab);
  }
  $("conversationSidebar").classList.toggle("hidden", tab !== "chat");
}

function bindEvents() {
  $("newKbButton").addEventListener("click", () => {
    $("kbForm").classList.toggle("hidden");
    $("kbNameInput").focus();
  });
  $("kbForm").addEventListener("submit", createKnowledgeBase);
  $("syncButton").addEventListener("click", syncKnowledgeBase);
  $("searchButton").addEventListener("click", doSearch);
  $("searchInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") doSearch();
  });
  $("tabChat").addEventListener("click", () => switchTab("chat"));
  $("tabSearch").addEventListener("click", () => switchTab("search"));
  $("tabKb").addEventListener("click", () => switchTab("kb"));
  $("tabModels").addEventListener("click", () => switchTab("models"));
  $("tabSettings").addEventListener("click", () => switchTab("settings"));
  $("newConversationButton").addEventListener("click", newConversation);
  $("clearChatButton").addEventListener("click", newConversation);
  $("sendButton").addEventListener("click", sendChat);
  $("stopButton").addEventListener("click", stopChat);
  $("chatInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendChat();
    }
  });
  $("newProviderButton").addEventListener("click", resetProviderForm);
  $("providerForm").addEventListener("submit", saveProvider);
  $("testProviderButton").addEventListener("click", () => {
    if (state.providerId) testProvider(state.providerId);
  });
  $("settingsForm").addEventListener("submit", saveSettings);
  $("loginForm").addEventListener("submit", submitLogin);
}

async function init() {
  bindEvents();
  switchTab("chat");
  createIcons();
  await refreshStatus();
  try {
    await loadKnowledgeBases();
    await loadConversations();
    await loadProviders();
    await loadSettings();
  } catch (error) {
    $("chatMessages").replaceChildren(errorNode(error.message));
  }
  window.setInterval(refreshStatus, 15000);
}

init();
