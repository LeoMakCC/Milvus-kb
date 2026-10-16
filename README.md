# KnowledgeQA

Windows-first portable knowledge base QA desktop application.

## Development

```powershell
& "$env:APPDATA\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

## M0 Run

```powershell
.\.venv\Scripts\python.exe -m knowledgeqa.desktop
```

## Manual Smoke Test

```powershell
.\scripts\run_dev.ps1
```

Expected: a desktop window opens, status shows "已运行", and closing the window exits the backend without leaving the lock file held.

## M2A End-to-End Check

Requires a running Milvus instance:

```powershell
.\.venv\Scripts\python.exe scripts\e2e_m2a.py
```

Expected: one Markdown file is ingested, one vector is inserted, and a related query returns at least one hit.

## Supported Documents

- Markdown: `.md`, `.markdown`
- Text and code: `.txt`, `.log`, `.py`, `.js`, `.ts`, `.java`, `.go`, `.sql`, `.json`, `.yaml`, `.yml`
- Web and data: `.html`, `.htm`, `.csv`
- Office: `.pdf`, `.docx`, `.xlsx`, `.xlsm`, `.pptx`
- Email: `.eml`, `.mbox`, `.mbx`, `.msg`

Email messages are deduplicated by `Message-ID` when available. Supported attachment formats are parsed and deduplicated by content hash. Unsupported attachments are recorded by file name.

## Retrieval

Search uses Milvus dense vector retrieval plus BM25 sparse retrieval, fused with RRF. An optional HTTP reranker can be configured without changing the indexing pipeline.

## Chat Provider

Set the following environment variables to enable streaming chat:

```powershell
$env:KB_LLM_BASE_URL = "https://api.example.com/v1"
$env:KB_LLM_API_KEY = "your-key"
$env:KB_LLM_MODEL = "your-model"
```

The local mock provider is available for development:

```powershell
.\.venv\Scripts\python.exe scripts\mock_openai_server.py
.\scripts\start_mock_llm_app.ps1
```

Provider configs can also be managed through `/api/v1/providers`. API keys are stored with Windows DPAPI and are never returned by the API.
