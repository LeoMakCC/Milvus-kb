-- 会话归档：archived_at 非空表示已归档，默认列表不再显示
ALTER TABLE conversations ADD COLUMN archived_at TEXT;
