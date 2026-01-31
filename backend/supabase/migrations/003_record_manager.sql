-- Module 3: Record Manager — content hashing & deduplication

-- Add content_hash column to documents
alter table documents add column content_hash text;

-- Unique index: one ready document per user per content hash
create unique index idx_documents_user_content_hash
  on documents (user_id, content_hash)
  where status = 'ready';

-- Plain index for fast hash lookups
create index idx_documents_content_hash on documents (content_hash);
