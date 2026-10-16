ALTER TABLE documents ADD COLUMN parent_document_id TEXT;
CREATE INDEX IF NOT EXISTS idx_documents_parent ON documents(parent_document_id);

CREATE TABLE IF NOT EXISTS email_attachments (
    id TEXT PRIMARY KEY,
    email_document_id TEXT NOT NULL,
    attachment_document_id TEXT,
    file_name TEXT NOT NULL,
    content_type TEXT,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (email_document_id) REFERENCES documents(id),
    FOREIGN KEY (attachment_document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_email_attachments_email
    ON email_attachments(email_document_id);
CREATE INDEX IF NOT EXISTS idx_email_attachments_hash
    ON email_attachments(content_hash);
