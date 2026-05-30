"""
Reporting Agent — generates business intelligence reports using the LLM.

Report types:
  • weekly   — jobs completed, revenue, top pest types, satisfaction
  • upsell   — customers due for re-treatment or renewal
  • custom   — AI-generated narrative from raw metrics
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.llm import LLMClient

SYSTEM_PROMPT = """You are a business analyst for PestGuard Pro, a pest control company.
Your role is to write concise, actionable business reports.

Always structure reports with:
1. Executive Summary (2–3 sentences)
2. Key Metrics (bullet points)
3. Insights & Trends
4. Recommended Actions (prioritised)

Keep language professional but plain. Avoid filler. Focus on what matters to the operations manager."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_weekly_report(metrics: dict) -> dict:
    """
    Generate a weekly performance report.

    Args:
        metrics: {
            jobs_completed, jobs_cancelled, total_revenue,
            new_leads, qualified_leads, hot_leads,
            avg_response_time_hours, top_pest_types: [{pest, count}],
            top_cities: [{city, count}],
            technician_utilization: [{name, jobs}]
        }
    """
    client = LLMClient()
    now = _utc_now()
    week_start = (now - timedelta(days=7)).strftime("%b %d")
    week_end = now.strftime("%b %d, %Y")

    prompt = f"""Generate a weekly performance report for PestGuard Pro.
Period: {week_start} – {week_end}

Raw metrics:
- Jobs completed: {metrics.get('jobs_completed', 0)}
- Jobs cancelled: {metrics.get('jobs_cancelled', 0)}
- Total revenue: €{metrics.get('total_revenue', 0):,.0f}
- New leads: {metrics.get('new_leads', 0)}
- Qualified leads: {metrics.get('qualified_leads', 0)}
- Hot leads (immediate): {metrics.get('hot_leads', 0)}
- Avg response time: {metrics.get('avg_response_time_hours', 'N/A')} hours
- Top pest types: {metrics.get('top_pest_types', [])}
- Top cities: {metrics.get('top_cities', [])}
- Technician utilisation: {metrics.get('technician_utilization', [])}

Write the report now."""

    response = client.chat(system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}], max_tokens=800)

    return {
        "report_type": "weekly",
        "title": f"Weekly Report — {week_start} to {week_end}",
        "period": {"start": week_start, "end": week_end},
        "metrics": metrics,
        "narrative": response.text,
        "generated_at": now.isoformat(),
    }


def generate_upsell_report(opportunities: list[dict]) -> dict:
    """
    Generate an upsell/re-engagement report from opportunity records.

    Args:
        opportunities: list from operations.detect_upsell_opportunities()
    """
    client = LLMClient()
    now = _utc_now()

    if not opportunities:
        return {
            "report_type": "upsell",
            "title": "Upsell Opportunities",
            "opportunities": [],
            "narrative": "No upsell opportunities identified this period. All active customers are engaged.",
            "generated_at": now.isoformat(),
        }

    renewals = [o for o in opportunities if o["opportunity_type"] == "contract_renewal"]
    re_treatments = [o for o in opportunities if o["opportunity_type"] == "re_treatment"]

    prompt = f"""Write a concise upsell opportunity report for the sales team.

Data:
- Contract renewals due (next 30 days): {len(renewals)}
  {renewals[:3]}

- Re-treatment opportunities (inactive 90+ days): {len(re_treatments)}
  {re_treatments[:3]}

Total revenue opportunity: approx. €{len(renewals) * 799 + len(re_treatments) * 249:,}

Provide a clear action plan with priorities."""

    response = client.chat(system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}], max_tokens=600)

    return {
        "report_type": "upsell",
        "title": "Upsell & Re-engagement Opportunities",
        "opportunities": opportunities,
        "summary": {
            "total": len(opportunities),
            "contract_renewals": len(renewals),
            "re_treatments": len(re_treatments),
            "estimated_revenue": len(renewals) * 799 + len(re_treatments) * 249,
        },
        "narrative": response.text,
        "generated_at": now.isoformat(),
    }


def generate_custom_report(question: str, context_data: dict) -> dict:
    """
    Generate a custom report from a natural language question.

    Args:
        question: e.g. "Which technician has the highest completion rate?"
        context_data: dict of relevant metrics/records
    """
    client = LLMClient()
    now = _utc_now()

    prompt = f"""Answer this business question for PestGuard Pro:

Question: {question}

Available data:
{context_data}

Provide a direct answer followed by supporting data and a recommended action."""

    response = client.chat(system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}], max_tokens=600)

    return {
        "report_type": "custom",
        "title": f"Custom Report: {question[:60]}",
        "question": question,
        "narrative": response.text,
        "generated_at": now.isoformat(),
    }
