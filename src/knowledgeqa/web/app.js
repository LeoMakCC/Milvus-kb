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
  showArchived: false,
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
    const item = document.createElement("div");
    item.className =
      "kb-item" + (kb.id === state.selectedKbId ? " active" : "");
    const open = document.createElement("button");
    open.type = "button";
    open.className = "kb-open";
    const icon = document.createElement("i");
    icon.dataset.lucide = "database";
    const label = document.createElement("span");
    label.textContent = kb.name;
    open.append(icon, label);
    open.addEventListener("click", () => selectKnowledgeBase(kb.id));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "kb-delete";
    remove.textContent = "×";
    remove.title = "删除知识库";
    remove.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteKnowledgeBase(kb);
    });

    item.append(open, remove);
    list.append(item);
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
  loadDocuments();
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
  loadDocuments();
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

async function deleteKnowledgeBase(kb) {
  const confirmed = window.confirm(
    `删除知识库「${kb.name}」？其中的文档、分块和向量都会被删除，且无法恢复。`,
  );
  if (!confirmed) return;
  try {
    const result = await api(`/api/v1/kbs/${encodeURIComponent(kb.id)}`, {
      method: "DELETE",
    });
    if (state.selectedKbId === kb.id) {
      state.selectedKbId = null;
    }
    localStorage.removeItem(directoryKey(kb.id));
    await loadKnowledgeBases();
    $("syncResult").textContent = result.milvus_dropped
      ? `已删除知识库「${kb.name}」及其向量集合`
      : `已删除知识库「${kb.name}」，但向量集合未删除成功，请检查 Milvus`;
  } catch (error) {
    window.alert(`删除失败：${error.message}`);
  }
}

async function browseDirectory() {
  const start = $("directoryInput").value.trim();
  const bridge = window.pywebview && window.pywebview.api;
  if (!bridge || typeof bridge.select_directory !== "function") {
    $("syncResult").textContent =
      "当前环境无法打开目录选择框，请直接粘贴文件夹路径";
    return;
  }
  try {
    const selected = await bridge.select_directory(start);
    if (selected) {
      $("directoryInput").value = selected;
    }
  } catch (error) {
    $("syncResult").textContent = `选择目录失败：${error.message || error}`;
  }
}

async function addDocuments() {
  const kb = selectedKb();
  if (!kb) {
    $("syncResult").textContent = "请先在左侧选择或新建知识库";
    return;
  }
  const bridge = window.pywebview && window.pywebview.api;
  if (!bridge || typeof bridge.select_files !== "function") {
    $("syncResult").textContent =
      "当前环境无法打开文件选择框，请改用「同步」并填写文件夹路径";
    return;
  }
  let paths = [];
  try {
    paths = await bridge.select_files($("directoryInput").value.trim());
  } catch (error) {
    $("syncResult").textContent = `选择文件失败：${error.message || error}`;
    return;
  }
  if (!paths || !paths.length) return;

  const button = $("addFilesButton");
  button.disabled = true;
  $("syncResult").textContent = `正在入库 ${paths.length} 个文件...`;
  try {
    const result = await api(
      `/api/v1/kbs/${encodeURIComponent(kb.id)}/documents`,
      {
        method: "POST",
        body: JSON.stringify({ paths }),
      },
    );
    let message =
      `新增 ${result.inserted} | 跳过 ${result.skipped} | 失败 ${result.failed}`;
    if (result.errors && result.errors.length) {
      const details = result.errors
        .slice(0, 3)
        .map((item) => `${item.path}：${item.error}`)
        .join("；");
      message += ` | ${details}`;
    }
    $("syncResult").textContent = message;
    await loadKnowledgeBases();
  } catch (error) {
    $("syncResult").textContent = `入库失败：${error.message}`;
  } finally {
    button.disabled = false;
    loadDocuments();
  }
}

async function syncKnowledgeBase() {
  const kb = selectedKb();
  const directory = $("directoryInput").value.trim();
  if (!kb) {
    $("syncResult").textContent = "请先在左侧选择或新建知识库";
    return;
  }
  if (!directory) {
    $("syncResult").textContent = "请先选择或填写要同步的文档目录";
    return;
  }
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
      `扫描 ${result.scanned} | 新增 ${result.inserted}` +
      ` | 跳过(未变化) ${result.skipped}` +
      ` | 附件新增 ${result.attachments_inserted ?? 0}` +
      ` | 附件复用 ${result.attachments_reused ?? 0}` +
      ` | 失败 ${result.failed}`;
  } catch (error) {
    $("syncResult").textContent = `同步失败：${error.message}`;
  } finally {
    button.disabled = false;
    loadDocuments();
  }
}

const DOC_STATUS_TEXT = {
  indexed: "已入库",
  indexing: "处理中",
  needs_ocr: "需 OCR",
  failed: "失败",
  pending: "待处理",
};

function formatBytes(value) {
  if (value === null || value === undefined) return "";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

async function loadDocuments() {
  const kb = selectedKb();
  const summaryBox = $("documentsSummary");
  const list = $("documentsList");
  if (!kb) {
    summaryBox.textContent = "未选择知识库";
    list.replaceChildren();
    return;
  }
  try {
    const result = await api(
      `/api/v1/kbs/${encodeURIComponent(kb.id)}/documents`,
    );
    renderDocuments(result);
  } catch (error) {
    summaryBox.textContent = `读取文档列表失败：${error.message}`;
  }
}

function renderDocuments(result) {
  const summary = result.summary || {};
  const entities =
    summary.milvus_entities === null || summary.milvus_entities === undefined
      ? "未知"
      : summary.milvus_entities;
  $("documentsSummary").textContent =
    `文档 ${summary.documents ?? 0} 个（已入库 ${summary.indexed ?? 0}，` +
    `失败 ${summary.failed ?? 0}）；分块 ${summary.chunks ?? 0}；` +
    `向量库实体 ${entities}`;
  const list = $("documentsList");
  list.replaceChildren();
  if (!result.documents.length) {
    list.append(emptyNode("暂无文档，先同步目录或添加文件"));
    return;
  }
  for (const doc of result.documents) {
    const row = document.createElement("div");
    row.className = "doc-row";
    const head = document.createElement("div");
    head.className = "doc-head";
    const name = document.createElement("span");
    name.className = "doc-name";
    name.textContent = doc.file_name;
    name.title = doc.id;
    const status = document.createElement("span");
    status.className = `doc-status ${doc.index_status}`;
    status.textContent = DOC_STATUS_TEXT[doc.index_status] || doc.index_status;
    head.append(name, status);
    const meta = document.createElement("div");
    meta.className = "doc-meta";
    meta.textContent = [
      doc.doc_type,
      `${doc.chunk_count} 块`,
      formatBytes(doc.size_bytes),
      doc.indexed_at ? `入库于 ${formatTime(doc.indexed_at)}` : "",
    ]
      .filter(Boolean)
      .join(" · ");
    row.append(head, meta);
    if (doc.last_error) {
      const error = document.createElement("div");
      error.className = "doc-error";
      error.textContent = doc.last_error;
      row.append(error);
    }
    list.append(row);
  }
}

function renderHits(hits) {
  const container = $("searchResults");
  container.replaceChildren();
  if (!hits.length) {
    container.append(emptyNode("未找到结果"));
    return;
  }
  hits.forEach((hit, index) => {
    const item = document.createElement("article");
    item.className = "result";
    const meta = document.createElement("div");
    meta.className = "result-meta";
    const score = document.createElement("span");
    score.className = "score";
    score.textContent =
      `#${index + 1} 相关度 ${Number(hit.score ?? 0).toFixed(4)}`;
    score.title = "混合检索（向量 + 关键词）融合分，仅用于排序比较";
    const source = document.createElement("span");
    source.className = "source";
    const page = Number(hit.page_no) > 0 ? ` · 第 ${hit.page_no} 页` : "";
    const span = Array.isArray(hit.chunk_span)
      ? ` · 片段 ${hit.chunk_span[0] + 1}–${hit.chunk_span[1] + 1}`
      : "";
    source.textContent =
      `${hit.source_path || hit.document_id || "unknown"}${page}${span}`;
    meta.append(score, source);
    const text = document.createElement("div");
    text.className = "result-text";
    text.textContent = hit.text || "";
    item.append(meta, text);
    container.append(item);
  });
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
    const body = message.content || "";
    if (message.error && body) {
      content.textContent = `${body}\n\n[回答未完成] ${message.error}`;
    } else {
      content.textContent = message.error || body || "…";
    }
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
  const query = state.showArchived ? "?archived=true" : "";
  state.conversations = await api(`/api/v1/conversations${query}`);
  renderConversations();
}

function renderConversations() {
  const list = $("conversationList");
  list.replaceChildren();
  $("toggleArchivedButton").textContent = state.showArchived
    ? "返回会话列表"
    : "查看已归档";
  if (!state.conversations.length) {
    list.append(
      emptyNode(state.showArchived ? "暂无已归档会话" : "暂无会话"),
    );
  }
  for (const conversation of state.conversations) {
    const item = document.createElement("div");
    item.className =
      "conversation-item" +
      (conversation.id === state.currentConversationId ? " active" : "");
    const open = document.createElement("button");
    open.type = "button";
    open.className = "conversation-open";
    const icon = document.createElement("i");
    icon.dataset.lucide = "message-square";
    const label = document.createElement("span");
    label.textContent = conversation.title || "新会话";
    open.append(icon, label);
    open.addEventListener("click", () => selectConversation(conversation.id));

    const action = document.createElement("button");
    action.type = "button";
    action.className = "conversation-archive";
    action.textContent = state.showArchived ? "恢复" : "归档";
    action.title = state.showArchived
      ? "恢复到会话列表"
      : "归档后不在会话列表中显示";
    action.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleConversationArchive(conversation);
    });

    item.append(open, action);
    list.append(item);
  }
  createIcons();
}

async function toggleConversationArchive(conversation) {
  const action = state.showArchived ? "unarchive" : "archive";
  try {
    await api(
      `/api/v1/conversations/${encodeURIComponent(conversation.id)}/${action}`,
      { method: "POST" },
    );
    if (!state.showArchived && state.currentConversationId === conversation.id) {
      newConversation();
    }
    await loadConversations();
  } catch (error) {
    window.alert(`操作失败：${error.message}`);
  }
}

function toggleArchivedView() {
  state.showArchived = !state.showArchived;
  loadConversations();
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
  try {
    return {
      type: eventType,
      data: JSON.parse(dataLines.join("\n")),
    };
  } catch (error) {
    return null;
  }
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
    loadConversations().catch(() => {});
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
    if (provider.active) {
      const badge = document.createElement("span");
      badge.className = "provider-badge";
      badge.textContent = "默认";
      title.append(badge);
    }
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
    activate.textContent = provider.active ? "已激活" : "设为默认";
    activate.title = "知识库问答使用该模型服务";
    if (provider.active) {
      activate.disabled = true;
    } else {
      activate.addEventListener("click", () => activateProvider(provider));
    }
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

async function activateProvider(provider) {
  const resultBox = $("providerTestResult");
  try {
    await api(
      `/api/v1/providers/${encodeURIComponent(provider.id)}/activate`,
      { method: "POST" },
    );
    await loadProviders();
    resultBox.textContent =
      `已将「${provider.name}」设为默认，知识库问答将使用该服务`;
  } catch (error) {
    resultBox.textContent = `激活失败：${error.message}`;
  }
}

function providerTestPayload() {
  const payload = {
    provider_id: $("providerId").value.trim() || null,
    provider_type: $("providerType").value,
    base_url: $("providerBaseUrl").value.trim(),
    model_name: $("providerModel").value.trim(),
    api_version: $("providerApiVersion").value.trim() || null,
  };
  const apiKey = $("providerApiKey").value.trim();
  if (apiKey) payload.api_key = apiKey;
  return payload;
}

function describeProviderTest(result) {
  const meta = [];
  if (result.model) meta.push(`模型 ${result.model}`);
  if (result.latency_ms) meta.push(`${result.latency_ms} ms`);
  const suffix = meta.length ? `（${meta.join("，")}）` : "";
  return result.ok
    ? `连接正常${suffix}`
    : `连接失败${suffix}：${result.message || "未知错误"}`;
}

async function testProviderForm() {
  const button = $("testProviderButton");
  const resultBox = $("providerTestResult");
  button.disabled = true;
  resultBox.textContent = "测试中...";
  try {
    const result = await api("/api/v1/providers/test", {
      method: "POST",
      body: JSON.stringify(providerTestPayload()),
    });
    resultBox.textContent = describeProviderTest(result);
  } catch (error) {
    resultBox.textContent = `测试失败：${error.message}`;
  } finally {
    button.disabled = false;
  }
}

async function testProvider(providerId) {
  const resultBox = $("providerTestResult");
  resultBox.textContent = "测试中...";
  try {
    const result = await api(
      `/api/v1/providers/${encodeURIComponent(providerId)}/test`,
      { method: "POST" },
    );
    resultBox.textContent = describeProviderTest(result);
  } catch (error) {
    resultBox.textContent = `测试失败：${error.message}`;
  }
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
  const savedBackupDir = localStorage.getItem("knowledgeqa:backupDir");
  if (savedBackupDir && !$("backupDirInput").value) {
    $("backupDirInput").value = savedBackupDir;
  }
  $("settingsResult").textContent = settings.restart_required
    ? `已保存。访问地址：${settings.access_url}，重启应用后生效。`
    : `访问地址：${settings.access_url}`;
  await loadBackups();
  await loadMilvusStatus();
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

async function loadBackups() {
  const backups = await api("/api/v1/backup");
  const box = $("backupStatus");
  if (!backups.length) {
    box.textContent = "暂无备份";
    box.title = "";
    return;
  }
  const latest = backups[0];
  box.textContent = `最近备份：${latest.name}（${latest.path}）`;
  box.title = latest.path;
}

async function browseBackupFile() {
  const bridge = window.pywebview && window.pywebview.api;
  if (!bridge || typeof bridge.select_backup_file !== "function") {
    $("backupStatus").textContent =
      "当前环境无法打开文件选择框，请直接粘贴备份文件路径";
    return;
  }
  try {
    const selected = await bridge.select_backup_file(
      $("restorePath").value.trim(),
    );
    if (selected) {
      $("restorePath").value = selected;
      $("backupStatus").textContent = `待恢复的备份文件：${selected}`;
      $("backupStatus").title = selected;
    }
  } catch (error) {
    $("backupStatus").textContent = `选择文件失败：${error.message}`;
  }
}

async function browseBackupDir() {
  const bridge = window.pywebview && window.pywebview.api;
  if (!bridge || typeof bridge.select_directory !== "function") {
    $("backupStatus").textContent =
      "当前环境无法打开目录选择框，请直接粘贴保存位置";
    return;
  }
  try {
    const selected = await bridge.select_directory(
      $("backupDirInput").value.trim(),
    );
    if (selected) {
      $("backupDirInput").value = selected;
      localStorage.setItem("knowledgeqa:backupDir", selected);
      $("backupStatus").textContent = `备份将保存到：${selected}`;
      $("backupStatus").title = selected;
    }
  } catch (error) {
    $("backupStatus").textContent = `选择目录失败：${error.message}`;
  }
}

async function createBackup() {
  const targetDir = $("backupDirInput").value.trim();
  $("backupStatus").textContent = "备份中...";
  try {
    const result = await api("/api/v1/backup", {
      method: "POST",
      body: JSON.stringify({
        include_milvus: true,
        target_dir: targetDir || null,
      }),
    });
    $("backupStatus").textContent = `已创建备份：${result.path}`;
    $("backupStatus").title = result.path;
    $("restorePath").value = result.path;
  } catch (error) {
    $("backupStatus").textContent = `备份失败：${error.message}`;
  }
}

async function restoreBackup() {
  const path = $("restorePath").value.trim();
  if (!path) return;
  if (!window.confirm("恢复备份会覆盖当前元数据，确定继续？")) return;
  $("backupStatus").textContent = "恢复中...";
  try {
    const result = await api("/api/v1/restore", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
    $("backupStatus").textContent = result.safety_backup
      ? `恢复完成，已生成安全副本：${result.safety_backup}`
      : "恢复完成";
    $("backupStatus").title = result.safety_backup || "";
  } catch (error) {
    $("backupStatus").textContent = error.message;
  }
}

async function loadMilvusStatus() {
  const status = await api("/api/v1/milvus/status");
  $("milvusLifecycleStatus").textContent =
    `Docker: ${status.available ? "可用" : "不可用"} | Milvus: ${status.running ? "运行中" : "未运行"}`;
}

async function startMilvus() {
  $("milvusLifecycleStatus").textContent = "启动中...";
  try {
    const result = await api("/api/v1/milvus/start", { method: "POST" });
    $("milvusLifecycleStatus").textContent =
      result.returncode === 0 ? "启动命令已执行" : "启动失败";
  } catch (error) {
    $("milvusLifecycleStatus").textContent = error.message;
  }
}

async function stopMilvus() {
  $("milvusLifecycleStatus").textContent = "停止中...";
  try {
    const result = await api("/api/v1/milvus/stop", { method: "POST" });
    $("milvusLifecycleStatus").textContent =
      result.returncode === 0 ? "停止命令已执行" : "停止失败";
  } catch (error) {
    $("milvusLifecycleStatus").textContent = error.message;
  }
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
  if (tab === "kb") {
    loadDocuments();
  }
}

function bindEvents() {
  $("newKbButton").addEventListener("click", () => {
    $("kbForm").classList.toggle("hidden");
    $("kbNameInput").focus();
  });
  $("kbForm").addEventListener("submit", createKnowledgeBase);
  $("browseDirectoryButton").addEventListener("click", browseDirectory);
  $("addFilesButton").addEventListener("click", addDocuments);
  $("refreshDocumentsButton").addEventListener("click", loadDocuments);
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
  $("toggleArchivedButton").addEventListener("click", toggleArchivedView);
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
  $("testProviderButton").addEventListener("click", testProviderForm);
  $("settingsForm").addEventListener("submit", saveSettings);
  $("loginForm").addEventListener("submit", submitLogin);
  $("createBackupButton").addEventListener("click", createBackup);
  $("chooseBackupDirButton").addEventListener("click", browseBackupDir);
  $("browseBackupButton").addEventListener("click", browseBackupFile);
  $("restoreBackupButton").addEventListener("click", restoreBackup);
  $("startMilvusButton").addEventListener("click", startMilvus);
  $("stopMilvusButton").addEventListener("click", stopMilvus);
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
