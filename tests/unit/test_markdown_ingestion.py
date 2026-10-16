from pathlib import Path

from knowledgeqa.ingestion.chunking import chunk_document
from knowledgeqa.ingestion.models import ParsedDocument
from knowledgeqa.parsers.markdown import parse_markdown


def test_markdown_parser_uses_first_h1_as_title(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text("# 合同说明\n\n付款条件...", encoding="utf-8")

    document = parse_markdown(path)

    assert document.title == "合同说明"
    assert document.text.startswith("# 合同说明")


def test_markdown_parser_falls_back_to_file_stem(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("没有标题的正文", encoding="utf-8")

    document = parse_markdown(path)

    assert document.title == "README"


def test_chunker_splits_long_markdown_and_preserves_section() -> None:
    document = ParsedDocument(
        title="doc",
        text="# A\n" + "甲" * 1200 + "\n# B\n" + "乙" * 1200,
    )

    chunks = chunk_document(document, max_chars=500, overlap=80)

    assert len(chunks) >= 4
    assert chunks[0].section == "# A"
    assert chunks[-1].section == "# B"
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
