from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime


# ── Lead schemas ──────────────────────────────────────────────────────

class LeadBase(BaseModel):
    lead_id: Optional[str] = None
    company_name: str
    contact_name: Optional[str] = None
    country: str
    phone: str
    email: Optional[str] = None
    language: str = "en"
    member_type: Optional[str] = None
    registration_date: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    posted_offer: bool = False
    posted_request: bool = False
    buyer_or_seller: Optional[str] = None
    product_interest: Optional[str] = None
    assigned_salesperson: Optional[str] = None
    last_contact_date: Optional[datetime] = None
    do_not_call: bool = False
    notes: Optional[str] = None
    source: str = "manual"


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    call_status: Optional[str] = None
    call_summary: Optional[str] = None
    next_action: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    human_escalation_required: Optional[bool] = None
    escalation_reason: Optional[str] = None
    lead_score: Optional[float] = None
    lead_type: Optional[str] = None
    urgency: Optional[str] = None
    membership_potential: Optional[str] = None
    do_not_call: Optional[bool] = None
    assigned_salesperson: Optional[str] = None
    notes: Optional[str] = None


class LeadResponse(LeadBase):
    id: int
    lead_score: float
    lead_type: Optional[str] = None
    urgency: Optional[str] = None
    membership_potential: Optional[str] = None
    call_status: str
    call_attempts: int
    last_call_date: Optional[datetime] = None
    call_summary: Optional[str] = None
    next_action: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    human_escalation_required: bool
    escalation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Call log schemas ──────────────────────────────────────────────────

class CallLogCreate(BaseModel):
    call_id: str
    lead_id: str
    phone: str
    country: Optional[str] = None
    voice_provider: str
    call_result: str
    duration_seconds: Optional[int] = None
    call_started_at: Optional[datetime] = None
    call_ended_at: Optional[datetime] = None
    lead_type: Optional[str] = None
    activity: Optional[str] = None
    products: List[str] = []
    species: List[str] = []
    volume: Optional[str] = None
    destination_market: Optional[str] = None
    origin_preference: Optional[str] = None
    urgency: Optional[str] = None
    membership_potential: Optional[str] = None
    lead_score: float = 0.0
    summary: Optional[str] = None
    next_action: Optional[str] = None
    human_escalation_required: bool = False
    escalation_reason: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    follow_up_message: Optional[str] = None
    transcript: Optional[str] = None
    recording_url: Optional[str] = None
    raw_payload: Optional[Any] = None


class CallLogResponse(CallLogCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Structured call output ────────────────────────────────────────────

class StructuredCallOutput(BaseModel):
    company_name: str = ""
    contact_name: str = ""
    country: str = ""
    phone: str = ""
    lead_type: str = "unknown"
    activity: str = ""
    products: List[str] = []
    species: List[str] = []
    volume: str = ""
    destination_market: str = ""
    origin_preference: str = ""
    urgency: str = "cold"
    membership_potential: str = "low"
    lead_score: float = 0.0
    call_result: str = "connected"
    summary: str = ""
    next_action: str = ""
    human_escalation_required: bool = False
    escalation_reason: str = ""
    follow_up_date: Optional[str] = None


# ── Call request ──────────────────────────────────────────────────────

class InitiateCallRequest(BaseModel):
    lead_id: str
    override_phone: Optional[str] = None
    script_type: Optional[str] = None  # buyer | seller | renewal | reactivation


class BulkCallRequest(BaseModel):
    lead_ids: List[str]
    max_concurrent: int = Field(default=5, le=20)


# ── Report schemas ────────────────────────────────────────────────────

class DailyReportResponse(BaseModel):
    id: int
    report_date: datetime
    leads_imported: int
    leads_called: int
    calls_connected: int
    qualified_buyers: int
    qualified_sellers: int
    premium_prospects: int
    renewal_prospects: int
    human_escalations: int
    wrong_numbers: int
    no_answer: int
    not_interested: int
    top_products: List[Any]
    top_countries: List[Any]
    best_leads: List[Any]
    market_comments: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Webhook payloads ──────────────────────────────────────────────────

class VapiWebhookPayload(BaseModel):
    message: Optional[Any] = None
    call: Optional[Any] = None

    class Config:
        extra = "allow"


class RetellWebhookPayload(BaseModel):
    event: Optional[str] = None
    call_id: Optional[str] = None
    agent_id: Optional[str] = None
    call_status: Optional[str] = None
    transcript: Optional[str] = None
    call_analysis: Optional[Any] = None

    class Config:
        extra = "allow"
