from __future__ import annotations

from typing import Any

from knowledgeqa.milvus.schema import collection_name, create_knowledge_base_collection


class MilvusStore:
    def __init__(self, uri: str, client: Any | None = None) -> None:
        self._uri = uri
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=self._uri)
        return self._client

    def is_available(self) -> bool:
        try:
            self.client.list_collections()
            return True
        except Exception:
            return False

    def ensure_collection(self, kb_id: str, dimension: int) -> None:
        name = collection_name(kb_id)
        if not self.client.has_collection(name):
            create_knowledge_base_collection(self.client, kb_id, dimension)

    def delete_document(self, kb_id: str, document_id: str) -> None:
        self.client.delete(
            collection_name(kb_id),
            filter=f'document_id == "{document_id}"',
        )

    def insert_chunks(self, kb_id: str, rows: list[dict]) -> list[int]:
        name = collection_name(kb_id)
        result = self.client.insert(name, rows)
        self.client.flush(name)
        return list(result.get("ids") or result.get("primary_keys") or [])

    def search(
        self,
        kb_id: str,
        vector: list[float],
        limit: int = 5,
    ) -> list[dict]:
        name = collection_name(kb_id)
        self.client.load_collection(name)
        results = self.client.search(
            name,
            data=[vector],
            limit=limit,
            output_fields=[
                "text",
                "document_id",
                "chunk_id",
                "page_no",
                "doc_type",
                "source_type",
            ],
            search_params={
                "metric_type": "COSINE",
                "params": {"ef": 128},
            },
            anns_field="vector",
        )
        hits: list[dict] = []
        for hit in results[0]:
            entity = dict(hit.get("entity") or {})
            hits.append(
                {
                    "id": hit.get("id"),
                    "score": hit.get("distance"),
                    **entity,
                }
            )
        return hits
