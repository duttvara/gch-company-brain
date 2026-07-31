# GCH Company Brain

GCH Company Brain is an internal AI intelligence system for Greater Change Health. It combines consumer conversations, clinical research, competitor/EAP web content, therapy and psychology reference material, and business KPI data into a source-cited question-answering interface.

The system is built as a multi-source RAG application with scheduled ingestion, Supabase pgvector storage, PostgreSQL full-text search, a mode-aware retrieval pipeline, and a Vercel-hosted web interface.

## Architecture

```text
Data sources
  -> ingestion scripts
  -> Supabase Postgres + pgvector
  -> mode-aware retrieval pipeline
  -> Vercel serverless API
  -> web interface
```

## Retrieval Pipeline

For document-backed modes, the API uses a multi-stage retrieval flow:

```text
user query
  -> deterministic query expansion
  -> vector search + PostgreSQL full-text search
  -> weighted reciprocal rank fusion
  -> duplicate and near-duplicate filtering
  -> LLM-based reranking
  -> source diversity filtering
  -> sentence-level evidence extraction
  -> cited answer generation
```

Business KPI reasoning uses structured KPI rows rather than document retrieval.

## Modes

- Consumer voice: Reddit-based consumer insight
- Research: PubMed and OpenAlex research synthesis
- Therapy books: book/reference-based content strategy
- Competitors & EAP: competitor and employer mental health market analysis
- Business KPIs: Stripe-backed business metric reasoning

## Repository Structure

```text
gch-brain-starter/
  ingestion scripts, Supabase SQL, CLI utilities

gch-brain-web/
  Vercel web app, API route, retrieval pipeline, tests

.github/workflows/
  scheduled and manually triggered ingestion workflows
```

## Key Technologies

- OpenAI embeddings and GPT models
- Supabase Postgres and pgvector
- PostgreSQL full-text search
- Weighted reciprocal rank fusion
- LLM-based reranking
- Vercel serverless functions
- Apify ingestion for Reddit and competitor websites
- GitHub Actions for scheduled ingestion
- Stripe API for KPI ingestion

## Setup

1. Install Python dependencies for ingestion.

```bash
cd gch-brain-starter
pip install -r requirements.txt
```

2. Create a local environment file.

```bash
cp .env.example .env
```

3. Add the required values to `.env`.

```text
OPENAI_API_KEY
APIFY_TOKEN
SUPABASE_URL
SUPABASE_SERVICE_KEY
STRIPE_API_KEY
```

4. Run the Supabase schema and search functions.

Copy `gch-brain-starter/supabase_setup.sql` into the Supabase SQL Editor and run it.

## Local Checks

```bash
cd gch-brain-web
node --test
node --check api/ask.js
```

```bash
cd gch-brain-starter
python3 -m py_compile ask.py ingest.py ingest_web.py ingest_research.py ingest_stripe.py ingest_pdfs.py
```

## Deployment

Deploy the web app from `gch-brain-web` using Vercel.

Required Vercel environment variables:

```text
OPENAI_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_KEY
KPI_PASSCODE
```

Optional model override variables:

```text
ANSWER_MODEL
BOOKS_ANSWER_MODEL
KPI_ANSWER_MODEL
RERANK_MODEL
USE_LLM_EXTRACTION
```

## GitHub Actions

The repository includes workflows for:

- Weekly company brain ingestion
- Manual KPI ingestion

Before enabling scheduled workflows, configure repository Actions secrets:

```text
OPENAI_API_KEY
APIFY_TOKEN
SUPABASE_URL
SUPABASE_SERVICE_KEY
STRIPE_API_KEY
```

## Security Notes

- Real `.env` files are ignored by Git.
- Supabase service role keys are used only server-side.
- Book/PDF source files are excluded from the repository.
- KPI access in the web app is passcode-protected.
