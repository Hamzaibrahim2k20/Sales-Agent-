from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, JSON, Enum
)
from sqlalchemy.sql import func
import enum
from database import Base


class LeadType(str, enum.Enum):
    buyer = "buyer"
    seller = "seller"
    both = "both"
    unknown = "unknown"


class Urgency(str, enum.Enum):
    hot = "hot"
    warm = "warm"
    cold = "cold"


class MembershipPotential(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class CallResult(str, enum.Enum):
    connected = "connected"
    no_answer = "no_answer"
    wrong_number = "wrong_number"
    not_interested = "not_interested"
    callback = "callback"
    voicemail = "voicemail"
    pending = "pending"


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(String, unique=True, index=True)

    # Contact info
    company_name = Column(String, index=True)
    contact_name = Column(String)
    country = Column(String, index=True)
    phone = Column(String)
    email = Column(String)
    language = Column(String, default="en")

    # Fordaq membership info
    member_type = Column(String)           # free, bronze, silver, gold, expired
    registration_date = Column(DateTime)
    last_activity = Column(DateTime)
    posted_offer = Column(Boolean, default=False)
    posted_request = Column(Boolean, default=False)

    # Commercial classification
    buyer_or_seller = Column(String)
    product_interest = Column(Text)
    species = Column(JSON, default=list)
    volume = Column(String)
    destination_market = Column(String)
    origin_preference = Column(String)

    # Assignment
    assigned_salesperson = Column(String)
    last_contact_date = Column(DateTime)
    do_not_call = Column(Boolean, default=False)

    # Scoring
    lead_score = Column(Float, default=0.0)
    lead_type = Column(String)
    urgency = Column(String)
    membership_potential = Column(String)

    # Call tracking
    call_status = Column(String, default="pending")
    call_attempts = Column(Integer, default=0)
    last_call_date = Column(DateTime)
    call_summary = Column(Text)
    next_action = Column(Text)
    follow_up_date = Column(DateTime)

    # Escalation
    human_escalation_required = Column(Boolean, default=False)
    escalation_reason = Column(Text)

    # Source
    source = Column(String, default="google_sheets")
    notes = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, unique=True, index=True)
    lead_id = Column(String, index=True)

    # Call metadata
    phone = Column(String)
    country = Column(String)
    voice_provider = Column(String)
    call_result = Column(String)
    duration_seconds = Column(Integer)
    call_started_at = Column(DateTime)
    call_ended_at = Column(DateTime)

    # Structured output from agent
    lead_type = Column(String)
    activity = Column(Text)
    products = Column(JSON, default=list)
    species = Column(JSON, default=list)
    volume = Column(String)
    destination_market = Column(String)
    origin_preference = Column(String)
    urgency = Column(String)
    membership_potential = Column(String)
    lead_score = Column(Float, default=0.0)
    summary = Column(Text)
    next_action = Column(Text)
    human_escalation_required = Column(Boolean, default=False)
    escalation_reason = Column(Text)
    follow_up_date = Column(DateTime)
    follow_up_message = Column(Text)

    # Raw data
    transcript = Column(Text)
    recording_url = Column(String)
    raw_payload = Column(JSON)

    created_at = Column(DateTime, server_default=func.now())


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_date = Column(DateTime, index=True)

    # Totals
    leads_imported = Column(Integer, default=0)
    leads_called = Column(Integer, default=0)
    calls_connected = Column(Integer, default=0)
    qualified_buyers = Column(Integer, default=0)
    qualified_sellers = Column(Integer, default=0)
    premium_prospects = Column(Integer, default=0)
    renewal_prospects = Column(Integer, default=0)
    human_escalations = Column(Integer, default=0)
    wrong_numbers = Column(Integer, default=0)
    no_answer = Column(Integer, default=0)
    not_interested = Column(Integer, default=0)

    # Market intelligence
    top_products = Column(JSON, default=list)
    top_countries = Column(JSON, default=list)
    best_leads = Column(JSON, default=list)
    market_comments = Column(Text)

    raw_data = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
