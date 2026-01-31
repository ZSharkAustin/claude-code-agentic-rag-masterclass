-- Module 2: BYO Retrieval + Memory
-- Messages, Documents, Chunks tables + pgvector + match_chunks function

-- Drop last_response_id from threads (no longer needed with Chat Completions)
alter table public.threads drop column if exists last_response_id;

-- Messages table
create table public.messages (
    id uuid default gen_random_uuid() primary key,
    thread_id uuid references public.threads(id) on delete cascade not null,
    role text not null check (role in ('user', 'assistant', 'system', 'tool')),
    content text not null,
    created_at timestamptz default now() not null
);

alter table public.messages enable row level security;

-- RLS via thread ownership
create policy "Users can view messages in their threads"
    on public.messages for select
    using (
        exists (
            select 1 from public.threads
            where threads.id = messages.thread_id
            and threads.user_id = auth.uid()
        )
    );

create policy "Users can insert messages in their threads"
    on public.messages for insert
    with check (
        exists (
            select 1 from public.threads
            where threads.id = messages.thread_id
            and threads.user_id = auth.uid()
        )
    );

create index idx_messages_thread_id on public.messages(thread_id);
create index idx_messages_created_at on public.messages(thread_id, created_at);

-- Documents table
create table public.documents (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references auth.users(id) on delete cascade not null,
    filename text not null,
    file_path text not null,
    file_size bigint not null,
    mime_type text not null,
    status text not null default 'uploading' check (status in ('uploading', 'processing', 'ready', 'error')),
    chunk_count integer not null default 0,
    error_message text,
    created_at timestamptz default now() not null,
    updated_at timestamptz default now() not null
);

alter table public.documents enable row level security;

create policy "Users can view their own documents"
    on public.documents for select
    using (auth.uid() = user_id);

create policy "Users can insert their own documents"
    on public.documents for insert
    with check (auth.uid() = user_id);

create policy "Users can update their own documents"
    on public.documents for update
    using (auth.uid() = user_id);

create policy "Users can delete their own documents"
    on public.documents for delete
    using (auth.uid() = user_id);

create index idx_documents_user_id on public.documents(user_id);

-- Trigger for updated_at on documents
create trigger documents_updated_at
    before update on public.documents
    for each row
    execute function public.update_updated_at();

-- Enable pgvector extension
create extension if not exists vector with schema extensions;

-- Chunks table
create table public.chunks (
    id uuid default gen_random_uuid() primary key,
    document_id uuid references public.documents(id) on delete cascade not null,
    content text not null,
    embedding vector(1536),
    chunk_index integer not null,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default now() not null
);

alter table public.chunks enable row level security;

-- RLS via document ownership
create policy "Users can view chunks of their documents"
    on public.chunks for select
    using (
        exists (
            select 1 from public.documents
            where documents.id = chunks.document_id
            and documents.user_id = auth.uid()
        )
    );

create policy "Users can insert chunks for their documents"
    on public.chunks for insert
    with check (
        exists (
            select 1 from public.documents
            where documents.id = chunks.document_id
            and documents.user_id = auth.uid()
        )
    );

create policy "Users can delete chunks of their documents"
    on public.chunks for delete
    using (
        exists (
            select 1 from public.documents
            where documents.id = chunks.document_id
            and documents.user_id = auth.uid()
        )
    );

create index idx_chunks_document_id on public.chunks(document_id);

-- match_chunks: SECURITY DEFINER function for similarity search
create or replace function public.match_chunks(
    query_embedding vector(1536),
    match_count integer default 5,
    filter_user_id uuid default null
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
    order by c.embedding <=> query_embedding
    limit match_count;
end;
$$;

-- Create documents storage bucket
insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do nothing;

-- Storage RLS: users upload to their own folder
create policy "Users can upload to their own folder"
    on storage.objects for insert
    with check (
        bucket_id = 'documents'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "Users can read their own files"
    on storage.objects for select
    using (
        bucket_id = 'documents'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy "Users can delete their own files"
    on storage.objects for delete
    using (
        bucket_id = 'documents'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

-- Enable Realtime on documents table
alter publication supabase_realtime add table public.documents;
