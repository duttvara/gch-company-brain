"""
ask_kpis.py  -  ask questions about your business KPIs. PRIVATE, local only.

Reads from two private sources (nothing is published to the web):
  1. A local CSV of your manual KPI sheet  ->  kpi.csv  (just download the sheet:
     File > Download > Comma-separated values, save it next to this script)
  2. Your live Stripe metrics stored in Supabase by ingest_stripe.py

It hands both tables to the LLM, which reads them and does the math (MRR, ARR,
growth, ratios). Financials never touch the public website.

Run it with:   python ask_kpis.py
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()
openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# where your downloaded KPI sheet lives (override with KPI_CSV in .env if you like)
KPI_CSV = os.environ.get(
    "KPI_CSV",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "kpi.csv"),
)

SYSTEM_PROMPT = (
    "You are the Greater Change Health finance brain. Answer questions about the "
    "company's KPIs using ONLY the tables provided. Do the math when asked "
    "(totals, month-over-month growth, ratios). Be precise with numbers and state "
    "which period a figure refers to. If the answer isn't in the data, say so. "
    "Do not invent numbers."
)


def load_local_csv():
    if KPI_CSV and os.path.exists(KPI_CSV):
        with open(KPI_CSV, encoding="utf-8", errors="replace") as f:
            return f.read()
    return ""


def load_stripe_snapshot():
    res = (supabase.table("kpi_snapshot")
           .select("metric,value,period,source")
           .order("period", desc=True)
           .limit(200)
           .execute())
    rows = res.data or []
    if not rows:
        return ""
    lines = ["metric,value,period,source"]
    for r in rows:
        lines.append(f"{r.get('metric')},{r.get('value')},{r.get('period')},{r.get('source')}")
    return "\n".join(lines)


def main():
    sheet = load_local_csv()
    stripe_data = load_stripe_snapshot()

    if not sheet and not stripe_data:
        raise SystemExit(
            "No KPI data found.\n"
            "  - Add a kpi.csv (download your sheet: File > Download > CSV), and/or\n"
            "  - run python ingest_stripe.py to pull Stripe metrics."
        )

    context = ""
    if sheet:
        context += "MANUAL KPI SHEET (CSV):\n" + sheet[:8000] + "\n\n"
    if stripe_data:
        context += "STRIPE METRICS (CSV, newest first):\n" + stripe_data[:6000] + "\n\n"

    question = input("Ask about the KPIs: ").strip()
    if not question:
        return

    resp = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context + "Question: " + question},
        ],
    )
    print("\n--- ANSWER ---")
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    main()
