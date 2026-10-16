from __future__ import annotations

from pathlib import Path

import pymupdf

from knowledgeqa.ingestion.models import ParsedDocument, ParsedSection
from knowledgeqa.parsers.base import OcrRequiredError


class PdfParser:
    extensions = {".pdf"}

    def parse(self, path: Path) -> ParsedDocument:
        document = pymupdf.open(path)
        try:
            sections: list[ParsedSection] = []
            for page_no, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                if text:
                    sections.append(
                        ParsedSection(
                            text=text,
                            section=f"第 {page_no} 页",
                            page_no=page_no,
                        )
                    )
            if not sections:
                raise OcrRequiredError(f"PDF contains no extractable text: {path}")
            title = (document.metadata or {}).get("title") or path.stem
            return ParsedDocument(
                title=title,
                text="\n\n".join(section.text for section in sections),
                doc_type="pdf",
                sections=sections,
            )
        finally:
            document.close()
