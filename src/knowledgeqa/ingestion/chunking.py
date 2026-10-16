from __future__ import annotations

import re

from knowledgeqa.ingestion.models import DocumentChunk, ParsedDocument

HEADING_SPLIT_RE = re.compile(r"(?m)(?=^#{1,4}\s)")
HEADING_RE = re.compile(r"^(#{1,4}\s+.+?)\s*$")


def _section_name(text: str) -> str | None:
    first_line = text.splitlines()[0].strip()
    match = HEADING_RE.match(first_line)
    return match.group(1).strip() if match else None


def chunk_document(
    document: ParsedDocument,
    max_chars: int = 1000,
    overlap: int = 120,
) -> list[DocumentChunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be between 0 and max_chars")

    sections = [section.strip() for section in HEADING_SPLIT_RE.split(document.text)]
    chunks: list[DocumentChunk] = []
    for section_text in sections:
        if not section_text:
            continue
        section = _section_name(section_text)
        if len(section_text) <= max_chars:
            chunks.append(
                DocumentChunk(
                    chunk_index=len(chunks),
                    text=section_text,
                    section=section,
                )
            )
            continue

        step = max_chars - overlap
        for start in range(0, len(section_text), step):
            piece = section_text[start:start + max_chars].strip()
            if len(piece) < 30:
                continue
            if section and not piece.startswith(section):
                piece = f"{section}\n{piece}"
            chunks.append(
                DocumentChunk(
                    chunk_index=len(chunks),
                    text=piece,
                    section=section,
                )
            )
    return chunks
