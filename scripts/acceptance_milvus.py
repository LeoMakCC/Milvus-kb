"""Milvus 依赖的验收用例：入库、检索、问答。

由 ``scripts/acceptance_report.py`` 调用，也可单独运行：

    .venv\\Scripts\\python.exe scripts\\acceptance_milvus.py
"""

from __future__ import annotations

import json
import mailbox
import socket
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8790"
MILVUS_HOST = "127.0.0.1"
MILVUS_PORT = 19530
NO_ANSWER_TEXT = "知识库中没有找到足够依据。"

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "dist"
    / "KnowledgeQA"
    / "data"
    / "temp"
    / "acceptance_docs"
)

# 每个格式一条独特关键词，用于验证对应文件确实入库
FORMAT_KEYWORDS = {
    "md": "HT-2024-013",
    "txt": "XG-9",
    "csv": "采购预算",
    "docx": "张伟",
    "xlsx": "SKU-4412",
    "pdf": "600",
    "eml": "EML-5566",
    "mbox": "ZZ-2026",
}


def _case(results: list[dict], name: str, fn):
    try:
        evidence = fn()
        results.append({"name": name, "status": "通过", "evidence": evidence})
        return evidence
    except Exception as exc:  # noqa: BLE001
        results.append({"name": name, "status": "失败", "evidence": str(exc)})
        return None


def milvus_port_open(timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((MILVUS_HOST, MILVUS_PORT), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_milvus(deadline_seconds: int = 240) -> bool:
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        if milvus_port_open():
            return True
        time.sleep(3)
    return False


def build_fixtures(root: Path = FIXTURE_ROOT) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    created: dict[str, str] = {}

    (root / "contract.md").write_text(
        "# 合同 HT-2024-013\n\n"
        "甲方：星海科技有限公司\n"
        "乙方：云枢数据有限公司\n\n"
        "付款条件：验收后30日内付款。\n"
        "质保期：24个月。\n",
        encoding="utf-8",
    )
    created["md"] = "contract.md"

    (root / "manual.txt").write_text(
        "设备型号 XG-9 网关的默认管理地址是 10.20.30.1，"
        "初始密码见随箱卡片。\n",
        encoding="utf-8",
    )
    created["txt"] = "manual.txt"

    (root / "budget.csv").write_text(
        "科目,金额\n采购预算,1200000\n差旅预算,80000\n",
        encoding="utf-8",
    )
    created["csv"] = "budget.csv"

    from docx import Document

    document = Document()
    document.add_heading("项目周报", level=1)
    document.add_paragraph("本周进度：数据迁移完成 80%，负责人 张伟。")
    document.save(root / "weekly.docx")
    created["docx"] = "weekly.docx"

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["SKU", "名称", "库存"])
    sheet.append(["SKU-4412", "边缘网关", 128])
    workbook.save(root / "inventory.xlsx")
    created["xlsx"] = "inventory.xlsx"

    import pymupdf

    pdf = pymupdf.open()
    page = pdf.new_page()
    chinese_font = Path("C:/Windows/Fonts/msyh.ttc")
    if chinese_font.exists():
        page.insert_text(
            (72, 100),
            "差旅管理办法",
            fontsize=14,
            fontname="msyh",
            fontfile=str(chinese_font),
        )
        page.insert_text(
            (72, 130),
            "住宿标准为每晚600元，超标部分自理。",
            fontsize=11,
            fontname="msyh",
            fontfile=str(chinese_font),
        )
    else:
        page.insert_text((72, 100), "Travel policy", fontsize=14)
        page.insert_text(
            (72, 130),
            "Accommodation budget: 600 CNY per night.",
            fontsize=11,
        )
    pdf.save(root / "policy.pdf")
    pdf.close()
    created["pdf"] = "policy.pdf"

    mail = EmailMessage()
    mail["Subject"] = "付款条件确认"
    mail["From"] = "buyer@example.com"
    mail["To"] = "seller@example.com"
    mail["Date"] = "Tue, 20 Oct 2026 09:30:00 +0800"
    mail["Message-ID"] = "<eml-5566@example.com>"
    mail.set_content("关于 EML-5566 号订单，验收后30日内付款。")
    mail.add_attachment(
        b"attachment-terms",
        maintype="text",
        subtype="plain",
        filename="terms.txt",
    )
    (root / "mail.eml").write_bytes(mail.as_bytes())
    created["eml"] = "mail.eml"

    box_path = root / "archive.mbox"
    box_path.unlink(missing_ok=True)
    box = mailbox.mbox(box_path)
    try:
        first = EmailMessage()
        first["Subject"] = "供应商资质"
        first["From"] = "vendor@example.com"
        first["To"] = "buyer@example.com"
        first["Date"] = "Mon, 19 Oct 2026 14:00:00 +0800"
        first["Message-ID"] = "<mbox-1@example.com>"
        first.set_content("资质文件已归档，编号 ZZ-2026。")
        box.add(first)

        second = EmailMessage()
        second["Subject"] = "第二封：合同附件"
        second["From"] = "vendor@example.com"
        second["To"] = "buyer@example.com"
        second["Date"] = "Mon, 19 Oct 2026 15:00:00 +0800"
        second["Message-ID"] = "<mbox-2@example.com>"
        second.set_content("合同附件已上传，供查阅。")
        box.add(second)
        box.flush()
    finally:
        box.close()
    created["mbox"] = "archive.mbox"

    return created


def _search(client: httpx.Client, kb_id: str, query: str, limit: int = 5) -> list[dict]:
    response = client.post(
        "/api/v1/search",
        json={"kb_id": kb_id, "query": query, "limit": limit},
    )
    response.raise_for_status()
    return response.json()["hits"]


def _stream_chat(
    client: httpx.Client,
    kb_ids: list[str],
    query: str,
) -> list[dict]:
    events: list[dict] = []
    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"kb_ids": kb_ids, "query": query},
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            events.append(json.loads(line[6:]))
    return events


def run(base_url: str = BASE_URL) -> dict:
    results: list[dict] = []
    evidence: dict[str, object] = {}

    with httpx.Client(base_url=base_url, timeout=httpx.Timeout(600.0, read=600.0)) as client:
        startup = {
            "port_open_before": milvus_port_open(),
        }
        if not startup["port_open_before"]:
            try:
                response = client.post("/api/v1/milvus/start")
                response.raise_for_status()
                startup["start_call"] = response.json()
            except Exception as exc:  # noqa: BLE001
                startup["start_call"] = f"failed: {exc}"
        startup["port_open_after"] = wait_for_milvus()
        evidence["milvus_startup"] = startup
        if not startup["port_open_after"]:
            return {
                "blocked": True,
                "results": [],
                "evidence": evidence,
                "reason": "Milvus 19530 端口不可连接",
            }

        fixtures = _case(
            results,
            "验收语料准备（7 种格式 + 邮件附件）",
            lambda: build_fixtures(),
        )
        evidence["fixtures"] = fixtures

        stamp = datetime.now().strftime("%H%M%S")
        kb = _case(
            results,
            "创建知识库",
            lambda: client.post(
                "/api/v1/kbs",
                json={"name": f"acceptance-{stamp}", "dimension": 512},
            ).raise_for_status().json(),
        )
        evidence["knowledge_base"] = kb
        if not kb:
            return {
                "blocked": False,
                "results": results,
                "evidence": evidence,
                "reason": "知识库创建失败",
            }

        def create_empty_kb() -> dict:
            kb_item = client.post(
                "/api/v1/kbs",
                json={"name": f"acceptance-empty-{stamp}", "dimension": 512},
            ).raise_for_status().json()
            empty_dir = FIXTURE_ROOT / "empty"
            empty_dir.mkdir(parents=True, exist_ok=True)
            client.post(
                f"/api/v1/kbs/{kb_item['id']}/sync",
                json={"directory": str(empty_dir)},
            ).raise_for_status()
            return kb_item

        empty_kb = _case(results, "创建空知识库（拒答用例）", create_empty_kb)

        sync = _case(
            results,
            "文档目录同步",
            lambda: client.post(
                f"/api/v1/kbs/{kb['id']}/sync",
                json={"directory": str(FIXTURE_ROOT)},
            ).raise_for_status().json(),
        )
        evidence["sync"] = sync
        if sync is not None:
            problems = []
            if sync.get("failed"):
                problems.append(f"failed={sync['failed']}")
            if sync.get("inserted", 0) < len(FORMAT_KEYWORDS):
                problems.append(
                    f"inserted={sync.get('inserted')} < {len(FORMAT_KEYWORDS)}"
                )
            if problems:
                results[-1]["status"] = "失败"
                results[-1]["evidence"] = f"{sync} | " + "; ".join(problems)

        def keyword_hits() -> dict:
            found: dict[str, object] = {}
            for fmt, keyword in FORMAT_KEYWORDS.items():
                hits = _search(client, kb["id"], keyword)
                match = next(
                    (hit for hit in hits if keyword in (hit.get("text") or "")),
                    None,
                )
                found[fmt] = {
                    "keyword": keyword,
                    "hit": match is not None,
                    "source_path": (match or {}).get("source_path"),
                    "doc_type": (match or {}).get("doc_type"),
                }
            missing = [fmt for fmt, item in found.items() if not item["hit"]]
            if missing:
                raise AssertionError(f"未命中的格式: {missing}")
            return found

        formats = _case(results, "各格式入库后关键词命中", keyword_hits)
        evidence["format_hits"] = formats

        def exact_keyword() -> dict:
            keyword = "SKU-4412"
            hits = _search(client, kb["id"], keyword, limit=3)
            assert hits, "检索无结果"
            assert keyword in (hits[0].get("text") or ""), "首条结果未包含关键词"
            return {
                "query": keyword,
                "top_source": hits[0].get("source_path"),
                "top_text": (hits[0].get("text") or "")[:120],
            }

        _case(results, "精确关键词检索", exact_keyword)

        def semantic() -> dict:
            hits = _search(client, kb["id"], "出差住宿每晚可以报销多少钱", limit=5)
            assert hits, "检索无结果"
            texts = " ".join(hit.get("text") or "" for hit in hits)
            assert "600" in texts, "语义检索未召回差旅标准片段"
            return {
                "query": "出差住宿每晚可以报销多少钱",
                "top_source": hits[0].get("source_path"),
                "sources": [hit.get("source_path") for hit in hits],
            }

        _case(results, "语义检索（跨表述召回）", semantic)

        def chat_with_citation() -> dict:
            events = _stream_chat(client, [kb["id"]], "合同 HT-2024-013 的付款条件是什么")
            retrieval = next(
                (event for event in events if event.get("type") == "retrieval"),
                None,
            )
            assert retrieval and retrieval["hits"], "未检索到依据"
            answer = "".join(
                event.get("text", "")
                for event in events
                if event.get("type") == "token"
            )
            assert "[1]" in answer, f"回答缺少引用标记: {answer}"
            done = next(
                (event for event in events if event.get("type") == "done"),
                None,
            )
            assert done, "缺少 done 事件"
            detail = client.get(
                f"/api/v1/conversations/{done['conversation_id']}"
            ).raise_for_status().json()
            assistant = [
                item for item in detail["messages"] if item["role"] == "assistant"
            ][-1]
            citations = json.loads(assistant["citations_json"])
            assert citations, "引用列表为空"
            assert citations[0]["source_path"], "引用缺少来源文件"
            return {
                "hit_count": len(retrieval["hits"]),
                "answer": answer[:120],
                "citation_count": len(citations),
                "first_citation": citations[0],
                "conversation_id": done["conversation_id"],
            }

        _case(results, "流式问答与引用", chat_with_citation)

        def refusal() -> dict:
            assert empty_kb, "空知识库未创建"
            events = _stream_chat(client, [empty_kb["id"]], "火星车的制动距离是多少")
            retrieval = next(
                (event for event in events if event.get("type") == "retrieval"),
                None,
            )
            assert retrieval is not None, "缺少 retrieval 事件"
            assert not retrieval["hits"], "空知识库不应召回片段"
            answer = "".join(
                event.get("text", "")
                for event in events
                if event.get("type") == "token"
            )
            assert answer == NO_ANSWER_TEXT, f"拒答文案不符: {answer}"
            return {"hits": 0, "answer": answer}

        _case(results, "无依据拒答", refusal)

        def idempotent_sync() -> dict:
            again = client.post(
                f"/api/v1/kbs/{kb['id']}/sync",
                json={"directory": str(FIXTURE_ROOT)},
            ).raise_for_status().json()
            assert again.get("inserted") == 0, f"重复同步仍新增: {again}"
            assert again.get("failed") == 0, f"重复同步失败: {again}"
            return again

        _case(results, "重复同步幂等", idempotent_sync)

    return {
        "blocked": False,
        "results": results,
        "evidence": evidence,
        "reason": "",
    }


if __name__ == "__main__":
    output = run()
    print(json.dumps(output, ensure_ascii=False, indent=2))
