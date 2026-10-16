from __future__ import annotations


class SearchService:
    def __init__(
        self,
        repository,
        embedder,
        milvus_store,
        reranker=None,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self._milvus_store = milvus_store
        self._reranker = reranker

    def search(self, kb_id: str, query: str, limit: int = 5) -> list[dict]:
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
        return hits
