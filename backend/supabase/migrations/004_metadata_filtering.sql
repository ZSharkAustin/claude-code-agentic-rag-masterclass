-- Module 4: Metadata Filtering
-- Update match_chunks to support JSONB metadata filtering + add GIN index

-- GIN index for fast JSONB containment queries on chunks.metadata
create index if not exists idx_chunks_metadata on public.chunks using gin (metadata);

-- Drop old match_chunks (3-param signature) before creating the new one
drop function if exists public.match_chunks(vector, integer, uuid);

-- Recreate match_chunks with metadata_filter parameter
create or replace function public.match_chunks(
    query_embedding vector(1536),
    match_count integer default 5,
    filter_user_id uuid default null,
    metadata_filter jsonb default null
)
returns table (
    id uuid,
    document_id uuid,
    content text,
    chunk_index integer,
    metadata jsonb,
    similarity float
)
language plpgsql
security definer
set search_path = 'public', 'extensions'
as $$
begin
    return query
    select
        c.id,
        c.document_id,
        c.content,
        c.chunk_index,
        c.metadata,
        1 - (c.embedding <=> query_embedding) as similarity
    from public.chunks c
    join public.documents d on d.id = c.document_id
    where d.user_id = filter_user_id
      and d.status = 'ready'
      and (metadata_filter is null or c.metadata @> metadata_filter)
    order by c.embedding <=> query_embedding
    limit match_count;
end;
$$;
