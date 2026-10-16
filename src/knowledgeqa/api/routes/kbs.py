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


def create_kbs_router(repository, ingestion_service) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/kbs")
    def list_knowledge_bases():
        return repository.list_knowledge_bases()

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

    return router
