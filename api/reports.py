from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
from database import get_db
from models import DailyReport
from schemas import DailyReportResponse
from services.report_generator import generate_daily_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate")
def trigger_report(
    background_tasks: BackgroundTasks,
    report_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Generate today's daily report (or a specific date)."""
    background_tasks.add_task(_run_report, report_date)
    return {"status": "report generation started", "date": str(report_date or date.today())}


@router.get("/", response_model=List[DailyReportResponse])
def list_reports(db: Session = Depends(get_db), limit: int = 30):
    return (
        db.query(DailyReport)
        .order_by(DailyReport.report_date.desc())
        .limit(limit)
        .all()
    )


@router.get("/latest", response_model=DailyReportResponse)
def latest_report(db: Session = Depends(get_db)):
    report = db.query(DailyReport).order_by(DailyReport.report_date.desc()).first()
    if not report:
        from fastapi import HTTPException
        raise HTTPException(404, detail="No reports generated yet")
    return report


@router.get("/today")
def today_report(db: Session = Depends(get_db)):
    """Generate and return today's report immediately."""
    return generate_daily_report(db)


def _run_report(report_date: Optional[date]):
    from database import SessionLocal
    from services.google_sheets import write_daily_report
    from config import settings

    db = SessionLocal()
    try:
        report = generate_daily_report(db, report_date)
        if settings.google_sheets_lead_sheet_id:
            try:
                write_daily_report(report)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Google Sheets report sync failed: %s", e)
    finally:
        db.close()
