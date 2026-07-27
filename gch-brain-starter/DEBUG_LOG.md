# Debug Log: Building the Reddit RAG Loop

A study log of every error we hit getting the starter brain working, what it
meant in plain English, why it happened, and how we fixed it. Read top to bottom.

Setup we were building: scrape Reddit (Apify) -> embed (OpenAI) -> store
(Supabase pgvector) -> ask a question and get a cited answer.

---

## The mental model to hold onto

Two flows, and most confusion came from mixing them up:

- **Filling the brain** = `ingest.py` (or `seed.py`). SLOW, because it collects
  data. It SAVES chunks. You do it occasionally.
- **Asking the brain** = `ask.py`. FAST. It only READS and answers. It saves nothing.

Rule: `ingest`/`seed` write. `ask` reads. That is it.

---

## Error 1: Anaconda Python was broken

**What I saw**
```
ModuleNotFoundError: No module named '_sysconfigdata__darwin_darwin'
```
while running `pip install -r requirements.txt`.

**What it meant**
`pip` itself couldn't figure out my system's platform. The Anaconda "base"
environment was misconfigured. Note: my Python could still *run* scripts, but
`pip` (the installer) was the broken piece.

**Why it happened**
A stale/wrong setting in the Anaconda base environment on macOS. Common Anaconda quirk.

**How we fixed it**
Stopped fighting the broken base and made a clean, separate environment:
```
conda create -n gchbrain python=3.11 -y
conda activate gchbrain
```
A fresh environment sidesteps whatever was corrupted in base.

**Lesson**
When a Python environment is weird, don't debug it forever. Make a fresh virtual
environment. `(gchbrain)` at the start of the terminal line means it's active.
You must re-run `conda activate gchbrain` in every new terminal window.

---

## Error 2: No module named 'dotenv'

**What I saw**
```
ModuleNotFoundError: No module named 'dotenv'
```
when running `python ingest.py`.

**What it meant**
The script needs a library called `python-dotenv`, and it wasn't installed.

**Why it happened**
The earlier `pip install` had failed (Error 1), so NOTHING got installed.

**How we fixed it**
Got the install working in the clean environment, which installed all the
libraries in `requirements.txt`.

**Lesson**
"No module named X" almost always means "you didn't (successfully) install X."
Check that your `pip install` actually finished without red errors.

---

## Error 3: cryptography refused to install

**What I saw**
```
ERROR: Failed building wheel for cryptography
error: failed-wheel-build-for-install
```
(with mentions of `maturin`, `cargo`, `rust`)

**What it meant**
One dependency, `cryptography`, tried to **compile itself from source code**.
Compiling it needs the Rust programming language installed, which I don't have,
so it failed. Because one package failed, the whole install stopped.

**Why it happened**
`pip` couldn't find a ready-made ("wheel") version for my exact setup, so it fell
back to building from scratch. Upgrading pip alone didn't fix it.

**How we fixed it**
Let **conda** install a prebuilt copy (conda always ships compiled binaries), then
let pip do the rest:
```
conda install -c conda-forge cryptography -y
pip install --prefer-binary -r requirements.txt
```

**Lesson**
"Failed building wheel" = pip is trying to compile C/Rust code and can't. Easiest
fixes: upgrade pip, or install that one package with conda, or use `--prefer-binary`.

---

## Error 4: OpenAI missing credentials

**What I saw**
```
openai.OpenAIError: Missing credentials. Please pass an api_key ...
```

**What it meant**
The code started OpenAI but found no API key.

**Why it happened**
The `OPENAI_API_KEY=` line in my `.env` file was empty (not filled in).

**How we fixed it**
Opened `.env`, pasted the real key right after the `=` (no spaces, no quotes),
saved with Cmd+S.

**Lesson**
"Missing credentials" = a key in your `.env` is blank or wrong. The format is
`NAME=value` with the value right after the equals sign.

---

## Error 5: Apify rejected the input (sort value)

**What I saw**
```
InvalidRequestError: Input is not valid: Field input.sort must be equal to
one of the allowed values: "", "relevance", "hot", "top", "new", "rising", "comments"
```

**What it meant**
Apify got a setting it didn't accept. I sent `sort = "TOP"` but it only accepts
lowercase like `"top"`.

**Why it happened**
The script had `"sort": "TOP"` and `"time": "YEAR"` in capitals. The actor wants lowercase.

**How we fixed it**
Changed them to `"sort": "top"` and `"time": "year"` in `ingest.py`.

**Lesson**
Read the error, it literally lists the allowed values. Actor inputs are picky
about exact spelling and case. Two good signs from this error: my OpenAI key
worked (it got past that), and Apify connected fine.

---

## Error 6: 'Run' object is not subscriptable

**What I saw**
```
TypeError: 'Run' object is not subscriptable
```
at `run["defaultDatasetId"]`.

**What it meant**
"Not subscriptable" = you used square brackets `[...]` on something that isn't a
dictionary/list. My newer Apify library returns the run as an *object*, and you
read an object's fields with a dot (`run.default_dataset_id`), not brackets.

**Why it happened**
Newer library version changed the return type from a dict to an object.

**How we fixed it**
Added a helper (`dataset_id_from_run`) that works whether the library returns a
dict or an object, and in either naming style.

**Lesson**
"X is not subscriptable" = wrong access style. Dicts use `x["key"]`, objects use
`x.attribute`. Library versions can change which one you get.

---

## Error 7: permission denied for table doc_chunks

**What I saw**
```
APIError: permission denied for table doc_chunks (code 42501)
hint: GRANT SELECT ON public.doc_chunks TO service_role
```

**What it meant**
My database key wasn't allowed to read/write that table.

**Why it happened**
When I created the Supabase project, I unchecked "Automatically expose new
tables." That is the setting that normally grants the key access to new tables.

**How we fixed it**
Granted the permissions manually in the Supabase SQL Editor:
```sql
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
grant execute on all functions in schema public to service_role;
```

**Lesson**
Database "permission denied" is about GRANTs, not your code. The error even gives
you the exact fix in the hint. Choices made at setup (like that checkbox) have
consequences later.

---

## Error 8: Apify said I'd exceed my usage

**What I saw**
```
ApifyApiError: By launching this job you will exceed your remaining usage of $0.01421.
```

**What it meant**
My free Apify credit was nearly gone, so it refused to start another scrape.

**Why it happened**
The earlier test scrapes used up the free monthly allowance.

**How we fixed it**
Two things:
1. Made `seed.py`, which fills the brain with sample posts using OpenAI only (no
   Apify), so I can test the "ask" side for free.
2. Upgraded to the Apify Starter plan and set a **monthly usage limit** (kept it
   at $29, the prepaid amount) so I can never be charged overage.

**Lesson**
Metered services can stop you mid-task. Always set a spending limit. And you
don't need live scraping to test the rest of the pipeline, sample data works.

---

## Error 9: unexpected keyword argument 'timeout_secs'

**What I saw**
```
TypeError: ActorClient.call() got an unexpected keyword argument 'timeout_secs'
```

**What it meant**
I passed a setting (`timeout_secs`) that my version of the Apify library's
`.call()` doesn't accept.

**Why it happened**
I added `max_items` and `timeout_secs` as safety caps, but this library version
doesn't take those arguments.

**How we fixed it**
Removed them. Cost is already capped by `maxItems`/`maxPostCount` inside the
input, plus the $29 account limit as a backstop.

**Lesson**
"unexpected keyword argument" = you passed an option the function doesn't have,
often a version mismatch. Remove it or check that version's docs.

---

## Error 10: No matching info found

**What I saw**
```
No matching info found. Did you run ingest.py first?
```

**What it meant**
`ask.py` searched the brain and found nothing.

**Why it happened**
The table was empty because the previous `ingest.py` run had errored before
saving anything.

**How we fixed it**
Actually got data in (via `seed.py` or a successful `ingest.py`), then asked again.

**Lesson**
Empty results usually mean the brain wasn't filled, not that search is broken.
Fill first (`ingest`/`seed`), then ask.

---

## Two "not an error" confusions worth remembering

**A) ingest is slow, ask is instant.**
Not a bug. `ingest.py` scrapes live (slow). `ask.py` just reads what's stored
(instant). This is the whole point of separating "fill" from "ask."

**B) "It saved chunks when I ran ask?"**
No. Those `saved 1...` lines were `ingest.py` finishing. I had typed `python
ask.py` before ingest was done, so the outputs overlapped on screen. `ask.py`
never saves.

**C) The scraper returned off-topic posts.**
My search pulled some "AITA" relationship posts instead of therapy-cost posts, so
answers were thin. That is a data-quality / search-relevance problem, not a code
bug. Fixes: better search terms, more results, or filtering. (A good next lesson.)

---

## Quick cheat sheet: error -> meaning

| Error text | Real meaning | Typical fix |
|---|---|---|
| No module named X | X isn't installed | `pip install X` (in the right env) |
| Failed building wheel | pip is compiling and can't | conda install it, or `--prefer-binary` |
| Missing credentials | a key in `.env` is blank/wrong | fill the key correctly |
| Input ... must be one of | bad value sent to an API | match allowed values exactly (case!) |
| not subscriptable | used `[ ]` on an object | use `.attribute` instead |
| permission denied (42501) | DB grants missing | run the GRANT the hint shows |
| exceed your usage | out of paid credit | add credit / set spend limit |
| unexpected keyword argument | passed an option that doesn't exist | remove it / check version |
| No matching info | brain is empty | run ingest/seed first |

---

## Concepts I picked up along the way
- **Virtual environments** isolate a project's Python so a broken base doesn't sink you.
- **Wheels vs source builds**: prebuilt (fast) vs compile-your-own (slow, can fail).
- **.env files** hold secret keys, separate from code.
- **Embeddings + pgvector** = search by meaning.
- **Grounding/citations**: the brain answers only from stored data and links sources.
- **Metered APIs** (Apify) need spending limits.
- **Library versions matter**: return types and arguments change between versions.
