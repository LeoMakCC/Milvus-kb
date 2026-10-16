from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from knowledgeqa.ingestion.chunking import chunk_document
from knowledgeqa.ingestion.models import (
    ParsedDocument,
    ParsedSection,
    SyncResult,
)
from knowledgeqa.parsers.email_parser import parse_email_file

EMAIL_EXTENSIONS = {".eml", ".mbox", ".mbx", ".msg"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class EmailIngestionService:
    def __init__(
        self,
        repository,
        embedder,
        milvus_store,
        max_chars: int = 1000,
        overlap: int = 120,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self._milvus_store = milvus_store
        self._max_chars = max_chars
        self._overlap = overlap
        self._ensured_kbs: set[str] = set()

    def sync_emails(self, kb_id: str, directory: Path) -> SyncResult:
        kb = self._repository.get_knowledge_base(kb_id)
        if kb is None:
            raise ValueError(f"Knowledge base not found: {kb_id}")
        if not directory.is_dir():
            raise ValueError(f"Directory not found: {directory}")

        if kb_id not in self._ensured_kbs:
            self._milvus_store.ensure_collection(kb_id, int(kb["dimension"]))
            self._ensured_kbs.add(kb_id)

        scanned = inserted = skipped = failed = 0
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in EMAIL_EXTENSIONS:
                continue
            try:
                messages = parse_email_file(path)
            except Exception:
                scanned += 1
                failed += 1
                continue

            for message in messages:
                scanned += 1
                if message.message_id and self._repository.get_email_by_message_id(
                    kb_id,
                    message.message_id,
                ):
                    skipped += 1
                    continue
                if self._repository.get_email_by_hash(kb_id, message.message_hash):
                    skipped += 1
                    continue

                try:
                    canonical_path = (
                        f"{path.resolve()}::{message.message_hash}"
                    )
                    document = self._repository.upsert_document(
                        kb_id=kb_id,
                        canonical_path=canonical_path,
                        file_name=path.name,
                        doc_type="email",
                        source_type="email_file",
                        source_hash=message.message_hash,
                        index_status="indexing",
                    )
                    self._milvus_store.delete_document(kb_id, document["id"])

                    parsed = ParsedDocument(
                        title=message.subject or path.stem,
                        text=message.body_text,
                        doc_type="email",
                        sections=[
                            ParsedSection(
                                text=message.body_text,
                                section=message.subject or None,
                            )
                        ]
                        if message.body_text
                        else [],
                    )
                    chunks = chunk_document(
                        parsed,
                        max_chars=self._max_chars,
                        overlap=self._overlap,
                    )
                    milvus_ids: list[int] = []
                    if chunks:
                        vectors = self._embedder.embed(
                            [chunk.text for chunk in chunks]
                        )
                        rows = [
                            {
                                "vector": vector,
                                "text": chunk.text,
                                "kb_id": kb_id,
                                "document_id": document["id"],
                                "chunk_id": (
                                    f"{document['id']}:{chunk.chunk_index}"
                                ),
                                "page_no": -1,
                                "doc_type": "email",
                                "source_type": "email_file",
                                "source_path": path.name,
                            }
                            for chunk, vector in zip(chunks, vectors)
                        ]
                        milvus_ids = self._milvus_store.insert_chunks(
                            kb_id,
                            rows,
                        )

                    self._repository.replace_chunks(
                        document["id"],
                        [
                            {
                                "chunk_index": chunk.chunk_index,
                                "chunk_hash": hashlib.sha256(
                                    chunk.text.encode("utf-8")
                                ).hexdigest(),
                                "milvus_id": (
                                    milvus_ids[index]
                                    if index < len(milvus_ids)
                                    else None
                                ),
                                "page_no": -1,
                                "section_path": chunk.section,
                            }
                            for index, chunk in enumerate(chunks)
                        ],
                    )
                    self._repository.upsert_email(
                        document_id=document["id"],
                        message_id=message.message_id,
                        thread_id=message.thread_id,
                        subject=message.subject,
                        from_addr=message.from_addr,
                        to_addr=message.to_addr,
                        cc_addr=message.cc_addr,
                        sent_at=message.sent_at,
                        message_hash=message.message_hash,
                    )
                    self._repository.upsert_document(
                        kb_id=kb_id,
                        canonical_path=canonical_path,
                        file_name=path.name,
                        doc_type="email",
                        source_type="email_file",
                        source_hash=message.message_hash,
                        index_status="indexed",
                        indexed_at=_utc_now(),
                    )
                    inserted += 1
                except Exception:
                    failed += 1

        return SyncResult(
            scanned=scanned,
            inserted=inserted,
            skipped=skipped,
            failed=failed,
        )
