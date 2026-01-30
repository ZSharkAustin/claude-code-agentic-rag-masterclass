create table public.threads (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references auth.users(id) on delete cascade not null,
    title text not null default 'New Chat',
    last_response_id text,
    created_at timestamptz default now() not null,
    updated_at timestamptz default now() not null
);

alter table public.threads enable row level security;

create policy "Users can view their own threads"
    on public.threads for select
    using (auth.uid() = user_id);

create policy "Users can create their own threads"
    on public.threads for insert
    with check (auth.uid() = user_id);

create policy "Users can update their own threads"
    on public.threads for update
    using (auth.uid() = user_id);

create policy "Users can delete their own threads"
    on public.threads for delete
    using (auth.uid() = user_id);

create index idx_threads_user_id on public.threads(user_id);

create or replace function public.update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger threads_updated_at
    before update on public.threads
    for each row
    execute function public.update_updated_at();
