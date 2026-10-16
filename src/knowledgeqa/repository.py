from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from knowledgeqa.db.connection import connect
from knowledgeqa.db.migrations import apply_migrations


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Repository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def initialize(self) -> None:
        conn = connect(self._db_path)
        try:
            apply_migrations(conn)
        finally:
            conn.close()

    def create_knowledge_base(
        self,
        name: str,
        dimension: int,
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
    ) -> dict:
        kb_id = uuid4().hex
        now = _utc_now()
        with connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO knowledge_bases(
                    id, name, description, collection_name, embedding_model,
                    dimension, index_version, only_local_model, status,
                    created_at, updated_at
                ) VALUES (?, ?, '', ?, ?, ?, 1, 0, 'active', ?, ?)
                """,
                (kb_id, name, f"kb_{kb_id}", embedding_model, dimension, now, now),
            )
            conn.commit()
        return self.get_knowledge_base(kb_id)

    def list_knowledge_bases(self) -> list[dict]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM knowledge_bases ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_knowledge_base(self, kb_id: str) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_bases WHERE id = ?",
                (kb_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_document_by_path(self, kb_id: str, canonical_path: str) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM documents
                WHERE kb_id = ? AND canonical_path = ?
                """,
                (kb_id, canonical_path),
            ).fetchone()
        return dict(row) if row else None

    def get_document(self, document_id: str) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        return dict(row) if row else None

    def upsert_document(
        self,
        kb_id: str,
        canonical_path: str,
        file_name: str,
        doc_type: str,
        source_type: str,
        source_hash: str | None,
        normalized_hash: str | None = None,
        size_bytes: int | None = None,
        mtime_ns: int | None = None,
        index_status: str = "pending",
        last_error: str | None = None,
        indexed_at: str | None = None,
    ) -> dict:
        existing = self.get_document_by_path(kb_id, canonical_path)
        now = _utc_now()
        if existing:
            with connect(self._db_path) as conn:
                conn.execute(
                    """
                    UPDATE documents
                    SET file_name = ?, doc_type = ?, source_type = ?,
                        source_hash = ?, normalized_hash = ?, size_bytes = ?,
                        mtime_ns = ?, index_status = ?, last_error = ?,
                        indexed_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        file_name,
                        doc_type,
                        source_type,
                        source_hash,
                        normalized_hash,
                        size_bytes,
                        mtime_ns,
                        index_status,
                        last_error,
                        indexed_at,
                        now,
                        existing["id"],
                    ),
                )
                conn.commit()
            return self.get_document(existing["id"])

        document_id = uuid4().hex
        with connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO documents(
                    id, kb_id, canonical_path, file_name, doc_type, source_type,
                    source_hash, normalized_hash, size_bytes, mtime_ns,
                    index_status, last_error, indexed_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    kb_id,
                    canonical_path,
                    file_name,
                    doc_type,
                    source_type,
                    source_hash,
                    normalized_hash,
                    size_bytes,
                    mtime_ns,
                    index_status,
                    last_error,
                    indexed_at,
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_document(document_id)

    def replace_chunks(self, document_id: str, chunks: list[dict]) -> None:
        now = _utc_now()
        with connect(self._db_path) as conn:
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT INTO chunks(
                        id, document_id, chunk_index, chunk_hash, page_no,
                        section_path, char_start, char_end, milvus_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid4().hex,
                        document_id,
                        chunk["chunk_index"],
                        chunk["chunk_hash"],
                        chunk.get("page_no"),
                        chunk.get("section_path"),
                        chunk.get("char_start"),
                        chunk.get("char_end"),
                        chunk.get("milvus_id"),
                        now,
                    ),
                )
            conn.commit()

    def list_documents(self, kb_id: str) -> list[dict]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE kb_id = ? ORDER BY file_name",
                (kb_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_chunks(self, document_id: str) -> list[dict]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
                (document_id,),
            ).fetchall()
        return [dict(row) for row in rows]
