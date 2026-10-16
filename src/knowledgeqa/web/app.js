const state = {
  kbs: [],
  selectedKbId: null,
  activeTab: "search",
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

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
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

function storageKey(kbId) {
  return `knowledgeqa:directory:${kbId}`;
}

function renderKnowledgeBases() {
  const list = $("kbList");
  list.replaceChildren();
  if (!state.kbs.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "暂无知识库";
    list.append(empty);
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
  createIcons();
}

function selectKnowledgeBase(kbId) {
  state.selectedKbId = kbId;
  const kb = selectedKb();
  $("kbTitle").textContent = kb ? kb.name : "未选择知识库";
  $("kbMeta").textContent = kb ? `维度 ${kb.dimension}` : "";
  $("directoryInput").value = localStorage.getItem(storageKey(kbId)) || "";
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
    $("directoryInput").value = localStorage.getItem(storageKey(kb.id)) || "";
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
  localStorage.setItem(storageKey(kb.id), directory);
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
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "未找到结果";
    container.append(empty);
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

async function search() {
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
    const container = $("searchResults");
    container.replaceChildren();
    const node = document.createElement("div");
    node.className = "empty-state";
    node.textContent = error.message;
    container.append(node);
  } finally {
    button.disabled = false;
  }
}

function switchTab(tab) {
  state.activeTab = tab;
  const searchActive = tab === "search";
  $("tabSearch").classList.toggle("active", searchActive);
  $("tabKb").classList.toggle("active", !searchActive);
  $("searchPanel").classList.toggle("hidden", !searchActive);
  $("kbPanel").classList.toggle("hidden", searchActive);
}

function bindEvents() {
  $("newKbButton").addEventListener("click", () => {
    $("kbForm").classList.toggle("hidden");
    $("kbNameInput").focus();
  });
  $("kbForm").addEventListener("submit", createKnowledgeBase);
  $("syncButton").addEventListener("click", syncKnowledgeBase);
  $("searchButton").addEventListener("click", search);
  $("searchInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") search();
  });
  $("tabSearch").addEventListener("click", () => switchTab("search"));
  $("tabKb").addEventListener("click", () => switchTab("kb"));
}

async function init() {
  bindEvents();
  createIcons();
  await refreshStatus();
  try {
    await loadKnowledgeBases();
  } catch (error) {
    $("kbList").textContent = error.message;
  }
  window.setInterval(refreshStatus, 15000);
}

init();
