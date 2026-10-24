from __future__ import annotations

import json
from collections.abc import Iterator

from knowledgeqa.providers.base import ChatMessage, ChatRequest

NO_ANSWER_TEXT = "知识库中没有找到足够依据。"

DEFAULT_CONVERSATION_TITLE = "新会话"
TITLE_MAX_CHARS = 24


def conversation_title(query: str, limit: int = TITLE_MAX_CHARS) -> str:
    """用首条提问生成会话标题，过长时截断并加省略号。"""
    text = " ".join(query.split())
    if not text:
        return DEFAULT_CONVERSATION_TITLE
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"

SYSTEM_PROMPT = (
    "你是知识库问答助手。只能根据提供的知识片段回答。"
    "每个关键结论后标注对应的片段编号，例如 [1]、[2]。"
    "如果片段不足，直接说明知识库中没有找到足够依据，不要编造。"
)


def build_context(hits: list[dict]) -> str:
    parts: list[str] = []
    for index, hit in enumerate(hits, start=1):
        source = hit.get("source_path") or hit.get("document_id") or "unknown"
        parts.append(f"[{index}] 来源: {source}\n{hit.get('text', '')}")
    return "\n\n".join(parts)


def build_messages(
    history: list[dict],
    hits: list[dict],
    query: str,
) -> list[ChatMessage]:
    messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
    for message in history[-6:]:
        messages.append(
            ChatMessage(
                role=message["role"],
                content=message["content"],
            )
        )
    messages.append(
        ChatMessage(
            role="user",
            content=(
                f"知识片段:\n{build_context(hits)}\n\n"
                f"问题: {query}"
            ),
        )
    )
    return messages


class AnswerService:
    def __init__(
        self,
        repository,
        search_service,
        provider,
        model_name: str | None = None,
        query_rewriter=None,
        provider_resolver=None,
    ) -> None:
        self._repository = repository
        self._search_service = search_service
        self._provider = provider
        self._model_name = model_name
        self._query_rewriter = query_rewriter
        self._provider_resolver = provider_resolver

    def _conversation(
        self,
        kb_ids: list[str],
        conversation_id: str | None,
        title: str | None = None,
    ):
        if conversation_id:
            conversation = self._repository.get_conversation(conversation_id)
            if conversation is not None:
                current = (conversation.get("title") or "").strip()
                if title and current in ("", DEFAULT_CONVERSATION_TITLE):
                    self._repository.update_conversation_title(
                        conversation["id"],
                        title,
                    )
                    conversation = {**conversation, "title": title}
                return conversation
        return self._repository.create_conversation(
            kb_ids=kb_ids,
            model_name=self._model_name,
            title=title,
        )

    def stream_answer(
        self,
        kb_ids: list[str],
        query: str,
        conversation_id: str | None = None,
    ) -> Iterator[dict]:
        yield {"type": "status", "message": "正在检索"}
        conversation = self._conversation(
            kb_ids,
            conversation_id,
            title=conversation_title(query),
        )
        history = self._repository.list_messages(conversation["id"])
        effective_query = query
        if history and self._query_rewriter is not None:
            effective_query = self._query_rewriter(history, query)

        hits: list[dict] = []
        for kb_id in kb_ids:
            try:
                hits.extend(
                    self._search_service.search(
                        kb_id,
                        effective_query,
                        limit=5,
                    )
                )
            except ValueError:
                # 知识库已被删除时跳过，避免历史会话直接报错
                continue
        hits = sorted(
            hits,
            key=lambda hit: float(hit.get("score") or 0),
            reverse=True,
        )[:5]
        yield {"type": "retrieval", "hits": hits}

        self._repository.add_message(conversation["id"], "user", query)
        if not hits:
            message = self._repository.add_message(
                conversation["id"],
                "assistant",
                NO_ANSWER_TEXT,
                citations_json="[]",
            )
            yield {"type": "token", "text": NO_ANSWER_TEXT}
            yield {
                "type": "done",
                "conversation_id": conversation["id"],
                "message_id": message["id"],
            }
            return

        parts: list[str] = []
        try:
            provider = self._provider
            model_name = self._model_name
            if self._provider_resolver is not None:
                provider, model_name = self._provider_resolver()
            messages = build_messages(history, hits, query)
            for chunk in provider.stream_chat(
                ChatRequest(messages=messages, model=model_name)
            ):
                if chunk.done:
                    break
                if not chunk.text:
                    continue
                parts.append(chunk.text)
                yield {"type": "token", "text": chunk.text}

            answer = "".join(parts)
            citations = [
                {
                    "index": index,
                    "source_path": hit.get("source_path"),
                    "document_id": hit.get("document_id"),
                    "chunk_id": hit.get("chunk_id"),
                }
                for index, hit in enumerate(hits, start=1)
            ]
            message = self._repository.add_message(
                conversation["id"],
                "assistant",
                answer,
                citations_json=json.dumps(citations, ensure_ascii=False),
            )
            yield {
                "type": "done",
                "conversation_id": conversation["id"],
                "message_id": message["id"],
            }
        except Exception as exc:  # noqa: BLE001
            partial = "".join(parts)
            if partial:
                # 保留已生成的部分，避免用户看到的回答凭空消失
                self._repository.add_message(
                    conversation["id"],
                    "assistant",
                    partial,
                    citations_json="[]",
                )
            yield {
                "type": "error",
                "message": f"模型服务调用失败：{exc}",
            }
