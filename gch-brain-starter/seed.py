"""
seed.py  -  fills the brain with a few SAMPLE posts, no Apify needed.

Use this to test the "ask" step when your Apify credit is used up.
It embeds a handful of realistic therapy-cost posts with OpenAI and
saves them into Supabase, exactly like ingest.py would, just without
the scraping. Costs a fraction of a cent.

Run it with:   python seed.py
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()
openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

EMBED_MODEL = "text-embedding-3-small"

# realistic sample posts about therapy affordability
SAMPLE_POSTS = [
    {"text": "I really want to start therapy but $150 a session is just impossible on my salary. Are there any actually affordable options out there?", "url": "sample://post/1"},
    {"text": "Been putting off therapy for years because of the cost. My insurance barely covers anything and out of pocket is brutal.", "url": "sample://post/2"},
    {"text": "Online therapy has been a game changer for me price wise. I found something around $40 a week, way better than the $120 a session I was quoted locally.", "url": "sample://post/3"},
    {"text": "As a broke college student I basically gave up on finding a therapist. Everything is either not taking new patients or way out of my budget.", "url": "sample://post/4"},
    {"text": "The hardest part of mental health care isn't finding a therapist, it's affording one consistently. Sliding scale helped but the wait times were months.", "url": "sample://post/5"},
    {"text": "I wish more services offered group therapy. It's so much cheaper than one on one and honestly helped me just as much.", "url": "sample://post/6"},
]


def embed(text):
    return openai.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding


def main():
    for i, post in enumerate(SAMPLE_POSTS, start=1):
        vector = embed(post["text"])
        supabase.table("doc_chunks").insert({
            "content": post["text"],
            "embedding": json.dumps(vector),
            "motion": "b2c",
            "source_type": "sample",
            "source_url": post["url"],
        }).execute()
        print(f"  saved {i}: {post['text'][:55]}...")
    print(f"\nDone. Saved {len(SAMPLE_POSTS)} sample posts. Now run:  python ask.py")


if __name__ == "__main__":
    main()
