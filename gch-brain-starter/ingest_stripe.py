"""
ingest_stripe.py  -  pull live financial metrics from Stripe into the brain.

Computes the real numbers from your Stripe account:
  - MRR (monthly recurring revenue, normalized across plan intervals)
  - ARR (= MRR x 12)
  - active_subscribers, trialing_subscribers, ARPU
  - new_customers_this_month, canceled_subs_this_month, approx churn %
  - gross_volume_this_month (charges minus refunds)

...and stores them in Supabase 'kpi_snapshot' with today's date, building history.
ask_kpis.py then answers from these numbers.

SECURITY: use a RESTRICTED, read-only Stripe key (rk_...), never your secret key.

Run it with:   python ingest_stripe.py
"""

import os
from datetime import date, datetime, timezone
from dotenv import load_dotenv
from supabase import create_client
import stripe

load_dotenv()
stripe.api_key = os.environ["STRIPE_API_KEY"]
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def g(obj, key, default=None):
    """Safe getter that works on Stripe objects AND plain dicts."""
    try:
        val = obj[key]
    except (KeyError, TypeError, AttributeError):
        return default
    return default if val is None else val


def monthly_amount(price, quantity):
    """Normalize any plan interval to a monthly dollar amount."""
    amount = g(price, "unit_amount", 0) * (quantity or 1)   # cents
    rec = g(price, "recurring", {})
    interval = g(rec, "interval", "month")
    count = g(rec, "interval_count", 1) or 1
    if interval == "year":
        amount = amount / (12 * count)
    elif interval == "month":
        amount = amount / count
    elif interval == "week":
        amount = amount * 52 / 12 / count
    elif interval == "day":
        amount = amount * 365 / 12 / count
    return amount / 100.0   # cents -> dollars


def compute_metrics():
    mrr = 0.0
    active = 0
    for sub in stripe.Subscription.list(status="active", limit=100).auto_paging_iter():
        active += 1
        items = g(sub, "items", {})
        for item in g(items, "data", []):
            mrr += monthly_amount(g(item, "price", {}), g(item, "quantity", 1))

    trialing = 0
    for _ in stripe.Subscription.list(status="trialing", limit=100).auto_paging_iter():
        trialing += 1

    # start of this month (UTC)
    now = datetime.now(timezone.utc)
    month_start = int(datetime(now.year, now.month, 1, tzinfo=timezone.utc).timestamp())

    new_customers = 0
    for _ in stripe.Customer.list(created={"gte": month_start}, limit=100).auto_paging_iter():
        new_customers += 1

    canceled = 0
    for sub in stripe.Subscription.list(status="canceled", limit=100).auto_paging_iter():
        ca = g(sub, "canceled_at")
        if ca and ca >= month_start:
            canceled += 1

    # actual money collected this month (charges minus refunds)
    gross = 0.0
    for ch in stripe.Charge.list(created={"gte": month_start}, limit=100).auto_paging_iter():
        if g(ch, "status") == "succeeded" and g(ch, "paid"):
            gross += (g(ch, "amount", 0) - g(ch, "amount_refunded", 0)) / 100.0

    arpu = round(mrr / active, 2) if active else 0.0
    churn_rate = round(canceled / (active + canceled) * 100, 2) if (active + canceled) else 0.0

    return {
        "MRR": round(mrr, 2),
        "ARR": round(mrr * 12, 2),
        "active_subscribers": active,
        "trialing_subscribers": trialing,
        "ARPU": arpu,
        "new_customers_this_month": new_customers,
        "canceled_subs_this_month": canceled,
        "churn_rate_pct_approx": churn_rate,
        "gross_volume_this_month": round(gross, 2),
    }


def main():
    print("Pulling metrics from Stripe...")
    metrics = compute_metrics()
    today = date.today().isoformat()

    # replace today's stripe snapshot (so same-day re-runs don't duplicate)
    supabase.table("kpi_snapshot").delete().eq("source", "stripe").eq("period", today).execute()

    for metric, value in metrics.items():
        supabase.table("kpi_snapshot").insert({
            "metric": metric,
            "value": value,
            "period": today,
            "source": "stripe",
        }).execute()
        print(f"  {metric}: {value}")

    print(f"\nDone. Stripe snapshot saved for {today}.")
    print("Ask about it with:  python ask_kpis.py")


if __name__ == "__main__":
    main()
