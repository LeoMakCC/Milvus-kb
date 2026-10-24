from __future__ import annotations

import json
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

    def delete_knowledge_base(self, kb_id: str) -> bool:
        """删除知识库及其全部文档、分块、邮件与任务记录。"""
        if self.get_knowledge_base(kb_id) is None:
            return False
        with connect(self._db_path) as conn:
            document_ids = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM documents WHERE kb_id = ?",
                    (kb_id,),
                )
            ]
            if document_ids:
                placeholders = ",".join("?" for _ in document_ids)
                conn.execute(
                    "DELETE FROM email_attachments "
                    f"WHERE email_document_id IN ({placeholders}) "
                    f"OR attachment_document_id IN ({placeholders})",
                    document_ids + document_ids,
                )
                conn.execute(
                    f"DELETE FROM emails WHERE document_id IN ({placeholders})",
                    document_ids,
                )
                conn.execute(
                    f"DELETE FROM chunks WHERE document_id IN ({placeholders})",
                    document_ids,
                )
                conn.execute(
                    "DELETE FROM document_aliases "
                    f"WHERE document_id IN ({placeholders})",
                    document_ids,
                )
            conn.execute("DELETE FROM documents WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM document_roots WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM index_versions WHERE kb_id = ?", (kb_id,))
            job_ids = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM jobs WHERE kb_id = ?",
                    (kb_id,),
                )
            ]
            if job_ids:
                job_placeholders = ",".join("?" for _ in job_ids)
                conn.execute(
                    f"DELETE FROM job_items WHERE job_id IN ({job_placeholders})",
                    job_ids,
                )
            conn.execute("DELETE FROM jobs WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))
            conn.commit()
        return True

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

    def get_document_by_source_hash(
        self,
        kb_id: str,
        source_hash: str,
    ) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM documents
                WHERE kb_id = ? AND source_hash = ?
                ORDER BY created_at
                LIMIT 1
                """,
                (kb_id, source_hash),
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
        parent_document_id: str | None = None,
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
                        indexed_at = ?, parent_document_id = ?, updated_at = ?
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
                        parent_document_id,
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
                    , parent_document_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    parent_document_id,
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

    def list_documents_with_chunk_counts(self, kb_id: str) -> list[dict]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT d.*, COUNT(c.id) AS chunk_count
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                WHERE d.kb_id = ?
                GROUP BY d.id
                ORDER BY d.file_name
                """,
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

    def upsert_email(
        self,
        document_id: str,
        message_id: str | None,
        thread_id: str | None,
        subject: str,
        from_addr: str,
        to_addr: str,
        cc_addr: str,
        sent_at: str,
        message_hash: str,
    ) -> dict:
        existing = self.get_email_by_document_id(document_id)
        if existing:
            with connect(self._db_path) as conn:
                conn.execute(
                    """
                    UPDATE emails
                    SET message_id = ?, thread_id = ?, subject = ?,
                        from_addr = ?, to_addr = ?, cc_addr = ?,
                        sent_at = ?, message_hash = ?
                    WHERE document_id = ?
                    """,
                    (
                        message_id,
                        thread_id,
                        subject,
                        from_addr,
                        to_addr,
                        cc_addr,
                        sent_at,
                        message_hash,
                        document_id,
                    ),
                )
                conn.commit()
            return self.get_email_by_document_id(document_id)

        email_id = uuid4().hex
        with connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO emails(
                    id, document_id, message_id, thread_id, subject,
                    from_addr, to_addr, cc_addr, sent_at, message_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email_id,
                    document_id,
                    message_id,
                    thread_id,
                    subject,
                    from_addr,
                    to_addr,
                    cc_addr,
                    sent_at,
                    message_hash,
                ),
            )
            conn.commit()
        return self.get_email_by_document_id(document_id)

    def get_email_by_document_id(self, document_id: str) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM emails WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_email_by_message_id(self, kb_id: str, message_id: str) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT emails.*
                FROM emails
                JOIN documents ON documents.id = emails.document_id
                WHERE documents.kb_id = ? AND emails.message_id = ?
                """,
                (kb_id, message_id),
            ).fetchone()
        return dict(row) if row else None

    def get_email_by_hash(self, kb_id: str, message_hash: str) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT emails.*
                FROM emails
                JOIN documents ON documents.id = emails.document_id
                WHERE documents.kb_id = ? AND emails.message_hash = ?
                """,
                (kb_id, message_hash),
            ).fetchone()
        return dict(row) if row else None

    def upsert_email_attachment(
        self,
        email_document_id: str,
        attachment_document_id: str | None,
        file_name: str,
        content_type: str,
        content_hash: str,
    ) -> dict:
        with connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM email_attachments
                WHERE email_document_id = ? AND file_name = ? AND content_hash = ?
                """,
                (email_document_id, file_name, content_hash),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE email_attachments
                    SET attachment_document_id = ?, content_type = ?
                    WHERE id = ?
                    """,
                    (attachment_document_id, content_type, row["id"]),
                )
                conn.commit()
                attachment_id = row["id"]
            else:
                attachment_id = uuid4().hex
                conn.execute(
                    """
                    INSERT INTO email_attachments(
                        id, email_document_id, attachment_document_id,
                        file_name, content_type, content_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        attachment_id,
                        email_document_id,
                        attachment_document_id,
                        file_name,
                        content_type,
                        content_hash,
                        _utc_now(),
                    ),
                )
                conn.commit()
        return self.get_email_attachment(attachment_id)

    def get_email_attachment(self, attachment_id: str) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM email_attachments WHERE id = ?",
                (attachment_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_email_attachments(self, email_document_id: str) -> list[dict]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM email_attachments
                WHERE email_document_id = ?
                ORDER BY file_name
                """,
                (email_document_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_email_thread(self, kb_id: str, thread_id: str) -> list[dict]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT emails.*, documents.file_name
                FROM emails
                JOIN documents ON documents.id = emails.document_id
                WHERE documents.kb_id = ? AND emails.thread_id = ?
                ORDER BY emails.sent_at, emails.id
                """,
                (kb_id, thread_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_conversation(
        self,
        kb_ids: list[str],
        provider_name: str | None = None,
        model_name: str | None = None,
        title: str | None = None,
    ) -> dict:
        conversation_id = uuid4().hex
        now = _utc_now()
        with connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversations(
                    id, title, kb_ids, provider_name, model_name,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    title or "新会话",
                    json.dumps(kb_ids, ensure_ascii=False),
                    provider_name,
                    model_name,
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_conversation(conversation_id)

    def update_conversation_title(
        self,
        conversation_id: str,
        title: str,
    ) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, _utc_now(), conversation_id),
            )
            conn.commit()

    def list_conversations(self, only_archived: bool = False) -> list[dict]:
        condition = "IS NOT NULL" if only_archived else "IS NULL"
        with connect(self._db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM conversations
                WHERE archived_at {condition}
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def set_conversation_archived(
        self,
        conversation_id: str,
        archived: bool,
    ) -> dict | None:
        if self.get_conversation(conversation_id) is None:
            return None
        now = _utc_now()
        with connect(self._db_path) as conn:
            conn.execute(
                "UPDATE conversations SET archived_at = ? WHERE id = ?",
                (now if archived else None, conversation_id),
            )
            conn.commit()
        return self.get_conversation(conversation_id)

    def get_conversation(self, conversation_id: str) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        return dict(row) if row else None

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations_json: str | None = None,
    ) -> dict:
        message_id = uuid4().hex
        now = _utc_now()
        with connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO messages(
                    id, conversation_id, role, content, citations_json,
                    token_usage_json, created_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    role,
                    content,
                    citations_json,
                    now,
                ),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            conn.commit()
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
        return dict(row) if row else {}

    def list_messages(self, conversation_id: str) -> list[dict]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at, rowid
                """,
                (conversation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_provider_config(
        self,
        name: str,
        provider_type: str,
        base_url: str | None = None,
        model_name: str | None = None,
        api_version: str | None = None,
        encrypted_secret: bytes | None = None,
        extra_headers_json: str | None = None,
        enabled: bool = True,
    ) -> dict:
        existing = self.get_provider_config_by_name(name)
        now = _utc_now()
        if existing:
            with connect(self._db_path) as conn:
                conn.execute(
                    """
                    UPDATE provider_configs
                    SET provider_type = ?, base_url = ?, model_name = ?,
                        api_version = ?, encrypted_secret = ?,
                        extra_headers_json = ?, enabled = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        provider_type,
                        base_url,
                        model_name,
                        api_version,
                        encrypted_secret,
                        extra_headers_json,
                        int(enabled),
                        now,
                        existing["id"],
                    ),
                )
                conn.commit()
            return self.get_provider_config(existing["id"])

        provider_id = uuid4().hex
        with connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO provider_configs(
                    id, name, provider_type, base_url, model_name,
                    api_version, encrypted_secret, extra_headers_json,
                    enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider_id,
                    name,
                    provider_type,
                    base_url,
                    model_name,
                    api_version,
                    encrypted_secret,
                    extra_headers_json,
                    int(enabled),
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_provider_config(provider_id)

    def list_provider_configs(self) -> list[dict]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM provider_configs ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_provider_config(self, provider_id: str) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM provider_configs WHERE id = ?",
                (provider_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_provider_config_by_name(self, name: str) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM provider_configs WHERE name = ?",
                (name,),
            ).fetchone()
        return dict(row) if row else None

    def set_active_provider(self, provider_id: str) -> None:
        provider = self.get_provider_config(provider_id)
        if provider is None:
            raise ValueError(f"Provider not found: {provider_id}")
        with connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO app_settings(key, value, encrypted, updated_at)
                VALUES ('active_provider', ?, 0, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (provider_id, _utc_now()),
            )
            conn.commit()

    def get_active_provider_config(self) -> dict | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'active_provider'"
            ).fetchone()
        if row:
            provider = self.get_provider_config(row["value"])
            if provider is not None:
                return provider
        with connect(self._db_path) as conn:
            first = conn.execute(
                """
                SELECT * FROM provider_configs
                WHERE enabled = 1
                ORDER BY created_at
                LIMIT 1
                """
            ).fetchone()
        return dict(first) if first else None

    def delete_provider_config(self, provider_id: str) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM provider_configs WHERE id = ?",
                (provider_id,),
            )
            conn.commit()

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
        return row["value"] if row else default

    def set_setting(
        self,
        key: str,
        value: str,
        encrypted: bool = False,
    ) -> None:
        with connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO app_settings(key, value, encrypted, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    encrypted = excluded.encrypted,
                    updated_at = excluded.updated_at
                """,
                (key, value, int(encrypted), _utc_now()),
            )
            conn.commit()

    def get_app_settings(self) -> dict[str, str]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT key, value FROM app_settings"
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}
