"""
ingest_web.py  -  add competitor + EAP website content to the brain (B2B intel).

Crawls a curated list of competitor and EAP-network pages with Apify's Website
Content Crawler (free, renders JavaScript, returns clean text), keeps the useful
pages via an LLM check, and stores them as source_type = "b2b".

Then the web app / CLI can answer "how do competitors position their employer
offering?" from real market pages.

Run it with:   python ingest_web.py
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
JUDGE_MODEL = "gpt-4o-mini"
CHUNK_SIZE = 3500
CHUNK_OVERLAP = 500

# curated competitor + EAP pages to study (edit freely)
START_URLS = [
    "https://www.betterhelp.com/",
    "https://www.talkspace.com/",
    "https://business.talkspace.com/",
    "https://www.lyrahealth.com/",
    "https://www.springhealth.com/",
    "https://www.modernhealth.com/",
    "https://www.calmhealth.com/",
    "https://www.headspace.com/organizations",
    "https://www.compsych.com/",           # EAP network
    "https://www.brightside.com/",         # telehealth mental health competitor
]


def chunk_text(text):
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i:i + CHUNK_SIZE])
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


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


def crawl():
    print(f"Crawling {len(START_URLS)} competitor / EAP pages...")
    run_input = {
        "startUrls": [{"url": u} for u in START_URLS],
        "crawlerType": "playwright:adaptive",   # renders JavaScript
        "maxCrawlDepth": 0,                      # only the pages we listed
        "maxResults": len(START_URLS) + 5,
        "saveMarkdown": True,
        "respectRobotsTxtFile": True,
        "proxyConfiguration": {"useApifyProxy": True},
    }
    run = apify.actor("apify/website-content-crawler").call(run_input=run_input)
    items = list(apify.dataset(dataset_id_from_run(run)).iterate_items())
    print(f"  got {len(items)} pages back")
    return items


def is_useful(text):
    """Page-level check: is this real competitive / market intel?"""
    prompt = (
        "You screen a web page for a mental-health company's competitive-intel library.\n"
        "Keep it if it reveals a competitor or EAP provider's offering, positioning, "
        "pricing, features, target market, or employer/B2B program details.\n"
        "Reply STRICT JSON: {\"useful\": true/false}.\n"
        "useful = false for cookie notices, legal boilerplate, careers pages, blog "
        "navigation, or empty/irrelevant content. When unsure, true.\n\n"
        f"TEXT:\n{text[:2000]}"
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


def main():
    items = crawl()
    saved, skipped = 0, 0

    for item in items:
        text = (item.get("markdown") or item.get("text") or "").strip()
        url = item.get("url")
        if len(text) < 200:
            skipped += 1
            continue
        if not is_useful(text):
            skipped += 1
            continue

        # refresh: delete any previous version of this page so re-runs don't duplicate
        if url:
            supabase.table("doc_chunks").delete().eq("source_url", url).execute()

        for chunk in chunk_text(text):
            if len(chunk.strip()) < 100:
                continue
            supabase.table("doc_chunks").insert({
                "content": chunk,
                "embedding": json.dumps(embed(chunk)),
                "motion": "b2b",
                "source_type": "b2b",
                "source_url": url,
            }).execute()
            saved += 1
        print(f"  saved page: {url}")

    print(f"\nDone. Saved {saved} chunks from competitor/EAP pages, skipped {skipped} pages.")
    print("Ask with:  python ask.py  (pick the Competitors & EAP filter)")


if __name__ == "__main__":
    main()
