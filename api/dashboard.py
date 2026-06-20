from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import Lead, CallLog

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    total_leads = db.query(Lead).count()
    dnc = db.query(Lead).filter(Lead.do_not_call == True).count()  # noqa
    escalations = db.query(Lead).filter(Lead.human_escalation_required == True).count()  # noqa

    score_dist = {
        "hot_80_plus": db.query(Lead).filter(Lead.lead_score >= 80).count(),
        "warm_50_79": db.query(Lead).filter(Lead.lead_score >= 50, Lead.lead_score < 80).count(),
        "cold_below_50": db.query(Lead).filter(Lead.lead_score < 50).count(),
    }

    call_results = (
        db.query(CallLog.call_result, func.count(CallLog.id))
        .group_by(CallLog.call_result)
        .all()
    )

    top_countries = (
        db.query(Lead.country, func.count(Lead.id).label("count"))
        .group_by(Lead.country)
        .order_by(func.count(Lead.id).desc())
        .limit(10)
        .all()
    )

    lead_types = (
        db.query(Lead.lead_type, func.count(Lead.id).label("count"))
        .group_by(Lead.lead_type)
        .all()
    )

    membership_potential = (
        db.query(Lead.membership_potential, func.count(Lead.id).label("count"))
        .group_by(Lead.membership_potential)
        .all()
    )

    return {
        "total_leads": total_leads,
        "do_not_call": dnc,
        "escalations_pending": escalations,
        "score_distribution": score_dist,
        "call_results": {r[0]: r[1] for r in call_results},
        "top_countries": [{"country": c[0], "count": c[1]} for c in top_countries],
        "lead_types": {t[0]: t[1] for t in lead_types},
        "membership_potential": {m[0]: m[1] for m in membership_potential},
    }


@router.get("/escalations")
def pending_escalations(db: Session = Depends(get_db)):
    leads = (
        db.query(Lead)
        .filter(Lead.human_escalation_required == True)  # noqa
        .order_by(Lead.lead_score.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "lead_id": l.lead_id,
            "company_name": l.company_name,
            "contact_name": l.contact_name,
            "country": l.country,
            "phone": l.phone,
            "lead_type": l.lead_type,
            "lead_score": l.lead_score,
            "urgency": l.urgency,
            "escalation_reason": l.escalation_reason,
            "call_summary": l.call_summary,
            "next_action": l.next_action,
        }
        for l in leads
    ]


@router.get("/hot-leads")
def hot_leads(db: Session = Depends(get_db)):
    leads = (
        db.query(Lead)
        .filter(Lead.lead_score >= 70)
        .order_by(Lead.lead_score.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "lead_id": l.lead_id,
            "company_name": l.company_name,
            "country": l.country,
            "lead_type": l.lead_type,
            "lead_score": l.lead_score,
            "urgency": l.urgency,
            "membership_potential": l.membership_potential,
            "call_summary": l.call_summary,
            "next_action": l.next_action,
            "follow_up_date": l.follow_up_date,
        }
        for l in leads
    ]
