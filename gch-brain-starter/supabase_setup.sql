-- ============================================================
-- Run this ONCE in the Supabase SQL Editor.
-- You already ran the first three statements when you made the
-- tables. The important NEW part is the match_documents function
-- at the bottom, which powers "search by meaning".
-- ============================================================

-- 1. turn on vector search (safe to run again)
create extension if not exists vector;

-- 2. table for text pieces + their meaning-fingerprints (already created)
create table if not exists doc_chunks (
  id           uuid primary key default gen_random_uuid(),
  parent_id    uuid,
  content      text not null,
  embedding    vector(1536),
  motion       text,
  source_type  text,
  source_url   text,
  published_at timestamptz,
  created_at   timestamptz default now()
);

-- 3. table for numbers (already created)
create table if not exists kpi_snapshot (
  id          uuid primary key default gen_random_uuid(),
  metric      text not null,
  value       numeric,
  period      date,
  source      text,
  created_at  timestamptz default now()
);

-- 3b. extra columns for richer insights (safe to run again)
alter table doc_chunks add column if not exists topic     text;
alter table doc_chunks add column if not exists subreddit text;
alter table doc_chunks add column if not exists upvotes   int;

-- 4. THE SEARCH FUNCTION: finds the closest chunks to a question,
--    optionally limited to certain sources (e.g. only reddit, or only research).
--    filter_sources = null means search everything.
drop function if exists match_documents(vector, int);
drop function if exists match_documents(vector, int, text[]);
create function match_documents(
  query_embedding vector(1536),
  match_count int default 8,
  filter_sources text[] default null
)
returns table (
  id          uuid,
  content     text,
  source_url  text,
  source_type text,
  subreddit   text,
  similarity  float
)
language sql stable
as $$
  select
    doc_chunks.id,
    doc_chunks.content,
    doc_chunks.source_url,
    doc_chunks.source_type,
    doc_chunks.subreddit,
    1 - (doc_chunks.embedding <=> query_embedding) as similarity
  from doc_chunks
  where doc_chunks.embedding is not null
    and (filter_sources is null or doc_chunks.source_type = any(filter_sources))
  order by doc_chunks.embedding <=> query_embedding
  limit match_count;
$$;

-- 5. HYBRID SEARCH: combines meaning search (embeddings) with exact-ish keyword
--    search (Postgres full text). This helps with named books, authors,
--    competitors, acronyms, metrics, and specific concepts like "shame vs guilt".
create index if not exists doc_chunks_hybrid_fts_idx
  on doc_chunks using gin (
    to_tsvector('english', content || ' ' || coalesce(source_url, ''))
  );

alter table doc_chunks
  add column if not exists search_vector tsvector
  generated always as (
    setweight(to_tsvector('english', coalesce(source_url, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(content, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(source_type, '')), 'C') ||
    setweight(to_tsvector('english', coalesce(subreddit, '')), 'C')
  ) stored;

create index if not exists doc_chunks_search_vector_idx
  on doc_chunks using gin(search_vector);

drop function if exists match_documents_full_text(text, int, text[]);
create function match_documents_full_text(
  query_text text,
  match_count int default 25,
  filter_sources text[] default null
)
returns table (
  id          uuid,
  content     text,
  source_url  text,
  source_type text,
  subreddit   text,
  rank        float
)
language sql stable
as $$
  with query as (
    select websearch_to_tsquery('english', coalesce(query_text, '')) as fts
  )
  select
    doc_chunks.id,
    doc_chunks.content,
    doc_chunks.source_url,
    doc_chunks.source_type,
    doc_chunks.subreddit,
    ts_rank_cd(doc_chunks.search_vector, query.fts) as rank
  from doc_chunks, query
  where doc_chunks.embedding is not null
    and query.fts::text <> ''
    and doc_chunks.search_vector @@ query.fts
    and (filter_sources is null or doc_chunks.source_type = any(filter_sources))
  order by rank desc
  limit match_count;
$$;

drop function if exists match_documents_hybrid(vector, text, int, text[]);
create function match_documents_hybrid(
  query_embedding vector(1536),
  query_text text,
  match_count int default 8,
  filter_sources text[] default null
)
returns table (
  id            uuid,
  content       text,
  source_url    text,
  source_type   text,
  subreddit     text,
  similarity    float,
  keyword_rank  float,
  hybrid_score  float
)
language sql stable
as $$
  with query as (
    select websearch_to_tsquery('english', coalesce(query_text, '')) as fts
  ),
  vector_candidates as (
    select doc_chunks.id
    from doc_chunks
    where doc_chunks.embedding is not null
      and (filter_sources is null or doc_chunks.source_type = any(filter_sources))
    order by doc_chunks.embedding <=> query_embedding
    limit greatest(match_count * 8, 50)
  ),
  keyword_candidates as (
    select doc_chunks.id
    from doc_chunks, query
    where doc_chunks.embedding is not null
      and (filter_sources is null or doc_chunks.source_type = any(filter_sources))
      and query.fts::text <> ''
      and to_tsvector('english', doc_chunks.content || ' ' || coalesce(doc_chunks.source_url, '')) @@ query.fts
    order by ts_rank_cd(
      to_tsvector('english', doc_chunks.content || ' ' || coalesce(doc_chunks.source_url, '')),
      query.fts
    ) desc
    limit greatest(match_count * 8, 50)
  ),
  candidates as (
    select id from vector_candidates
    union
    select id from keyword_candidates
  ),
  scored as (
    select
      doc_chunks.id,
      doc_chunks.content,
      doc_chunks.source_url,
      doc_chunks.source_type,
      doc_chunks.subreddit,
      1 - (doc_chunks.embedding <=> query_embedding) as similarity,
      ts_rank_cd(
        to_tsvector('english', doc_chunks.content || ' ' || coalesce(doc_chunks.source_url, '')),
        websearch_to_tsquery('english', coalesce(query_text, ''))
      ) as keyword_rank
    from doc_chunks
    join candidates on candidates.id = doc_chunks.id
  )
  select
    scored.id,
    scored.content,
    scored.source_url,
    scored.source_type,
    scored.subreddit,
    scored.similarity,
    scored.keyword_rank,
    (
      scored.similarity * 0.72 +
      (scored.keyword_rank / (scored.keyword_rank + 1.0)) * 0.28
    ) as hybrid_score
  from scored
  order by hybrid_score desc
  limit match_count;
$$;
