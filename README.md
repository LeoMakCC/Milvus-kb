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

Email messages are deduplicated by `Message-ID` when available. Attachment names are indexed in M3B; attachment content parsing is added in M3C.
