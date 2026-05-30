"""
Operations Automation Agent — scheduling, reminders, and post-job follow-ups.

Capabilities:
  • Auto-assign technicians to jobs based on city/specialty match
  • Generate SMS/email reminders for jobs due within 24 hours
  • Generate post-job follow-up messages (review requests)
  • Detect upsell opportunities (customers due for re-treatment)
  • Cluster jobs by region to minimise travel time
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from services.comms import send_email, send_sms

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── Technician assignment ─────────────────────────────────────────────────────

def assign_technician(job: dict, technicians: list[dict]) -> dict | None:
    """
    Pick the best available technician for a job.

    Preference order:
      1. Serves the city AND has matching specialty
      2. Serves the city only
      3. Any available technician (fallback)
    """
    city = job.get("city", "").lower()
    pest = job.get("pest_type", "").lower()
    available = [t for t in technicians if t.get("is_available", True)]

    # Exact match: city + specialty
    for tech in available:
        areas = [a.lower() for a in tech.get("service_areas", [])]
        specialties = [s.lower() for s in tech.get("specialties", [])]
        if city in areas and any(s in pest for s in specialties):
            return tech

    # City match only
    for tech in available:
        areas = [a.lower() for a in tech.get("service_areas", [])]
        if city in areas:
            return tech

    # Fallback
    return available[0] if available else None


# ── Reminder generation ───────────────────────────────────────────────────────

def generate_job_reminders(jobs: list[dict]) -> list[dict]:
    """
    Return reminder payloads for jobs scheduled in the next 24 hours
    that haven't had a reminder sent yet.
    """
    now = _utc_now()
    window_end = now + timedelta(hours=24)
    reminders = []

    for job in jobs:
        if job.get("reminder_sent"):
            continue
        if job.get("status") != "scheduled":
            continue

        scheduled_raw = job.get("scheduled_at")
        if not scheduled_raw:
            continue

        scheduled = (
            scheduled_raw if isinstance(scheduled_raw, datetime)
            else datetime.fromisoformat(str(scheduled_raw))
        )
        if not (now <= scheduled <= window_end):
            continue

        customer_name = job.get("customer_name", "Valued Customer")
        customer_phone = job.get("customer_phone", "")
        customer_email = job.get("customer_email", "")
        tech_name = job.get("technician_name", "our technician")
        slot = scheduled.strftime("%A %b %d at %I:%M %p")
        pest = job.get("pest_type", "pest control")

        sms_body = (
            f"Reminder: Your {pest} treatment with PestGuard Pro is tomorrow — "
            f"{slot}. {tech_name} will arrive at your address. "
            f"Questions? Call us anytime."
        )
        email_subject = f"Reminder: Your PestGuard Pro appointment — {slot}"
        email_body = (
            f"Hi {customer_name},\n\n"
            f"Just a reminder that your {pest} treatment is scheduled for {slot}.\n\n"
            f"Your technician: {tech_name}\n"
            f"Address: {job.get('address', 'on file')}\n\n"
            f"Please ensure the affected area is accessible. "
            f"Pets and children should vacate for 2–4 hours after treatment.\n\n"
            f"See you soon,\nPestGuard Pro Team"
        )

        sent_sms = send_sms(customer_phone, sms_body) if customer_phone else False
        sent_email = send_email(customer_email, email_subject, email_body) if customer_email else False

        reminders.append({
            "job_id": job["id"],
            "sms_sent": sent_sms,
            "email_sent": sent_email,
            "message": sms_body,
        })

    return reminders


# ── Post-job follow-up ────────────────────────────────────────────────────────

def generate_followup_messages(jobs: list[dict]) -> list[dict]:
    """
    Send review requests for jobs completed in the last 48 hours
    that haven't had a follow-up sent.
    """
    now = _utc_now()
    cutoff = now - timedelta(hours=48)
    followups = []

    for job in jobs:
        if job.get("follow_up_sent"):
            continue
        if job.get("status") != "completed":
            continue

        completed_raw = job.get("completed_at")
        if not completed_raw:
            continue

        completed = (
            completed_raw if isinstance(completed_raw, datetime)
            else datetime.fromisoformat(str(completed_raw))
        )
        if completed < cutoff:
            continue

        customer_name = job.get("customer_name", "Valued Customer")
        customer_email = job.get("customer_email", "")
        pest = job.get("pest_type", "pest")
        first_name = customer_name.split()[0] if customer_name else "there"

        subject = f"How did your {pest} treatment go? — PestGuard Pro"
        body = (
            f"Hi {first_name},\n\n"
            f"We hope your {pest} treatment went smoothly! "
            f"Your satisfaction is our priority — if you have any concerns in the next 30 days, "
            f"we'll come back at no extra charge (our guarantee).\n\n"
            f"If you were happy with the service, we'd really appreciate a quick review:\n"
            f"👉 Leave a review → https://g.page/pestguardpro/review\n\n"
            f"And if you'd like to stay pest-free year-round, ask us about our annual plan (€799/year).\n\n"
            f"Thanks for choosing PestGuard Pro!\n"
            f"The PestGuard Team"
        )

        sent = send_email(customer_email, subject, body) if customer_email else False
        followups.append({
            "job_id": job["id"],
            "email_sent": sent,
            "subject": subject,
        })

    return followups


# ── Upsell detection ──────────────────────────────────────────────────────────

def detect_upsell_opportunities(customers: list[dict], jobs: list[dict]) -> list[dict]:
    """
    Find customers who:
      • Had a one-off treatment 90+ days ago with no follow-up job
      • Are on a contract nearing renewal
    """
    now = _utc_now()
    ninety_days_ago = now - timedelta(days=90)
    opportunities = []

    completed_by_customer: dict[str, datetime] = {}
    for job in jobs:
        if job.get("status") != "completed":
            continue
        cid = job.get("customer_id")
        if not cid:
            continue
        completed_raw = job.get("completed_at")
        if not completed_raw:
            continue
        completed = (
            completed_raw if isinstance(completed_raw, datetime)
            else datetime.fromisoformat(str(completed_raw))
        )
        if cid not in completed_by_customer or completed > completed_by_customer[cid]:
            completed_by_customer[cid] = completed

    for customer in customers:
        cid = customer.get("id")
        last_job = completed_by_customer.get(cid)

        # One-off customers inactive for 90+ days
        if customer.get("contract_type") == "one-off" and last_job and last_job < ninety_days_ago:
            days_ago = (now - last_job).days
            opportunities.append({
                "customer_id": cid,
                "customer_name": customer.get("name"),
                "customer_email": customer.get("email"),
                "reason": f"Last treatment was {days_ago} days ago — due for re-treatment",
                "opportunity_type": "re_treatment",
                "recommended_action": "Send re-engagement email with seasonal pest prevention offer",
            })

        # Contract renewal within 30 days
        contract_end_raw = customer.get("contract_end")
        if contract_end_raw and customer.get("contract_type") != "one-off":
            contract_end = (
                contract_end_raw if isinstance(contract_end_raw, datetime)
                else datetime.fromisoformat(str(contract_end_raw))
            )
            days_to_renewal = (contract_end - now).days
            if 0 <= days_to_renewal <= 30:
                opportunities.append({
                    "customer_id": cid,
                    "customer_name": customer.get("name"),
                    "customer_email": customer.get("email"),
                    "reason": f"Contract renews in {days_to_renewal} days",
                    "opportunity_type": "contract_renewal",
                    "recommended_action": "Send renewal offer with loyalty discount",
                })

    return opportunities


# ── Schedule optimisation (cluster jobs by city) ──────────────────────────────

def cluster_jobs_by_city(jobs: list[dict]) -> dict[str, list[dict]]:
    """Group pending/scheduled jobs by city for efficient routing."""
    clusters: dict[str, list[dict]] = {}
    for job in jobs:
        if job.get("status") not in ("scheduled", "pending"):
            continue
        city = job.get("city", "unknown")
        clusters.setdefault(city, []).append(job)
    return clusters
