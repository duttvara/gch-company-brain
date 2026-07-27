"""
ingest.py  -  fills the brain with useful therapy consumer insight.

Simple rule: scrape posts + comments from therapy subreddits, and let the LLM
decide ONE thing per piece: "would this be useful to a therapy / mental-health
provider?" If yes, store it. If no (rules posts, bot messages, jokes, off-topic),
skip it. No topic buckets to fight with.

This usefulness gate is reusable: later, PDFs and other sources can flow through
the same "is this useful?" check before being stored.

Run it with:   python ingest.py
"""

import os
import json
from dotenv import load_dotenv
from apify_client import ApifyClient
from openai import OpenAI
from supabase import create_client

load_dotenv()
apify = ApifyClient(os.environ["APIFY_TOKEN"])
openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

EMBED_MODEL = "text-embedding-3-small"
JUDGE_MODEL = "gpt-4o-mini"   # cheap model just for the keep/skip decision

SUBREDDITS = ["therapy", "mentalhealth", "askatherapist", "TalkTherapy"]

JUNK_SUBREDDITS = {
    "amitheasshole", "aitah", "relationship_advice", "relationships", "tifu",
}


def scrape_reddit():
    urls = [f"https://www.reddit.com/r/{s}/" for s in SUBREDDITS]
    print(f"Pulling posts + comments from: {', '.join('r/' + s for s in SUBREDDITS)} ...")
    run_input = {
        "urls": urls,
        "sort": "hot",               # active threads = real discussion
        "maxPostsPerSource": 12,     # posts per subreddit
        "includeComments": True,     # the real insight lives in comments
        "maxCommentsPerPost": 12,    # how MANY comments per post
        "commentDepth": 2,           # how DEEP into reply threads (not a comment count)
        "deduplicatePosts": True,
    }
    run = apify.actor("automation-lab/reddit-scraper").call(run_input=run_input)
    items = list(apify.dataset(dataset_id_from_run(run)).iterate_items())
    print(f"  got {len(items)} raw items back")
    return items

def dataset_id_from_run(run):
    if isinstance(run, dict):
        return run.get("defaultDatasetId") or run.get("default_dataset_id")
    for attr in ("default_dataset_id", "defaultDatasetId"):
        if hasattr(run, attr): 
            return getattr(run, attr)
    if hasattr(run, "model_dump"):
        d = run.model_dump()
        return d.get("defaultDatasetId") or d.get("default_dataset_id")
    raise RuntimeError("Could not find the dataset id on the Apify run result.")


def get_text(item):
    parts = []
    for key in ("title", "selfText", "body", "text", "selftext"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    return "\n".join(dict.fromkeys(parts))


def get_subreddit(item):
    name = item.get("subreddit") or item.get("communityName") or ""
    if name.lower().startswith("r/"):
        name = name[2:]
    return name.lower()


def is_useful(text):
    """The one decision: would this help a therapy / mental-health provider?"""
    prompt = (
        "You screen text for a therapy / mental-health provider's insight library.\n"
        "Keep it if it reflects a real person's experience, opinion, question, need, "
        "complaint, or preference about therapy or mental health (anything that helps "
        "the provider understand their market or clients).\n"
        "Reply with STRICT JSON: {\"useful\": true/false}.\n"
        "useful = false for subreddit rules, mod or bot messages, FAQs, deleted/removed "
        "text, jokes, or content unrelated to therapy or mental health. When unsure, true.\n\n"
        f"TEXT:\n{text[:1500]}"
    )
    resp = openai.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=30,
        temperature=0,
    )
    return bool(json.loads(resp.choices[0].message.content).get("useful", True))


def embed(text):
    return openai.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding


def already_have(url):
    """True if we've already stored this exact post/comment (skip it)."""
    if not url:
        return False
    res = supabase.table("doc_chunks").select("id").eq("source_url", url).limit(1).execute()
    return bool(res.data)


def main():
    items = scrape_reddit()
    saved, skipped = 0, 0

    for item in items:
        text = get_text(item)
        subreddit = get_subreddit(item)
        url = item.get("url") or item.get("link") or item.get("permalink")

        # cheap pre-filters before spending an LLM call
        if len(text) < 40 or subreddit in JUNK_SUBREDDITS:
            skipped += 1
            continue

        # skip anything we already have (so weekly runs only add NEW posts)
        if already_have(url):
            skipped += 1
            continue

        if not is_useful(text):
            skipped += 1
            continue

        vector = embed(text[:4000])
        supabase.table("doc_chunks").insert({
            "content": text[:4000],
            "embedding": json.dumps(vector),
            "motion": "b2c",
            "source_type": "reddit",
            "source_url": url,
            "subreddit": subreddit,
            "upvotes": item.get("score"),
        }).execute()

        saved += 1
        print(f"  saved r/{subreddit}: {text[:60].replace(chr(10), ' ')}...")

    print(f"\nDone. Saved {saved} useful pieces, skipped {skipped}.")
    print("Now run:  python ask.py")


if __name__ == "__main__":
    main()
