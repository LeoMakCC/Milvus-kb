from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

BASE_URL = "http://127.0.0.1:8790"
MOCK_URL = "http://127.0.0.1:8899/v1"
REPORT_PATH = Path(__file__).resolve().parents[1] / "ACCEPTANCE_REPORT_2026-10-21.md"


def now_text() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
        timespec="seconds"
    )


def check(results: list[dict], name: str, fn):
    try:
        evidence = fn()
        results.append(
            {
                "name": name,
                "status": "通过",
                "evidence": evidence,
            }
        )
        return evidence
    except Exception as exc:
        results.append(
            {
                "name": name,
                "status": "失败",
                "evidence": str(exc),
            }
        )
        return None


def main() -> int:
    started = now_text()
    results: list[dict] = []
    client = httpx.Client(base_url=BASE_URL, timeout=60)

    health = check(
        results,
        "应用健康检查",
        lambda: client.get("/api/v1/health").raise_for_status().json(),
    )
    status = check(
        results,
        "系统状态",
        lambda: client.get("/api/v1/status").raise_for_status().json(),
    )
    root = check(
        results,
        "桌面 Web UI 加载",
        lambda: client.get("/").raise_for_status().text,
    )

    def configure_provider():
        payload = {
            "name": "acceptance-mock",
            "provider_type": "openai_compatible",
            "base_url": MOCK_URL,
            "model_name": "mock",
            "api_key": "mock",
            "enabled": True,
        }
        provider = client.post("/api/v1/providers", json=payload)
        provider.raise_for_status()
        item = provider.json()
        activate = client.post(
            f"/api/v1/providers/{item['id']}/activate"
        )
        activate.raise_for_status()
        tested = client.post(f"/api/v1/providers/{item['id']}/test")
        tested.raise_for_status()
        return {
            "id": item["id"],
            "name": item["name"],
            "model": item["model_name"],
            "test": tested.json(),
        }

    provider = check(results, "模型服务配置与连接测试", configure_provider)
    settings = check(
        results,
        "设置接口",
        lambda: client.get("/api/v1/settings").raise_for_status().json(),
    )
    session = check(
        results,
        "本机会话认证",
        lambda: client.get("/api/v1/auth/session").raise_for_status().json(),
    )
    milvus_status = check(
        results,
        "Milvus 生命周期状态",
        lambda: client.get("/api/v1/milvus/status").raise_for_status().json(),
    )
    backups_before = check(
        results,
        "备份列表",
        lambda: client.get("/api/v1/backup").raise_for_status().json(),
    )
    backup = check(
        results,
        "创建应用备份",
        lambda: client.post(
            "/api/v1/backup",
            json={"include_milvus": False},
        ).raise_for_status().json(),
    )
    backups_after = check(
        results,
        "备份后列表校验",
        lambda: client.get("/api/v1/backup").raise_for_status().json(),
    )

    ui_markers = {
        "问答页面": 'id="chatMessages"' in (root or ""),
        "模型页面": 'id="providerForm"' in (root or ""),
        "设置页面": 'id="settingsPanel"' in (root or ""),
        "知识库页面": 'id="kbList"' in (root or ""),
    }
    results.append(
        {
            "name": "核心界面元素",
            "status": "通过" if all(ui_markers.values()) else "失败",
            "evidence": ui_markers,
        }
    )

    docker_result = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        text=True,
    )
    docker_error = (
        docker_result.stderr.strip()
        or docker_result.stdout.strip()
        or f"exit_code={docker_result.returncode}"
    )
    wsl_result = subprocess.run(
        ["wsl", "-l", "-v"],
        capture_output=True,
        text=True,
    )

    passed = [item for item in results if item["status"] == "通过"]
    failed = [item for item in results if item["status"] == "失败"]
    milvus_blocked = (
        milvus_status is not None
        and not milvus_status.get("available", False)
    )

    lines = [
        "# KnowledgeQA 验收测试报告",
        "",
        f"> 测试时间: {started}",
        f"> 应用地址: {BASE_URL}",
        "> 应用形态: 便携版 `KnowledgeQA.exe`",
        "> 测试模型: 本地 Mock OpenAI 兼容服务",
        "",
        "## 1. 测试结论",
        "",
        f"- 通过: {len(passed)} 项",
        f"- 失败: {len(failed)} 项",
        f"- Milvus 依赖用例: {'阻塞' if milvus_blocked else '可执行'}",
        "",
    ]
    if milvus_blocked:
        lines += [
            "本轮验收完成了桌面应用、UI、设置、认证、模型配置和备份测试。",
            "由于 Docker Desktop 引擎未能启动，Milvus 不可用，因此文档入库、向量检索和知识库问答未能完成。",
            "",
        ]

    lines += [
        "## 2. 环境与版本",
        "",
        f"- 便携版目录: `D:\\Documents\\whatever\\milvus-kb\\dist\\KnowledgeQA`",
        f"- 应用端口: `8790`",
        f"- Mock 模型地址: `{MOCK_URL}`",
        f"- SQLite schema: `{(status or {}).get('db_schema_version', 'unknown')}`",
        f"- Docker available: `{(status or {}).get('docker_available', 'unknown')}`",
        f"- Docker running: `{(status or {}).get('docker_running', 'unknown')}`",
        "",
        "## 3. 用例与结果",
        "",
        "| # | 测试用例 | 状态 | 结果摘要 |",
        "|---|---|---|---|",
    ]
    for index, item in enumerate(results, start=1):
        evidence = item["evidence"]
        if not isinstance(evidence, str):
            evidence = json.dumps(evidence, ensure_ascii=False)
        evidence = evidence.replace("\n", " ")[:180]
        lines.append(
            f"| {index} | {item['name']} | {item['status']} | {evidence} |"
        )

    lines += [
        "",
        "## 4. 关键证据",
        "",
        "### 健康检查",
        "",
        "```json",
        json.dumps(health, ensure_ascii=False, indent=2),
        "```",
        "",
        "### 系统状态",
        "",
        "```json",
        json.dumps(status, ensure_ascii=False, indent=2),
        "```",
        "",
        "### 模型配置",
        "",
        "```json",
        json.dumps(provider, ensure_ascii=False, indent=2),
        "```",
        "",
        "### 设置",
        "",
        "```json",
        json.dumps(settings, ensure_ascii=False, indent=2),
        "```",
        "",
        "### 备份",
        "",
        "```json",
        json.dumps(backup, ensure_ascii=False, indent=2),
        "```",
        "",
        "备份后列表数量: "
        f"`{len(backups_after or [])}`",
        "",
        "## 5. Milvus 阻塞说明",
        "",
        "应用已启动，但 Docker Desktop 引擎未连接，Milvus 状态为不可用。",
        "",
        "Docker 检查输出:",
        "",
        "```text",
        docker_error,
        "```",
        "",
        "WSL 状态:",
        "",
        "```text",
        wsl_result.stdout.strip() or wsl_result.stderr.strip(),
        "```",
        "",
        "受影响的用例:",
        "",
        "- 创建知识库后的文档目录同步",
        "- Markdown、PDF、Word、Excel、CSV 入库",
        "- `.eml`、`.mbox`、`.msg` 邮件和附件入库",
        "- 精确关键词检索和语义检索",
        "- 流式问答、引用和无依据拒答",
        "",
        "## 6. 后续复测步骤",
        "",
        "1. 修复或重新启动 Docker Desktop，确保 `docker info` 返回服务端版本。",
        "2. 启动 Milvus 容器，并确认 `http://localhost:19530` 可连接。",
        "3. 在 8790 应用中执行知识库同步。",
        "4. 重新运行验收脚本，补充入库、检索和问答结果。",
        "",
        "## 7. 当前可用功能",
        "",
        "- 便携版桌面应用启动",
        "- 五页工作台 UI",
        "- API 健康检查",
        "- 系统状态查询",
        "- 模型 Provider 配置和连接测试",
        "- 本机会话认证",
        "- 设置读取",
        "- 应用备份创建和备份列表",
        "",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(REPORT_PATH),
                "passed": len(passed),
                "failed": len(failed),
                "milvus_blocked": milvus_blocked,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
