from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    dimension: int = 512


class SyncRequest(BaseModel):
    directory: str


class AddDocumentsRequest(BaseModel):
    paths: list[str]


def create_kbs_router(
    repository,
    ingestion_service,
    milvus_store=None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/kbs")
    def list_knowledge_bases():
        return repository.list_knowledge_bases()

    @router.get("/kbs/{kb_id}/documents")
    def list_knowledge_base_documents(kb_id: str):
        if repository.get_knowledge_base(kb_id) is None:
            raise HTTPException(404, "Knowledge base not found")
        rows = repository.list_documents_with_chunk_counts(kb_id)
        documents = [
            {
                "id": row["id"],
                "file_name": row["file_name"],
                "doc_type": row["doc_type"],
                "source_type": row["source_type"],
                "index_status": row["index_status"],
                "chunk_count": int(row.get("chunk_count") or 0),
                "size_bytes": row.get("size_bytes"),
                "indexed_at": row.get("indexed_at"),
                "last_error": row.get("last_error"),
            }
            for row in rows
        ]
        entities = None
        if milvus_store is not None:
            try:
                entities = milvus_store.count_entities(kb_id)
            except Exception:  # noqa: BLE001
                entities = None
        return {
            "documents": documents,
            "summary": {
                "documents": len(documents),
                "indexed": sum(
                    1
                    for item in documents
                    if item["index_status"] == "indexed"
                ),
                "failed": sum(
                    1 for item in documents if item["index_status"] == "failed"
                ),
                "chunks": sum(item["chunk_count"] for item in documents),
                "milvus_entities": entities,
            },
        }

    @router.post("/kbs")
    def create_knowledge_base(request: CreateKnowledgeBaseRequest):
        try:
            return repository.create_knowledge_base(
                name=request.name,
                dimension=request.dimension,
            )
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/kbs/{kb_id}/sync")
    def sync_knowledge_base(kb_id: str, request: SyncRequest):
        if ingestion_service is None:
            raise HTTPException(503, "Ingestion service is not configured")
        try:
            if hasattr(ingestion_service, "sync_all"):
                result = ingestion_service.sync_all(
                    kb_id,
                    Path(request.directory),
                )
            elif hasattr(ingestion_service, "sync_documents"):
                result = ingestion_service.sync_documents(
                    kb_id,
                    Path(request.directory),
                )
            else:
                result = ingestion_service.sync_markdown(
                    kb_id,
                    Path(request.directory),
                )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return asdict(result)

    @router.post("/kbs/{kb_id}/documents")
    def add_documents(kb_id: str, request: AddDocumentsRequest):
        if ingestion_service is None:
            raise HTTPException(503, "Ingestion service is not configured")
        if not request.paths:
            raise HTTPException(400, "No document paths provided")
        try:
            result = ingestion_service.sync_files(
                kb_id,
                [Path(item) for item in request.paths],
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return asdict(result)

    @router.delete("/kbs/{kb_id}")
    def delete_knowledge_base(kb_id: str):
        if repository.get_knowledge_base(kb_id) is None:
            raise HTTPException(404, "Knowledge base not found")
        dropped = False
        if milvus_store is not None:
            try:
                dropped = milvus_store.drop_collection(kb_id)
            except Exception:  # noqa: BLE001
                dropped = False
        repository.delete_knowledge_base(kb_id)
        return {"deleted": True, "milvus_dropped": dropped}

    @router.get("/kbs/{kb_id}/threads/{thread_id}")
    def email_thread(kb_id: str, thread_id: str):
        return {
            "thread_id": thread_id,
            "messages": repository.list_email_thread(kb_id, thread_id),
        }

    return router
