# GCH Company Brain - Weekend 1 Starter

Your first working slice of the company brain: scrape Reddit, understand it with OpenAI, store it in Supabase, and ask it questions with cited answers.

```
Reddit (Apify)  ->  embed (OpenAI)  ->  store (Supabase pgvector)  ->  ask (OpenAI)
```

## What you need first
- Your Supabase project (done)
- An OpenAI API key: https://platform.openai.com/api-keys
- Your Apify token: https://console.apify.com/account/integrations
- Python 3.9 or newer installed

## Setup (once)

1. Open a terminal in this folder.

2. Install the libraries:
   ```
   pip install -r requirements.txt
   ```

3. Create your secrets file. Copy `.env.example` to `.env`, then open `.env`
   and paste in your real keys.
   ```
   cp .env.example .env
   ```

4. In the Supabase SQL Editor, run the contents of `supabase_setup.sql`.
   The only new piece is the `match_documents` function at the bottom, which
   is what lets the brain search by meaning. The tables you already made.

## Run it

1. Fill the brain with Reddit data:
   ```
   python ingest.py
   ```
   You should see it save ~10 to 15 chunks.

2. Ask it something:
   ```
   python ask.py
   ```
   Try: `what do people say about therapy being too expensive?`

You will get an answer with `[1] [2]` citations and a list of source links.
That is a real, working RAG brain. Everything else we build is widening this.

## What each file does
- `ingest.py` - collects Reddit posts, embeds them, saves them (the background job)
- `ask.py` - answers a question from what is saved (the live job)
- `supabase_setup.sql` - the database setup, including the search function
- `.env` - your private keys (never share or commit this)

## Cost
Tiny. The Reddit scrape is a few cents, OpenAI embeddings for 15 short posts is
a fraction of a cent, and one question is well under a cent.

## Next steps after this works
1. Add a second source (PDFs from a Google Drive folder).
2. Add the "numbers" path: pull Stripe data into the `kpi_snapshot` table.
3. Add a router so number-questions and meaning-questions go different ways.
4. Wrap it in the agent loop for multi-step questions.
