"""
Processes raw webhook payloads from Vapi / Retell into structured call outputs.
Uses Claude to parse call transcripts into the structured JSON format.
"""

import json
import logging
from typing import Optional
import anthropic
from config import settings
from schemas import StructuredCallOutput
from agent.system_prompt import MASTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """
You are a call analysis assistant. You received a transcript of a Fordaq sales call.

Extract the information from the transcript and return ONLY a valid JSON object
in this exact schema — no markdown, no explanation, just the raw JSON:

{
  "company_name": "string",
  "contact_name": "string",
  "country": "string",
  "phone": "string",
  "lead_type": "buyer|seller|both|unknown",
  "activity": "string — what the company does",
  "products": ["list", "of", "products"],
  "species": ["list", "of", "wood", "species"],
  "volume": "string — volume/quantity mentioned",
  "destination_market": "string",
  "origin_preference": "string",
  "urgency": "hot|warm|cold",
  "membership_potential": "high|medium|low",
  "lead_score": 0,
  "call_result": "connected|no_answer|wrong_number|not_interested|callback|voicemail",
  "summary": "2-3 sentence summary of the call",
  "next_action": "specific recommended next action",
  "human_escalation_required": false,
  "escalation_reason": "string — empty if no escalation",
  "follow_up_date": "YYYY-MM-DD or empty string"
}

Lead scoring (add points to reach 0-100):
- Buyer posted clear request: +25
- Has phone + email: +10
- Regular/monthly demand: +20
- Clear product specs: +15
- Import/export market: +10
- Requested supplier contact access: +15
- Decision maker confirmed: +5
- Seller has export-ready products: +25
- Seller has current stock: +15
- Seller has target markets: +15
- Seller has certifications/photos: +10

Urgency: hot=80+, warm=50-79, cold=<50

Escalation triggers: pricing, discount, invoice, renewal, complaint, fraud,
advertising, "speak to a person", refund, cancellation, already paid member.

Transcript to analyse:
"""


class CallProcessor:
    def __init__(self):
        self._client: Optional[anthropic.Anthropic] = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._client

    def parse_vapi_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a Vapi webhook payload.
        Returns dict with call metadata + structured output, or None if not a call-end event.
        """
        message = payload.get("message", {})
        msg_type = message.get("type", "")

        if msg_type != "end-of-call-report":
            return None

        call = message.get("call", {})
        transcript = message.get("transcript", "")
        recording_url = message.get("recordingUrl", "")
        summary = message.get("summary", "")
        ended_reason = message.get("endedReason", "")

        metadata = call.get("metadata", {})
        lead_id = metadata.get("lead_id", "")

        call_result = _vapi_ended_reason_to_result(ended_reason)
        structured = self._extract_structured_output(transcript, call_result, summary)

        return {
            "call_id": call.get("id", ""),
            "lead_id": lead_id,
            "phone": call.get("customer", {}).get("number", ""),
            "country": metadata.get("country", ""),
            "voice_provider": "vapi",
            "call_result": call_result,
            "duration_seconds": int(message.get("durationSeconds", 0)),
            "transcript": transcript,
            "recording_url": recording_url,
            "raw_payload": payload,
            **structured,
        }

    def parse_retell_webhook(self, payload: dict) -> Optional[dict]:
        """
        Parse a Retell webhook payload.
        Returns dict with call metadata + structured output, or None if not a call-end event.
        """
        event = payload.get("event", "")
        if event != "call_ended":
            return None

        call_id = payload.get("call_id", "")
        transcript = payload.get("transcript", "")
        analysis = payload.get("call_analysis", {}) or {}
        call_status = payload.get("call_status", "")
        metadata = payload.get("metadata", {})
        lead_id = metadata.get("lead_id", "")

        call_result = _retell_status_to_result(call_status)
        structured = self._extract_structured_output(transcript, call_result, "")

        return {
            "call_id": call_id,
            "lead_id": lead_id,
            "phone": payload.get("to_number", ""),
            "country": "",
            "voice_provider": "retell",
            "call_result": call_result,
            "duration_seconds": int(payload.get("duration_ms", 0) / 1000),
            "transcript": transcript,
            "recording_url": payload.get("recording_url", ""),
            "raw_payload": payload,
            **structured,
        }

    def _extract_structured_output(
        self,
        transcript: str,
        call_result: str,
        summary: str,
    ) -> dict:
        """Use Claude to parse transcript → structured call output."""

        if not transcript or call_result in ("no_answer", "wrong_number", "voicemail"):
            return {
                "lead_type": "unknown",
                "activity": "",
                "products": [],
                "species": [],
                "volume": "",
                "destination_market": "",
                "origin_preference": "",
                "urgency": "cold",
                "membership_potential": "low",
                "lead_score": 0,
                "summary": summary or f"Call result: {call_result}",
                "next_action": "Retry call in 24 hours" if call_result == "no_answer" else "",
                "human_escalation_required": False,
                "escalation_reason": "",
                "follow_up_date": "",
                "follow_up_message": "",
            }

        if not settings.anthropic_api_key:
            return _fallback_extraction(transcript, call_result)

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": EXTRACTION_PROMPT + transcript,
                    }
                ],
            )
            raw = message.content[0].text.strip()
            data = json.loads(raw)

            from services.follow_up import generate_follow_up, generate_escalation_note
            data["follow_up_message"] = generate_follow_up(data)
            if data.get("human_escalation_required"):
                data["escalation_note"] = generate_escalation_note(data)

            return data

        except (json.JSONDecodeError, Exception) as e:
            logger.error("Claude extraction failed: %s", e)
            return _fallback_extraction(transcript, call_result)


def _vapi_ended_reason_to_result(reason: str) -> str:
    mapping = {
        "customer-ended-call": "connected",
        "assistant-ended-call": "connected",
        "no-answer": "no_answer",
        "busy": "no_answer",
        "failed": "no_answer",
        "customer-did-not-answer": "no_answer",
        "voicemail": "voicemail",
        "silence-timed-out": "no_answer",
        "machine-detected": "voicemail",
    }
    return mapping.get(reason, "connected")


def _retell_status_to_result(status: str) -> str:
    mapping = {
        "ended": "connected",
        "error": "no_answer",
        "voicemail_reached": "voicemail",
        "no_answer": "no_answer",
    }
    return mapping.get(status, "connected")


def _fallback_extraction(transcript: str, call_result: str) -> dict:
    """Keyword-based fallback when Claude API is not configured or unreachable."""
    lower = transcript.lower()

    lead_type = "unknown"
    if any(k in lower for k in ["buy", "import", "sourcing", "looking for", "need", "require", "purchase"]):
        lead_type = "buyer"
    if any(k in lower for k in ["sell", "export", "offer", "produce", "manufacture", "sawmill", "supplier"]):
        lead_type = "seller" if lead_type != "buyer" else "both"

    species = []
    for s in ["pine", "oak", "spruce", "fir", "beech", "eucalyptus", "teak",
              "poplar", "birch", "cedar", "larch", "hardwood", "softwood", "tropical"]:
        if s in lower:
            species.append(s)

    products = []
    for p in ["sawn timber", "logs", "plywood", "panels", "pallets", "veneer", "flooring",
              "mdf", "osb", "hdf", "lumber", "boards", "beams", "pellets", "chips"]:
        if p in lower:
            products.append(p)

    # Volume hints
    volume = ""
    for hint in ["container", "m3", "cbm", "m³", "lorry", "truck"]:
        if hint in lower:
            volume = f"See transcript — '{hint}' mentioned"
            break

    # Destination hints
    destination = ""
    for market in ["jeddah", "riyadh", "dubai", "karachi", "mumbai", "lagos", "casablanca"]:
        if market in lower:
            destination = market.title()
            break

    escalation_kws = [
        "price", "cost", "how much", "pricing", "discount", "invoice",
        "renew", "renewal", "complaint", "refund", "cancel", "cheated",
        "adverti", "banner", "speak to someone", "your manager",
    ]
    escalation_required = any(k in lower for k in escalation_kws)
    escalation_reason = ""
    if escalation_required:
        matched = [k for k in escalation_kws if k in lower]
        escalation_reason = f"Keyword match in transcript: {', '.join(matched[:3])}"

    score = 10
    if lead_type != "unknown":
        score += 20
    if species:
        score += 10
    if products:
        score += 10
    if volume:
        score += 10

    data = {
        "lead_type": lead_type,
        "activity": "",
        "products": products,
        "species": species,
        "volume": volume,
        "destination_market": destination,
        "origin_preference": "",
        "urgency": "warm" if score >= 40 else "cold",
        "membership_potential": "medium" if lead_type != "unknown" else "low",
        "lead_score": min(score, 60),
        "summary": "Call connected. Transcript keywords extracted — add Anthropic API key for full AI analysis.",
        "next_action": "Manual review recommended" + (" — ESCALATE: pricing/renewal mentioned" if escalation_required else ""),
        "human_escalation_required": escalation_required,
        "escalation_reason": escalation_reason,
        "follow_up_date": "",
        "follow_up_message": "",
    }

    # Generate follow-up email even in fallback mode
    try:
        from services.follow_up import generate_follow_up
        data["follow_up_message"] = generate_follow_up(data)
    except Exception:
        pass

    return data
