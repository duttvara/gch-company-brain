"""
ask.py  -  STEP 2 of the company brain.

What it does:
  1. Takes your question.
  2. Turns it into a meaning-fingerprint with OpenAI.
  3. Asks Supabase for the closest saved chunks (search by meaning).
  4. Hands those chunks to OpenAI and gets a cited answer.

Run it with:   python ask.py
Then type a question like:  what do people say about therapy being expensive?
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

openai = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o"   # stronger synthesis than mini, still cheap for one question

SYSTEM_PROMPT = (
    "You are the Greater Change Health company brain, summarizing what real people "
    "say online so a mental-health provider can understand their market and clients.\n"
    "Use ONLY the numbered sources. Synthesize and summarize what they express: "
    "the themes, complaints, needs, and notable quotes. Cite sources like [1], [2].\n"
    "Only say you don't have enough information if the sources are genuinely unrelated "
    "to the question. Otherwise, give the best summary the sources support. "
    "Do not invent facts beyond the sources."
)


def embed(text):
    resp = openai.embeddings.create(model=EMBED_MODEL, input=text)
    return resp.data[0].embedding


def find_relevant_chunks(question, k=8, sources=None):
    """Hybrid search: vector meaning + keyword rank, with old vector fallback."""
    qvec = embed(question)
    try:
        result = supabase.rpc("match_documents_hybrid", {
            "query_embedding": json.dumps(qvec),
            "query_text": question,
            "match_count": k,
            "filter_sources": sources,
        }).execute()
    except Exception:
        result = supabase.rpc("match_documents", {
            "query_embedding": json.dumps(qvec),   # sent as a string, same as ingest
            "match_count": k,
            "filter_sources": sources,             # e.g. ["reddit"] or ["research","pdf"]
        }).execute()
    return result.data or []


def answer(question, sources=None):
    chunks = find_relevant_chunks(question, sources=sources)
    if not chunks:
        print("\nNo matching info found. Did you run ingest.py first?")
        return

    # build a numbered context block for the model
    context_lines = []
    for i, c in enumerate(chunks, start=1):
        url = c.get("source_url") or "no link"
        context_lines.append(f"[{i}] (source: {url})\n{c['content']}")
    context = "\n\n".join(context_lines)

    resp = openai.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {question}"},
        ],
    )
    print("\n--- ANSWER ---")
    print(resp.choices[0].message.content)

    print("\n--- SOURCES ---")
    for i, c in enumerate(chunks, start=1):
        sub = c.get("subreddit")
        tag = f"r/{sub}" if sub else "source"
        print(f"[{i}] {tag}  {c.get('source_url') or 'no link'}")


def main():
    question = input("Ask the brain a question: ").strip()
    if not question:
        return
    choice = input("Answer from? [1] consumer  [2] research  [3] books  [4] competitors/EAP  [Enter] all: ").strip()
    sources = {"1": ["reddit"], "2": ["research"], "3": ["pdf"], "4": ["b2b"]}.get(choice)  # None = all
    answer(question, sources)


if __name__ == "__main__":
    main()
