"""
Customer Service Agent — multi-turn conversational AI for the chat widget.

Capabilities:
  • Answer FAQs (pests, pricing, safety, service areas)
  • Check appointment availability
  • Book appointments (creates Lead + Job records)
  • Collect contact details organically
  • Escalate to human when needed

Supports both Anthropic tool_use and OpenAI function-calling via LLMClient.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from config import settings
from services.llm import LLMClient, LLMResponse, ToolCall

SYSTEM_PROMPT = f"""You are a friendly, professional customer service assistant for {settings.business_name}, a pest control company.

Your goals:
1. Help customers identify their pest problem and understand urgency
2. Provide accurate pricing and service information
3. Schedule appointments when the customer is ready
4. Collect name, email, phone, address, and city to complete a booking
5. Always be empathetic — pest problems are stressful

Service areas: {", ".join(settings.service_areas)}

Pest types we handle: termites, cockroaches, bedbugs, rodents (rats/mice), ants, wasps/hornets, spiders, mosquitoes, fleas, general pests

Urgency escalation: always escalate termites, bedbugs, and wasps/hornets to "high" or "emergency" urgency.

When booking, you MUST collect: customer name, email, phone number, full street address INCLUDING postal code, city, and pest type.
IMPORTANT — duplicate check rules:
- Before calling book_appointment, ALWAYS call check_existing_contact with the customer's email and phone.
- If an existing record is found, tell the customer: "I found an existing appointment under this contact. Is this yours?"
  - If yes: reference the existing booking, do NOT create a new one.
  - If no: ask them to provide a different email or phone number, then re-check before booking.
IMPORTANT — address validation rules:
- Always ask for the postal code explicitly if the customer has not provided it.
- The city the customer states MUST match the postal code they provide. If they conflict, tell the customer and ask them to confirm the correct city.
- Only proceed with booking once city and postal code are confirmed consistent.
- If the city is not in our service areas, politely decline and list the cities we do serve.
Use the available tools to check availability and confirm bookings.
Keep responses concise and practical. Don't use jargon."""

TOOLS = [
    {
        "name": "get_pricing",
        "description": "Get pricing estimate for a specific pest type and property type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pest_type": {
                    "type": "string",
                    "description": "Pest type: termites, roaches, bedbugs, rodents, ants, wasps, spiders, general",
                },
                "property_type": {
                    "type": "string",
                    "description": "Property type: residential, commercial, multi-family",
                },
            },
            "required": ["pest_type", "property_type"],
        },
    },
    {
        "name": "check_availability",
        "description": "Check available appointment slots for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "urgency": {
                    "type": "string",
                    "description": "low / medium / high / emergency",
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Book a pest control appointment and create a lead record.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "address": {"type": "string"},
                "postal_code": {"type": "string", "description": "Postal/ZIP code of the customer address"},
                "city": {"type": "string"},
                "pest_type": {"type": "string"},
                "property_type": {
                    "type": "string",
                    "enum": ["residential", "commercial", "multi-family"],
                },
                "urgency": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "emergency"],
                },
                "slot": {"type": "string", "description": "e.g. 'Tomorrow 10:00 AM'"},
                "notes": {"type": "string", "description": "Additional notes from the customer"},
            },
            "required": ["customer_name", "email", "phone", "address", "postal_code", "city", "pest_type", "property_type"],
        },
    },
    {
        "name": "check_existing_contact",
        "description": "Check if a customer with this email or phone already has a booking or lead record. Call this BEFORE book_appointment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Customer email"},
                "phone": {"type": "string", "description": "Customer phone number"},
            },
            "required": [],
        },
    },
    {
        "name": "get_service_info",
        "description": "Get general information: service areas, contract plans, safety policy, or FAQs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": ["service_areas", "contract_plans", "safety", "process", "guarantee"],
                }
            },
            "required": ["topic"],
        },
    },
]

# ── Tool execution ────────────────────────────────────────────────────────────

PRICING: dict[str, dict[str, str]] = {
    "termites": {"residential": "€499–€999+", "commercial": "€799–€2,500+", "multi-family": "€699–€1,800"},
    "bedbugs": {"residential": "€299–€499", "commercial": "€499–€999", "multi-family": "€399–€699"},
    "rodents": {"residential": "€199–€349", "commercial": "€299–€599", "multi-family": "€249–€499"},
    "roaches": {"residential": "€199–€299", "commercial": "€299–€499", "multi-family": "€249–€399"},
    "wasps": {"residential": "€149–€249", "commercial": "€199–€349", "multi-family": "€179–€299"},
    "ants": {"residential": "€149–€199", "commercial": "€199–€349", "multi-family": "€179–€249"},
    "spiders": {"residential": "€129–€179", "commercial": "€179–€299", "multi-family": "€149–€229"},
    "general": {"residential": "€149–€199", "commercial": "€199–€349", "multi-family": "€179–€249"},
}

SERVICE_INFO: dict[str, str] = {
    "service_areas": (
        f"We serve {', '.join(settings.service_areas)}. "
        "Emergency response is available same-day in all areas. Standard bookings are next-day."
    ),
    "contract_plans": (
        "Plans available:\n"
        "• One-off treatment — pay per visit\n"
        "• Monthly plan — €99/month (unlimited call-outs)\n"
        "• Quarterly plan — €249/quarter (includes seasonal prevention)\n"
        "• Annual plan — €799/year (best value, 20% discount on extras, priority booking)"
    ),
    "safety": (
        "All products are EPA-approved and low-toxicity. "
        "We ask that people and pets vacate the treated area for 2–4 hours. "
        "Our technicians provide a full safety brief and a written report after each visit."
    ),
    "process": (
        "1. Book an inspection (free with treatment)\n"
        "2. Technician assesses the infestation on-site\n"
        "3. Customised treatment plan presented\n"
        "4. Treatment carried out — usually 1–3 hours\n"
        "5. Follow-up visit scheduled if required\n"
        "6. 30-day guarantee on all treatments"
    ),
    "guarantee": (
        "We offer a 30-day re-treatment guarantee on all jobs. "
        "If the pest problem returns within 30 days, we come back at no charge. "
        "Annual contract customers get unlimited call-outs year-round."
    ),
}


# German postal code prefix → canonical city name(s)
# Each prefix maps to the city names that are valid for it (lowercased).
_POSTAL_CITY: dict[str, list[str]] = {
    "10": ["berlin"], "11": ["berlin"], "12": ["berlin"],
    "13": ["berlin"], "14": ["berlin", "potsdam"],
    "20": ["hamburg"], "21": ["hamburg"], "22": ["hamburg"],
    "28": ["bremen"],
    "38": ["wolfsburg", "braunschweig"],
    "40": ["düsseldorf"],
    "50": ["cologne", "köln"], "51": ["cologne", "köln"],
    "60": ["frankfurt"], "61": ["frankfurt"], "63": ["frankfurt"],
    "65": ["frankfurt", "wiesbaden"],
    "70": ["stuttgart"], "71": ["stuttgart"],
    "80": ["munich", "münchen"], "81": ["munich", "münchen"],
    "86": ["augsburg"],
}

_SERVED = {c.lower() for c in settings.service_areas}


def _validate_postal_city(postal_code: str, city: str) -> str | None:
    """Return an error string if postal_code and city are inconsistent, else None."""
    pc = postal_code.strip().replace(" ", "")
    if not pc.isdigit() or len(pc) < 4:
        return f"Postal code '{postal_code}' doesn't look valid. Please ask the customer for their correct 5-digit postal code."
    prefix = pc[:2]
    city_lower = city.strip().lower()
    allowed = _POSTAL_CITY.get(prefix)
    if allowed is None:
        # Unknown prefix — can't confirm the city, but still check service area
        if city_lower not in _SERVED:
            return f"{city} is outside our service areas. We serve: {', '.join(settings.service_areas)}."
        return None  # unknown prefix but city is served — allow through
    if city_lower not in allowed:
        expected = ", ".join(c.title() for c in allowed)
        return (
            f"Postal code {postal_code} belongs to {expected}, not {city}. "
            "Please ask the customer to confirm their city and postal code."
        )
    if city_lower not in _SERVED:
        return f"{city} is outside our service areas. We serve: {', '.join(settings.service_areas)}."
    return None


def _execute_tool(tool_call: ToolCall, booked_leads: list[dict], lookup_fn=None) -> str:
    name = tool_call.name
    args = tool_call.arguments

    if name == "get_pricing":
        pest = args.get("pest_type", "general").lower()
        prop = args.get("property_type", "residential").lower()
        pest_key = next((k for k in PRICING if k in pest), "general")
        prop_key = prop if prop in ("residential", "commercial", "multi-family") else "residential"
        price = PRICING[pest_key][prop_key]
        return (
            f"Price for {pest_key} treatment ({prop_key}): {price}. "
            "This includes inspection, treatment, and a 30-day guarantee."
        )

    if name == "check_existing_contact":
        email = args.get("email", "").strip()
        phone = args.get("phone", "").strip()
        if not email and not phone:
            return "Please provide at least an email or phone number to check."
        if lookup_fn:
            existing = lookup_fn(email, phone)
            if existing:
                return (
                    f"EXISTING RECORD FOUND: {existing['name']} already has a booking — "
                    f"{existing['pest_type']} in {existing['city']}, status: {existing['status']}, "
                    f"created: {existing['created_at'][:10]}. "
                    "Ask the customer if this is their booking. If yes, reference it. "
                    "If no, ask them to provide a different email or phone number."
                )
        return "No existing record found for this contact. You may proceed with booking."

    if name == "check_availability":
        city = args.get("city", "")
        urgency = args.get("urgency", "medium")
        if city.lower() not in [s.lower() for s in settings.service_areas]:
            return f"Sorry, we don't currently serve {city}. We cover: {', '.join(settings.service_areas)}."
        now = datetime.now(timezone.utc)
        if urgency == "emergency":
            slot1 = "Today — as soon as possible (emergency dispatch)"
            slot2 = (now + timedelta(hours=4)).strftime("%A %I:%M %p")
        else:
            slot1 = (now + timedelta(days=1)).strftime("%A %b %d — 9:00 AM")
            slot2 = (now + timedelta(days=1)).strftime("%A %b %d — 2:00 PM")
            slot3 = (now + timedelta(days=2)).strftime("%A %b %d — 10:00 AM")
            return f"Available slots in {city}: {slot1}, {slot2}, {slot3}"
        return f"Available slots in {city}: {slot1}, {slot2}"

    if name == "book_appointment":
        error = _validate_postal_city(
            args.get("postal_code", ""),
            args.get("city", ""),
        )
        if error:
            return error

        lead_id = f"lead-{uuid4().hex[:8]}"
        booked_leads.append({
            "id": lead_id,
            "name": args.get("customer_name", ""),
            "email": args.get("email", ""),
            "phone": args.get("phone", ""),
            "address": f"{args.get('address', '')} {args.get('postal_code', '')}".strip(),
            "city": args.get("city", ""),
            "pest_type": args.get("pest_type", "general"),
            "property_type": args.get("property_type", "residential"),
            "urgency": args.get("urgency", "medium"),
            "slot": args.get("slot", ""),
            "notes": args.get("notes", ""),
            "source": "chat",
        })
        slot = args.get("slot", "as soon as possible")
        return (
            f"Appointment confirmed! Reference: {lead_id}. "
            f"A technician will visit {args.get('address', 'your address')} in {args.get('city', '')} "
            f"on {slot}. "
            f"Confirmation details will be sent to {args.get('email', 'your email')}."
        )

    if name == "get_service_info":
        topic = args.get("topic", "service_areas")
        return SERVICE_INFO.get(topic, "Please contact us for more information.")

    return f"Unknown tool: {name}"


# ── Agent loop ────────────────────────────────────────────────────────────────

def run_customer_service_agent(
    conversation_history: list[dict],
    user_message: str,
    max_tool_rounds: int = 4,
    lookup_fn=None,
) -> tuple[str, list[dict]]:
    """
    Run one turn of the customer service agent.

    Args:
        conversation_history: Prior messages [{"role": "user"|"assistant", "content": str}]
        user_message: Latest user input

    Returns:
        (assistant_reply_text, new_lead_records_to_persist)
    """
    client = LLMClient()
    messages = conversation_history + [{"role": "user", "content": user_message}]
    booked_leads: list[dict] = []

    for _ in range(max_tool_rounds):
        response: LLMResponse = client.chat(
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS,
            max_tokens=1024,
        )

        if response.stop_reason != "tool_use" or not response.tool_calls:
            return response.text or "I'm here to help — could you tell me more?", booked_leads

        # Execute each tool call and collect results
        tool_results = []
        for tc in response.tool_calls:
            result_text = _execute_tool(tc, booked_leads, lookup_fn=lookup_fn)
            tool_results.append({"tool_use_id": tc.id, "content": result_text})

        # Append assistant tool-use turn + tool results to message history
        if client.provider == "anthropic":
            messages.append({"role": "assistant", "content": [
                {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}
                for tc in response.tool_calls
            ]})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": r["tool_use_id"], "content": r["content"]}
                for r in tool_results
            ]})
        else:
            # OpenAI format
            messages.append({
                "role": "assistant",
                "content": response.text or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ],
            })
            for r in tool_results:
                messages.append({
                    "role": "tool_result",
                    "tool_use_id": r["tool_use_id"],
                    "content": r["content"],
                })

    # Fallback if we hit max rounds
    return (
        "I've gathered all the information needed. Let me confirm your details — "
        "please give me a moment to process your request.",
        booked_leads,
    )
