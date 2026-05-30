"""
Lead Qualification Agent — scores and tiers inbound pest control leads.

Scoring dimensions:
  • Pest type urgency     (0–30)  — termites/bedbugs highest
  • Property type         (0–20)  — commercial > multi-family > residential
  • Location match        (0–15)  — in service area vs adjacent vs outside
  • Urgency signals       (0–20)  — keywords + explicit urgency flag
  • Repeat customer       (0–10)
  • Contact completeness  (0–5)   — has phone + address

Tier thresholds:
  hot       ≥ 70  → same-day callback, high ACV opportunity
  qualified 50–69 → schedule visit within 48 h
  nurture   < 50  → email sequence, collect more signals
"""
from __future__ import annotations

from config import settings

PEST_SCORES: dict[str, int] = {
    "termites": 30,
    "bedbugs": 28,
    "bed bugs": 28,
    "rodents": 22,
    "rats": 22,
    "mice": 22,
    "roaches": 20,
    "cockroaches": 20,
    "wasps": 18,
    "hornets": 18,
    "fleas": 14,
    "ants": 10,
    "spiders": 8,
    "mosquitoes": 8,
    "general": 10,
}

PROPERTY_SCORES: dict[str, int] = {
    "commercial": 20,
    "multi-family": 15,
    "multifamily": 15,
    "residential": 10,
}

URGENCY_KEYWORD_BONUS = 15
URGENCY_FLAG_SCORES: dict[str, int] = {
    "emergency": 20,
    "high": 15,
    "medium": 8,
    "low": 2,
}

ANNUAL_VALUE_MAP: dict[str, int] = {
    "termites": 1200,
    "bedbugs": 800,
    "bed bugs": 800,
    "rodents": 600,
    "rats": 600,
    "mice": 600,
    "roaches": 500,
    "cockroaches": 500,
    "wasps": 350,
    "hornets": 350,
    "ants": 250,
    "general": 300,
}

URGENCY_KEYWORDS = [
    "urgent", "emergency", "asap", "immediately", "today", "tonight",
    "right now", "spreading", "getting worse", "can't sleep", "health risk",
    "my child", "baby", "pest everywhere",
]


def _pest_score(pest_type: str) -> tuple[int, str]:
    pt = pest_type.lower()
    for key, score in PEST_SCORES.items():
        if key in pt:
            return score, f"Pest type '{key}' carries urgency score {score}"
    return PEST_SCORES["general"], f"General pest type scores {PEST_SCORES['general']}"


def _property_score(property_type: str) -> tuple[int, str]:
    pt = property_type.lower()
    score = PROPERTY_SCORES.get(pt, PROPERTY_SCORES["residential"])
    return score, f"{property_type.capitalize()} property scores {score} (commercial = highest revenue)"


def _location_score(city: str) -> tuple[int, str]:
    normalized = [s.lower() for s in settings.service_areas]
    if city.lower() in normalized:
        return 15, f"{city} is within our primary service area"
    return 0, f"{city} is outside current service areas — route to expansion queue"


def _urgency_score(urgency_flag: str, description: str) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = URGENCY_FLAG_SCORES.get(urgency_flag.lower(), 8)
    reasons.append(f"Urgency flag '{urgency_flag}' contributes {score} points")

    if description:
        desc_lower = description.lower()
        matched = [kw for kw in URGENCY_KEYWORDS if kw in desc_lower]
        if matched:
            score = min(score + URGENCY_KEYWORD_BONUS, 20)
            reasons.append(f"Urgency keywords detected: {', '.join(matched[:3])}")

    return score, reasons


def qualify_lead(lead: dict) -> dict:
    """
    Score a lead and return qualification metadata.

    Args:
        lead: dict with keys: pest_type, property_type, city, urgency,
              pest_description, is_repeat_customer, phone, address

    Returns:
        dict: score, tier, next_step, recommended_channel, reasons, estimated_value
    """
    score = 0
    reasons: list[str] = []

    pest_s, pest_r = _pest_score(lead.get("pest_type", "general"))
    score += pest_s
    reasons.append(pest_r)

    prop_s, prop_r = _property_score(lead.get("property_type", "residential"))
    score += prop_s
    reasons.append(prop_r)

    loc_s, loc_r = _location_score(lead.get("city", ""))
    score += loc_s
    reasons.append(loc_r)

    urg_s, urg_r = _urgency_score(
        lead.get("urgency", "medium"),
        lead.get("pest_description", ""),
    )
    score += urg_s
    reasons.extend(urg_r)

    if lead.get("is_repeat_customer"):
        score += 10
        reasons.append("Repeat customer — higher lifetime value and trust")

    has_phone = bool(lead.get("phone", "").strip())
    has_address = bool(lead.get("address", "").strip())
    if has_phone and has_address:
        score += 5
        reasons.append("Full contact details available — ready for dispatch")
    elif has_phone or has_address:
        score += 2
        reasons.append("Partial contact info — may need follow-up to confirm address")

    score = min(score, 100)

    pest_key = lead.get("pest_type", "general").lower()
    base_value = next((v for k, v in ANNUAL_VALUE_MAP.items() if k in pest_key), ANNUAL_VALUE_MAP["general"])
    if lead.get("property_type", "residential").lower() == "commercial":
        estimated_value = int(base_value * 2.5)
    elif "multi" in lead.get("property_type", "").lower():
        estimated_value = int(base_value * 1.8)
    else:
        estimated_value = base_value

    if score >= 70:
        tier = "hot"
        next_step = "Call within 2 hours and offer same-day or next-morning slot"
        recommended_channel = "phone + email"
    elif score >= 50:
        tier = "qualified"
        next_step = "Send personalised email and schedule a visit within 48 hours"
        recommended_channel = "email"
    else:
        tier = "nurture"
        next_step = "Add to nurture email sequence and follow up in 7 days"
        recommended_channel = "email nurture"

    return {
        "score": score,
        "tier": tier,
        "next_step": next_step,
        "recommended_channel": recommended_channel,
        "reasons": reasons[:6],
        "estimated_value": estimated_value,
    }
