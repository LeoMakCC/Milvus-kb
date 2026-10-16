from email.message import EmailMessage
from pathlib import Path

from knowledgeqa.services.email_ingestion import EmailIngestionService


class FakeRepository:
    def __init__(self) -> None:
        self.knowledge_base = {"id": "kb1", "dimension": 2}
        self.documents_by_path = {}
        self.documents_by_hash = {}
        self.chunks = {}
        self.emails_by_message_id = {}
        self.emails_by_hash = {}
        self.email_attachments = []
        self.next_document = 1

    def get_knowledge_base(self, kb_id: str):
        return self.knowledge_base if kb_id == "kb1" else None

    def get_document_by_path(self, kb_id: str, canonical_path: str):
        return self.documents_by_path.get(canonical_path)

    def upsert_document(self, **fields):
        path = fields["canonical_path"]
        existing = self.documents_by_path.get(path)
        document = dict(existing or {})
        document.update(fields)
        document["id"] = existing["id"] if existing else f"doc{self.next_document}"
        if not existing:
            self.next_document += 1
        self.documents_by_path[path] = document
        if fields.get("source_hash"):
            self.documents_by_hash[fields["source_hash"]] = document
        return document

    def replace_chunks(self, document_id: str, chunks: list[dict]) -> None:
        self.chunks[document_id] = chunks

    def upsert_email(self, document_id: str, **fields):
        email = {"document_id": document_id, **fields}
        if fields.get("message_id"):
            self.emails_by_message_id[fields["message_id"]] = email
        self.emails_by_hash[fields["message_hash"]] = email
        return email

    def get_email_by_message_id(self, kb_id: str, message_id: str):
        return self.emails_by_message_id.get(message_id)

    def get_email_by_hash(self, kb_id: str, message_hash: str):
        return self.emails_by_hash.get(message_hash)

    def get_document_by_source_hash(self, kb_id: str, source_hash: str):
        return self.documents_by_hash.get(source_hash)

    def upsert_email_attachment(self, **fields):
        existing = next(
            (
                item
                for item in self.email_attachments
                if item["email_document_id"] == fields["email_document_id"]
                and item["file_name"] == fields["file_name"]
                and item["content_hash"] == fields["content_hash"]
            ),
            None,
        )
        if existing:
            existing.update(fields)
            return existing
        item = {"id": f"attachment-{len(self.email_attachments) + 1}", **fields}
        self.email_attachments.append(item)
        return item


class FakeEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]


class FakeMilvusStore:
    def __init__(self) -> None:
        self.ensured = []
        self.inserted = []
        self.deleted = []

    def ensure_collection(self, kb_id: str, dimension: int) -> None:
        self.ensured.append((kb_id, dimension))

    def delete_document(self, kb_id: str, document_id: str) -> None:
        self.deleted.append((kb_id, document_id))

    def insert_chunks(self, kb_id: str, rows: list[dict]) -> list[int]:
        self.inserted.append((kb_id, rows))
        return list(range(1, len(rows) + 1))


def write_email(path: Path, message_id: str = "<abc@example.com>") -> None:
    message = EmailMessage()
    message["Subject"] = "付款条件"
    message["From"] = "a@example.com"
    message["To"] = "b@example.com"
    message["Date"] = "Thu, 16 Oct 2026 10:00:00 +0800"
    message["Message-ID"] = message_id
    message.set_content("验收后30日内付款。")
    path.write_bytes(message.as_bytes())


def test_sync_emails_indexes_email_and_skips_duplicate(tmp_path: Path) -> None:
    write_email(tmp_path / "one.eml")
    write_email(tmp_path / "two.eml")
    repository = FakeRepository()
    store = FakeMilvusStore()
    service = EmailIngestionService(repository, FakeEmbedder(), store)

    result = service.sync_emails("kb1", tmp_path)

    assert result.scanned == 2
    assert result.inserted == 1
    assert result.skipped == 1
    assert len(store.inserted) == 1
    assert store.inserted[0][1][0]["doc_type"] == "email"
    assert repository.emails_by_message_id["<abc@example.com>"]["subject"] == "付款条件"


def test_sync_emails_indexes_attachment_names(tmp_path: Path) -> None:
    message = EmailMessage()
    message["Subject"] = "附件邮件"
    message["From"] = "a@example.com"
    message["To"] = "b@example.com"
    message["Message-ID"] = "<attachment@example.com>"
    message.set_content("正文")
    message.add_attachment(
        b"terms",
        maintype="text",
        subtype="plain",
        filename="terms.txt",
    )
    (tmp_path / "attachment.eml").write_bytes(message.as_bytes())
    store = FakeMilvusStore()
    service = EmailIngestionService(FakeRepository(), FakeEmbedder(), store)

    result = service.sync_emails("kb1", tmp_path)

    assert result.inserted == 1
    assert "附件: terms.txt" in store.inserted[0][1][0]["text"]


def test_sync_emails_indexes_and_reuses_attachment_content(tmp_path: Path) -> None:
    for index, message_id in enumerate(
        ["<one@example.com>", "<two@example.com>"],
        start=1,
    ):
        message = EmailMessage()
        message["Subject"] = f"附件邮件 {index}"
        message["From"] = "a@example.com"
        message["To"] = "b@example.com"
        message["Message-ID"] = message_id
        message.set_content(f"正文 {index}")
        message.add_attachment(
            b"attachment content about supplier delay",
            maintype="text",
            subtype="plain",
            filename="terms.txt",
        )
        (tmp_path / f"mail{index}.eml").write_bytes(message.as_bytes())

    repository = FakeRepository()
    store = FakeMilvusStore()
    service = EmailIngestionService(repository, FakeEmbedder(), store)

    result = service.sync_emails("kb1", tmp_path)

    assert result.inserted == 2
    assert result.attachments_inserted == 1
    assert result.attachments_reused == 1
    attachment_documents = [
        document
        for document in repository.documents_by_path.values()
        if document.get("source_type") == "email_attachment"
    ]
    assert len(attachment_documents) == 1
    assert attachment_documents[0]["parent_document_id"]
    attachment_rows = [
        row
        for _, rows in store.inserted
        for row in rows
        if row.get("source_type") == "email_attachment"
    ]
    assert len(attachment_rows) == 1
    assert "supplier delay" in attachment_rows[0]["text"]
    assert len(repository.email_attachments) == 2
