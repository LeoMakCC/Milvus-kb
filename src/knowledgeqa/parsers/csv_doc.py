from __future__ import annotations

import csv
from pathlib import Path

from knowledgeqa.ingestion.models import ParsedDocument, ParsedSection


class CsvParser:
    extensions = {".csv"}

    def parse(self, path: Path) -> ParsedDocument:
        lines: list[str] = []
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
            for row in csv.reader(handle):
                lines.append(" | ".join(cell.strip() for cell in row))
        text = "\n".join(line for line in lines if line)
        return ParsedDocument(
            title=path.stem,
            text=text,
            doc_type="csv",
            sections=[ParsedSection(text=text)] if text else [],
        )
