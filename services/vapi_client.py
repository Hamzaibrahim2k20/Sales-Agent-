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
        language: Optional[str] = None,
    ) -> dict:
        # Resolve language: explicit field beats country inference
        lang = language or _language_code(country)

        script = get_script_for_lead(lead_type, member_type)
        context = _build_context(company_name, contact_name, country, product_interest, lang)
        system_prompt = MASTER_SYSTEM_PROMPT + "\n\n" + script + "\n\n" + context

        transcriber = _transcriber_config(lang)
        voice = _voice_config(lang)
        first_msg = _opening_message(contact_name, company_name, lang)
        end_phrases = _end_call_phrases(lang)

        payload = {
            "phoneNumberId": self.phone_number_id,
            "customer": {
                "number": phone,
                "name": contact_name or company_name,
            },
            "assistant": {
                "transcriber": transcriber,
                "model": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-6",
                    "messages": [
                        {"role": "system", "content": system_prompt}
                    ],
                    "temperature": 0.4,
                },
                "voice": voice,
                "firstMessage": first_msg,
                "endCallMessage": _end_call_message(lang),
                "endCallPhrases": end_phrases,
                "maxDurationSeconds": settings.call_timeout_seconds,
            },
            "metadata": {
                "lead_id": lead_id,
                "company_name": company_name,
                "country": country,
                "language": lang,
            },
            "serverUrl": webhook_url,
        }

        # If a pre-configured assistant exists, use it as the base
        if self.assistant_id:
            payload["assistantId"] = self.assistant_id
            # Override with call-specific context via assistantOverrides
            payload["assistantOverrides"] = {
                "transcriber": transcriber,
                "model": {
                    "messages": [{"role": "system", "content": system_prompt}]
                },
                "voice": voice,
                "firstMessage": first_msg,
                "endCallPhrases": end_phrases,
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
        language: Optional[str] = None,
    ) -> dict:
        lang = language or _language_code(country)
        script = get_script_for_lead(lead_type, member_type)
        context = _build_context(company_name, contact_name, country, product_interest, lang)
        opening = _opening_message(contact_name, company_name, lang)

        payload = {
            "from_number": self.from_number,
            "to_number": phone,
            "agent_id": self.agent_id,
            "retell_llm_dynamic_variables": {
                "lead_id": lead_id,
                "company_name": company_name,
                "contact_name": contact_name or "",
                "country": country,
                "language": lang,
                "product_interest": product_interest or "",
                "opening_message": opening,
                "system_prompt_extension": script + "\n\n" + context,
            },
            "metadata": {
                "lead_id": lead_id,
                "language": lang,
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


# ── Language helpers ──────────────────────────────────────────────────

# Explicit language code → config bundles
# Each bundle: (deepgram_lang, voice_provider, voice_id_or_name, azure_locale)
_LANG_CONFIG: dict[str, dict] = {
    "en": {
        "deepgram": "en",
        "deepgram_model": "nova-2",
        "voice_provider": "11labs",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",          # ElevenLabs Rachel (English)
    },
    "ar": {
        # Deepgram nova-2 supports Arabic
        "deepgram": "ar",
        "deepgram_model": "nova-2",
        # ElevenLabs has Arabic voices; fallback to Azure TTS which has top-quality Arabic
        "voice_provider": "azure",
        "voice_id": "ar-SA-ZariyahNeural",             # Azure Arabic (Saudi) female
    },
    "ur": {
        # Deepgram does not have a dedicated Urdu model — use Hindi (hi) which
        # shares the Nastaliq/Devanagari phoneme space and works well for Urdu.
        # Alternatively use "multi" for automatic language detection.
        "deepgram": "hi",
        "deepgram_model": "nova-2",
        # Azure TTS has certified Urdu (Pakistan) voices
        "voice_provider": "azure",
        "voice_id": "ur-PK-UzmaNeural",                # Azure Urdu (Pakistan) female
    },
    "fr": {
        "deepgram": "fr",
        "deepgram_model": "nova-2",
        "voice_provider": "11labs",
        "voice_id": "XB0fDUnXU5powFXDhCwa",            # ElevenLabs Charlotte (French)
    },
    "de": {
        "deepgram": "de",
        "deepgram_model": "nova-2",
        "voice_provider": "azure",
        "voice_id": "de-DE-KatjaNeural",
    },
    "it": {
        "deepgram": "it",
        "deepgram_model": "nova-2",
        "voice_provider": "azure",
        "voice_id": "it-IT-ElsaNeural",
    },
    "es": {
        "deepgram": "es",
        "deepgram_model": "nova-2",
        "voice_provider": "azure",
        "voice_id": "es-ES-ElviraNeural",
    },
    "pt": {
        "deepgram": "pt",
        "deepgram_model": "nova-2",
        "voice_provider": "azure",
        "voice_id": "pt-PT-RaquelNeural",
    },
    "tr": {
        "deepgram": "tr",
        "deepgram_model": "nova-2",
        "voice_provider": "azure",
        "voice_id": "tr-TR-EmelNeural",
    },
    "pl": {
        "deepgram": "pl",
        "deepgram_model": "nova-2",
        "voice_provider": "azure",
        "voice_id": "pl-PL-AgnieszkaNeural",
    },
    "ro": {
        "deepgram": "ro",
        "deepgram_model": "nova-2",
        "voice_provider": "azure",
        "voice_id": "ro-RO-AlinaNeural",
    },
    "ru": {
        "deepgram": "ru",
        "deepgram_model": "nova-2",
        "voice_provider": "azure",
        "voice_id": "ru-RU-SvetlanaNeural",
    },
    "zh": {
        "deepgram": "zh",
        "deepgram_model": "nova-2",
        "voice_provider": "azure",
        "voice_id": "zh-CN-XiaoxiaoNeural",
    },
    "hi": {
        "deepgram": "hi",
        "deepgram_model": "nova-2",
        "voice_provider": "azure",
        "voice_id": "hi-IN-SwaraNeural",
    },
}

# Country → language code
_COUNTRY_TO_LANG: dict[str, str] = {
    # Arabic-speaking
    "saudi arabia": "ar", "uae": "ar", "egypt": "ar", "kuwait": "ar",
    "qatar": "ar", "bahrain": "ar", "jordan": "ar", "oman": "ar",
    "iraq": "ar", "morocco": "ar", "algeria": "ar", "tunisia": "ar",
    "libya": "ar", "sudan": "ar", "lebanon": "ar", "syria": "ar",
    # Urdu-speaking
    "pakistan": "ur",
    # Hindi-speaking
    "india": "hi",
    # European
    "france": "fr", "belgium": "fr",
    "germany": "de", "austria": "de",
    "switzerland": "de",           # multilingual but DE is most common in timber trade
    "italy": "it",
    "spain": "es", "mexico": "es", "colombia": "es", "chile": "es",
    "brazil": "pt", "portugal": "pt",
    "turkey": "tr",
    "poland": "pl",
    "romania": "ro",
    "russia": "ru", "ukraine": "ru", "belarus": "ru",
    "china": "zh",
}

# Opening messages in key languages
_OPENING: dict[str, tuple[str, str]] = {
    # lang: (named_version, unnamed_version)
    "en": (
        "Hello, is this {name} from {company}? This is calling from Fordaq, the timber and wood-products marketplace. I am calling just to understand your activity briefly. Is now a good moment?",
        "Hello, I am trying to reach someone from {company}. This is Fordaq, the timber marketplace. Am I through to the right person?",
    ),
    "ar": (
        "مرحباً، هل أتحدث مع {name} من شركة {company}؟ أنا أتصل من شركة Fordaq، منصة تجارة الأخشاب والمنتجات الخشبية. أتصل فقط لأفهم نشاطكم التجاري بشكل مختصر. هل الوقت مناسب الآن؟",
        "مرحباً، أحاول التواصل مع شخص من شركة {company}. أنا من شركة Fordaq لتجارة الأخشاب. هل وصلت إلى الشخص المناسب؟",
    ),
    "ur": (
        "السلام علیکم، کیا میں {name} صاحب سے {company} کمپنی سے بات کر رہا ہوں؟ میں Fordaq کی طرف سے کال کر رہا ہوں، جو لکڑی اور لکڑی کی مصنوعات کی بین الاقوامی منڈی ہے۔ کیا ابھی بات کرنا ممکن ہے؟",
        "السلام علیکم، میں {company} کمپنی سے کسی سے بات کرنا چاہتا ہوں۔ میں Fordaq سے ہوں۔ کیا آپ صحیح شخص ہیں؟",
    ),
    "fr": (
        "Bonjour, est-ce que je parle à {name} de {company}? J'appelle de la part de Fordaq, la plateforme B2B pour le bois et les produits forestiers. J'appelle juste pour mieux comprendre votre activité. Est-ce que c'est un bon moment?",
        "Bonjour, je cherche à joindre quelqu'un de {company}. C'est Fordaq, la plateforme bois. Suis-je avec la bonne personne?",
    ),
    "de": (
        "Guten Tag, spreche ich mit {name} von {company}? Hier ist Fordaq, der B2B-Marktplatz für Holz und Holzprodukte. Ich rufe kurz an, um Ihre Geschäftstätigkeit besser zu verstehen. Haben Sie einen Moment?",
        "Guten Tag, ich versuche jemanden von {company} zu erreichen. Hier ist Fordaq, der Holzmarktplatz. Bin ich richtig verbunden?",
    ),
    "tr": (
        "Merhaba, {company} şirketinden {name} ile mi görüşüyorum? Ben Fordaq'tan arıyorum, kereste ve ahşap ürünleri B2B pazaryeri. Kısaca işletmenizi anlamak için arıyorum. Uygun bir zaman mı?",
        "Merhaba, {company} şirketinden biriyle görüşmek istiyorum. Ben Fordaq'tan arıyorum. Doğru kişiyle mi konuşuyorum?",
    ),
    "ro": (
        "Bună ziua, vorbesc cu {name} de la {company}? Sunt de la Fordaq, platforma B2B pentru cherestea și produse din lemn. Vă sun să înțeleg activitatea dumneavoastră. Este un moment potrivit?",
        "Bună ziua, încerc să iau legătura cu cineva de la {company}. Sunt de la Fordaq. Am ajuns la persoana potrivită?",
    ),
    "hi": (
        "नमस्ते, क्या मैं {company} से {name} जी से बात कर रहा हूँ? मैं Fordaq की तरफ़ से call कर रहा हूँ — यह लकड़ी और wood products का B2B marketplace है। मैं बस आपके business के बारे में थोड़ा समझना चाहता था। क्या अभी बात करना ठीक रहेगा?",
        "नमस्ते, मैं {company} से किसी से बात करना चाहता हूँ। मैं Fordaq से हूँ। क्या आप सही व्यक्ति हैं?",
    ),
    "ru": (
        "Добрый день, это {name} из компании {company}? Звоню из Fordaq, B2B-маркетплейса для древесины и продуктов деревообработки. Звоню, чтобы коротко узнать о вашей деятельности. Удобно сейчас говорить?",
        "Добрый день, хочу связаться с кем-то из {company}. Это Fordaq. Я попал к нужному человеку?",
    ),
    "pl": (
        "Dzień dobry, czy rozmawiam z {name} z {company}? Dzwonię z Fordaq, platformy B2B dla drewna i produktów drzewnych. Chciałem krótko zapytać o Państwa działalność. Czy to dobry moment?",
        "Dzień dobry, staram się skontaktować z kimś z {company}. Tu Fordaq. Czy rozmawiam z właściwą osobą?",
    ),
}

# End-call thank-you by language
_END_CALL_MSG: dict[str, str] = {
    "en": "Thank you for speaking with Fordaq. Have a great day. Goodbye.",
    "ar": "شكراً جزيلاً على وقتكم. نتمنى لكم يوماً سعيداً. مع السلامة.",
    "ur": "آپ کا بہت شکریہ۔ اللہ حافظ۔",
    "fr": "Merci pour votre temps. Bonne journée. Au revoir.",
    "de": "Vielen Dank für Ihre Zeit. Einen schönen Tag noch. Auf Wiederhören.",
    "tr": "Zaman ayırdığınız için teşekkürler. İyi günler. Güle güle.",
    "ro": "Vă mulțumesc pentru timpul acordat. O zi bună. La revedere.",
    "ru": "Спасибо за уделённое время. Хорошего дня. До свидания.",
    "pl": "Dziękuję za poświęcony czas. Miłego dnia. Do widzenia.",
    "it": "Grazie per il suo tempo. Buona giornata. Arrivederci.",
    "es": "Gracias por su tiempo. Que tenga un buen día. Adiós.",
    "pt": "Obrigado pelo seu tempo. Tenha um bom dia. Adeus.",
    "hi": "आपके समय के लिए धन्यवाद। अच्छा दिन बिताएं। नमस्ते।",
    "zh": "感谢您的时间。祝您一天愉快。再见。",
}

# Language-appropriate opt-out / end-call detection phrases
_END_PHRASES: dict[str, list[str]] = {
    "en": ["goodbye", "bye", "end call", "stop calling", "do not call again", "not interested"],
    "ar": ["مع السلامة", "وداعاً", "لا أريد", "لا شكراً", "لا تتصل مرة أخرى"],
    "ur": ["اللہ حافظ", "خدا حافظ", "ٹھیک ہے شکریہ", "دوبارہ فون نہ کریں"],
    "fr": ["au revoir", "bonne journée", "pas intéressé", "ne rappellez pas"],
    "de": ["auf wiederhören", "tschüss", "kein interesse", "nicht mehr anrufen"],
    "tr": ["güle güle", "hoşça kal", "ilgilenmiyorum", "aramayın"],
    "ro": ["la revedere", "pa", "nu mă interesează"],
    "ru": ["до свидания", "пока", "не интересует", "не звоните"],
    "pl": ["do widzenia", "pa", "nie jestem zainteresowany"],
}


def _language_code(country: str) -> str:
    return _COUNTRY_TO_LANG.get(country.lower(), "en")


def _transcriber_config(lang: str) -> dict:
    cfg = _LANG_CONFIG.get(lang, _LANG_CONFIG["en"])
    config = {
        "provider": "deepgram",
        "model": cfg.get("deepgram_model", "nova-2"),
        "language": cfg.get("deepgram", "en"),
    }
    # For languages where mid-call switching is common (e.g. Pakistan — Urdu+English mix),
    # enable Deepgram's multi-language mode so both are transcribed correctly.
    if lang in ("ur", "hi"):
        config["model"] = "nova-2"
        config["language"] = "multi"  # Deepgram auto-detects language per utterance
    return config


def _voice_config(lang: str) -> dict:
    cfg = _LANG_CONFIG.get(lang, _LANG_CONFIG["en"])
    provider = cfg.get("voice_provider", "11labs")
    voice_id = cfg.get("voice_id", "21m00Tcm4TlvDq8ikWAM")

    if provider == "azure":
        return {
            "provider": "azure",
            "voiceId": voice_id,
        }
    # ElevenLabs
    return {
        "provider": "11labs",
        "voiceId": voice_id,
        "stability": 0.5,
        "similarityBoost": 0.75,
    }


def _opening_message(contact_name: Optional[str], company_name: str, lang: str = "en") -> str:
    templates = _OPENING.get(lang, _OPENING["en"])
    name_part = contact_name.split()[0] if contact_name else ""
    if name_part:
        return templates[0].format(name=name_part, company=company_name)
    return templates[1].format(company=company_name)


def _end_call_message(lang: str) -> str:
    return _END_CALL_MSG.get(lang, _END_CALL_MSG["en"])


def _end_call_phrases(lang: str) -> list[str]:
    # Always include English phrases as a fallback (many non-native speakers say English words)
    phrases = _END_PHRASES.get(lang, [])
    if lang != "en":
        phrases = phrases + _END_PHRASES["en"]
    return list(dict.fromkeys(phrases))  # deduplicate while preserving order


def _build_context(
    company_name: str,
    contact_name: Optional[str],
    country: str,
    product_interest: Optional[str],
    lang: str = "en",
) -> str:
    lines = [
        "CURRENT LEAD CONTEXT:",
        f"Company: {company_name}",
        f"Contact: {contact_name or 'Unknown'}",
        f"Country: {country}",
        f"Preferred language: {lang}",
    ]
    if product_interest:
        lines.append(f"Known product interest: {product_interest}")
    if lang != "en":
        lines.append(
            f"IMPORTANT: Start and conduct this call in '{lang}'. "
            "If the person switches to English at any point, match their language immediately. "
            "If they mix languages (e.g. Urdu + English), follow their lead naturally."
        )
    return "\n".join(lines)
