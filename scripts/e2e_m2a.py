from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from pymilvus import MilvusClient

from knowledgeqa.embedding import FastEmbedEmbedder
from knowledgeqa.milvus.schema import collection_name
from knowledgeqa.milvus.store import MilvusStore
from knowledgeqa.repository import Repository
from knowledgeqa.services.ingestion import IngestionService
from knowledgeqa.services.search import SearchService


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--milvus-uri", default="http://localhost:19530")
    args = parser.parse_args()

    root = Path(tempfile.mkdtemp(prefix="knowledgeqa-e2e-"))
    kb_id = None
    try:
        repository = Repository(root / "meta.db")
        repository.initialize()
        embedder = FastEmbedEmbedder()
        dimension = embedder.dimension()
        kb = repository.create_knowledge_base(
            name="E2E-M2A",
            dimension=dimension,
        )
        kb_id = kb["id"]

        docs = root / "docs"
        docs.mkdir()
        (docs / "contract.md").write_text(
            "# 合同 HT-2024-013\n付款条件：验收后30日内付款。\n",
            encoding="utf-8",
        )

        store = MilvusStore(args.milvus_uri)
        result = IngestionService(repository, embedder, store).sync_markdown(
            kb_id,
            docs,
        )
        hits = SearchService(repository, embedder, store).search(
            kb_id,
            "HT-2024-013 的付款条件",
            limit=3,
        )

        print(
            json.dumps(
                {
                    "dimension": dimension,
                    "sync": {
                        "scanned": result.scanned,
                        "inserted": result.inserted,
                        "skipped": result.skipped,
                        "failed": result.failed,
                    },
                    "hit_count": len(hits),
                    "top_text": hits[0]["text"] if hits else None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        if kb_id:
            try:
                MilvusClient(uri=args.milvus_uri).drop_collection(
                    collection_name(kb_id)
                )
            except Exception:
                pass
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
