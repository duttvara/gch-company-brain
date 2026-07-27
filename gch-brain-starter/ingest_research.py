"""
ingest_research.py  -  pull the LATEST, HIGH-QUALITY mental-health research.

Two free sources, no API keys:
  - PubMed (NCBI)  : the gold standard for clinical research. We bias it toward
                     the strongest evidence (meta-analyses, systematic reviews, RCTs).
  - OpenAlex       : broader open catalog, good for coverage.

It finds recent papers on your topics, skips ones already stored (dedup by link
AND by title so the two sources don't double up), and saves title + abstract into
the same Supabase brain as source_type = "research".

Run on a schedule (cron / GitHub Action) and the brain stays current on its own.

Run it with:   python ingest_research.py
"""

import os
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()
openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

EMBED_MODEL = "text-embedding-3-small"
CONTACT_EMAIL = "tim@henge.co"     # politeness token for both APIs

# --- optimized, business-aligned topics (sharp beats broad) ---
TOPICS = [
    "cost barriers to accessing mental health care",
    "teletherapy effectiveness",
    "digital mental health interventions",
    "employee assistance program mental health outcomes",
    "psychotherapy dropout and retention",
]

DAYS_BACK = 365        # research moves slower than Reddit; a year keeps it rich
PER_TOPIC = 15         # papers per source per topic
# PubMed only: keep the strongest evidence types. Set False to widen.
HIGH_EVIDENCE = True
EVIDENCE_FILTER = " AND (meta-analysis[pt] OR systematic review[pt] OR randomized controlled trial[pt])"


# ----------------------- PubMed (NCBI E-utilities) -----------------------
def pubmed_search(query, days):
    term = query + (EVIDENCE_FILTER if HIGH_EVIDENCE else "")
    params = {
        "db": "pubmed", "term": term, "retmax": str(PER_TOPIC),
        "sort": "relevance", "retmode": "json",
        "datetype": "pdat", "reldate": str(days),
        "email": CONTACT_EMAIL, "tool": "gch-brain",
    }
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=40) as r:
        data = json.loads(r.read().decode())
    return data.get("esearchresult", {}).get("idlist", [])


def pubmed_fetch(pmids):
    if not pmids:
        return []
    params = {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract",
              "retmode": "xml", "email": CONTACT_EMAIL, "tool": "gch-brain"}
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        root = ET.fromstring(r.read())

    out = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID") or ""
        title = "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else ""
        abstract = " ".join(
            "".join(e.itertext()) for e in art.findall(".//Abstract/AbstractText")
        ).strip()
        year = art.findtext(".//PubDate/Year") or art.findtext(".//PubDate/MedlineDate") or ""
        authors = []
        for a in art.findall(".//Author"):
            ln, fn = a.findtext("LastName"), a.findtext("ForeName")
            if ln:
                authors.append(f"{fn} {ln}" if fn else ln)
        out.append({
            "title": title, "abstract": abstract, "year": year,
            "authors": authors[:5],
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return out


# ----------------------- OpenAlex -----------------------
def reconstruct_abstract(inv):
    if not inv:
        return ""
    positions = {}
    for word, idxs in inv.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))


def openalex_search(query, from_date):
    params = {
        "search": query, "filter": f"from_publication_date:{from_date}",
        "sort": "publication_date:desc", "per-page": str(PER_TOPIC), "mailto": CONTACT_EMAIL,
    }
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": f"gch-brain/1.0 ({CONTACT_EMAIL})"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode())

    out = []
    for w in data.get("results", []):
        out.append({
            "title": w.get("title") or "",
            "abstract": reconstruct_abstract(w.get("abstract_inverted_index")),
            "year": w.get("publication_year") or "",
            "authors": [a["author"]["display_name"] for a in w.get("authorships", []) if a.get("author")][:5],
            "url": w.get("doi") or w.get("id"),
        })
    return out


# ----------------------- shared -----------------------
def already_have(url):
    res = supabase.table("doc_chunks").select("id").eq("source_url", url).limit(1).execute()
    return bool(res.data)


def embed(text):
    return openai.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding


def save(paper, seen_urls, seen_titles):
    url = paper.get("url")
    title = (paper.get("title") or "").strip()
    key = title.lower()
    if not url or url in seen_urls or key in seen_titles:
        return "dup"
    abstract = (paper.get("abstract") or "").strip()
    if len(abstract) < 100:
        return "thin"
    seen_urls.add(url)
    seen_titles.add(key)
    if already_have(url):
        return "have"

    content = (
        f"{title} ({paper.get('year')})\n"
        f"Authors: {', '.join(paper.get('authors', []))}\n\n"
        f"{abstract}"
    )
    supabase.table("doc_chunks").insert({
        "content": content,
        "embedding": json.dumps(embed(content[:6000])),
        "motion": "shared",
        "source_type": "research",
        "source_url": url,
    }).execute()
    return "saved"


def main():
    from_date = (date.today() - timedelta(days=DAYS_BACK)).isoformat()
    print(f"Pulling research since {from_date} (high-evidence PubMed + OpenAlex)...")

    seen_urls, seen_titles = set(), set()
    saved = 0

    for topic in TOPICS:
        print(f"\n[{topic}]")
        papers = []
        try:
            pmids = pubmed_search(topic, DAYS_BACK)
            time.sleep(0.4)
            papers += pubmed_fetch(pmids)
            time.sleep(0.4)
        except Exception as e:
            print(f"  ! PubMed failed: {e}")
        try:
            papers += openalex_search(topic, from_date)
        except Exception as e:
            print(f"  ! OpenAlex failed: {e}")

        for paper in papers:
            if save(paper, seen_urls, seen_titles) == "saved":
                saved += 1
                print(f"  saved: {paper['title'][:70]}...")

    print(f"\nDone. Saved {saved} new papers into the brain.")
    print("Ask about them with:  python ask.py  (pick the Research filter)")


if __name__ == "__main__":
    main()
