from __future__ import annotations

import re
from pathlib import Path

from knowledgeqa.ingestion.models import ParsedDocument

H1_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")


def parse_markdown(path: Path) -> ParsedDocument:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    match = H1_RE.search(text)
    title = match.group(1).strip() if match else path.stem
    return ParsedDocument(title=title, text=text, doc_type="markdown")
