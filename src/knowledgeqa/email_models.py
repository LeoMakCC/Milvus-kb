from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmailAttachment:
    file_name: str
    content_type: str
    payload: bytes


@dataclass(frozen=True)
class ParsedEmail:
    message_id: str | None
    thread_id: str | None
    subject: str
    from_addr: str
    to_addr: str
    cc_addr: str
    sent_at: str
    body_text: str
    message_hash: str
    source_path: str
    attachments: list[EmailAttachment] = field(default_factory=list)
