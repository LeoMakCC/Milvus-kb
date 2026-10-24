from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class SearchRequest(BaseModel):
    kb_id: str
    query: str
    limit: int = 5
    expand_context: bool = True


def create_search_router(search_service) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/search")
    def search(request: SearchRequest):
        try:
            hits = search_service.search(
                kb_id=request.kb_id,
                query=request.query,
                limit=request.limit,
                expand_context=request.expand_context,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"hits": hits}

    return router
