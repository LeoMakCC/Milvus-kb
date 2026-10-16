from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedSection:
    text: str
    section: str | None = None
    page_no: int = -1


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    text: str
    doc_type: str = "markdown"
    sections: list[ParsedSection] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentChunk:
    chunk_index: int
    text: str
    section: str | None = None
    page_no: int = -1


@dataclass(frozen=True)
class SyncResult:
    scanned: int
    inserted: int
    skipped: int
    failed: int
    attachments_inserted: int = 0
    attachments_reused: int = 0
