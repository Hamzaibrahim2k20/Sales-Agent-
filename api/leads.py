from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
from database import get_db
from models import Lead
from schemas import LeadCreate, LeadUpdate, LeadResponse
from services.lead_scoring import score_lead, prioritise_call_queue
import uuid

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("/", response_model=List[LeadResponse])
def list_leads(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    country: Optional[str] = None,
    lead_type: Optional[str] = None,
    urgency: Optional[str] = None,
    call_status: Optional[str] = None,
    human_escalation: Optional[bool] = None,
    min_score: Optional[float] = None,
):
    q = db.query(Lead)
    if country:
        q = q.filter(Lead.country.ilike(f"%{country}%"))
    if lead_type:
        q = q.filter(Lead.lead_type == lead_type)
    if urgency:
        q = q.filter(Lead.urgency == urgency)
    if call_status:
        q = q.filter(Lead.call_status == call_status)
    if human_escalation is not None:
        q = q.filter(Lead.human_escalation_required == human_escalation)
    if min_score is not None:
        q = q.filter(Lead.lead_score >= min_score)
    q = q.order_by(Lead.lead_score.desc())
    return q.offset(skip).limit(limit).all()


@router.post("/", response_model=LeadResponse, status_code=201)
def create_lead(lead_in: LeadCreate, db: Session = Depends(get_db)):
    if not lead_in.lead_id:
        lead_in.lead_id = str(uuid.uuid4())[:12]

    existing = db.query(Lead).filter(Lead.lead_id == lead_in.lead_id).first()
    if existing:
        raise HTTPException(400, detail=f"Lead {lead_in.lead_id} already exists")

    lead = Lead(**lead_in.model_dump())
    db.add(lead)
    db.flush()

    # Auto-score
    result = score_lead(lead)
    lead.lead_score = result.score
    lead.lead_type = result.lead_type
    lead.urgency = result.urgency
    lead.membership_potential = result.membership_potential

    db.commit()
    db.refresh(lead)
    return lead


@router.get("/queue", response_model=List[LeadResponse])
def call_queue(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=200),
):
    """Return leads sorted by priority, ready to call."""
    leads = (
        db.query(Lead)
        .filter(
            Lead.do_not_call == False,  # noqa: E712
            Lead.call_status.in_(["pending", "no_answer", "callback"]),
        )
        .all()
    )
    return prioritise_call_queue(leads)[:limit]


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(404, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(lead_id: str, update: LeadUpdate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(404, detail="Lead not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=204)
def delete_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(404, detail="Lead not found")
    db.delete(lead)
    db.commit()


@router.post("/{lead_id}/score", response_model=LeadResponse)
def rescore_lead(lead_id: str, db: Session = Depends(get_db)):
    """Recalculate the lead score."""
    lead = db.query(Lead).filter(Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(404, detail="Lead not found")
    result = score_lead(lead)
    lead.lead_score = result.score
    lead.lead_type = result.lead_type
    lead.urgency = result.urgency
    lead.membership_potential = result.membership_potential
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/bulk-import")
def bulk_import(leads_in: List[LeadCreate], db: Session = Depends(get_db)):
    """Import multiple leads at once (e.g. from CSV upload)."""
    created = 0
    skipped = 0
    for lead_in in leads_in:
        if not lead_in.lead_id:
            lead_in.lead_id = str(uuid.uuid4())[:12]
        existing = db.query(Lead).filter(Lead.lead_id == lead_in.lead_id).first()
        if existing:
            skipped += 1
            continue
        lead = Lead(**lead_in.model_dump())
        db.add(lead)
        db.flush()
        result = score_lead(lead)
        lead.lead_score = result.score
        lead.lead_type = result.lead_type
        lead.urgency = result.urgency
        lead.membership_potential = result.membership_potential
        created += 1
    db.commit()
    return {"created": created, "skipped": skipped}


@router.post("/sync-from-sheets")
def sync_from_sheets(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Pull leads from Google Sheets and import into DB."""
    background_tasks.add_task(_sync_sheets_task, db)
    return {"status": "sync started"}


def _sync_sheets_task(db: Session):
    from services.google_sheets import fetch_leads
    import uuid as _uuid

    rows = fetch_leads()
    created = skipped = 0
    for row in rows:
        lid = row.get("lead_id") or str(_uuid.uuid4())[:12]
        existing = db.query(Lead).filter(Lead.lead_id == lid).first()
        if existing:
            skipped += 1
            continue
        lead = Lead(
            lead_id=lid,
            company_name=row.get("company_name", ""),
            contact_name=row.get("contact_name"),
            country=row.get("country", ""),
            phone=row.get("phone", ""),
            email=row.get("email"),
            language=row.get("language", "en"),
            member_type=row.get("member_type"),
            buyer_or_seller=row.get("buyer_or_seller"),
            product_interest=row.get("product_interest"),
            assigned_salesperson=row.get("assigned_salesperson"),
            do_not_call=str(row.get("do_not_call", "")).lower() in ("true", "yes", "1"),
            notes=row.get("notes"),
            source="google_sheets",
        )
        db.add(lead)
        db.flush()
        result = score_lead(lead)
        lead.lead_score = result.score
        lead.lead_type = result.lead_type
        lead.urgency = result.urgency
        lead.membership_potential = result.membership_potential
        created += 1
    db.commit()
