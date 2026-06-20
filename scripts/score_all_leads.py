#!/usr/bin/env python3
"""
Re-score all leads in the database.
Useful after updating the scoring rules.

Usage:
    python scripts/score_all_leads.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import SessionLocal, init_db
from models import Lead
from services.lead_scoring import score_lead


def main():
    init_db()
    db = SessionLocal()

    leads = db.query(Lead).all()
    print(f"Scoring {len(leads)} leads…")

    updated = 0
    for lead in leads:
        result = score_lead(lead)
        lead.lead_score = result.score
        lead.lead_type = result.lead_type
        lead.urgency = result.urgency
        lead.membership_potential = result.membership_potential
        updated += 1

    db.commit()
    db.close()
    print(f"Done. {updated} leads updated.")


if __name__ == "__main__":
    main()
