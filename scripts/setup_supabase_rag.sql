create extension if not exists vector;

create table if not exists rag_documents (
    id text primary key,
    filename text not null,
    storage_path text,
    created_at timestamptz not null default now()
);

create table if not exists rag_chunks (
    id text primary key,
    document_id text not null references rag_documents(id) on delete cascade,
    chunk_index integer not null,
    content text not null,
    metadata jsonb not null default '{}',
    embedding vector(384),
    created_at timestamptz not null default now()
);

create index if not exists idx_rag_chunks_document on rag_chunks(document_id, chunk_index);
create index if not exists idx_rag_chunks_embedding
    on rag_chunks using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create or replace function match_rag_chunks(
    query_embedding vector(384),
    match_count integer default 5
)
returns table (
    id text,
    document_id text,
    content text,
    metadata jsonb,
    similarity double precision
)
language sql stable
set search_path = public, extensions
as $$
    select
        rag_chunks.id,
        rag_chunks.document_id,
        rag_chunks.content,
        rag_chunks.metadata,
        1 - (rag_chunks.embedding <=> query_embedding) as similarity
    from rag_chunks
    where rag_chunks.embedding is not null
    order by rag_chunks.embedding <=> query_embedding
    limit match_count;
$$;

alter table rag_documents enable row level security;
alter table rag_chunks enable row level security;
