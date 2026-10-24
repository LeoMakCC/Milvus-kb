# KnowledgeQA

面向 Windows 的本地知识库问答桌面应用：用 pywebview 做桌面外壳，FastAPI 提供本地 API，SQLite 保存元数据，Milvus 保存向量，支持文档入库、混合检索与流式 RAG 问答。应用以便携目录方式运行，数据全部留在本机。

## 功能概览

- **知识库管理**：创建、切换、删除知识库；删除时同步清理元数据与向量集合。
- **文档入库**：目录同步（递归、增量、按哈希跳过未变化文件）与单文件添加；支持 Markdown、TXT/代码、HTML、CSV、PDF、Word、Excel、PowerPoint；邮件支持 `.eml`、`.mbox`、`.mbx`、`.msg` 及其附件。
- **混合检索**：稠密向量（COSINE）+ BM25 稀疏检索，RRF 融合；命中结果自动带出相邻上下文、合并同文档重复命中，并标注来源文件、页码与片段范围。
- **RAG 问答**：流式输出、引用编号、无依据拒答；支持多轮会话与 OpenAI 兼容模型服务。
- **模型管理**：多服务配置、连接测试（`/models` 不可用时回退到 chat 探针）、设置默认服务。
- **备份与恢复**：SQLite 快照 + 可选 Milvus 向量数据，支持自定义保存目录；恢复前自动生成安全副本。
- **可选局域网访问**：默认关闭，开启后需共享密码登录。
- **桌面体验**：系统托盘、单实例锁、子进程不弹控制台窗口。

## 目录结构

```text
.
├── src/knowledgeqa/            # 应用源码
│   ├── api/                    # FastAPI 应用与路由
│   ├── db/                     # SQLite 连接、迁移脚本
│   ├── milvus/                 # 集合 schema 与向量存取
│   ├── parsers/                # 文档、邮件解析器
│   ├── providers/              # OpenAI 兼容 / Azure 模型适配
│   ├── security/               # 会话、密码、Windows DPAPI 密钥存储
│   ├── services/               # 入库、检索服务
│   ├── web/                    # 桌面 UI（HTML/CSS/JS）
│   ├── answer.py               # RAG 问答服务
│   ├── backup.py               # 备份与恢复
│   ├── config.py               # 配置与环境变量
│   └── desktop.py              # 桌面入口
├── scripts/                    # 开发、打包、验收与测试脚本
├── tests/                      # 单元测试与集成测试
├── build/pyinstaller/          # PyInstaller 打包配置
├── docs/                       # 设计与实现计划文档
├── static/                     # 旧版原型页面（kb_server.py 使用）
├── docker-compose.yml          # Milvus + etcd
├── pyproject.toml              # 依赖与工具配置
└── README.md
```

运行期生成、不纳入版本管理的目录：`data/`（数据库、日志、备份、模型缓存）、`dist/`（便携包）、`build/`（打包中间产物）、`.venv/`。

## 环境要求

- Windows 10/11
- Python 3.12
- Docker Desktop（运行 Milvus；`docker info` 需可用）
- 首次使用需下载嵌入模型 `BAAI/bge-small-zh-v1.5`（约 100 MB，需联网）

## 安装与运行

```powershell
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 2. 启动 Milvus（etcd + standalone）
docker compose -p knowledgeqa -f docker-compose.yml up -d

# 3. 启动桌面应用（默认 http://127.0.0.1:8787）
.\.venv\Scripts\python.exe -m knowledgeqa.desktop
```

开发时也可以只起后端 API：

```powershell
.\scripts\run_dev.ps1
```

打包便携版：

```powershell
.\scripts\build_portable.ps1        # 输出 dist\KnowledgeQA
.\scripts\make_release.ps1          # 生成 zip、SHA-256 与 manifest
```

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `KB_HOST` | API 监听地址 | `127.0.0.1` |
| `KB_PORT` | API 端口 | `8787` |
| `KB_LAN_ENABLED` | 是否允许局域网访问（`1` 开启） | `0` |
| `KB_MILVUS_URI` | Milvus 连接地址 | `http://localhost:19530` |
| `KB_LLM_BASE_URL` | OpenAI 兼容接口地址（如 `https://api.example.com/v1`） | 空 |
| `KB_LLM_API_KEY` | 模型服务 API Key | 空 |
| `KB_LLM_MODEL` | 模型名称 | 空 |

说明：

- `KB_LLM_*` 仅作为兜底配置；日常使用建议在「模型」页配置服务，API Key 会用 Windows DPAPI 加密后存入本地数据库，接口不会回读明文。
- 任何密钥都不要写进代码或提交到仓库，本地可用 `.env` 或系统环境变量（`.env` 已在 `.gitignore` 中）。
- 若通过系统代理访问外部接口，本地地址（`localhost`/`127.0.0.1`）会自动跳过代理。

## 使用方法

1. **知识库**：点侧边栏 `+` 新建知识库；「选择目录」后点「同步目录」批量入库，或「添加文件」逐个挑选。下方「已入库文档」可查看每个文件的状态、分块数、大小与入库时间，以及 Milvus 中的实体数。
2. **检索**：选择知识库后输入问题或关键词，返回带上下文的结果，头部显示来源文件、页码与片段范围。
3. **问答**：选择知识库后提问，回答流式输出并带 `[1]` 一类引用；点引用可展开对应原文片段。检索不到依据时会固定回复「知识库中没有找到足够依据。」。
4. **模型**：填写名称、类型、Base URL、模型名与 API Key，保存后可「测试」连通性；点「设为默认」决定问答使用的服务。
5. **设置**：局域网开关与共享密码、创建/恢复备份、Milvus 启停。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

端到端检查（需要已启动的 Milvus）：

```powershell
.\.venv\Scripts\python.exe scripts\e2e_m2a.py
```

## 数据与备份

- 元数据：`data/metadata.db`（知识库、文档、分块映射、会话、模型配置、设置）。
- 备份：默认写入 `data/backups`，包含 SQLite 快照与清单；勾选后可包含 Milvus 向量卷。恢复前会把当前数据库另存为 `pre-restore-*.db`。
- 原始文档不会复制进应用目录，仍保留在原位置；恢复后重新同步目录即可（未变化的文件按哈希跳过）。

## 贡献指南

1. Fork 仓库并从 `main` 拉出功能分支：`git checkout -b feat/your-feature`。
2. 保持改动聚焦，新增行为需补充测试；提交前运行 `pytest` 并确保全部通过。
3. 遵循现有代码风格：Python 使用类型标注、4 空格缩进、行宽 88；前端保持无框架的原生实现。
4. 提交信息建议使用 `feat:`、`fix:`、`docs:`、`chore:` 前缀。
5. 不要提交 `data/`、`dist/`、`.venv/`、日志、备份文件，以及任何密钥、令牌或含个人信息的测试语料。
6. 发起 Pull Request，说明改动目的、影响范围与验证方式。

## 安全说明

- API Key 通过 Windows DPAPI 加密存储，仅当前 Windows 用户可解密。
- 局域网模式默认关闭；开启后远程访问需要共享密码，且建议只在可信网络中使用。
- 本仓库不包含任何真实密钥、账号、个人数据或本机路径；示例配置均使用占位符。
