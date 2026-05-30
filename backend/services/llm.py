"""
Unified LLM client — supports Anthropic (Claude) and Azure/OpenAI.

Usage:
    llm = LLMClient()
    response = llm.chat(system="You are…", messages=[{"role":"user","content":"Hi"}])
    print(response.text)

Tool-use response:
    response.tool_calls  →  list[ToolCall]
    response.stop_reason →  "end_turn" | "tool_use"
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from config import settings

log = logging.getLogger(__name__)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"


# ── Tool format converters ────────────────────────────────────────────────────

def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Convert Anthropic-style tool defs to OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]


def _to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    """Prepend system message for OpenAI format."""
    result = []
    if system:
        result.append({"role": "system", "content": system})
    for m in messages:
        if m["role"] == "tool_result":
            result.append({
                "role": "tool",
                "tool_call_id": m.get("tool_use_id", ""),
                "content": str(m.get("content", "")),
            })
        elif m["role"] == "assistant" and m.get("tool_calls"):
            # Preserve tool_calls — dropping them causes a 400 from Azure/OpenAI
            result.append({
                "role": "assistant",
                "content": m.get("content") or "",
                "tool_calls": m["tool_calls"],
            })
        else:
            result.append({"role": m["role"], "content": m.get("content", "")})
    return result


# ── Main client ───────────────────────────────────────────────────────────────

class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.llm_provider.lower()

    def chat(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        if self.provider == "anthropic":
            return self._anthropic(system, messages, tools, max_tokens)
        if self.provider in ("azure", "openai"):
            return self._openai(system, messages, tools, max_tokens)
        return self._mock(system, messages, tools)

    # ── Anthropic ─────────────────────────────────────────────────────────────

    def _anthropic(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int,
    ) -> LLMResponse:
        try:
            import anthropic as sdk
        except ImportError:
            return self._fallback("anthropic SDK not installed")

        if not settings.anthropic_api_key:
            return self._fallback("ANTHROPIC_API_KEY not set")

        client = sdk.Anthropic(api_key=settings.anthropic_api_key)
        kwargs: dict = {
            "model": settings.anthropic_model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            resp = client.messages.create(**kwargs)
        except Exception as exc:
            return self._fallback(f"Anthropic error: {exc}")

        text_parts = [b.text for b in resp.content if hasattr(b, "text")]
        tool_calls = [
            ToolCall(id=b.id, name=b.name, arguments=b.input)
            for b in resp.content
            if b.type == "tool_use"
        ]
        stop = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text=" ".join(text_parts), tool_calls=tool_calls, stop_reason=stop)

    # ── OpenAI / Azure ────────────────────────────────────────────────────────

    def _openai(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int,
    ) -> LLMResponse:
        try:
            from openai import AzureOpenAI, OpenAI
        except ImportError:
            return self._fallback("openai SDK not installed")

        if self.provider == "azure":
            if not (settings.azure_openai_api_key and settings.azure_openai_endpoint and settings.azure_openai_deployment):
                return self._fallback("Azure OpenAI not fully configured")
            client = AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
            )
            model = settings.azure_openai_deployment
        else:
            if not settings.openai_api_key:
                return self._fallback("OPENAI_API_KEY not set")
            client = OpenAI(api_key=settings.openai_api_key)
            model = settings.openai_model

        oai_messages = _to_openai_messages(system, messages)
        # Newer Azure/OpenAI models (o1, o3, gpt-4o >= 2024-09) require max_completion_tokens
        token_param = "max_completion_tokens" if self.provider == "azure" else "max_tokens"
        kwargs: dict = {"model": model, "messages": oai_messages, token_param: max_tokens}
        if tools:
            kwargs["tools"] = _to_openai_tools(tools)
            kwargs["tool_choice"] = "auto"

        log.debug(
            "Azure/OpenAI request — endpoint=%s deployment=%s api_version=%s tools=%s",
            settings.azure_openai_endpoint,
            settings.azure_openai_deployment,
            settings.azure_openai_api_version,
            [t["function"]["name"] for t in kwargs.get("tools", [])],
        )

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:
            log.error("Azure/OpenAI error: %s", exc)
            return self._fallback(f"{self.provider} error: {exc}")

        choice = resp.choices[0]
        msg = choice.message
        text = msg.content or ""
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        stop = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop)

    # ── Mock / fallback ───────────────────────────────────────────────────────

    def _mock(self, system: str, messages: list[dict], tools: list[dict] | None) -> LLMResponse:
        import re
        from uuid import uuid4 as _uuid4

        last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        last_lower = last.lower() if isinstance(last, str) else ""

        # Collect all user text to extract contact details
        all_user_text = " ".join(
            m["content"] for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)
        )

        # Extract email and phone from conversation
        emails = re.findall(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", all_user_text)
        phones = re.findall(r"(?:\+?\d[\d\s\-]{6,}\d)", all_user_text)

        # If a city, email and phone are present → simulate a full booking
        served = [c.lower() for c in settings.service_areas]
        detected_city = next((c.title() for c in served if c in all_user_text.lower()), None)

        BOOKING_TRIGGERS = ["confirm", "book it", "yes, book", "go ahead", "proceed", "book now", "schedule it"]
        wants_booking = any(t in last_lower for t in BOOKING_TRIGGERS) or (
            any(w in last_lower for w in ["book", "appointment", "schedule"])
            and emails and detected_city
        )

        if wants_booking and emails and phones and detected_city and tools:
            name_match = re.search(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b", all_user_text)
            customer_name = name_match.group(1) if name_match else "Demo Customer"
            tool_id = f"mock-{_uuid4().hex[:8]}"
            return LLMResponse(
                text="",
                tool_calls=[ToolCall(
                    id=tool_id,
                    name="book_appointment",
                    arguments={
                        "customer_name": customer_name,
                        "email": emails[0],
                        "phone": phones[0].strip(),
                        "address": "Demo Street 1",
                        "postal_code": "10115" if detected_city == "Berlin" else "80331",
                        "city": detected_city,
                        "pest_type": next(
                            (p for p in ["termites", "bedbugs", "rodents", "roaches", "wasps", "ants"]
                             if p in all_user_text.lower()), "general"
                        ),
                        "property_type": "residential",
                        "urgency": "high" if any(w in all_user_text.lower() for w in ["urgent", "emergency", "asap"]) else "medium",
                        "slot": "Tomorrow 10:00 AM",
                        "notes": "Booked via chat (mock mode)",
                    },
                )],
                stop_reason="tool_use",
            )

        if any(w in last_lower for w in ["price", "cost", "how much", "pricing"]):
            text = (
                "Our pricing depends on the pest type and property size. "
                "A typical residential treatment ranges from €149 for general pests up to €999+ for termites. "
                "Would you like a specific quote? I can check availability and book an inspection for you."
            )
        elif any(w in last_lower for w in ["book", "appointment", "schedule", "available", "visit"]):
            text = (
                "I'd be happy to schedule a visit! We have slots available this week. "
                "Could you share your city, address, and a preferred date? "
                "I'll confirm the appointment right away."
            )
        elif any(w in last_lower for w in ["area", "serve", "location", "city", "where"]):
            text = (
                "We currently serve Berlin, Munich, Hamburg, Frankfurt, Cologne, and Stuttgart. "
                "If you're nearby, we can usually reach you within 24 hours for standard jobs or same-day for emergencies."
            )
        elif any(w in last_lower for w in ["termite", "termites"]):
            text = (
                "Termite infestations are serious and need fast action — they can cause significant structural damage. "
                "We offer full inspections starting at €199, followed by targeted treatment. "
                "I'd recommend booking an emergency inspection. Shall I check availability now?"
            )
        elif any(w in last_lower for w in ["safe", "pet", "child", "kid", "family"]):
            text = (
                "All our treatments use EPA-approved, low-toxicity products. "
                "We ask that pets and children vacate the treated area for 2–4 hours after application. "
                "Our technicians will give you a full safety brief before starting."
            )
        elif any(w in last_lower for w in ["contract", "plan", "subscription", "annual", "monthly"]):
            text = (
                "We offer flexible service plans: monthly (€99/mo), quarterly (€249/quarter), and annual (€799/year). "
                "Annual plans include unlimited call-outs and a 20% discount on add-on treatments. "
                "Would you like me to set up a quote for your property?"
            )
        elif any(w in last_lower for w in ["hello", "hi", "hey", "help", "start"]):
            text = (
                "Hello! Welcome to PestGuard Pro. I'm your AI assistant — I can help you with pricing, "
                "scheduling, pest information, and booking appointments. "
                "What pest issue can I help you with today?"
            )
        else:
            text = (
                "Thanks for reaching out to PestGuard Pro! I can help with pricing, scheduling, "
                "pest identification, and bookings. Could you tell me more about your pest problem "
                "and your location so I can assist you better?"
            )
        return LLMResponse(text=text, tool_calls=[], stop_reason="end_turn")

    def _fallback(self, reason: str) -> LLMResponse:
        return LLMResponse(
            text=(
                f"[AI unavailable: {reason}] "
                "Thanks for reaching out to PestGuard Pro! Please call us directly or leave your contact details "
                "and we'll get back to you shortly."
            ),
            stop_reason="end_turn",
        )


llm_client = LLMClient()
