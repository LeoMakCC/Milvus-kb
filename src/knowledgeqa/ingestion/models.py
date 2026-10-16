from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    text: str
    doc_type: str = "markdown"


@dataclass(frozen=True)
class DocumentChunk:
    chunk_index: int
    text: str
    section: str | None = None


@dataclass(frozen=True)
class SyncResult:
    scanned: int
    inserted: int
    skipped: int
    failed: int
