#!/usr/bin/env python3
"""
Import leads from a CSV file into the database.

Usage:
    python scripts/import_csv.py leads.csv
    python scripts/import_csv.py templates/lead_sheet_template.csv --dry-run
"""

import sys
import os
import csv
import uuid
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import SessionLocal, init_db
from models import Lead
from services.lead_scoring import score_lead


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in ("true", "yes", "1")


def parse_date(value: str):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def import_csv(filepath: str, dry_run: bool = False):
    init_db()
    db = SessionLocal()

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} rows in {filepath}")

    created = skipped = errors = 0
    for row in rows:
        company = row.get("company_name", "").strip()
        phone = row.get("phone", "").strip()
        if not company or not phone:
            print(f"  SKIP (no company/phone): {row}")
            skipped += 1
            continue

        lead_id = row.get("lead_id", "").strip() or str(uuid.uuid4())[:12]

        if not dry_run:
            existing = db.query(Lead).filter(Lead.lead_id == lead_id).first()
            if existing:
                print(f"  SKIP (exists): {lead_id} — {company}")
                skipped += 1
                continue

        try:
            lead = Lead(
                lead_id=lead_id,
                company_name=company,
                contact_name=row.get("contact_name"),
                country=row.get("country", ""),
                phone=phone,
                email=row.get("email"),
                language=row.get("language", "en"),
                member_type=row.get("member_type"),
                registration_date=parse_date(row.get("registration_date")),
                last_activity=parse_date(row.get("last_activity")),
                buyer_or_seller=row.get("buyer_or_seller"),
                product_interest=row.get("product_interest"),
                posted_offer=parse_bool(row.get("posted_offer", "false")),
                posted_request=parse_bool(row.get("posted_request", "false")),
                assigned_salesperson=row.get("assigned_salesperson"),
                last_contact_date=parse_date(row.get("last_contact_date")),
                do_not_call=parse_bool(row.get("do_not_call", "false")),
                notes=row.get("notes"),
                source=row.get("source", "csv_import"),
            )

            result = score_lead(lead)
            lead.lead_score = result.score
            lead.lead_type = result.lead_type
            lead.urgency = result.urgency
            lead.membership_potential = result.membership_potential

            if dry_run:
                print(f"  DRY RUN: {lead_id} — {company} | score={lead.lead_score} | type={lead.lead_type} | urgency={lead.urgency}")
            else:
                db.add(lead)
                db.commit()
                print(f"  CREATED: {lead_id} — {company} | score={lead.lead_score} | type={lead.lead_type}")
            created += 1

        except Exception as e:
            print(f"  ERROR: {company} — {e}")
            db.rollback()
            errors += 1

    db.close()
    print(f"\nDone: {created} created, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import leads from CSV")
    parser.add_argument("filepath", help="Path to CSV file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    args = parser.parse_args()
    import_csv(args.filepath, dry_run=args.dry_run)
