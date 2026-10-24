# -*- coding: utf-8 -*-
"""
个人向量知识库 - 入库脚本 (Milvus + fastembed 本地中文 embedding)

用法:
  python kb_build.py                    # 扫描当前目录, 增量入库
  python kb_build.py --dir ./docs       # 指定文档目录
  python kb_build.py --reset            # 清空重建
"""
import argparse
import hashlib
import os
import re
import sys
import time

# 防止系统 HTTP 代理劫持 localhost 上的 gRPC 连接
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

from pymilvus import MilvusClient, DataType
from fastembed import TextEmbedding

# ---------- 配置 ----------
MILVUS_URI = os.environ.get("KB_MILVUS_URI", "http://localhost:19530")
COLLECTION = os.environ.get("KB_COLLECTION", "personal_kb")
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"   # 中文小模型, 512 维, 首次运行自动下载 ~100MB
CHUNK_SIZE = 500       # 目标块大小(字符)
CHUNK_OVERLAP = 80     # 相邻块重叠
SCAN_EXTS = {".md", ".txt", ".py", ".html"}
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
    "data",
}


def iter_documents(root: str):
    """递归扫描目录, 产出 (path, text)"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in SCAN_EXTS:
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                if text.strip():
                    yield path, text
            except OSError as e:
                print(f"  [跳过] {path}: {e}")


def clean_text(text: str) -> str:
    """去掉 markdown 代码块之外的多余空白, 压缩连续空行"""
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """优先按 markdown 标题切大段, 再按字符数滑窗细切"""
    sections = re.split(r"\n(?=#{1,4}\s)", text)  # 按标题行切
    chunks = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        if len(sec) <= size:
            chunks.append(sec)
            continue
        step = size - overlap
        for i in range(0, len(sec), step):
            piece = sec[i:i + size].strip()
            if len(piece) >= 30:  # 丢弃过短的碎块
                chunks.append(piece)
    return chunks


def build_schema(client: MilvusClient, dim: int):
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field("text", DataType.VARCHAR, max_length=8192)
    schema.add_field("source", DataType.VARCHAR, max_length=1024)
    schema.add_field("chunk_id", DataType.INT64)
    schema.add_field("file_hash", DataType.VARCHAR, max_length=64)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector", index_type="HNSW",
        metric_type="COSINE", params={"M": 16, "efConstruction": 200},
    )
    client.create_collection(COLLECTION, schema=schema, index_params=index_params)
    print(f"[+] 已创建集合 {COLLECTION} (dim={dim}, HNSW/COSINE)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.getcwd(),
                    help="要入库的文档目录 (默认当前目录)")
    ap.add_argument("--reset", action="store_true", help="清空集合后全量重建")
    args = ap.parse_args()

    print("[1/4] 加载 embedding 模型 (首次运行会下载模型)...")
    model = TextEmbedding(EMBED_MODEL)
    dim = len(next(iter(model.embed(["测试"]))))
    print(f"      模型就绪, 向量维度 {dim}")

    print("[2/4] 连接 Milvus...")
    client = MilvusClient(uri=MILVUS_URI)
    if client.has_collection(COLLECTION):
        if args.reset:
            client.drop_collection(COLLECTION)
            print("[!] 已清空旧集合")
        else:
            # 读取已有文件的 hash, 用于增量更新
            client.load_collection(COLLECTION)
            old_hashes = set()
            for row in client.query(
                COLLECTION, filter='file_hash != ""',
                output_fields=["file_hash"], limit=16384,
            ):
                old_hashes.add(row["file_hash"])
    else:
        old_hashes = set()

    if not client.has_collection(COLLECTION):
        build_schema(client, dim)

    print(f"[3/4] 扫描并切分 {args.dir} ...")
    docs, seen_hashes = [], set()
    for path, text in iter_documents(args.dir):
        h = hashlib.md5(text.encode("utf-8")).hexdigest()
        seen_hashes.add(h)
        status = "跳过(未变化)" if h in old_hashes else "入库"
        chunks = chunk_text(clean_text(text))
        for cid, ch in enumerate(chunks):
            docs.append({
                "text": ch, "source": os.path.relpath(path, args.dir),
                "chunk_id": cid, "file_hash": h, "_status": status,
            })
        print(f"  {status}: {os.path.basename(path)} ({len(chunks)} 块)")

    new_docs = [d for d in docs if d["_status"] == "入库"]
    for d in docs:
        d.pop("_status")

    # 删除内容已变化的旧 chunk
    if old_hashes and new_docs:
        changed = {d["file_hash"] for d in new_docs} & old_hashes
        for h in changed:
            client.delete(COLLECTION, filter=f'file_hash == "{h}"')
        if changed:
            print(f"[!] 删除了 {len(changed)} 个已变化文件的旧向量")

    if not new_docs:
        print("没有需要入库的新内容。")
        return

    print(f"[4/4] 向量化并写入 {len(new_docs)} 个 chunk ...")
    texts = [d["text"] for d in new_docs]
    t0 = time.time()
    vectors = list(model.embed(texts, batch_size=64))
    for d, v in zip(new_docs, vectors):
        d["vector"] = v.tolist()
    client.insert(COLLECTION, new_docs)
    client.flush(COLLECTION)
    stats = client.get_collection_stats(COLLECTION)
    print(f"完成: 写入 {len(new_docs)} 块, 耗时 {time.time()-t0:.1f}s, "
          f"集合总行数 {stats.get('row_count', '?')}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
