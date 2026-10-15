# -*- coding: utf-8 -*-
"""
个人向量知识库 - 检索问答脚本

用法:
  python kb_query.py "MediaCrawler 的整体架构是怎样的"
  python kb_query.py            # 进入交互模式
"""
import argparse
import json
import os
import sys

# 防止系统 HTTP 代理劫持 localhost 上的 gRPC 连接
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

from pymilvus import MilvusClient
from fastembed import TextEmbedding

MILVUS_URI = "http://localhost:19530"
COLLECTION = "personal_kb"
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
TOP_K = 5

# 可选: 配置 OpenAI 兼容 LLM 后自动生成回答 (留空则只做检索)
# 支持任意 OpenAI 兼容接口, 例如 DeepSeek / 智谱 / Ollama
LLM_BASE_URL = os.environ.get("KB_LLM_BASE_URL", "")   # 如 https://api.deepseek.com/v1
LLM_API_KEY = os.environ.get("KB_LLM_API_KEY", "")
LLM_MODEL = os.environ.get("KB_LLM_MODEL", "deepseek-chat")


def search(client: MilvusClient, model: TextEmbedding, query: str, k: int = TOP_K):
    vec = list(model.embed([query]))[0].tolist()
    client.load_collection(COLLECTION)
    res = client.search(
        COLLECTION, data=[vec], limit=k,
        output_fields=["text", "source", "chunk_id"],
        search_params={"metric_type": "COSINE", "params": {"ef": 128}},
    )
    hits = []
    for hit in res[0]:
        hits.append({
            "score": hit["distance"],
            "text": hit["entity"]["text"],
            "source": hit["entity"]["source"],
            "chunk_id": hit["entity"]["chunk_id"],
        })
    return hits


def print_hits(hits):
    print("\n" + "=" * 60)
    for i, h in enumerate(hits, 1):
        preview = h["text"][:200].replace("\n", " ") + ("..." if len(h["text"]) > 200 else "")
        print(f"[{i}] 相关度 {h['score']:.3f}  来源: {h['source']} (块 {h['chunk_id']})")
        print(f"    {preview}\n")


def ask_llm(query: str, hits) -> str:
    """用 OpenAI 兼容接口生成回答, 依赖 requests"""
    import requests
    context = "\n\n".join(
        f"【片段{i}】(来源: {h['source']})\n{h['text']}" for i, h in enumerate(hits, 1)
    )
    prompt = (
        "你是用户的个人知识库助手。请仅根据下面的知识片段回答问题,"
        "并标注引用了哪些片段。如果片段中没有足够信息, 请直接说明。\n\n"
        f"知识片段:\n{context}\n\n问题: {query}"
    )
    resp = requests.post(
        f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="*", help="检索问题, 留空进入交互模式")
    ap.add_argument("-k", type=int, default=TOP_K)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = ap.parse_args()

    print("加载模型与连接 Milvus ...")
    model = TextEmbedding(EMBED_MODEL)
    client = MilvusClient(uri=MILVUS_URI)
    if not client.has_collection(COLLECTION):
        print("知识库不存在, 请先运行 kb_build.py")
        return

    queries = [" ".join(args.query)] if args.query else None
    while True:
        if queries is None:
            try:
                q = input("\n问题 (q 退出) > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q or q.lower() in ("q", "quit", "exit"):
                break
        else:
            q = queries[0]
            queries = None

        hits = search(client, model, q, args.k)
        if not hits:
            print("没有检索到相关内容。")
            continue

        if args.json:
            print(json.dumps(hits, ensure_ascii=False, indent=2))
        else:
            print_hits(hits)
            if LLM_BASE_URL and LLM_API_KEY:
                print("-" * 60)
                print("回答:")
                try:
                    print(ask_llm(q, hits))
                except Exception as e:
                    print(f"LLM 调用失败: {e}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
