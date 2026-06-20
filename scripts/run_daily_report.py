#!/usr/bin/env python3
"""
Generate and optionally sync the daily report.

Usage:
    python scripts/run_daily_report.py
    python scripts/run_daily_report.py --date 2026-06-19 --sync-sheets
"""

import sys
import os
import argparse
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import SessionLocal, init_db
from services.report_generator import generate_daily_report


def main():
    parser = argparse.ArgumentParser(description="Generate daily report")
    parser.add_argument("--date", help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--sync-sheets", action="store_true", help="Write report to Google Sheets")
    args = parser.parse_args()

    report_date = None
    if args.date:
        report_date = date.fromisoformat(args.date)

    init_db()
    db = SessionLocal()

    try:
        print("Generating daily report…")
        report = generate_daily_report(db, report_date)

        print("\n" + "=" * 50)
        print("FORDAQ CALLING AGENT — DAILY REPORT")
        print(f"Date: {report.get('report_date')}")
        print("=" * 50)
        print(f"Leads imported:      {report['leads_imported']}")
        print(f"Leads called:        {report['leads_called']}")
        print(f"Calls connected:     {report['calls_connected']}")
        print(f"Qualified buyers:    {report['qualified_buyers']}")
        print(f"Qualified sellers:   {report['qualified_sellers']}")
        print(f"Premium prospects:   {report['premium_prospects']}")
        print(f"Renewal prospects:   {report['renewal_prospects']}")
        print(f"Human escalations:   {report['human_escalations']}")
        print(f"Wrong numbers:       {report['wrong_numbers']}")
        print(f"No answer:           {report['no_answer']}")
        print(f"Not interested:      {report['not_interested']}")

        if report.get("top_products"):
            print("\nTop Products:")
            for p in report["top_products"][:5]:
                print(f"  {p['product']}: {p['count']}")

        if report.get("top_countries"):
            print("\nTop Countries:")
            for c in report["top_countries"][:5]:
                print(f"  {c['country']}: {c['count']}")

        if report.get("market_comments"):
            print(f"\nComments: {report['market_comments']}")

        if args.sync_sheets:
            from services.google_sheets import write_daily_report
            print("\nSyncing to Google Sheets…")
            write_daily_report(report)
            print("Done.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
