from __future__ import annotations


def _strip_repeated_heading(previous: str, following: str) -> str:
    """切块时每个分块会重复所属章节标题，拼接前去掉。"""
    first_line, separator, rest = following.partition("\n")
    if separator and first_line.startswith("#") and first_line in previous:
        return rest
    return following


def _chunk_index(chunk_id: str) -> int:
    _, _, suffix = str(chunk_id).rpartition(":")
    try:
        return int(suffix)
    except ValueError:
        return 0


def merge_chunks(texts: list[str], max_overlap: int = 240) -> str:
    """拼接相邻分块，尽量削掉重叠部分。"""
    if not texts:
        return ""
    merged = texts[0]
    for text in texts[1:]:
        following = _strip_repeated_heading(merged, text)
        limit = min(len(merged), len(following), max_overlap)
        joined = False
        for size in range(limit, 0, -1):
            if merged.endswith(following[:size]):
                merged = merged + following[size:]
                joined = True
                break
        if not joined:
            merged = f"{merged}\n\n{following}"
    return merged


class SearchService:
    def __init__(
        self,
        repository,
        embedder,
        milvus_store,
        reranker=None,
        context_window: int = 1,
        max_merged_chunks: int = 6,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self._milvus_store = milvus_store
        self._reranker = reranker
        self._context_window = max(0, context_window)
        self._max_merged_chunks = max(1, max_merged_chunks)

    def search(
        self,
        kb_id: str,
        query: str,
        limit: int = 5,
        expand_context: bool = False,
    ) -> list[dict]:
        if not query.strip():
            raise ValueError("Query cannot be empty")
        if self._repository.get_knowledge_base(kb_id) is None:
            raise ValueError(f"Knowledge base not found: {kb_id}")
        vector = self._embedder.embed([query])[0]
        if hasattr(self._milvus_store, "hybrid_search"):
            hits = self._milvus_store.hybrid_search(
                kb_id,
                vector,
                query,
                limit=limit,
            )
        else:
            hits = self._milvus_store.search(kb_id, vector, limit=limit)
        if self._reranker is not None:
            try:
                hits = self._reranker.rerank(query, hits, top_k=limit)
            except Exception:
                hits = hits[:limit]
        if expand_context and self._context_window > 0:
            hits = self._expand_context(kb_id, hits)
            hits = self._merge_overlapping(kb_id, hits)
        return hits

    def _merge_overlapping(self, kb_id: str, hits: list[dict]) -> list[dict]:
        """同一文档中位置相邻/重叠的命中合并为一条，避免结果重复。"""
        max_chunks = self._max_merged_chunks
        merged: list[dict] = []
        for hit in hits:
            span = hit.get("chunk_span")
            document_id = hit.get("document_id")
            if not span or not document_id:
                merged.append(hit)
                continue

            target = None
            for existing in merged:
                existing_span = existing.get("chunk_span")
                if existing.get("document_id") != document_id or not existing_span:
                    continue
                if (
                    span[0] <= existing_span[1] + 1
                    and existing_span[0] <= span[1] + 1
                ):
                    target = existing
                    break

            if target is None:
                merged.append(hit)
                continue

            start = min(span[0], target["chunk_span"][0])
            end = max(span[1], target["chunk_span"][1])
            if end - start + 1 > max_chunks:
                merged.append(hit)
                continue
            if [start, end] != target["chunk_span"]:
                chunk_ids = [
                    f"{document_id}:{offset}"
                    for offset in range(start, end + 1)
                ]
                rows = self._milvus_store.chunks_by_ids(kb_id, chunk_ids)
                rows.sort(key=lambda row: _chunk_index(row.get("chunk_id") or ""))
                target["text"] = merge_chunks(
                    [row.get("text") or "" for row in rows]
                )
                target["chunk_span"] = [start, end]
            target["score"] = max(
                float(target.get("score") or 0),
                float(hit.get("score") or 0),
            )
            target["merged_count"] = int(target.get("merged_count") or 1) + 1
        return merged

    def _expand_context(self, kb_id: str, hits: list[dict]) -> list[dict]:
        """把命中分块与前后相邻分块拼起来，避免结果过于碎片化。"""
        window = self._context_window
        cache: dict[str, dict] = {}

        for hit in hits:
            chunk_id = str(hit.get("chunk_id") or "")
            document_id, separator, index_text = chunk_id.rpartition(":")
            if not separator:
                continue
            try:
                index = int(index_text)
            except ValueError:
                continue

            offsets = range(max(0, index - window), index + window + 1)
            wanted = [f"{document_id}:{offset}" for offset in offsets]
            missing = [item for item in wanted if item not in cache]
            if missing:
                for row in self._milvus_store.chunks_by_ids(kb_id, missing):
                    cache[str(row.get("chunk_id"))] = row

            available_offsets = [
                offset
                for offset in offsets
                if f"{document_id}:{offset}" in cache
            ]
            if len(available_offsets) <= 1:
                continue

            texts = [
                cache[f"{document_id}:{offset}"].get("text") or ""
                for offset in available_offsets
            ]
            hit["text"] = merge_chunks(texts)
            hit["chunk_span"] = [
                available_offsets[0],
                available_offsets[-1],
            ]
        return hits
