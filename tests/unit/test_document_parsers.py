from pathlib import Path

import pytest

from knowledgeqa.parsers.base import UnsupportedDocumentError
from knowledgeqa.parsers.registry import parse_document


def test_plain_text_parser_reads_python_file(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    document = parse_document(path)

    assert document.doc_type == "py"
    assert "def hello" in document.text


def test_html_parser_strips_markup(tmp_path: Path) -> None:
    path = tmp_path / "page.html"
    path.write_text(
        "<html><head><title>标题</title></head><body><p>正文内容</p></body></html>",
        encoding="utf-8",
    )

    document = parse_document(path)

    assert document.title == "标题"
    assert "正文内容" in document.text
    assert "<p>" not in document.text


def test_csv_parser_turns_rows_into_lines(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("name,value\nalpha,1\n", encoding="utf-8")

    document = parse_document(path)

    assert "name | value" in document.text
    assert "alpha | 1" in document.text


def test_unknown_extension_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unknown.xyz"
    path.write_text("data", encoding="utf-8")

    with pytest.raises(UnsupportedDocumentError):
        parse_document(path)
