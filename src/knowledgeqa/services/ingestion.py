from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from knowledgeqa.ingestion.chunking import chunk_document
from knowledgeqa.ingestion.models import SyncResult
from knowledgeqa.parsers.base import OcrRequiredError
from knowledgeqa.parsers.registry import parse_document, supported_extensions


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class IngestionService:
    def __init__(
        self,
        repository,
        embedder,
        milvus_store,
        max_chars: int = 1000,
        overlap: int = 120,
        email_ingestion_service=None,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self._milvus_store = milvus_store
        self._max_chars = max_chars
        self._overlap = overlap
        self._email_ingestion_service = email_ingestion_service
        self._ensured_kbs: set[str] = set()

    def sync_all(self, kb_id: str, directory: Path) -> SyncResult:
        document_result = self.sync_documents(kb_id, directory)
        if self._email_ingestion_service is None:
            return document_result
        email_result = self._email_ingestion_service.sync_emails(kb_id, directory)
        return SyncResult(
            scanned=document_result.scanned + email_result.scanned,
            inserted=document_result.inserted + email_result.inserted,
            skipped=document_result.skipped + email_result.skipped,
            failed=document_result.failed + email_result.failed,
            attachments_inserted=(
                document_result.attachments_inserted
                + email_result.attachments_inserted
            ),
            attachments_reused=(
                document_result.attachments_reused
                + email_result.attachments_reused
            ),
        )

    def sync_documents(self, kb_id: str, directory: Path) -> SyncResult:
        return self._sync(kb_id, directory, supported_extensions())

    def sync_markdown(self, kb_id: str, directory: Path) -> SyncResult:
        return self._sync(kb_id, directory, {".md", ".markdown"})

    def _sync(
        self,
        kb_id: str,
        directory: Path,
        extensions: set[str],
    ) -> SyncResult:
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
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue
            scanned += 1
            canonical_path = str(path.resolve())
            source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            existing = self._repository.get_document_by_path(kb_id, canonical_path)
            if (
                existing
                and existing.get("source_hash") == source_hash
                and existing.get("index_status") == "indexed"
            ):
                skipped += 1
                continue

            try:
                parsed = parse_document(path)
                chunks = chunk_document(
                    parsed,
                    max_chars=self._max_chars,
                    overlap=self._overlap,
                )
                stat = path.stat()
                document = self._repository.upsert_document(
                    kb_id=kb_id,
                    canonical_path=canonical_path,
                    file_name=path.name,
                    doc_type=parsed.doc_type,
                    source_type="local_file",
                    source_hash=source_hash,
                    size_bytes=stat.st_size,
                    mtime_ns=stat.st_mtime_ns,
                    index_status="indexing",
                )
                self._milvus_store.delete_document(kb_id, document["id"])

                milvus_ids: list[int] = []
                if chunks:
                    vectors = self._embedder.embed([chunk.text for chunk in chunks])
                    rows = [
                        {
                            "vector": vector,
                            "text": chunk.text,
                            "kb_id": kb_id,
                            "document_id": document["id"],
                            "chunk_id": f"{document['id']}:{chunk.chunk_index}",
                            "page_no": chunk.page_no,
                            "doc_type": parsed.doc_type,
                            "source_type": "local_file",
                            "source_path": path.name,
                        }
                        for chunk, vector in zip(chunks, vectors)
                    ]
                    milvus_ids = self._milvus_store.insert_chunks(kb_id, rows)

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
                            "page_no": chunk.page_no,
                            "section_path": chunk.section,
                        }
                        for index, chunk in enumerate(chunks)
                    ],
                )
                self._repository.upsert_document(
                    kb_id=kb_id,
                    canonical_path=canonical_path,
                    file_name=path.name,
                    doc_type=parsed.doc_type,
                    source_type="local_file",
                    source_hash=source_hash,
                    size_bytes=stat.st_size,
                    mtime_ns=stat.st_mtime_ns,
                    index_status="indexed",
                    indexed_at=_utc_now(),
                )
                inserted += 1
            except OcrRequiredError as exc:
                self._repository.upsert_document(
                    kb_id=kb_id,
                    canonical_path=canonical_path,
                    file_name=path.name,
                    doc_type=path.suffix.lower().lstrip("."),
                    source_type="local_file",
                    source_hash=source_hash,
                    index_status="needs_ocr",
                    last_error=str(exc),
                )
                failed += 1
            except Exception as exc:
                self._repository.upsert_document(
                    kb_id=kb_id,
                    canonical_path=canonical_path,
                    file_name=path.name,
                    doc_type=path.suffix.lower().lstrip("."),
                    source_type="local_file",
                    source_hash=source_hash,
                    index_status="failed",
                    last_error=str(exc),
                )
                failed += 1

        return SyncResult(
            scanned=scanned,
            inserted=inserted,
            skipped=skipped,
            failed=failed,
        )
