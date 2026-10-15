# -*- coding: utf-8 -*-
"""
个人向量知识库 - FastAPI 服务 (Milvus + fastembed)

启动:
  python kb_server.py            # 默认 http://127.0.0.1:8787
  PORT=9000 python kb_server.py

可选 LLM 问答 (OpenAI 兼容接口):
  set KB_LLM_BASE_URL=https://api.deepseek.com/v1
  set KB_LLM_API_KEY=sk-xxx
  set KB_LLM_MODEL=deepseek-chat
"""
import os
import sys
import threading
import time

# 防止系统 HTTP 代理劫持 localhost 上的 gRPC 连接
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb_build import (  # noqa: E402
    COLLECTION, EMBED_MODEL, MILVUS_URI, SCAN_EXTS, SKIP_DIRS,
    clean_text, chunk_text, iter_documents,
)

import hashlib  # noqa: E402
from pymilvus import MilvusClient  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DOC_DIR = os.path.dirname(BASE_DIR)  # 默认工作区根目录

app = FastAPI(title="个人向量知识库")

# ---------- 惰性单例: embedding 模型 / milvus client ----------
_lock = threading.Lock()
_model = None
_client = None


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from fastembed import TextEmbedding
                print("正在加载 embedding 模型 (首次运行会下载)...")
                _model = TextEmbedding(EMBED_MODEL)
    return _model


def get_client():
    global _client
    if _client is None:
        _client = MilvusClient(uri=MILVUS_URI)
    if not _client.has_collection(COLLECTION):
        raise HTTPException(503, f"集合 {COLLECTION} 不存在, 请先在'知识入库'页执行入库")
    return _client


def milvus_ok() -> bool:
    try:
        c = MilvusClient(uri=MILVUS_URI)
        c.list_collections()
        return True
    except Exception:
        return False


# ---------- 入库后台任务 ----------
_build_state = {"running": False, "log": [], "done": False, "error": None}


def _log(msg: str):
    _build_state["log"].append(msg)
    print("[build]", msg)


def run_build(doc_dir: str, reset: bool):
    try:
        _build_state.update(running=True, log=[], done=False, error=None)
        model = get_model()
        dim = len(next(iter(model.embed(["测试"]))))
        _log(f"模型就绪 (dim={dim})")

        client = MilvusClient(uri=MILVUS_URI)
        old_hashes = set()
        if client.has_collection(COLLECTION):
            if reset:
                client.drop_collection(COLLECTION)
                _log("已清空旧集合, 全量重建")
            else:
                client.load_collection(COLLECTION)
                for row in client.query(
                    COLLECTION, filter='file_hash != ""',
                    output_fields=["file_hash"], limit=16384,
                ):
                    old_hashes.add(row["file_hash"])

        if not client.has_collection(COLLECTION):
            from kb_build import build_schema
            build_schema(client, dim)

        _log(f"扫描 {doc_dir} ...")
        docs = []
        n_files = 0
        for path, text in iter_documents(doc_dir):
            h = hashlib.md5(text.encode("utf-8")).hexdigest()
            chunks = chunk_text(clean_text(text))
            for cid, ch in enumerate(chunks):
                docs.append({
                    "text": ch, "source": os.path.relpath(path, doc_dir),
                    "chunk_id": cid, "file_hash": h,
                })
            n_files += 1
            _log(f"  {'跳过(未变化)' if h in old_hashes else '待入库'}: "
                 f"{os.path.basename(path)} ({len(chunks)} 块)")

        new_docs = [d for d in docs if d["file_hash"] not in old_hashes]
        if old_hashes and new_docs:
            changed = {d["file_hash"] for d in new_docs} & old_hashes
            for h in changed:
                client.delete(COLLECTION, filter=f'file_hash == "{h}"')
            if changed:
                _log(f"删除 {len(changed)} 个已变化文件的旧向量")

        if not new_docs:
            _log("没有需要入库的新内容。")
            _build_state["done"] = True
            return

        _log(f"向量化 {len(new_docs)} 个 chunk ...")
        t0 = time.time()
        texts = [d["text"] for d in new_docs]
        vectors = list(model.embed(texts, batch_size=64))
        for d, v in zip(new_docs, vectors):
            d["vector"] = v.tolist()
        for i in range(0, len(new_docs), 500):
            client.insert(COLLECTION, new_docs[i:i + 500])
        client.flush(COLLECTION)
        stats = client.get_collection_stats(COLLECTION)
        _log(f"完成: 写入 {len(new_docs)} 块, 耗时 {time.time()-t0:.1f}s, "
             f"集合总行数 {stats.get('row_count', '?')}")
        _build_state["done"] = True
    except Exception as e:
        _build_state["error"] = str(e)
        _log(f"出错: {e}")
    finally:
        _build_state["running"] = False


# ---------- API ----------
class SearchReq(BaseModel):
    query: str
    k: int = 5
    ask_llm: bool = False


class BuildReq(BaseModel):
    dir: str = DEFAULT_DOC_DIR
    reset: bool = False


@app.get("/")
def index():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))


@app.get("/api/status")
def status():
    ok = milvus_ok()
    info = {"milvus": "已连接" if ok else "未连接 (需启动 Docker 中的 Milvus)",
            "collection": COLLECTION, "model": EMBED_MODEL,
            "llm": bool(os.environ.get("KB_LLM_BASE_URL") and os.environ.get("KB_LLM_API_KEY")),
            "doc_dir": DEFAULT_DOC_DIR}
    if ok:
        try:
            c = MilvusClient(uri=MILVUS_URI)
            if c.has_collection(COLLECTION):
                c.load_collection(COLLECTION)
                info["rows"] = c.get_collection_stats(COLLECTION).get("row_count", 0)
        except Exception:
            pass
    return info


@app.post("/api/search")
def search(req: SearchReq):
    if not req.query.strip():
        raise HTTPException(400, "问题不能为空")
    client = get_client()
    model = get_model()
    vec = list(model.embed([req.query]))[0].tolist()
    client.load_collection(COLLECTION)
    res = client.search(
        COLLECTION, data=[vec], limit=min(req.k, 20),
        output_fields=["text", "source", "chunk_id"],
        search_params={"metric_type": "COSINE", "params": {"ef": 128}},
    )
    hits = [{
        "score": round(h["distance"], 4),
        "text": h["entity"]["text"],
        "source": h["entity"]["source"],
        "chunk_id": h["entity"]["chunk_id"],
    } for h in res[0]]

    answer = None
    if req.ask_llm and hits and os.environ.get("KB_LLM_BASE_URL") and os.environ.get("KB_LLM_API_KEY"):
        answer = ask_llm(req.query, hits)
    elif req.ask_llm and not os.environ.get("KB_LLM_BASE_URL"):
        answer = "(未配置 LLM: 设置环境变量 KB_LLM_BASE_URL / KB_LLM_API_KEY 后可自动生成回答)"
    return {"hits": hits, "answer": answer}


def ask_llm(query: str, hits):
    import requests
    context = "\n\n".join(
        f"【片段{i}】(来源: {h['source']})\n{h['text']}" for i, h in enumerate(hits, 1)
    )
    prompt = (
        "你是用户的个人知识库助手。请仅根据下面的知识片段回答问题, 并标注引用了哪些片段。"
        "如果片段中没有足够信息, 请直接说明。\n\n"
        f"知识片段:\n{context}\n\n问题: {query}"
    )
    resp = requests.post(
        f"{os.environ['KB_LLM_BASE_URL'].rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['KB_LLM_API_KEY']}"},
        json={"model": os.environ.get("KB_LLM_MODEL", "deepseek-chat"),
              "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.3},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


@app.post("/api/build")
def build(req: BuildReq):
    if _build_state["running"]:
        raise HTTPException(409, "已有入库任务在进行中")
    if not os.path.isdir(req.dir):
        raise HTTPException(400, f"目录不存在: {req.dir}")
    if not milvus_ok():
        raise HTTPException(503, "Milvus 未连接, 请先启动 Docker 中的 Milvus")
    threading.Thread(target=run_build, args=(req.dir, req.reset), daemon=True).start()
    return {"started": True, "dir": req.dir, "reset": req.reset}


@app.get("/api/build/status")
def build_status():
    return _build_state


if __name__ == "__main__":
    import uvicorn
    sys.stdout.reconfigure(encoding="utf-8")
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8787)))
