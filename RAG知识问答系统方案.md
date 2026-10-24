# 基于 Milvus 的 RAG 知识问答系统方案

> 版本: v1.0 | 日期: 2026-10-15
> 适用对象: 个人知识库 / 小团队内部知识问答
> 现状基线: 本仓库 `milvus-kb/` 目录已有可运行原型

---

## 1. 目标与场景

构建一套"本地文档入库 → 向量检索 → LLM 生成带引用回答"的知识问答系统，核心诉求：

- **私有化**：文档与向量数据全部留在本机，不出域
- **低成本**：embedding 本地推理，LLM 走按量付费的 OpenAI 兼容接口（可切 Ollama 全本地）
- **可信回答**：答案必须标注来源片段，检索不到就明说，不编造
- **可持续**：文档增删改后增量更新，不需要全量重建

---

## 2. 总体架构

```
┌─────────────────────────── 文档侧（离线/低频） ───────────────────────────┐
│                                                                          │
│  文档目录(.md/.txt/.py/.html) ──> 扫描 & 清洗 ──> 切分(chunk) ──> 向量化   │
│                                        │               │                 │
│                              md5 哈希增量比对    bge-small-zh-v1.5(本地)    │
│                                        │               │                 │
│                                        ▼               ▼                 │
│                              删除旧 hash 向量     批量 insert             │
└────────────────────────────────────────┬─────────────────────────────────┘
                                         ▼
                          ┌──────────────────────────┐
                          │   Milvus 2.5 (standalone) │
                          │   集合 personal_kb        │
                          │   HNSW + COSINE           │
                          └────────────┬─────────────┘
                                       │
┌─────────────────────────── 查询侧（在线） ────────────────────────────────┐
│                                       │                                  │
│   Web UI (static/index.html)          ▼                                  │
│        │  FastAPI :8787  ──> query 向量化 ──> top-k 检索 ──> 拼装 Prompt   │
│        │                                                     │           │
│        └── hits 列表(带来源) <────────────────────────────────┤           │
│                                                    OpenAI 兼容 LLM        │
│                                                    (DeepSeek/智谱/Ollama) │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 技术选型（与现状对照）

| 层 | 选型 | 现状 | 备注 |
|---|---|---|---|
| 向量库 | Milvus 2.5.6 standalone (Docker) | ✅ 已部署 | docker-compose 含 etcd，数据在 named volume |
| Embedding | BAAI/bge-small-zh-v1.5（512 维，fastembed 本地推理） | ✅ 已接入 | 中文效果够用；升级候选见 §6 |
| 切分 | 按标题切大段 + 字符滑窗（500/80） | ✅ 已实现 | 见 §6.1 优化点 |
| 索引 | HNSW (M=16, efConstruction=200) + COSINE | ✅ 已建 | 个人规模(百万级以下)足够 |
| 服务 | FastAPI :8787 + 静态页 | ✅ 已实现 | 入库走后台线程，状态可轮询 |
| LLM | OpenAI 兼容接口，环境变量配置 | ✅ 已实现 | 默认 deepseek-chat，可换任意兼容服务 |
| 增量 | 文件内容 md5 比对，变更删旧插新 | ✅ 已实现 | 有 16384 条查询上限的隐患，见 §6.4 |

**结论：MVP 已闭环，当前重点不是重写，而是检索质量与工程健壮性的迭代。**

---

## 4. 数据模型设计

集合 `personal_kb`：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT64, 主键, auto_id | 向量自增 ID |
| vector | FLOAT_VECTOR(512) | bge-small-zh-v1.5 输出 |
| text | VARCHAR(8192) | chunk 原文 |
| source | VARCHAR(1024) | 相对路径（引用定位用） |
| chunk_id | INT64 | 文件内块序号 |
| file_hash | VARCHAR(64) | 文件内容 md5，增量更新键 |

索引：`vector` 上 HNSW/COSINE；检索时 `ef=128`。

> 规划中扩展字段（§6.3 混合检索需要）：`sparse_vector SPARSE_FLOAT_VECTOR`、`file_mtime INT64`。

---

## 5. 核心流程

### 5.1 入库流程（kb_build.py / kb_server.py /api/build）
1. 扫描目录（跳过 `.git`、第三方代码库等 SKIP_DIRS）
2. 读文件 → 清洗（压缩连续空行）
3. 按一级~四级标题切段，超长段按 500 字滑窗（overlap 80）细切，丢弃 <30 字碎块
4. md5 比对：未变化跳过；变化的先 `delete(file_hash==h)` 再插入
5. 本地批量向量化（batch=64）→ 分批 insert → flush

### 5.2 问答流程（kb_query.py / kb_server.py /api/search）
1. 问题向量化 → Milvus top-k 检索（默认 k=5）
2. 拼装 Prompt：系统角色 + 编号片段（带来源）+ 问题，约束"仅根据片段回答并标注引用"
3. LLM 生成回答；temperature=0.3 抑制发挥
4. 返回 `answer + hits[]`，前端同时展示片段与相关度，可溯源

---

## 6. 迭代路线

### P0 — 检索质量（收益最大，优先做）

**6.1 混合检索（稠密 + BM25 稀疏）**
Milvus 2.5 原生支持全文检索（内置 BM25 分词器），无需外挂 Elasticsearch：
- schema 增加 `sparse_vector` 字段（SPARSE_FLOAT_VECTOR），`text` 字段开启 `enable_analyzer=True`，配置中文分词
- 重建索引时对 sparse 向量建 SPARSE_INVERTED_INDEX/BM25
- 查询时用 `hybrid_search` 同时发起稠密 + 稀疏两路，RRF 融合
- 动机：纯向量检索对**专有名词、代码标识符、精确文件名**召回差，BM25 恰好补齐，这是个人知识库最常见的失败场景

**6.2 重排序（Rerank）**
- 检索 top-20 → reranker 精排 → 取 top-5 给 LLM
- 候选：`BAAI/bge-reranker-v2-m3`（本地，需 GPU 或慢速 CPU）/ SiliconFlow、Jina 的 rerank API（免费额度够个人用）
- rerank 对最终回答质量的提升通常仅次于混合检索

**6.3 Embedding 升级（可选）**
- bge-small-zh-v1.5 → `BAAI/bge-m3`（1024 维，多语言+长文本 8192 token，且自带 sparse 输出，与 6.1 天然配套）
- 注意换模型必须 `--reset` 全量重建，维度不同不能混存

**6.4 修掉已知隐患**
- `kb_build.py` 增量比对用 `query(limit=16384)` 拉全量 hash，超 1.6 万块后会漏 → 改为按文件路径查询，或新增一个 `kb_meta` 小集合只存 (path, hash)
- `kb_server.py` 的 `/api/build` 后台线程无锁化日志会无限增长 → 加 ring buffer 上限

### P1 — 体验与覆盖面

**6.5 文档格式扩展**：接入 PDF（PyMuPDF）、docx（python-docx）、xlsx，扫描目录扩展对应后缀；PDF 按页切并在 `source` 里带页码
**6.6 自动增量**：watchdog 监听目录变更（防抖 30s）触发单文件重建；或定时任务每天跑一次增量入库
**6.7 多轮对话**：前端带会话历史；追问前先用 LLM 把"它支持哪些格式？"改写成独立问题再检索（condense question）
**6.8 引用体验**：回答中的【片段N】编号渲染为可点击链接，跳转展示原文与来源路径

### P2 — 质量评估与规模化

**6.9 评测集**：手工整理 30~50 条"问题 → 期望命中的文件/片段"金标集，每次调参跑一遍 Recall@5 / MRR，避免凭感觉调优
**6.10 备份**：定期 `docker run --rm -v milvus_milvus-data:/data -v ./backup:/bak alpine tar czf /bak/milvus-$(date +%F).tgz /data`（或使用 Milvus 官方 backup 工具）
**6.11 管理界面**：挂 Attu（Milvus 官方 GUI）看集合状态、调试查询
**6.12 规模升级路径**：数据到千万级向量或需多副本时，docker-compose standalone → Milvus Distributed + MinIO + S3

---

## 7. 部署与运行手册

```bash
# 1. 启动 Milvus
cd milvus-kb && docker compose up -d

# 2. 首次入库（全量）
python kb_build.py --reset

# 3. 命令行问答
python kb_query.py "这个项目的整体架构"

# 4. Web 服务
export KB_LLM_BASE_URL=https://api.deepseek.com/v1
export KB_LLM_API_KEY=sk-xxx
python kb_server.py        # http://127.0.0.1:8787
```

依赖：pymilvus、fastembed、fastapi、uvicorn、requests、pydantic；注意脚本内已设置 `NO_PROXY=localhost` 防 gRPC 被系统代理劫持。

---

## 8. 风险与对策

| 风险 | 对策 |
|---|---|
| 纯向量召回不准（名词/代码类问题） | P0 混合检索 + rerank |
| 换 embedding 模型导致新旧向量不可比 | 模型名写进集合名或 meta，换模型强制全量重建 |
| 增量逻辑在大库上失效（16384 上限） | P0-6.4 改造元数据存储 |
| 文件删除后向量残留 | 当前只处理"变化"，需增加"扫描时未出现的 hash 批量删除" |
| LLM 幻觉 | Prompt 已强制"仅根据片段回答"；可再加"答案中每个论断必须带片段编号"约束 |
