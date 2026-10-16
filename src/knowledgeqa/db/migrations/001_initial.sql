CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    encrypted INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    collection_name TEXT NOT NULL UNIQUE,
    embedding_model TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    index_version INTEGER NOT NULL DEFAULT 1,
    only_local_model INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_roots (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    path TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    include_globs TEXT NOT NULL DEFAULT '',
    exclude_globs TEXT NOT NULL DEFAULT '',
    max_file_size_bytes INTEGER NOT NULL DEFAULT 209715200,
    follow_symlinks INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id)
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    canonical_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_hash TEXT,
    normalized_hash TEXT,
    size_bytes INTEGER,
    mtime_ns INTEGER,
    index_status TEXT NOT NULL DEFAULT 'pending',
    duplicate_of TEXT,
    canonical_document_id TEXT,
    missing_since TEXT,
    last_error TEXT,
    indexed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id)
);

CREATE INDEX IF NOT EXISTS idx_documents_kb_id ON documents(kb_id);
CREATE INDEX IF NOT EXISTS idx_documents_source_hash ON documents(source_hash);
CREATE INDEX IF NOT EXISTS idx_documents_normalized_hash ON documents(normalized_hash);
CREATE INDEX IF NOT EXISTS idx_documents_canonical_path ON documents(canonical_path);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(index_status);

CREATE TABLE IF NOT EXISTS document_aliases (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    alias_path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    message_id TEXT,
    thread_id TEXT,
    subject TEXT,
    from_addr TEXT,
    to_addr TEXT,
    cc_addr TEXT,
    sent_at TEXT,
    message_hash TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
CREATE INDEX IF NOT EXISTS idx_emails_thread_id ON emails(thread_id);
CREATE INDEX IF NOT EXISTS idx_emails_message_hash ON emails(message_hash);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_hash TEXT NOT NULL,
    page_no INTEGER,
    section_path TEXT,
    char_start INTEGER,
    char_end INTEGER,
    milvus_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_hash ON chunks(chunk_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_milvus_id ON chunks(milvus_id);

CREATE TABLE IF NOT EXISTS index_versions (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    collection_name TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    schema_version INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    kb_id TEXT,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    total_items INTEGER NOT NULL DEFAULT 0,
    processed_items INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_items (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    document_id TEXT,
    item_path TEXT,
    item_state TEXT NOT NULL,
    item_error TEXT,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '新会话',
    kb_ids TEXT NOT NULL DEFAULT '[]',
    provider_name TEXT,
    model_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations_json TEXT,
    token_usage_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS provider_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    provider_type TEXT NOT NULL,
    base_url TEXT,
    model_name TEXT,
    api_version TEXT,
    encrypted_secret BLOB,
    extra_headers_json TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    subject TEXT,
    source_ip TEXT,
    detail_json TEXT,
    created_at TEXT NOT NULL
);
