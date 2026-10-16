from __future__ import annotations

from pathlib import Path

from knowledgeqa.ingestion.models import ParsedDocument
from knowledgeqa.parsers.base import DocumentParser, UnsupportedDocumentError
from knowledgeqa.parsers.csv_doc import CsvParser
from knowledgeqa.parsers.docx import DocxParser
from knowledgeqa.parsers.html import HtmlParser
from knowledgeqa.parsers.markdown import parse_markdown
from knowledgeqa.parsers.pdf import PdfParser
from knowledgeqa.parsers.plain_text import PlainTextParser
from knowledgeqa.parsers.pptx import PptxParser
from knowledgeqa.parsers.xlsx import XlsxParser


class MarkdownParser:
    extensions = {".md", ".markdown"}

    def parse(self, path: Path) -> ParsedDocument:
        return parse_markdown(path)


PARSERS: list[DocumentParser] = [
    MarkdownParser(),
    PlainTextParser(),
    HtmlParser(),
    CsvParser(),
    PdfParser(),
    DocxParser(),
    XlsxParser(),
    PptxParser(),
]


def parser_for(path: Path) -> DocumentParser:
    suffix = path.suffix.lower()
    for parser in PARSERS:
        if suffix in parser.extensions:
            return parser
    raise UnsupportedDocumentError(f"Unsupported document extension: {suffix}")


def parse_document(path: Path) -> ParsedDocument:
    return parser_for(path).parse(path)


def supported_extensions() -> set[str]:
    extensions: set[str] = set()
    for parser in PARSERS:
        extensions.update(parser.extensions)
    return extensions
