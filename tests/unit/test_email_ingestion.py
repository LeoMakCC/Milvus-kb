from email.message import EmailMessage
from pathlib import Path

from knowledgeqa.services.email_ingestion import EmailIngestionService


class FakeRepository:
    def __init__(self) -> None:
        self.knowledge_base = {"id": "kb1", "dimension": 2}
        self.documents_by_path = {}
        self.chunks = {}
        self.emails_by_message_id = {}
        self.emails_by_hash = {}
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
