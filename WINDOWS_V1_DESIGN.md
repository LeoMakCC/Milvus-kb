# KnowledgeQA Windows v1 详细设计

> 状态: 已冻结 | 日期: 2026-10-16
> 目标平台: Windows 10/11 64 位
> 后续平台: macOS
> 交付形态: 免安装便携包
> 关联文档: `RAG知识问答系统方案.md`

---

## 1. 目标与边界

### 1.1 目标

构建一个可在 Windows 本机运行的桌面知识库问答系统，支持文档和邮件入库、Milvus 向量检索、带引用回答、多知识库、多轮会话和局域网访问。

核心目标:

- 数据私有: 文档、邮件、向量和元数据默认保存在本机。
- 本地向量检索: 使用 Milvus standalone。
- 云端与本地模型双模式: 通过 OpenAI 兼容接口接入。
- 可解释回答: 回答必须带来源片段和引用。
- 可持续同步: 支持增量检查、去重、任务恢复和备份。
- 低门槛部署: 免安装便携包、首次启动向导、依赖检测。
- 可跨平台演进: Windows 优先，代码结构支持后续 macOS。

### 1.2 非目标

以下能力不进入 Windows v1:

- 扫描 PDF 和图片 OCR。
- `.pst`、`.ost`、IMAP、Exchange 和 Microsoft Graph 直连。
- macOS 发行包。
- 自动更新。
- 多实例并行。
- 完整用户账号、角色和权限系统。
- 分布式 Milvus。
- 付费代码签名。
- 跨会话长期记忆和用户偏好。

---

## 2. 总体架构

```text
+------------------------------------------------------+
|                  pywebview 桌面窗口                   |
|             WebView2 + HTML/CSS/JavaScript            |
+---------------------------+--------------------------+
                            |
                            | HTTP + SSE
                            v
+------------------------------------------------------+
|                   FastAPI 本地服务                    |
|                                                      |
|  +-------------+  +-------------+  +--------------+  |
|  | 知识库管理  |  | 入库任务    |  | 对话与检索   |  |
|  +-------------+  +-------------+  +--------------+  |
|  +-------------+  +-------------+  +--------------+  |
|  | 模型网关    |  | SQLite 元数据| | 备份与恢复   |  |
|  +-------------+  +-------------+  +--------------+  |
+---------------------------+--------------------------+
                            |
                            | pymilvus
                            v
+------------------------------------------------------+
|             Milvus standalone Docker                  |
|        每个知识库一个 collection                     |
|        稠密向量索引 + BM25 稀疏索引                  |
+------------------------------------------------------+
```

### 2.1 运行时组成

| 组件 | 责任 |
|---|---|
| `KnowledgeQA.exe` | 启动器、依赖检测、托盘、窗口生命周期 |
| `pywebview` | 提供桌面窗口和前端承载 |
| FastAPI | 本地 API、流式回答、任务控制 |
| SQLite | 权威元数据、任务状态、会话、配置 |
| Milvus | 向量和稀疏检索 |
| Docker Desktop | 运行 Milvus 和 etcd |
| 模型网关 | 云端模型、本地模型、Azure OpenAI |

---

## 3. 进程与生命周期

### 3.1 启动流程

1. 检查程序目录是否可写。
2. 检查单实例锁。
3. 检查 WebView2 Runtime。
4. 检查 Docker Desktop 是否安装。
5. 检查 Docker 服务是否运行。
6. 检查 Milvus 镜像和容器状态。
7. 必要时执行 `docker compose up -d`。
8. 检查 SQLite schema 版本。
9. 启动 FastAPI。
10. 打开 pywebview 桌面窗口。
11. 执行启动增量检查。

### 3.2 退出流程

无运行任务时:

- 刷新 SQLite。
- 停止 FastAPI。
- 关闭窗口。
- Milvus 默认保持运行。

有运行任务时:

- 显示任务类型、进度、当前文件和已完成数量。
- 选项一: 继续后台运行并最小化到托盘。
- 选项二: 停止任务并退出。
- 选项三: 取消退出。

停止任务时:

- 停止领取新文件。
- 等待当前原子步骤完成。
- 将任务标记为 `cancelled` 或 `interrupted`。
- 写入任务状态和停止原因。
- 下次启动时继续未完成任务。

### 3.3 单实例

- 使用进程锁文件。
- 检测到已有实例时，唤起已有窗口。
- Docker Compose 使用固定项目名 `knowledgeqa`。
- 容器名称使用固定前缀 `knowledgeqa-`。
- 第一版不支持多个便携副本同时运行。

---

## 4. 便携目录结构

```text
KnowledgeQA\
├── KnowledgeQA.exe
├── runtime\
├── static\
├── docker-compose.yml
├── model-adapters\
├── platform\
│   ├── windows\
│   └── macos\
└── data\
    ├── config.json
    ├── metadata.db
    ├── logs\
    ├── models\
    ├── milvus-data\
    ├── backups\
    └── temp\
```

规则:

- 默认使用程序目录下的 `data\`。
- 程序目录不可写时，允许切换到用户数据目录。
- 不在安装目录写入模型缓存以外的临时数据。
- OneDrive、坚果云和网络共享盘不推荐作为 `data\` 目录。
- 更新时只替换程序文件，保留 `data\`。

---

## 5. SQLite 元数据设计

SQLite 使用 WAL 模式和 `busy_timeout`。它保存权威元数据、任务状态、配置、会话和引用关系。

### 5.1 schema_migrations

```sql
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
```

### 5.2 app_settings

```sql
CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    encrypted INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
```

### 5.3 knowledge_bases

```sql
CREATE TABLE knowledge_bases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    collection_name TEXT NOT NULL UNIQUE,
    embedding_model TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    index_version INTEGER NOT NULL DEFAULT 1,
    only_local_model INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 5.4 document_roots

```sql
CREATE TABLE document_roots (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    path TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    include_globs TEXT NOT NULL DEFAULT '',
    exclude_globs TEXT NOT NULL DEFAULT '',
    max_file_size_bytes INTEGER NOT NULL DEFAULT 209715200,
    follow_symlinks INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id)
);
```

### 5.5 documents

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    canonical_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_hash TEXT,
    normalized_hash TEXT,
    size_bytes INTEGER,
    mtime_ns INTEGER,
    index_status TEXT NOT NULL DEFAULT 'pending',
    duplicate_of TEXT,
    canonical_document_id TEXT,
    missing_since TEXT,
    last_error TEXT,
    indexed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id)
);
```

索引:

```sql
CREATE INDEX idx_documents_kb_id ON documents(kb_id);
CREATE INDEX idx_documents_source_hash ON documents(source_hash);
CREATE INDEX idx_documents_normalized_hash ON documents(normalized_hash);
CREATE INDEX idx_documents_canonical_path ON documents(canonical_path);
CREATE INDEX idx_documents_status ON documents(index_status);
```

### 5.6 document_aliases

```sql
CREATE TABLE document_aliases (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    alias_path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);
```

### 5.7 emails

```sql
CREATE TABLE emails (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    message_id TEXT,
    thread_id TEXT,
    subject TEXT,
    from_addr TEXT,
    to_addr TEXT,
    cc_addr TEXT,
    sent_at TEXT,
    message_hash TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE INDEX idx_emails_message_id ON emails(message_id);
CREATE INDEX idx_emails_thread_id ON emails(thread_id);
CREATE INDEX idx_emails_message_hash ON emails(message_hash);
```

### 5.8 chunks

```sql
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_hash TEXT NOT NULL,
    page_no INTEGER,
    section_path TEXT,
    char_start INTEGER,
    char_end INTEGER,
    milvus_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_chunk_hash ON chunks(chunk_hash);
CREATE INDEX idx_chunks_milvus_id ON chunks(milvus_id);
```

### 5.9 index_versions

```sql
CREATE TABLE index_versions (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    collection_name TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    schema_version INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id)
);
```

### 5.10 jobs

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    kb_id TEXT,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    total_items INTEGER NOT NULL DEFAULT 0,
    processed_items INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 5.11 job_items

```sql
CREATE TABLE job_items (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    document_id TEXT,
    item_path TEXT,
    item_state TEXT NOT NULL,
    item_error TEXT,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);
```

### 5.12 conversations

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '新会话',
    kb_ids TEXT NOT NULL DEFAULT '[]',
    provider_name TEXT,
    model_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 5.13 messages

```sql
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations_json TEXT,
    token_usage_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

### 5.14 provider_configs

```sql
CREATE TABLE provider_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    provider_type TEXT NOT NULL,
    base_url TEXT,
    model_name TEXT,
    api_version TEXT,
    encrypted_secret BLOB,
    extra_headers_json TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 5.15 audit_logs

```sql
CREATE TABLE audit_logs (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    subject TEXT,
    source_ip TEXT,
    detail_json TEXT,
    created_at TEXT NOT NULL
);
```

---

## 6. Milvus schema

每个知识库使用独立 collection，名称为 `kb_<uuid>`。

### 6.1 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INT64, auto_id | 主键 |
| `vector` | FLOAT_VECTOR(dim) | 稠密向量 |
| `sparse` | SPARSE_FLOAT_VECTOR | BM25 稀疏向量 |
| `text` | VARCHAR(8192) | 切块原文，Milvus 全文检索需要 |
| `kb_id` | VARCHAR(64) | 知识库 ID |
| `document_id` | VARCHAR(64) | 文档 ID |
| `chunk_id` | VARCHAR(64) | 切块 ID |
| `page_no` | INT64 | 页码 |
| `doc_type` | VARCHAR(32) | 文档类型 |
| `source_type` | VARCHAR(32) | 来源类型 |

### 6.2 索引

- 稠密索引: HNSW + COSINE。
- 稀疏索引: SPARSE_INVERTED_INDEX + BM25。
- 文本字段开启 analyzer。
- 使用 Milvus Function 将 `text` 字段映射为 `sparse` 字段，函数类型为 `BM25`。
- `text` 字段开启 analyzer，中文文档配置中文分词参数。
- `sparse` 字段建立 `SPARSE_INVERTED_INDEX`，metric 使用 `BM25`。
- 查询时使用 `hybrid_search`，RRF 融合。

### 6.3 版本约束

- Milvus 版本固定，不使用 `latest`。
- Embedding 模型和维度写入 `index_versions`。
- 更换 Embedding 模型必须重建 collection。
- 不允许多个模型产生的向量混存。

---

## 7. 文档解析

### 7.1 支持格式

文本和代码:

- `.md`
- `.txt`
- `.html`
- `.py`
- `.js`
- `.ts`
- `.java`
- `.go`
- `.sql`
- `.json`
- `.yaml`

办公文档:

- `.pdf`
- `.docx`
- `.xlsx`
- `.pptx`
- `.csv`

邮件:

- `.eml`
- `.mbox`
- `.msg`

### 7.2 解析器接口

每个解析器输出统一结构:

```json
{
  "title": "文档标题",
  "text": "解析后的正文",
  "pages": [
    {
      "page_no": 1,
      "text": "第一页文本",
      "sections": []
    }
  ],
  "metadata": {
    "doc_type": "pdf",
    "source_type": "local_file"
  }
}
```

### 7.3 切块规则

- Markdown 优先按标题层级切块。
- PDF 优先按页和段落切块，保留页码。
- Word 按标题和段落切块。
- Excel 和 CSV 按工作表、行组和表头组合切块。
- PowerPoint 按幻灯片和文本块切块。
- 代码按函数、类和逻辑块切块。
- 邮件按正文、引用历史和附件分别切块。
- 默认目标大小 800 到 1200 字符。
- 超长块使用滑窗，建议重叠 100 到 150 字符。
- 过短且没有语义的块丢弃。

### 7.4 扫描件处理

- 检测到 PDF 没有可提取文本时，标记 `needs_ocr`。
- 图片附件记录文件信息，但不生成文本向量。
- 页面显示需要 OCR 的文档列表。
- 不静默把空文本写入知识库。

---

## 8. 邮件入库

### 8.1 邮件字段

- `Message-ID`
- `In-Reply-To`
- `References`
- 主题
- 发件人
- 收件人
- 抄送
- 发送时间
- 正文
- 引用历史
- 附件列表

### 8.2 邮件去重

优先级:

1. 有 `Message-ID` 时使用 `Message-ID`。
2. 没有 `Message-ID` 时使用规范化字段组合哈希。
3. 附件使用附件内容哈希。

重复邮件只保留主记录，其他位置作为别名或来源记录。

### 8.3 mbox 处理

- `.mbox` 必须按单封邮件解析。
- 每次同步比较 `message_id` 集合。
- 消失的邮件标记为 `missing`，不立即删除。
- 同一封邮件移动到另一个 `.mbox` 时保留向量。

---

## 9. 去重与增量更新

### 9.1 三层指纹

| 指纹 | 计算对象 | 用途 |
|---|---|---|
| `source_hash` | 原始文件字节 | 完全重复判断 |
| `normalized_hash` | 解析和清洗后正文 | 疑似重复判断 |
| `chunk_hash` | 切块文本 | 块级重复判断 |

### 9.2 文件状态

```text
discovered
pending
parsing
embedding
indexing
indexed
missing
needs_ocr
failed
cancelled
```

### 9.3 更新规则

- 路径相同、内容未变: 跳过。
- 路径相同、内容变化: 删除旧 chunks，重新入库。
- 路径不同、`source_hash` 相同: 只保留主文档和别名。
- 路径不同、`normalized_hash` 相同: 标记疑似重复，不自动删除。
- 文件移动或改名: 更新路径，不重新生成向量。
- 文件消失: 标记 `missing`，延迟清理。
- 网络目录不可访问: 不触发删除逻辑。

---

## 10. 检索流程

### 10.1 查询流程

```text
用户问题
  -> 会话改写(多轮追问时)
  -> 查询向量化
  -> Milvus 稠密检索
  -> Milvus BM25 检索
  -> RRF 融合
  -> 可选 Rerank
  -> Top 5 上下文
  -> LLM 回答
  -> 引用展示
```

### 10.2 默认参数

| 参数 | 默认值 |
|---|---|
| 每路召回 | Top 20 |
| 送 LLM 上下文 | Top 5 |
| 稠密索引 | HNSW + COSINE |
| 稀疏索引 | BM25 |
| 融合方式 | RRF |
| Rerank | 默认关闭 |
| 流式输出 | 默认开启 |

### 10.3 无答案处理

- 如果 Top 5 没有足够相关片段，不调用 LLM 编造。
- 返回明确的“知识库中没有找到足够依据”。
- 可以展示低置信度候选，但必须标注原因。

---

## 11. 模型网关

### 11.1 支持类型

- OpenAI 兼容 Chat Completions。
- Azure OpenAI。
- OpenAI Responses API，第二版。
- Anthropic 原生 API，第二版。
- Gemini 原生 API，第二版。
- 自定义 HTTP 服务，按 OpenAI 兼容协议处理。

### 11.2 配置字段

```json
{
  "name": "deepseek",
  "provider_type": "openai_compatible",
  "base_url": "https://api.example.com/v1",
  "model_name": "example-chat",
  "api_key": "encrypted",
  "headers": {},
  "enabled": true
}
```

### 11.3 行为

- 首次启动由用户选择模型。
- 不预置 API Key。
- 云端模型和本地模型共用调用代码。
- 支持流式输出和停止生成。
- 支持连接测试和模型列表测试。
- 支持知识库级“仅本地模型”。
- 日志中脱敏 API Key、密码和令牌。

---

## 12. API 设计

### 12.1 健康与状态

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 服务存活 |
| GET | `/api/v1/status` | Docker、Milvus、模型和任务状态 |

### 12.2 知识库

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/kbs` | 知识库列表 |
| POST | `/api/v1/kbs` | 创建知识库 |
| GET | `/api/v1/kbs/{id}` | 知识库详情 |
| PATCH | `/api/v1/kbs/{id}` | 修改知识库 |
| DELETE | `/api/v1/kbs/{id}` | 删除知识库 |
| POST | `/api/v1/kbs/{id}/roots` | 绑定目录 |
| POST | `/api/v1/kbs/{id}/scan-preview` | 扫描预览 |
| POST | `/api/v1/kbs/{id}/sync` | 启动同步 |
| POST | `/api/v1/kbs/{id}/rebuild` | 重建索引 |
| GET | `/api/v1/kbs/{id}/documents` | 文档列表 |
| GET | `/api/v1/kbs/{id}/missing` | 缺失文件 |
| POST | `/api/v1/kbs/{id}/cleanup-missing` | 清理缺失向量 |

### 12.3 任务

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/jobs` | 任务列表 |
| GET | `/api/v1/jobs/{id}` | 任务详情 |
| POST | `/api/v1/jobs/{id}/cancel` | 取消任务 |
| GET | `/api/v1/jobs/{id}/events` | 任务进度流 |

### 12.4 对话与检索

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/chat/stream` | 流式问答 |
| GET | `/api/v1/conversations` | 会话列表 |
| POST | `/api/v1/conversations` | 新建会话 |
| GET | `/api/v1/conversations/{id}` | 会话详情 |
| DELETE | `/api/v1/conversations/{id}` | 删除会话 |
| POST | `/api/v1/search` | 只检索不生成 |

### 12.5 模型与设置

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/providers` | 模型服务列表 |
| POST | `/api/v1/providers` | 新增模型服务 |
| PATCH | `/api/v1/providers/{id}` | 修改模型服务 |
| DELETE | `/api/v1/providers/{id}` | 删除模型服务 |
| POST | `/api/v1/providers/test` | 测试连接 |
| GET | `/api/v1/settings` | 设置 |
| PUT | `/api/v1/settings` | 更新设置 |

### 12.6 备份与局域网

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/backup` | 创建备份 |
| POST | `/api/v1/restore` | 恢复备份 |
| POST | `/api/v1/auth/login` | 局域网登录 |
| POST | `/api/v1/auth/logout` | 退出 |
| GET | `/api/v1/auth/session` | 会话状态 |

---

## 13. 前端设计

### 13.1 页面

四个主页面:

- 对话
- 知识库
- 模型
- 设置

### 13.2 对话页

- 左侧会话列表。
- 中间聊天区域。
- 右侧来源预览。
- 流式回答。
- 停止生成。
- 引用编号可点击。
- 选择知识库范围。
- 临时切换模型。
- 显示无答案状态。

### 13.3 知识库页

- 知识库列表。
- 创建、编辑、删除。
- 目录绑定。
- 扫描预览。
- 同步任务进度。
- 文档状态列表。
- 缺失文件列表。
- 重复文件报告。
- `needs_ocr` 列表。

### 13.4 模型页

- 云端模型服务。
- 本地兼容服务。
- Azure OpenAI。
- 连接测试。
- 默认模型和备用模型。
- 知识库级本地模型策略。

### 13.5 设置页

- 端口。
- 局域网开关。
- 共享密码。
- 数据目录。
- 日志。
- 备份和恢复。
- 退出时 Milvus 行为。
- 版本检查。

### 13.6 状态栏

```text
Milvus: 已连接
Embedding: 已加载
当前模型: DeepSeek
后台任务: 正在同步 12/80
局域网访问: 已关闭
```

---

## 14. 安全设计

### 14.1 本机模式

- FastAPI 默认绑定 `127.0.0.1`。
- 本机桌面窗口免登录。
- Milvus 只绑定本机。

### 14.2 局域网模式

- 默认关闭。
- 开启后绑定 `0.0.0.0`。
- 使用共享密码和短期会话令牌。
- 连续失败登录临时锁定来源 IP。
- 记录访问日志。
- 仅限可信内网。

### 14.3 密钥

- API Key 使用 Windows DPAPI 加密。
- 日志自动脱敏。
- 备份中不包含明文密钥。
- 局域网模式下不允许普通用户读取模型密钥。

### 14.4 日志

默认不记录:

- 用户问题原文。
- 文档正文。
- 邮件正文。
- 检索片段全文。
- API Key、密码和令牌。
- 完整敏感路径。

调试日志:

- 必须由用户明确开启。
- 默认 24 小时过期。
- 导出前自动脱敏。
- 支持一键清空。

---

## 15. 备份与恢复

### 15.1 备份内容

```text
backup/
├── manifest.json
├── config.json
├── metadata.db
├── milvus-data/
├── logs/
└── model-info.json
```

### 15.2 备份流程

1. 暂停新任务。
2. 等待当前批次完成。
3. 使用 SQLite 在线备份接口。
4. 备份配置和模型版本。
5. 备份 Milvus 数据。
6. 写入 manifest。
7. 打包为带时间戳的压缩文件。

### 15.3 恢复流程

1. 应用进入维护模式。
2. 校验版本兼容性。
3. 备份当前数据。
4. 恢复 SQLite、配置和 Milvus 数据。
5. 校验文档数量和向量数量。
6. 重启服务并执行索引检查。

---

## 16. 打包与发布

### 16.1 Windows 构建

- PyInstaller `onedir`。
- zip 名称: `KnowledgeQA-portable.zip`。
- 不写注册表。
- 不创建开始菜单项。
- 桌面快捷方式由用户选择。

### 16.2 发布文件

```text
KnowledgeQA-portable.zip
KnowledgeQA-portable.zip.sha256
manifest.json
```

### 16.3 manifest.json

```json
{
  "app_version": "1.0.0",
  "build_time": "2026-10-16T12:00:00+08:00",
  "git_commit": "abc1234",
  "milvus_version": "2.5.x",
  "embedding_model": "BAAI/bge-small-zh-v1.5",
  "vector_dimension": 512,
  "sha256": {
    "KnowledgeQA-portable.zip": "...",
    "KnowledgeQA.exe": "...",
    "docker-compose.yml": "..."
  }
}
```

### 16.4 代码签名

- 第一版不做付费代码签名。
- 发布 SHA-256 校验值。
- 说明 SmartScreen 可能提示未知发布者。
- 预留签名配置。

---

## 17. 错误处理

错误分类:

- `DEPENDENCY_MISSING`
- `DOCKER_NOT_RUNNING`
- `MILVUS_UNAVAILABLE`
- `PORT_IN_USE`
- `MODEL_CONNECTION_FAILED`
- `MODEL_AUTH_FAILED`
- `PARSE_FAILED`
- `OCR_REQUIRED`
- `EMBEDDING_FAILED`
- `INDEX_WRITE_FAILED`
- `DISK_SPACE_LOW`
- `BACKUP_FAILED`
- `RESTORE_FAILED`
- `VERSION_INCOMPATIBLE`

每个错误必须包含:

- 面向用户的说明。
- 可能原因。
- 处理步骤。
- 重试入口。
- 技术日志引用。

---

## 18. 测试与验收

### 18.1 测试类型

- SQLite 单元测试。
- 文档解析器测试。
- 邮件解析和去重测试。
- 切块测试。
- Milvus schema 和检索集成测试。
- 模型网关测试。
- FastAPI 接口测试。
- pywebview 生命周期测试。
- 备份恢复测试。
- 异常退出和任务恢复测试。

### 18.2 评测集

至少准备:

- 10 到 20 份真实文档。
- 10 到 20 封真实邮件。
- 30 到 50 条问题。
- 每条问题标注期望命中的文档或邮件。

覆盖类型:

- 精确编号。
- 模糊语义。
- 多轮追问。
- 知识库无答案。
- 重复文件。
- 重复邮件。
- 邮件附件。

### 18.3 验收指标

| 指标 | 目标 |
|---|---|
| 文档解析成功率 | 支持格式达到 95% 以上 |
| 入库任务可恢复 | 中途退出不产生重复向量 |
| Top 5 召回率 | 80% 以上 |
| 引用正确性 | 90% 以上 |
| 无答案问题 | 不编造 |
| 重复文件 | 不产生重复向量 |
| 邮件去重 | 同一 `Message-ID` 只保留一份主记录 |
| 首次回答延迟 | 云端模型尽量控制在 3 秒内 |

---

## 19. 开发里程碑

### M0 桌面壳和基础服务

- 目录结构。
- pywebview 窗口。
- FastAPI 启动。
- 单实例锁。
- 托盘和退出保护。

### M1 元数据与 Milvus

- SQLite schema。
- Milvus collection 创建。
- Docker 生命周期。
- 状态页。

### M2 单格式入库和检索

- Markdown 解析。
- 切块。
- Embedding。
- 稠密检索。
- 基础问答界面。

### M3 多格式和邮件

- PDF、Word、Excel、PowerPoint、CSV。
- 邮件 `.eml`、`.mbox`、`.msg`。
- 附件解析。
- 去重和增量更新。

### M4 混合检索和模型网关

- BM25。
- RRF。
- 可选 Rerank。
- OpenAI 兼容网关。
- Azure OpenAI。
- 流式回答。

### M5 多知识库和管理界面

- 多知识库。
- 目录绑定。
- 扫描预览。
- 任务进度。
- 来源预览。
- 设置页。

### M6 安全、备份和发布

- 局域网模式。
- 共享密码。
- 备份恢复。
- 日志脱敏。
- PyInstaller 打包。
- SHA-256 发布清单。
- 验收评测。

---

## 20. 后续平台

### 20.1 macOS 适配点

- 使用 `pywebview` 加 WKWebView。
- 打包为 `.app`，可发布 `.dmg` 或 zip。
- 数据目录默认使用 `~/Library/Application Support/KnowledgeQA`。
- 托盘改为菜单栏图标。
- Docker 命令和路径使用平台适配层。
- 使用 Developer ID 签名和 notarization。
- 分别构建 Intel 和 Apple Silicon 版本。

### 20.2 后续能力

- OCR。
- `.pst`、`.ost` 和邮箱直连。
- 自动更新。
- 跨会话长期记忆。
- 完整用户和权限系统。
- 分布式 Milvus。
- 云端备份。

---

## 21. 关键决策摘要

| 项目 | 决策 |
|---|---|
| 桌面外壳 | pywebview + WebView2 |
| 后端 | Python + FastAPI |
| 数据库 | SQLite WAL |
| 向量库 | Milvus standalone |
| 元数据权威来源 | SQLite |
| 默认 Embedding | bge-small-zh-v1.5 |
| 检索 | 稠密 + BM25 + RRF |
| Rerank | 默认关闭，可选 |
| LLM | OpenAI 兼容 + Azure |
| 本地模型 | 外部 Ollama 等兼容服务 |
| 多知识库 | 支持 |
| 去重 | source_hash + normalized_hash + chunk_hash |
| OCR | v1 不处理，只提示 |
| 邮件 | .eml、.mbox、.msg |
| 多轮 | 当前会话内 |
| 备份 | 内置手动备份和恢复 |
| 局域网 | 可选，共享密码 + 令牌 |
| 更新 | 手动替换程序文件 |
| 打包 | PyInstaller onedir + zip |
| 签名 | v1 不付费签名 |
| 平台 | Windows 优先，macOS 后续 |
