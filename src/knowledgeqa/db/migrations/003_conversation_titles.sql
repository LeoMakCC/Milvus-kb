-- 把历史会话的默认标题替换为该会话的第一条用户提问
UPDATE conversations
SET title = (
    SELECT CASE
        WHEN length(trim(m.content)) > 24
            THEN substr(trim(m.content), 1, 24) || '…'
        ELSE trim(m.content)
    END
    FROM messages m
    WHERE m.conversation_id = conversations.id
      AND m.role = 'user'
      AND trim(m.content) <> ''
    ORDER BY m.created_at, m.rowid
    LIMIT 1
)
WHERE title IN ('新会话', '')
  AND EXISTS (
      SELECT 1
      FROM messages m
      WHERE m.conversation_id = conversations.id
        AND m.role = 'user'
        AND trim(m.content) <> ''
  );
