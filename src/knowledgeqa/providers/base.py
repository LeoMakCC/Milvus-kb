from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatRequest:
    messages: list[ChatMessage]
    model: str | None = None
    temperature: float = 0.3


@dataclass(frozen=True)
class ChatChunk:
    text: str
    done: bool = False


@dataclass(frozen=True)
class ChatResponse:
    text: str
    usage: dict | None = None


class ChatProvider(Protocol):
    def chat(self, request: ChatRequest) -> ChatResponse: ...

    def stream_chat(self, request: ChatRequest):
        ...
