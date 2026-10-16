from __future__ import annotations

from typing import Protocol


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        hits: list[dict],
        top_k: int,
    ) -> list[dict]: ...


class NoopReranker:
    def rerank(
        self,
        query: str,
        hits: list[dict],
        top_k: int,
    ) -> list[dict]:
        return hits[:top_k]


class HttpReranker:
    def __init__(
        self,
        endpoint: str,
        api_key: str = "",
        model: str = "rerank-model",
        client=None,
        timeout: float = 30.0,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._model = model
        self._client = client
        self._timeout = timeout

    def _get_client(self):
        if self._client is None:
            import httpx

            self._client = httpx.Client()
        return self._client

    def rerank(
        self,
        query: str,
        hits: list[dict],
        top_k: int,
    ) -> list[dict]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        response = self._get_client().post(
            self._endpoint,
            headers=headers,
            json={
                "model": self._model,
                "query": query,
                "documents": [hit.get("text", "") for hit in hits],
                "top_n": top_k,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        reranked: list[dict] = []
        for item in data.get("results", []):
            index = item.get("index")
            if index is None or not 0 <= index < len(hits):
                continue
            hit = dict(hits[index])
            hit["rerank_score"] = item.get("relevance_score")
            reranked.append(hit)
        return reranked[:top_k] if reranked else hits[:top_k]
