from __future__ import annotations

import json

from fastapi import APIRouter
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
    def list_conversations():
        return repository.list_conversations()

    @router.get("/conversations/{conversation_id}")
    def get_conversation(conversation_id: str):
        return {
            "conversation": repository.get_conversation(conversation_id),
            "messages": repository.list_messages(conversation_id),
        }

    return router
