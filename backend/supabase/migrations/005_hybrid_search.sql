-- Module 6: Hybrid Search
-- Add full-text search column, GIN index, and RRF-based hybrid search function

-- A) Stored generated tsvector column (auto-computed from content)
alter table public.chunks
    add column if not exists fts tsvector
    generated always as (to_tsvector('english', content)) stored;

-- B) GIN index for full-text search
create index if not exists idx_chunks_fts on public.chunks using gin (fts);

-- C) Hybrid search function combining vector + full-text via Reciprocal Rank Fusion
create or replace function public.match_chunks_hybrid(
    query_embedding vector(1536),
    match_count integer default 5,
    filter_user_id uuid default null,
    metadata_filter jsonb default null,
    query_text text default '',
    rrf_k integer default 60,
    candidate_count integer default 30
)
returns table (
    id uuid,
    document_id uuid,
    content text,
    chunk_index integer,
    metadata jsonb,
    similarity float,
    rrf_score float
)
language plpgsql
security definer
set search_path = 'public', 'extensions'
as $$
begin
    return query
    with vector_results as (
        select
            c.id,
            c.document_id,
            c.content,
            c.chunk_index,
            c.metadata,
            (1 - (c.embedding <=> query_embedding))::float as similarity,
            row_number() over (order by c.embedding <=> query_embedding) as rank_ix
        from public.chunks c
        join public.documents d on d.id = c.document_id
        where d.user_id = filter_user_id
          and d.status = 'ready'
          and (metadata_filter is null or c.metadata @> metadata_filter)
        order by c.embedding <=> query_embedding
        limit candidate_count
    ),
    fts_results as (
        select
            c.id,
            c.document_id,
            c.content,
            c.chunk_index,
            c.metadata,
            (1 - (c.embedding <=> query_embedding))::float as similarity,
            row_number() over (order by ts_rank(c.fts, websearch_to_tsquery('english', query_text)) desc) as rank_ix
        from public.chunks c
        join public.documents d on d.id = c.document_id
        where d.user_id = filter_user_id
          and d.status = 'ready'
          and (metadata_filter is null or c.metadata @> metadata_filter)
          and c.fts @@ websearch_to_tsquery('english', query_text)
        order by ts_rank(c.fts, websearch_to_tsquery('english', query_text)) desc
        limit candidate_count
    ),
    combined as (
        select
            coalesce(v.id, f.id) as id,
            coalesce(v.document_id, f.document_id) as document_id,
            coalesce(v.content, f.content) as content,
            coalesce(v.chunk_index, f.chunk_index) as chunk_index,
            coalesce(v.metadata, f.metadata) as metadata,
            coalesce(v.similarity, f.similarity) as similarity,
            ((1.0 / (rrf_k + coalesce(v.rank_ix, candidate_count + 1))) +
            (1.0 / (rrf_k + coalesce(f.rank_ix, candidate_count + 1))))::float as rrf_score
        from vector_results v
        full outer join fts_results f on v.id = f.id
    )
    select
        combined.id,
        combined.document_id,
        combined.content,
        combined.chunk_index,
        combined.metadata,
        combined.similarity,
        combined.rrf_score
    from combined
    order by combined.rrf_score desc
    limit match_count;
end;
$$;
