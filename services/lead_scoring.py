"""
Lead scoring engine — produces a 0–100 score and priority tier.

Buyer signals and seller signals are scored separately and the
higher of the two is returned together with the detected lead_type.
"""

from dataclasses import dataclass
from typing import Optional
from models import Lead


@dataclass
class ScoreResult:
    score: float
    lead_type: str          # buyer | seller | both | unknown
    urgency: str            # hot | warm | cold
    membership_potential: str  # high | medium | low
    reasons: list[str]


def score_lead(lead: Lead) -> ScoreResult:
    buyer_score, buyer_reasons = _score_buyer(lead)
    seller_score, seller_reasons = _score_seller(lead)

    if buyer_score > 0 and seller_score > 0:
        score = (buyer_score + seller_score) / 2
        lead_type = "both"
        reasons = buyer_reasons + seller_reasons
    elif buyer_score >= seller_score:
        score = buyer_score
        lead_type = "buyer"
        reasons = buyer_reasons
    else:
        score = seller_score
        lead_type = "seller"
        reasons = seller_reasons

    if not reasons:
        lead_type = "unknown"

    # Override with explicit buyer_or_seller if provided
    if lead.buyer_or_seller in ("buyer", "seller", "both"):
        lead_type = lead.buyer_or_seller

    score = min(score, 100.0)
    urgency = _urgency(score)
    membership_potential = _membership_potential(lead, score)

    return ScoreResult(
        score=round(score, 1),
        lead_type=lead_type,
        urgency=urgency,
        membership_potential=membership_potential,
        reasons=reasons,
    )


def _score_buyer(lead: Lead) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []

    if lead.posted_request:
        score += 25
        reasons.append("Posted a buyer request (+25)")

    if lead.phone and lead.email:
        score += 10
        reasons.append("Has both phone and email (+10)")
    elif lead.phone or lead.email:
        score += 4

    product = (lead.product_interest or "").lower()
    if any(kw in product for kw in ["monthly", "regular", "weekly", "ongoing", "standing order"]):
        score += 20
        reasons.append("Indicates regular/monthly demand (+20)")

    if _has_clear_specs(product):
        score += 15
        reasons.append("Product/dimensions are clear (+15)")

    if lead.country and _is_import_market(lead.country):
        score += 10
        reasons.append(f"Import-relevant market: {lead.country} (+10)")

    notes = (lead.notes or "").lower()
    if any(kw in notes for kw in ["contact", "supplier", "access", "reach", "find"]):
        score += 15
        reasons.append("Expressed interest in supplier contact (+15)")

    if _is_decision_maker(lead.contact_name):
        score += 5
        reasons.append("Likely decision maker (+5)")

    return score, reasons


def _score_seller(lead: Lead) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []

    if lead.posted_offer:
        score += 25
        reasons.append("Posted a seller offer (+25)")

    notes = (lead.notes or "").lower()
    product = (lead.product_interest or "").lower()

    if any(kw in notes + product for kw in ["export", "fob", "cif", "cfr", "shipping", "container"]):
        score += 15
        reasons.append("Export-ready signals (+15)")

    if any(kw in notes for kw in ["stock", "available", "ready", "immediate", "ex stock"]):
        score += 15
        reasons.append("Has current stock (+15)")

    if any(kw in notes for kw in ["target", "market", "buyer", "customer", "europe", "middle east", "gulf", "asia"]):
        score += 15
        reasons.append("Has target markets (+15)")

    if any(kw in notes for kw in ["fsc", "pefc", "certified", "photo", "grade", "specification"]):
        score += 10
        reasons.append("Has certification / detailed specs (+10)")

    if lead.country and _is_export_country(lead.country):
        score += 10
        reasons.append(f"Strong export origin: {lead.country} (+10)")

    if lead.phone and lead.email:
        score += 5

    if _is_decision_maker(lead.contact_name):
        score += 10
        reasons.append("Likely decision maker (+10)")

    return score, reasons


def _urgency(score: float) -> str:
    if score >= 80:
        return "hot"
    if score >= 50:
        return "warm"
    return "cold"


def _membership_potential(lead: Lead, score: float) -> str:
    member = (lead.member_type or "").lower()

    if member in ("silver", "gold"):
        return "low"   # already paying

    if member == "expired" or score >= 70:
        return "high"

    if score >= 45:
        return "medium"

    return "low"


def _has_clear_specs(text: str) -> bool:
    dimension_kws = ["mm", "cm", "x", "thickness", "width", "length", "m3", "cbm", "mfbm"]
    species_kws = ["pine", "oak", "spruce", "fir", "beech", "eucalyptus", "teak", "poplar",
                   "birch", "cedar", "hardwood", "softwood", "tropical"]
    return any(k in text for k in dimension_kws) or any(k in text for k in species_kws)


def _is_import_market(country: str) -> bool:
    import_markets = {
        "saudi arabia", "uae", "qatar", "kuwait", "bahrain", "oman",
        "egypt", "pakistan", "india", "bangladesh", "china", "korea",
        "japan", "vietnam", "thailand", "nigeria", "ghana", "morocco",
        "algeria", "tunisia", "jordan", "iraq", "iran", "turkey",
    }
    return country.lower() in import_markets


def _is_export_country(country: str) -> bool:
    export_countries = {
        "romania", "ukraine", "russia", "belarus", "poland", "finland",
        "sweden", "germany", "austria", "france", "brazil", "chile",
        "new zealand", "australia", "canada", "usa", "latvia", "estonia",
        "lithuania", "czechia", "slovakia", "hungary", "bulgaria",
    }
    return country.lower() in export_countries


def _is_decision_maker(name: Optional[str]) -> bool:
    if not name:
        return False
    titles = ["ceo", "director", "owner", "manager", "md", "gm", "president",
              "head", "chief", "founder", "partner", "proprietor"]
    return any(t in name.lower() for t in titles)


def prioritise_call_queue(leads: list[Lead]) -> list[Lead]:
    """Sort leads by score descending; do-not-call leads go last."""
    return sorted(
        leads,
        key=lambda l: (not l.do_not_call, l.lead_score or 0),
        reverse=True,
    )
