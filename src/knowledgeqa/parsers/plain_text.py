from __future__ import annotations

from pathlib import Path

from knowledgeqa.ingestion.models import ParsedDocument, ParsedSection


class PlainTextParser:
    extensions = {
        ".txt",
        ".log",
        ".py",
        ".js",
        ".ts",
        ".java",
        ".go",
        ".sql",
        ".json",
        ".yaml",
        ".yml",
    }

    def parse(self, path: Path) -> ParsedDocument:
        text = path.read_text(encoding="utf-8-sig", errors="ignore").strip()
        doc_type = path.suffix.lower().lstrip(".")
        return ParsedDocument(
            title=path.stem,
            text=text,
            doc_type=doc_type,
            sections=[ParsedSection(text=text)] if text else [],
        )
