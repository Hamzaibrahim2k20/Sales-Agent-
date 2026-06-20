"""
Vapi voice agent client.
Docs: https://docs.vapi.ai
"""

import httpx
import logging
from typing import Optional
from config import settings
from agent.system_prompt import MASTER_SYSTEM_PROMPT, get_script_for_lead

logger = logging.getLogger(__name__)

VAPI_BASE_URL = "https://api.vapi.ai"


class VapiClient:
    def __init__(self):
        self.api_key = settings.vapi_api_key
        self.phone_number_id = settings.vapi_phone_number_id
        self.assistant_id = settings.vapi_assistant_id
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_call(
        self,
        phone: str,
        lead_id: str,
        company_name: str,
        contact_name: Optional[str],
        country: str,
        lead_type: str,
        member_type: str,
        product_interest: Optional[str],
        webhook_url: str,
    ) -> dict:
        script = get_script_for_lead(lead_type, member_type)
        context = _build_context(company_name, contact_name, country, product_interest)
        system_prompt = MASTER_SYSTEM_PROMPT + "\n\n" + script + "\n\n" + context

        payload = {
            "phoneNumberId": self.phone_number_id,
            "customer": {
                "number": phone,
                "name": contact_name or company_name,
            },
            "assistant": {
                "transcriber": {
                    "provider": "deepgram",
                    "model": "nova-2",
                    "language": _language_code(country),
                },
                "model": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-6",
                    "messages": [
                        {"role": "system", "content": system_prompt}
                    ],
                    "temperature": 0.4,
                },
                "voice": {
                    "provider": "11labs",
                    "voiceId": "21m00Tcm4TlvDq8ikWAM",  # ElevenLabs Rachel
                },
                "firstMessage": _opening_message(contact_name, company_name),
                "endCallMessage": "Thank you for speaking with Fordaq. Have a great day.",
                "endCallPhrases": [
                    "goodbye", "bye", "hang up", "end call",
                    "thank you goodbye", "stop calling",
                ],
                "maxDurationSeconds": settings.call_timeout_seconds,
            },
            "metadata": {
                "lead_id": lead_id,
                "company_name": company_name,
                "country": country,
            },
            "serverUrl": webhook_url,
        }

        # If a pre-configured assistant exists, use it as the base
        if self.assistant_id:
            payload["assistantId"] = self.assistant_id
            # Override with call-specific context via assistantOverrides
            payload["assistantOverrides"] = {
                "model": {
                    "messages": [{"role": "system", "content": system_prompt}]
                },
                "firstMessage": _opening_message(contact_name, company_name),
                "metadata": payload["metadata"],
            }
            del payload["assistant"]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{VAPI_BASE_URL}/call",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_call(self, call_id: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{VAPI_BASE_URL}/call/{call_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def list_calls(self, limit: int = 50) -> list:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{VAPI_BASE_URL}/call",
                headers=self.headers,
                params={"limit": limit},
            )
            response.raise_for_status()
            return response.json()

    async def end_call(self, call_id: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.delete(
                f"{VAPI_BASE_URL}/call/{call_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()


class RetellClient:
    """
    Retell AI voice agent client.
    Docs: https://docs.retellai.com
    """

    def __init__(self):
        self.api_key = settings.retell_api_key
        self.agent_id = settings.retell_agent_id
        self.from_number = settings.retell_phone_number
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_call(
        self,
        phone: str,
        lead_id: str,
        company_name: str,
        contact_name: Optional[str],
        country: str,
        lead_type: str,
        member_type: str,
        product_interest: Optional[str],
        webhook_url: str,
    ) -> dict:
        script = get_script_for_lead(lead_type, member_type)
        context = _build_context(company_name, contact_name, country, product_interest)

        payload = {
            "from_number": self.from_number,
            "to_number": phone,
            "agent_id": self.agent_id,
            "retell_llm_dynamic_variables": {
                "lead_id": lead_id,
                "company_name": company_name,
                "contact_name": contact_name or "",
                "country": country,
                "product_interest": product_interest or "",
                "system_prompt_extension": script + "\n\n" + context,
            },
            "metadata": {
                "lead_id": lead_id,
            },
            "webhook_url": webhook_url,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.retellai.com/v2/create-phone-call",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_call(self, call_id: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"https://api.retellai.com/v2/get-call/{call_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()


def get_voice_client():
    """Return the configured voice client."""
    provider = settings.voice_provider.lower()
    if provider == "retell":
        return RetellClient()
    return VapiClient()


# ── Helpers ───────────────────────────────────────────────────────────

def _opening_message(contact_name: Optional[str], company_name: str) -> str:
    name_part = contact_name.split()[0] if contact_name else ""
    if name_part:
        return (
            f"Hello, is this {name_part} from {company_name}? "
            "This is calling from Fordaq, the timber and wood-products marketplace. "
            "I'm calling just to introduce myself and understand your activity briefly. "
            "Is now a good moment?"
        )
    return (
        f"Hello, I am trying to reach someone from {company_name}. "
        "This is calling from Fordaq, the timber and wood-products marketplace. "
        "Am I through to the right person?"
    )


def _build_context(
    company_name: str,
    contact_name: Optional[str],
    country: str,
    product_interest: Optional[str],
) -> str:
    lines = [
        "CURRENT LEAD CONTEXT:",
        f"Company: {company_name}",
        f"Contact: {contact_name or 'Unknown'}",
        f"Country: {country}",
    ]
    if product_interest:
        lines.append(f"Known product interest: {product_interest}")
    return "\n".join(lines)


def _language_code(country: str) -> str:
    lang_map = {
        "france": "fr", "belgium": "fr", "switzerland": "fr",
        "germany": "de", "austria": "de",
        "italy": "it",
        "spain": "es", "mexico": "es", "colombia": "es",
        "brazil": "pt", "portugal": "pt",
        "saudi arabia": "ar", "uae": "ar", "egypt": "ar",
        "kuwait": "ar", "qatar": "ar", "bahrain": "ar", "jordan": "ar",
        "morocco": "ar", "algeria": "ar", "tunisia": "ar",
        "turkey": "tr",
        "poland": "pl",
        "romania": "ro",
        "russia": "ru", "ukraine": "ru",
        "china": "zh",
    }
    return lang_map.get(country.lower(), "en")
