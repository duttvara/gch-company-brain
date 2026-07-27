"""
ingest_pdfs.py  -  add books/papers (PDF or EPUB) to the brain.

How to use:
  1. Put your .pdf and/or .epub files in the "pdfs" folder next to this script.
  2. Run:  python ingest_pdfs.py

It reads each file, splits it into bite-size chunks, embeds them with OpenAI, and
stores them in the SAME Supabase table as everything else (source_type = "pdf").
So ask.py and the web app can answer from your books too, no other changes needed.

Note: works on real text files. Scanned/image PDFs need OCR (not handled here).
"""

import os
import glob
import json
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
from pypdf import PdfReader
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

load_dotenv()
openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

EMBED_MODEL = "text-embedding-3-small"
PDF_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdfs")

CHUNK_SIZE = 3500      # characters per chunk (~800 tokens)
CHUNK_OVERLAP = 500    # overlap so ideas aren't cut in half


def chunk_text(text):
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + CHUNK_SIZE])
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def read_pdf(path):
    reader = PdfReader(path)
    pages = [(page.extract_text() or "") for page in reader.pages]
    return " ".join("\n".join(pages).split())


def read_epub(path):
    # Case 1: the epub got unzipped into a folder. Read its html chapters directly.
    if os.path.isdir(path):
        html_files = sorted(
            glob.glob(os.path.join(path, "**", "*.xhtml"), recursive=True) +
            glob.glob(os.path.join(path, "**", "*.html"), recursive=True) +
            glob.glob(os.path.join(path, "**", "*.htm"), recursive=True)
        )
        parts = []
        for hf in html_files:
            with open(hf, "rb") as f:
                parts.append(BeautifulSoup(f.read(), "html.parser").get_text(" "))
        return " ".join(" ".join(parts).split())

    # Case 2: a normal single .epub file.
    book = epub.read_epub(path)
    parts = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:      # the readable chapters
            soup = BeautifulSoup(item.get_content(), "html.parser")
            parts.append(soup.get_text(" "))
    return " ".join(" ".join(parts).split())


def read_book(path):
    """Pick the right reader based on file type."""
    if path.lower().endswith(".epub"):
        return read_epub(path)
    return read_pdf(path)


def embed(text):
    return openai.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding


def main():
    paths = sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")) +
                   glob.glob(os.path.join(PDF_FOLDER, "*.epub")))
    if not paths:
        print(f"No PDF or EPUB files found in:\n  {PDF_FOLDER}\nPut your books there and run again.")
        return

    total = 0
    for path in paths:
        name = os.path.basename(path)
        print(f"Reading {name} ...")
        try:
            text = read_book(path)
        except Exception as e:
            print(f"  ! could not read {name}: {e}")
            continue

        if len(text) < 200:
            print(f"  skipped {name}: almost no text found (is it a scanned image?)")
            continue

        chunks = chunk_text(text)
        saved_here = 0
        for chunk in chunks:
            if len(chunk.strip()) < 100:
                continue
            vector = embed(chunk)
            supabase.table("doc_chunks").insert({
                "content": chunk,
                "embedding": json.dumps(vector),
                "motion": "shared",
                "source_type": "pdf",
                "source_url": name,
            }).execute()
            saved_here += 1
            total += 1
        print(f"  saved {saved_here} chunks from {name}")

    print(f"\nDone. Saved {total} book chunks into the brain.")
    print("Ask about them with:  python ask.py")


if __name__ == "__main__":
    main()
