from pathlib import Path

from knowledgeqa.repository import Repository


def test_create_and_list_knowledge_base(tmp_path: Path) -> None:
    repo = Repository(tmp_path / "meta.db")
    repo.initialize()

    kb = repo.create_knowledge_base(name="项目A", dimension=512)

    assert kb["name"] == "项目A"
    assert kb["collection_name"].startswith("kb_")
    assert repo.list_knowledge_bases()[0]["id"] == kb["id"]
    assert repo.get_knowledge_base(kb["id"])["dimension"] == 512


def test_upsert_document_and_replace_chunks(tmp_path: Path) -> None:
    repo = Repository(tmp_path / "meta.db")
    repo.initialize()
    kb = repo.create_knowledge_base(name="项目A", dimension=512)

    document = repo.upsert_document(
        kb_id=kb["id"],
        canonical_path=str(tmp_path / "a.md"),
        file_name="a.md",
        doc_type="markdown",
        source_type="local_file",
        source_hash="hash1",
        index_status="indexed",
    )
    repo.replace_chunks(
        document["id"],
        [
            {
                "chunk_index": 0,
                "chunk_hash": "chunk1",
                "milvus_id": 1,
                "section_path": "# A",
            }
        ],
    )

    assert repo.list_documents(kb["id"])[0]["file_name"] == "a.md"
    assert repo.list_chunks(document["id"])[0]["chunk_hash"] == "chunk1"

    updated = repo.upsert_document(
        kb_id=kb["id"],
        canonical_path=str(tmp_path / "a.md"),
        file_name="a.md",
        doc_type="markdown",
        source_type="local_file",
        source_hash="hash2",
        index_status="indexed",
    )

    assert updated["id"] == document["id"]
    assert updated["source_hash"] == "hash2"
