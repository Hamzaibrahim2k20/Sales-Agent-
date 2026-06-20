from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from database import get_db
from models import Lead, CallLog
from schemas import (
    CallLogResponse, InitiateCallRequest, BulkCallRequest
)
from services.vapi_client import get_voice_client
from config import settings

router = APIRouter(prefix="/calls", tags=["calls"])


@router.post("/initiate")
async def initiate_call(
    request: InitiateCallRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.lead_id == request.lead_id).first()
    if not lead:
        raise HTTPException(404, detail="Lead not found")

    if lead.do_not_call:
        raise HTTPException(400, detail="Lead is marked do-not-call")

    phone = request.override_phone or lead.phone
    if not phone:
        raise HTTPException(400, detail="No phone number available")

    lead_type = request.script_type or lead.lead_type or "unknown"
    webhook_url = f"{settings.public_base_url}/webhooks/vapi"

    client = get_voice_client()
    try:
        result = await client.create_call(
            phone=phone,
            lead_id=lead.lead_id,
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            country=lead.country,
            lead_type=lead_type,
            member_type=lead.member_type or "",
            product_interest=lead.product_interest,
            webhook_url=webhook_url,
            language=lead.language or None,
        )
    except Exception as e:
        raise HTTPException(502, detail=f"Voice provider error: {e}")

    # Update lead call tracking
    lead.call_attempts = (lead.call_attempts or 0) + 1
    lead.last_call_date = datetime.utcnow()
    lead.call_status = "in_progress"
    db.commit()

    return {
        "status": "call_initiated",
        "lead_id": lead.lead_id,
        "call_id": result.get("id"),
        "provider": settings.voice_provider,
    }


@router.post("/bulk-initiate")
async def bulk_initiate_calls(
    request: BulkCallRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Queue multiple calls. Processes sequentially in background."""
    background_tasks.add_task(
        _process_bulk_calls, request.lead_ids, request.max_concurrent
    )
    return {
        "status": "queued",
        "count": len(request.lead_ids),
        "max_concurrent": request.max_concurrent,
    }


@router.get("/", response_model=List[CallLogResponse])
def list_calls(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    call_result: str = None,
    lead_id: str = None,
):
    q = db.query(CallLog)
    if call_result:
        q = q.filter(CallLog.call_result == call_result)
    if lead_id:
        q = q.filter(CallLog.lead_id == lead_id)
    q = q.order_by(CallLog.created_at.desc())
    return q.offset(skip).limit(limit).all()


@router.get("/{call_id}", response_model=CallLogResponse)
def get_call(call_id: str, db: Session = Depends(get_db)):
    call = db.query(CallLog).filter(CallLog.call_id == call_id).first()
    if not call:
        raise HTTPException(404, detail="Call not found")
    return call


@router.get("/lead/{lead_id}", response_model=List[CallLogResponse])
def calls_for_lead(lead_id: str, db: Session = Depends(get_db)):
    return (
        db.query(CallLog)
        .filter(CallLog.lead_id == lead_id)
        .order_by(CallLog.created_at.desc())
        .all()
    )


async def _process_bulk_calls(lead_ids: List[str], max_concurrent: int):
    """Background task — calls each lead sequentially."""
    import asyncio
    from database import SessionLocal

    db = SessionLocal()
    client = get_voice_client()
    webhook_url = f"{settings.public_base_url}/webhooks/vapi"

    try:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def call_one(lead_id: str):
            async with semaphore:
                lead = db.query(Lead).filter(Lead.lead_id == lead_id).first()
                if not lead or lead.do_not_call or not lead.phone:
                    return
                try:
                    await client.create_call(
                        phone=lead.phone,
                        lead_id=lead.lead_id,
                        company_name=lead.company_name,
                        contact_name=lead.contact_name,
                        country=lead.country,
                        lead_type=lead.lead_type or "unknown",
                        member_type=lead.member_type or "",
                        product_interest=lead.product_interest,
                        webhook_url=webhook_url,
                        language=lead.language or None,
                    )
                    lead.call_attempts = (lead.call_attempts or 0) + 1
                    lead.last_call_date = datetime.utcnow()
                    lead.call_status = "in_progress"
                    db.commit()
                    await asyncio.sleep(2)  # polite gap between calls
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error("Call failed for %s: %s", lead_id, e)

        await asyncio.gather(*[call_one(lid) for lid in lead_ids])
    finally:
        db.close()
