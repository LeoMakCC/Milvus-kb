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


def test_upsert_email_and_find_by_message_id(tmp_path: Path) -> None:
    repo = Repository(tmp_path / "meta.db")
    repo.initialize()
    kb = repo.create_knowledge_base(name="邮件", dimension=2)
    document = repo.upsert_document(
        kb_id=kb["id"],
        canonical_path="mail#1",
        file_name="mail.eml",
        doc_type="email",
        source_type="email_file",
        source_hash="hash",
        index_status="indexed",
    )

    repo.upsert_email(
        document_id=document["id"],
        message_id="<abc@example.com>",
        thread_id="<thread@example.com>",
        subject="付款条件",
        from_addr="a@example.com",
        to_addr="b@example.com",
        cc_addr="",
        sent_at="2026-10-16T00:00:00Z",
        message_hash="mh1",
    )

    assert (
        repo.get_email_by_message_id(kb["id"], "<abc@example.com>")["subject"]
        == "付款条件"
    )
    assert repo.get_email_by_hash(kb["id"], "mh1")["document_id"] == document["id"]


def test_link_email_attachments_and_list_thread(tmp_path: Path) -> None:
    repo = Repository(tmp_path / "meta.db")
    repo.initialize()
    kb = repo.create_knowledge_base(name="附件", dimension=2)
    email_document = repo.upsert_document(
        kb_id=kb["id"],
        canonical_path="mail#1",
        file_name="mail.eml",
        doc_type="email",
        source_type="email_file",
        source_hash="mail-hash",
        index_status="indexed",
    )
    repo.upsert_email(
        document_id=email_document["id"],
        message_id="<abc@example.com>",
        thread_id="<thread@example.com>",
        subject="付款条件",
        from_addr="a@example.com",
        to_addr="b@example.com",
        cc_addr="",
        sent_at="2026-10-16T00:00:00Z",
        message_hash="mh1",
    )
    attachment_document = repo.upsert_document(
        kb_id=kb["id"],
        canonical_path="mail#1::terms.txt",
        file_name="terms.txt",
        doc_type="txt",
        source_type="email_attachment",
        source_hash="attach-hash",
        index_status="indexed",
        parent_document_id=email_document["id"],
    )

    repo.upsert_email_attachment(
        email_document_id=email_document["id"],
        attachment_document_id=attachment_document["id"],
        file_name="terms.txt",
        content_type="text/plain",
        content_hash="attach-hash",
    )

    assert repo.get_document_by_source_hash(kb["id"], "attach-hash")["id"] == attachment_document["id"]
    assert repo.list_email_attachments(email_document["id"])[0]["file_name"] == "terms.txt"
    assert repo.list_email_thread(kb["id"], "<thread@example.com>")[0]["message_id"] == "<abc@example.com>"


def test_conversation_and_messages(tmp_path: Path) -> None:
    repo = Repository(tmp_path / "meta.db")
    repo.initialize()

    conversation = repo.create_conversation(
        kb_ids=["kb1"],
        provider_name="test-provider",
        model_name="test-model",
    )
    repo.add_message(conversation["id"], "user", "问题")
    repo.add_message(
        conversation["id"],
        "assistant",
        "回答",
        citations_json="[1]",
    )

    assert repo.list_conversations()[0]["id"] == conversation["id"]
    assert [
        message["role"]
        for message in repo.list_messages(conversation["id"])
    ] == ["user", "assistant"]
    assert repo.get_conversation(conversation["id"])["model_name"] == "test-model"


def test_provider_config_round_trip(tmp_path: Path) -> None:
    repo = Repository(tmp_path / "meta.db")
    repo.initialize()

    provider = repo.upsert_provider_config(
        name="local",
        provider_type="openai_compatible",
        base_url="http://127.0.0.1:8899/v1",
        model_name="mock",
        encrypted_secret=b"secret",
        enabled=True,
    )
    repo.set_active_provider(provider["id"])

    assert repo.get_provider_config(provider["id"])["name"] == "local"
    assert repo.get_provider_config_by_name("local")["model_name"] == "mock"
    assert repo.list_provider_configs()[0]["id"] == provider["id"]
    assert repo.get_active_provider_config()["id"] == provider["id"]

    repo.delete_provider_config(provider["id"])
    assert repo.get_provider_config(provider["id"]) is None


def test_app_settings_round_trip(tmp_path: Path) -> None:
    repo = Repository(tmp_path / "meta.db")
    repo.initialize()

    repo.set_setting("lan_enabled", "1")
    repo.set_setting("shared_password_hash", "hash")

    assert repo.get_setting("lan_enabled") == "1"
    assert repo.get_setting("missing", "default") == "default"
    assert repo.get_app_settings()["shared_password_hash"] == "hash"
