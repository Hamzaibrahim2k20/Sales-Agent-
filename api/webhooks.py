"""
Webhook receivers for Vapi and Retell.

Both platforms POST call events here. This module:
1. Parses the payload
2. Extracts structured output via Claude
3. Updates the lead in DB
4. Writes call log
5. Syncs back to Google Sheets
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends
from database import get_db
from models import Lead, CallLog
from services.call_processor import CallProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

processor = CallProcessor()


@router.post("/vapi")
async def vapi_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    payload = await request.json()
    logger.info("Vapi webhook received: type=%s", payload.get("message", {}).get("type"))

    result = processor.parse_vapi_webhook(payload)
    if result is None:
        # Not a call-end event we need to process
        return {"status": "ignored"}

    background_tasks.add_task(_persist_call_result, result)
    return {"status": "received"}


@router.post("/retell")
async def retell_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    payload = await request.json()
    logger.info("Retell webhook received: event=%s", payload.get("event"))

    result = processor.parse_retell_webhook(payload)
    if result is None:
        return {"status": "ignored"}

    background_tasks.add_task(_persist_call_result, result)
    return {"status": "received"}


@router.post("/test")
async def test_webhook(payload: dict):
    """
    Test endpoint — simulate a call result without a real call.
    Send a JSON body matching StructuredCallOutput.
    """
    from services.follow_up import generate_follow_up
    payload["follow_up_message"] = generate_follow_up(payload)
    return {"status": "ok", "parsed": payload}


def _persist_call_result(result: dict):
    """Save call result to DB and sync to Google Sheets (if configured)."""
    from database import SessionLocal
    from config import settings

    db = SessionLocal()
    try:
        lead_id = result.get("lead_id", "")
        call_id = result.get("call_id", f"manual-{datetime.utcnow().timestamp()}")

        # Skip duplicate call IDs
        existing = db.query(CallLog).filter(CallLog.call_id == call_id).first()
        if existing:
            return

        # Build call log
        log = CallLog(
            call_id=call_id,
            lead_id=lead_id,
            phone=result.get("phone", ""),
            country=result.get("country", ""),
            voice_provider=result.get("voice_provider", "vapi"),
            call_result=result.get("call_result", "connected"),
            duration_seconds=result.get("duration_seconds"),
            call_started_at=result.get("call_started_at"),
            call_ended_at=datetime.utcnow(),
            lead_type=result.get("lead_type"),
            activity=result.get("activity"),
            products=result.get("products", []),
            species=result.get("species", []),
            volume=result.get("volume"),
            destination_market=result.get("destination_market"),
            origin_preference=result.get("origin_preference"),
            urgency=result.get("urgency"),
            membership_potential=result.get("membership_potential"),
            lead_score=result.get("lead_score", 0),
            summary=result.get("summary"),
            next_action=result.get("next_action"),
            human_escalation_required=result.get("human_escalation_required", False),
            escalation_reason=result.get("escalation_reason"),
            follow_up_message=result.get("follow_up_message"),
            transcript=result.get("transcript"),
            recording_url=result.get("recording_url"),
            raw_payload=result.get("raw_payload"),
        )
        db.add(log)

        # Update lead record
        if lead_id:
            lead = db.query(Lead).filter(Lead.lead_id == lead_id).first()
            if lead:
                lead.call_status = result.get("call_result", "connected")
                lead.call_summary = result.get("summary")
                lead.next_action = result.get("next_action")
                lead.human_escalation_required = result.get("human_escalation_required", False)
                lead.escalation_reason = result.get("escalation_reason")
                lead.lead_score = result.get("lead_score", lead.lead_score)
                lead.lead_type = result.get("lead_type") or lead.lead_type
                lead.urgency = result.get("urgency") or lead.urgency
                lead.membership_potential = result.get("membership_potential") or lead.membership_potential
                lead.last_call_date = datetime.utcnow()

                if result.get("follow_up_date"):
                    try:
                        lead.follow_up_date = datetime.strptime(
                            result["follow_up_date"], "%Y-%m-%d"
                        )
                    except ValueError:
                        pass

        db.commit()

        # Sync to Google Sheets if configured (optional — skip if library broken or not set up)
        if settings.google_sheets_lead_sheet_id:
            try:
                from services.google_sheets import append_call_log, update_lead_status
                append_call_log({
                    **result,
                    "call_date": datetime.utcnow().isoformat(),
                    "products": ", ".join(result.get("products", [])),
                    "species": ", ".join(result.get("species", [])),
                })
                if lead_id:
                    update_lead_status(lead_id, {
                        "call_status": result.get("call_result"),
                        "call_summary": result.get("summary"),
                        "next_action": result.get("next_action"),
                        "human_escalation": str(result.get("human_escalation_required", False)),
                        "lead_score": result.get("lead_score", 0),
                    })
            except Exception as e:
                logger.warning("Google Sheets sync skipped: %s", e)

    except Exception as e:
        logger.error("Failed to persist call result: %s", e)
        db.rollback()
    finally:
        db.close()
