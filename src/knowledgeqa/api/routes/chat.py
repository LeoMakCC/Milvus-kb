from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


class ChatStreamRequest(BaseModel):
    kb_ids: list[str]
    query: str
    conversation_id: str | None = None


def _event_stream(answer_service, request: ChatStreamRequest):
    for event in answer_service.stream_answer(
        kb_ids=request.kb_ids,
        query=request.query,
        conversation_id=request.conversation_id,
    ):
        event_type = event.get("type", "message")
        yield (
            f"event: {event_type}\n"
            f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        )


def create_chat_router(answer_service, repository) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/chat/stream")
    def chat_stream(request: ChatStreamRequest):
        return StreamingResponse(
            _event_stream(answer_service, request),
            media_type="text/event-stream",
        )

    @router.get("/conversations")
    def list_conversations(archived: bool = False):
        return repository.list_conversations(only_archived=archived)

    @router.get("/conversations/{conversation_id}")
    def get_conversation(conversation_id: str):
        return {
            "conversation": repository.get_conversation(conversation_id),
            "messages": repository.list_messages(conversation_id),
        }

    @router.post("/conversations/{conversation_id}/archive")
    def archive_conversation(conversation_id: str):
        conversation = repository.set_conversation_archived(
            conversation_id,
            True,
        )
        if conversation is None:
            raise HTTPException(404, "Conversation not found")
        return {"ok": True, "archived": True}

    @router.post("/conversations/{conversation_id}/unarchive")
    def unarchive_conversation(conversation_id: str):
        conversation = repository.set_conversation_archived(
            conversation_id,
            False,
        )
        if conversation is None:
            raise HTTPException(404, "Conversation not found")
        return {"ok": True, "archived": False}

    return router
