# GCH Company Brain Ingestion

This folder contains the ingestion and database setup scripts for GCH Company Brain.

## Data Sources

- `ingest.py`: Reddit consumer discussions
- `ingest_research.py`: PubMed and OpenAlex research
- `ingest_web.py`: competitor and EAP website content
- `ingest_pdfs.py`: local PDF/EPUB reference material
- `ingest_stripe.py`: Stripe business KPI snapshots
- `supabase_setup.sql`: tables, pgvector setup, full-text search, and retrieval RPCs

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Add the required API keys to `.env`, then run `supabase_setup.sql` in the Supabase SQL Editor.

## Common Commands

```bash
python ingest.py
python ingest_research.py
python ingest_web.py
python ingest_stripe.py
```

Local book/reference ingestion is intentionally not scheduled because source files are excluded from the repository.

## CLI Testing

```bash
python ask.py
python ask_kpis.py
```

## Notes

- `.env` is ignored by Git.
- `pdfs/` is ignored by Git.
- Use a restricted read-only Stripe key for KPI ingestion.
