"""
Daily report generator.
Aggregates call results from the database and produces a structured report.
"""

from collections import Counter
from datetime import datetime, date, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from models import CallLog, Lead, DailyReport


def generate_daily_report(db: Session, report_date: Optional[date] = None) -> dict:

    if report_date is None:
        report_date = date.today()

    start = datetime.combine(report_date, datetime.min.time())
    end = start + timedelta(days=1)

    calls = (
        db.query(CallLog)
        .filter(CallLog.created_at >= start, CallLog.created_at < end)
        .all()
    )

    leads_imported = db.query(Lead).count()
    leads_called = len(set(c.lead_id for c in calls))
    calls_connected = sum(1 for c in calls if c.call_result == "connected")
    qualified_buyers = sum(1 for c in calls if c.lead_type == "buyer" and c.call_result == "connected")
    qualified_sellers = sum(1 for c in calls if c.lead_type == "seller" and c.call_result == "connected")
    premium_prospects = sum(1 for c in calls if c.membership_potential == "high")
    renewal_prospects = sum(1 for c in calls if _is_renewal(c))
    human_escalations = sum(1 for c in calls if c.human_escalation_required)
    wrong_numbers = sum(1 for c in calls if c.call_result == "wrong_number")
    no_answer = sum(1 for c in calls if c.call_result == "no_answer")
    not_interested = sum(1 for c in calls if c.call_result == "not_interested")

    # Top products
    all_products = []
    for c in calls:
        if c.products:
            all_products.extend(c.products)
    top_products = [
        {"product": p, "count": cnt}
        for p, cnt in Counter(all_products).most_common(10)
    ]

    # Top countries
    country_counts = Counter(c.country for c in calls if c.country)
    top_countries = [
        {"country": k, "count": v}
        for k, v in country_counts.most_common(10)
    ]

    # Best leads (top 5 by score)
    best = sorted(
        [c for c in calls if c.call_result == "connected"],
        key=lambda c: c.lead_score or 0,
        reverse=True,
    )[:5]
    best_leads = [
        {
            "company_name": c.lead_id,  # would join to Lead table in production
            "country": c.country,
            "lead_type": c.lead_type,
            "lead_score": c.lead_score,
            "next_action": c.next_action,
        }
        for c in best
    ]

    market_comments = _generate_market_comments(calls)

    report_data = {
        "report_date": report_date.isoformat(),
        "leads_imported": leads_imported,
        "leads_called": leads_called,
        "calls_connected": calls_connected,
        "qualified_buyers": qualified_buyers,
        "qualified_sellers": qualified_sellers,
        "premium_prospects": premium_prospects,
        "renewal_prospects": renewal_prospects,
        "human_escalations": human_escalations,
        "wrong_numbers": wrong_numbers,
        "no_answer": no_answer,
        "not_interested": not_interested,
        "top_products": top_products,
        "top_countries": top_countries,
        "best_leads": best_leads,
        "market_comments": market_comments,
    }

    # Persist to DB
    existing = (
        db.query(DailyReport)
        .filter(DailyReport.report_date >= start, DailyReport.report_date < end)
        .first()
    )
    if existing:
        for k, v in report_data.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
        existing.raw_data = report_data
        db.commit()
        db.refresh(existing)
    else:
        dr = DailyReport(
            report_date=start,
            raw_data=report_data,
            **{k: v for k, v in report_data.items()
               if k not in ("report_date", "top_products", "top_countries", "best_leads", "market_comments")},
        )
        dr.top_products = top_products
        dr.top_countries = top_countries
        dr.best_leads = best_leads
        dr.market_comments = market_comments
        db.add(dr)
        db.commit()
        db.refresh(dr)

    return report_data


def _is_renewal(call: CallLog) -> bool:  # noqa: E302
    return bool(
        call.escalation_reason and
        any(kw in (call.escalation_reason or "").lower()
            for kw in ["renew", "renewal", "reactivat", "expired"])
    )


def _generate_market_comments(calls: list[CallLog]) -> str:
    if not calls:
        return "No calls completed today."

    connected = [c for c in calls if c.call_result == "connected"]
    if not connected:
        return f"{len(calls)} call attempts made. No connections established."

    buyer_count = sum(1 for c in connected if c.lead_type == "buyer")
    seller_count = sum(1 for c in connected if c.lead_type == "seller")

    products_seen = set()
    for c in connected:
        if c.products:
            products_seen.update(c.products[:3])

    countries_seen = set(c.country for c in connected if c.country)

    lines = [
        f"{len(connected)} calls connected out of {len(calls)} attempts "
        f"({round(len(connected)/len(calls)*100)}% connect rate).",
        f"Buyers qualified: {buyer_count}. Sellers qualified: {seller_count}.",
    ]
    if products_seen:
        lines.append(f"Products mentioned: {', '.join(list(products_seen)[:6])}.")
    if countries_seen:
        lines.append(f"Countries covered: {', '.join(list(countries_seen)[:6])}.")

    return " ".join(lines)
