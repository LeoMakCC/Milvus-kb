from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from knowledgeqa.ingestion.models import ParsedDocument, ParsedSection


class HtmlParser:
    extensions = {".html", ".htm"}

    def parse(self, path: Path) -> ParsedDocument:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(raw, "html.parser")
        text = soup.get_text("\n", strip=True)
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else path.stem
        return ParsedDocument(
            title=title or path.stem,
            text=text,
            doc_type="html",
            sections=[ParsedSection(text=text, section=title or None)] if text else [],
        )
