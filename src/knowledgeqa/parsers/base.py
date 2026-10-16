from __future__ import annotations

from pathlib import Path
from typing import Protocol

from knowledgeqa.ingestion.models import ParsedDocument


class UnsupportedDocumentError(ValueError):
    pass


class OcrRequiredError(ValueError):
    pass


class DocumentParser(Protocol):
    extensions: set[str]

    def parse(self, path: Path) -> ParsedDocument: ...
