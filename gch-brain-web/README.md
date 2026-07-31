# GCH Company Brain Web App

This folder contains the Vercel-hosted web interface and serverless API for GCH Company Brain.

## Components

- `index.html`: browser UI
- `api/ask.js`: serverless answer endpoint
- `lib/retrieval/`: multi-stage retrieval pipeline
- `test/retrieval.test.js`: retrieval utility tests

## Retrieval

The API performs mode-aware retrieval using query expansion, vector search, PostgreSQL full-text search, weighted reciprocal rank fusion, deduplication, LLM-based reranking, source diversity filtering, and sentence-level evidence extraction.

## Test

```bash
node --test
node --check api/ask.js
```

## Deployment

Deploy from this directory with Vercel.

Required environment variables:

```text
OPENAI_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_KEY
KPI_PASSCODE
```
