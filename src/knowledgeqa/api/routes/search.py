from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class SearchRequest(BaseModel):
    kb_id: str
    query: str
    limit: int = 5


def create_search_router(search_service) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/search")
    def search(request: SearchRequest):
        try:
            hits = search_service.search(
                kb_id=request.kb_id,
                query=request.query,
                limit=request.limit,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"hits": hits}

    return router
