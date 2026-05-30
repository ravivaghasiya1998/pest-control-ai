"""
Main service layer — orchestrates agents, DB access, and business logic.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from config import settings
from data.seed import get_seed_jobs, get_seed_leads, get_seed_technicians
from database import session_scope
from models.model import (
    ActivityItem, Base, Conversation, Customer, Job, Lead, Message,
    Report, Technician, User, UserSession, utc_now,
)
from services.agents.customer_service import run_customer_service_agent
from services.agents.operations import (
    assign_technician,
    cluster_jobs_by_city,
    detect_upsell_opportunities,
    generate_followup_messages,
    generate_job_reminders,
)
from services.agents.qualification import qualify_lead
from services.agents.reporting import generate_upsell_report, generate_weekly_report


# ── Utilities ─────────────────────────────────────────────────────────────────

def isoformat(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.isoformat().replace("+00:00", "Z")


def _as_utc(dt: datetime | None) -> datetime | None:
    """Make a datetime timezone-aware (UTC) if it is naive — SQLite returns naive datetimes."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ── Serializers ───────────────────────────────────────────────────────────────

def ser_user(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name,
        "role": u.role, "phone": u.phone or "",
        "must_change_password": u.must_change_password,
        "delete_requested": u.delete_requested,
        "created_at": isoformat(u.created_at),
    }


def ser_lead(l: Lead) -> dict:
    return {
        "id": l.id, "name": l.name, "email": l.email, "phone": l.phone or "",
        "address": l.address or "", "city": l.city, "property_type": l.property_type,
        "pest_type": l.pest_type, "pest_description": l.pest_description or "",
        "urgency": l.urgency, "source": l.source, "status": l.status,
        "qualification": l.qualification or {}, "outreach": l.outreach or {},
        "is_repeat_customer": l.is_repeat_customer, "annual_value": l.annual_value or 0,
        "created_at": isoformat(l.created_at), "updated_at": isoformat(l.updated_at),
    }


def ser_job(j: Job) -> dict:
    tech_name = None
    if j.technician:
        tech_name = j.technician.name
    return {
        "id": j.id, "lead_id": j.lead_id, "customer_id": j.customer_id,
        "technician_id": j.technician_id, "technician_name": tech_name,
        "service_type": j.service_type, "pest_type": j.pest_type,
        "address": j.address, "city": j.city, "status": j.status,
        "scheduled_at": isoformat(j.scheduled_at), "completed_at": isoformat(j.completed_at),
        "price": j.price, "notes": j.notes or "",
        "reminder_sent": j.reminder_sent, "follow_up_sent": j.follow_up_sent,
        "review_requested": j.review_requested, "created_at": isoformat(j.created_at),
    }


def ser_technician(t: Technician) -> dict:
    return {
        "id": t.id, "name": t.name, "email": t.email, "phone": t.phone,
        "service_areas": t.service_areas or [], "specialties": t.specialties or [],
        "is_available": t.is_available,
    }


def ser_message(m: Message) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content, "created_at": isoformat(m.created_at)}


def ser_activity(a: ActivityItem) -> dict:
    return {
        "timestamp": isoformat(a.timestamp), "category": a.category,
        "message": a.message, "lead_id": a.lead_id, "job_id": a.job_id,
    }


def ser_report(r: Report) -> dict:
    return {
        "id": r.id, "report_type": r.report_type, "title": r.title,
        "content": r.content or {}, "generated_at": isoformat(r.generated_at),
    }


# ── Auth ──────────────────────────────────────────────────────────────────────

def hash_password(password: str, salt: str | None = None) -> str:
    salt_value = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt_value.encode(), 240000)
    return f"{salt_value}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, expected = stored.split("$", 1)
    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, f"{salt}${expected}")


def hash_token(token: str) -> str:
    return hashlib.sha256(f"{settings.auth_secret}:{token}".encode()).hexdigest()


def register_user(email: str, full_name: str, password: str) -> dict:
    with session_scope() as s:
        if s.scalar(select(User).where(User.email == email)):
            raise ValueError("A user with this email already exists")
        user = User(email=email, full_name=full_name, password_hash=hash_password(password), role="user")
        s.add(user)
        s.flush()
        return ser_user(user)


def _create_session(user: User, s: Session) -> tuple[str, dict]:
    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(hours=settings.auth_token_ttl_hours)
    s.execute(delete(UserSession).where(UserSession.user_id == user.id))
    s.add(UserSession(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    s.flush()
    return token, ser_user(user)


def login_user(email: str, password: str) -> dict:
    with session_scope() as s:
        user = s.scalar(select(User).where(User.email == email))
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")
        token, user_data = _create_session(user, s)
        return {"access_token": token, "token_type": "bearer", "user": user_data}


def get_current_user(token: str) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    with session_scope() as s:
        record = s.scalar(
            select(UserSession).where(
                UserSession.token_hash == hash_token(token),
                UserSession.expires_at > utc_now(),
            )
        )
        if not record:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        user = s.get(User, record.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User no longer exists")
        s.expunge(user)
        return user


# ── Leads ─────────────────────────────────────────────────────────────────────

def _find_duplicate_lead(s, email: str | None, phone: str | None) -> tuple[object | None, str]:
    """Return (existing_lead, conflict_field) or (None, '')."""
    conditions = []
    if email and email.strip():
        conditions.append(Lead.email == email.strip())
    if phone and phone.strip():
        conditions.append(Lead.phone == phone.strip())
    if not conditions:
        return None, ""
    existing = s.scalar(select(Lead).where(or_(*conditions)))
    if not existing:
        return None, ""
    field = "email" if existing.email == (email or "").strip() else "phone"
    return existing, field


def create_lead(data: dict) -> dict:
    with session_scope() as s:
        existing, field = _find_duplicate_lead(s, data.get("email"), data.get("phone"))
        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "duplicate_lead",
                    "conflict_field": field,
                    "existing": ser_lead(existing),
                },
            )
        lead = Lead(
            id=f"lead-{uuid4().hex[:8]}",
            **{k: v for k, v in data.items() if hasattr(Lead, k)},
        )
        s.add(lead)
        s.add(ActivityItem(category="system", message=f"New lead created: {lead.name} ({lead.pest_type})"))
        s.flush()
        return ser_lead(lead)


def list_leads(status: str | None = None, city: str | None = None) -> dict:
    with session_scope() as s:
        stmt = select(Lead).order_by(Lead.created_at.desc())
        if status:
            stmt = stmt.where(Lead.status == status)
        if city:
            stmt = stmt.where(Lead.city == city)
        leads = s.scalars(stmt).all()
        return {"items": [ser_lead(l) for l in leads], "count": len(leads)}


def get_lead(lead_id: str) -> dict:
    with session_scope() as s:
        lead = s.get(Lead, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
        return ser_lead(lead)


def qualify_lead_service(lead_id: str) -> dict:
    with session_scope() as s:
        lead = s.get(Lead, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
        q = qualify_lead(ser_lead(lead))
        lead.qualification = q
        lead.status = q["tier"]
        lead.annual_value = q["estimated_value"]
        s.add(ActivityItem(
            category="qualification",
            lead_id=lead.id,
            message=f"{lead.name} scored {q['score']} — tier: {q['tier']}",
        ))
        s.flush()
        return {"lead": ser_lead(lead)}


def qualify_all_leads() -> dict:
    with session_scope() as s:
        leads = s.scalars(select(Lead).where(Lead.status == "new")).all()
        results = []
        for lead in leads:
            q = qualify_lead(ser_lead(lead))
            lead.qualification = q
            lead.status = q["tier"]
            lead.annual_value = q["estimated_value"]
            results.append({"id": lead.id, "score": q["score"], "tier": q["tier"]})
            s.add(ActivityItem(
                category="qualification",
                lead_id=lead.id,
                message=f"Bulk qualification: {lead.name} → {q['tier']} (score {q['score']})",
            ))
        s.flush()
        return {"qualified": len(results), "results": results}


# ── Jobs ──────────────────────────────────────────────────────────────────────

def create_job(data: dict) -> dict:
    with session_scope() as s:
        job = Job(id=f"job-{uuid4().hex[:8]}", **{k: v for k, v in data.items() if hasattr(Job, k)})
        s.add(job)
        s.flush()
        s.refresh(job)
        return {"job": ser_job(job)}


def list_jobs(status: str | None = None, city: str | None = None, technician_id: int | None = None) -> dict:
    with session_scope() as s:
        stmt = select(Job).order_by(Job.scheduled_at.asc())
        if technician_id:
            stmt = stmt.where(Job.technician_id == technician_id)
        if status:
            stmt = stmt.where(Job.status == status)
        if city:
            stmt = stmt.where(Job.city == city)
        jobs = s.scalars(stmt).all()
        return {"items": [ser_job(j) for j in jobs], "count": len(jobs)}


def update_job(job_id: str, data: dict) -> dict:
    with session_scope() as s:
        job = s.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        for k, v in data.items():
            if v is not None and hasattr(job, k):
                setattr(job, k, v)
        s.flush()
        s.refresh(job)
        return {"job": ser_job(job)}


def auto_assign_jobs() -> dict:
    """Assign unassigned scheduled jobs to the best available technician."""
    with session_scope() as s:
        unassigned = s.scalars(
            select(Job).where(Job.status == "scheduled", Job.technician_id.is_(None))
        ).all()
        techs = [ser_technician(t) for t in s.scalars(select(Technician)).all()]
        assigned_count = 0
        for job in unassigned:
            job_dict = ser_job(job)
            tech = assign_technician(job_dict, techs)
            if tech:
                job.technician_id = tech["id"]
                assigned_count += 1
                s.add(ActivityItem(
                    category="scheduling",
                    job_id=job.id,
                    message=f"Auto-assigned {tech['name']} to {job.pest_type} job in {job.city}",
                ))
        s.flush()
        return {"assigned": assigned_count, "total_unassigned": len(unassigned)}


def send_reminders() -> dict:
    with session_scope() as s:
        jobs = s.scalars(select(Job).where(Job.status == "scheduled")).all()
        jobs_with_context = []
        for j in jobs:
            d = ser_job(j)
            if j.lead:
                d["customer_name"] = j.lead.name
                d["customer_email"] = j.lead.email
                d["customer_phone"] = j.lead.phone
            jobs_with_context.append(d)

        results = generate_job_reminders(jobs_with_context)

        for r in results:
            job = s.get(Job, r["job_id"])
            if job:
                job.reminder_sent = True
                s.add(ActivityItem(
                    category="comms",
                    job_id=r["job_id"],
                    message=f"Reminder sent for job {r['job_id']}",
                ))
        s.flush()
        return {"reminders_sent": len(results)}


def send_followups() -> dict:
    with session_scope() as s:
        jobs = s.scalars(select(Job).where(Job.status == "completed", Job.follow_up_sent == False)).all()
        jobs_with_context = []
        for j in jobs:
            d = ser_job(j)
            if j.lead:
                d["customer_name"] = j.lead.name
                d["customer_email"] = j.lead.email
            jobs_with_context.append(d)

        results = generate_followup_messages(jobs_with_context)

        for r in results:
            job = s.get(Job, r["job_id"])
            if job:
                job.follow_up_sent = True
                job.review_requested = True
                s.add(ActivityItem(
                    category="comms",
                    job_id=r["job_id"],
                    message=f"Follow-up + review request sent for job {r['job_id']}",
                ))
        s.flush()
        return {"followups_sent": len(results)}


# ── Chat ──────────────────────────────────────────────────────────────────────

def chat_message(session_id: str, user_message: str, visitor_name: str, visitor_email: str) -> dict:
    with session_scope() as s:
        conv = s.scalar(select(Conversation).where(Conversation.id == session_id))
        if not conv:
            conv = Conversation(
                id=session_id, visitor_name=visitor_name, visitor_email=visitor_email
            )
            s.add(conv)
            s.flush()

        history = [
            {"role": m.role, "content": m.content}
            for m in (s.scalars(select(Message).where(Message.conversation_id == session_id).order_by(Message.created_at)).all())
        ]

        def lookup_contact(email: str, phone: str):
            lead, _ = _find_duplicate_lead(s, email, phone)
            return ser_lead(lead) if lead else None

        reply, new_leads = run_customer_service_agent(history, user_message, lookup_fn=lookup_contact)

        s.add(Message(conversation_id=session_id, role="user", content=user_message))
        s.add(Message(conversation_id=session_id, role="assistant", content=reply))

        persisted_leads = []
        for ld in new_leads:
            existing, conflict_field = _find_duplicate_lead(s, ld.get("email"), ld.get("phone"))
            if existing:
                persisted_leads.append({
                    "id": existing.id, "name": existing.name,
                    "is_existing": True, "conflict_field": conflict_field,
                })
                continue
            lead = Lead(
                id=f"lead-{uuid4().hex[:8]}",
                name=ld.get("name", ""), email=ld.get("email", ""),
                phone=ld.get("phone", ""), address=ld.get("address", ""),
                city=ld.get("city", ""), property_type=ld.get("property_type", "residential"),
                pest_type=ld.get("pest_type", "general"), pest_description=ld.get("notes", ""),
                urgency=ld.get("urgency", "medium"), source="chat",
            )
            s.add(lead)
            s.flush()  # persist lead so job FK resolves

            urgency = ld.get("urgency", "medium")
            hours_until = 4 if urgency == "emergency" else (24 if urgency == "high" else 48)
            job = Job(
                id=f"job-{uuid4().hex[:8]}",
                lead_id=lead.id,
                service_type=f"{ld.get('pest_type', 'general')} treatment",
                pest_type=ld.get("pest_type", "general"),
                address=ld.get("address", ""),
                city=ld.get("city", ""),
                status="scheduled",
                scheduled_at=utc_now() + timedelta(hours=hours_until),
                notes=f"Booked via chat. Slot: {ld.get('slot', 'TBD')}. {ld.get('notes', '')}".strip(". "),
            )
            s.add(job)
            s.flush()  # write job row before activity_items FK reference

            s.add(ActivityItem(
                category="chat",
                lead_id=lead.id,
                job_id=job.id,
                message=f"Chat booking: {lead.name} — {lead.pest_type} in {lead.city}",
            ))
            persisted_leads.append({"id": lead.id, "name": lead.name, "job_id": job.id})

        s.flush()
        return {"session_id": session_id, "reply": reply, "booked_leads": persisted_leads}


def get_conversation(session_id: str) -> dict:
    with session_scope() as s:
        conv = s.scalar(select(Conversation).where(Conversation.id == session_id))
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        msgs = s.scalars(
            select(Message).where(Message.conversation_id == session_id).order_by(Message.created_at)
        ).all()
        return {
            "id": conv.id, "visitor_name": conv.visitor_name,
            "visitor_email": conv.visitor_email, "status": conv.status,
            "messages": [ser_message(m) for m in msgs],
            "created_at": isoformat(conv.created_at),
        }


# ── Technicians ───────────────────────────────────────────────────────────────

def list_technicians() -> dict:
    with session_scope() as s:
        techs = s.scalars(select(Technician)).all()
        return {"items": [ser_technician(t) for t in techs]}


# ── Reports ───────────────────────────────────────────────────────────────────

def generate_report(report_type: str, user_id: int | None = None, question: str = "") -> dict:
    with session_scope() as s:
        now = utc_now()
        week_ago = now - timedelta(days=7)

        if report_type == "weekly":
            completed = s.scalars(
                select(Job).where(Job.status == "completed", Job.completed_at >= week_ago)
            ).all()
            new_leads = s.scalar(select(func.count()).select_from(Lead).where(Lead.created_at >= week_ago)) or 0
            hot_leads = s.scalar(select(func.count()).select_from(Lead).where(Lead.status == "hot")) or 0
            qualified_leads = s.scalar(
                select(func.count()).select_from(Lead).where(Lead.status.in_(["hot", "qualified"]))
            ) or 0

            pest_counts: dict[str, int] = {}
            city_counts: dict[str, int] = {}
            total_revenue = 0.0
            for j in completed:
                total_revenue += j.price or 0
                pest_counts[j.pest_type] = pest_counts.get(j.pest_type, 0) + 1
                city_counts[j.city] = city_counts.get(j.city, 0) + 1

            techs = s.scalars(select(Technician)).all()
            tech_jobs = {}
            for j in completed:
                if j.technician_id:
                    tech = next((t for t in techs if t.id == j.technician_id), None)
                    if tech:
                        tech_jobs[tech.name] = tech_jobs.get(tech.name, 0) + 1

            metrics = {
                "jobs_completed": len(completed),
                "jobs_cancelled": s.scalar(
                    select(func.count()).select_from(Job).where(Job.status == "cancelled", Job.created_at >= week_ago)
                ) or 0,
                "total_revenue": total_revenue,
                "new_leads": new_leads,
                "hot_leads": hot_leads,
                "qualified_leads": qualified_leads,
                "top_pest_types": sorted(
                    [{"pest": k, "count": v} for k, v in pest_counts.items()],
                    key=lambda x: x["count"], reverse=True
                )[:5],
                "top_cities": sorted(
                    [{"city": k, "count": v} for k, v in city_counts.items()],
                    key=lambda x: x["count"], reverse=True
                )[:5],
                "technician_utilization": [{"name": k, "jobs": v} for k, v in tech_jobs.items()],
            }
            content = generate_weekly_report(metrics)

        elif report_type == "upsell":
            customers = [
                {
                    "id": c.id, "name": c.name, "email": c.email,
                    "contract_type": c.contract_type, "contract_end": c.contract_end,
                }
                for c in s.scalars(select(Customer)).all()
            ]
            all_jobs = [
                {
                    "id": j.id, "customer_id": j.customer_id,
                    "status": j.status, "completed_at": j.completed_at,
                }
                for j in s.scalars(select(Job)).all()
            ]
            opportunities = detect_upsell_opportunities(customers, all_jobs)
            content = generate_upsell_report(opportunities)

        else:
            content = {"report_type": "custom", "narrative": "Custom reports coming soon.", "generated_at": now.isoformat()}

        report = Report(
            report_type=report_type,
            title=content.get("title", f"{report_type.capitalize()} Report"),
            content=content,
            generated_by_user_id=user_id,
        )
        s.add(report)
        s.flush()
        return ser_report(report)


def list_reports() -> dict:
    with session_scope() as s:
        reports = s.scalars(select(Report).order_by(Report.generated_at.desc()).limit(20)).all()
        return {"items": [ser_report(r) for r in reports]}


# ── Dashboard ─────────────────────────────────────────────────────────────────

def get_dashboard() -> dict:
    with session_scope() as s:
        now = utc_now()
        leads = s.scalars(select(Lead)).all()
        hot = [l for l in leads if l.status == "hot"]
        qualified = [l for l in leads if l.status in {"hot", "qualified"}]
        forecast = sum(l.annual_value for l in qualified)

        jobs = s.scalars(select(Job)).all()
        today_jobs = [j for j in jobs if j.scheduled_at and _as_utc(j.scheduled_at).date() == now.date()]
        completed_jobs = [j for j in jobs if j.status == "completed"]
        total_revenue = sum(j.price for j in completed_jobs)

        activities = s.scalars(
            select(ActivityItem).order_by(ActivityItem.timestamp.desc()).limit(10)
        ).all()

        top_leads = sorted(leads, key=lambda l: (l.qualification or {}).get("score", 0), reverse=True)[:5]
        upcoming_jobs = sorted(
            [j for j in jobs if j.status == "scheduled" and j.scheduled_at and _as_utc(j.scheduled_at) >= now],
            key=lambda j: _as_utc(j.scheduled_at)
        )[:5]

        return {
            "metrics": [
                {"label": "Total Leads", "value": len(leads), "hint": "All inbound inquiries"},
                {"label": "Hot Leads", "value": len(hot), "hint": "Score ≥ 70 — call immediately"},
                {"label": "Jobs Today", "value": len(today_jobs), "hint": "Scheduled for today"},
                {"label": "Forecasted Revenue", "value": f"€{forecast:,}", "hint": "Qualified pipeline ACV"},
                {"label": "Total Revenue", "value": f"€{total_revenue:,.0f}", "hint": "Completed jobs"},
            ],
            "recent_activity": [ser_activity(a) for a in activities],
            "top_leads": [ser_lead(l) for l in top_leads],
            "upcoming_jobs": [ser_job(j) for j in upcoming_jobs],
            "system_summary": {
                "qualified_count": len(qualified),
                "hot_count": len(hot),
                "avg_score": round(
                    sum((l.qualification or {}).get("score", 0) for l in leads if l.qualification)
                    / max(1, sum(1 for l in leads if l.qualification)), 1
                ),
                "jobs_completed": len(completed_jobs),
                "provider": settings.llm_provider,
            },
        }


# ── Admin / user management ───────────────────────────────────────────────────

def create_technician_account(data: dict) -> dict:
    import random
    otp = "".join([str(random.randint(0, 9)) for _ in range(8)])

    with session_scope() as s:
        if s.scalar(select(User).where(User.email == data["email"])):
            raise ValueError("A user with this email already exists")
        if s.scalar(select(Technician).where(Technician.email == data["email"])):
            raise ValueError("A technician with this email already exists")

        tech = Technician(
            name=data["full_name"],
            email=data["email"],
            phone=data.get("phone", ""),
            service_areas=data.get("service_areas", []),
            specialties=data.get("specialties", []),
        )
        s.add(tech)
        s.flush()

        user = User(
            email=data["email"],
            full_name=data["full_name"],
            phone=data.get("phone", ""),
            password_hash=hash_password(otp),
            role="technician",
            must_change_password=True,
            technician_id=tech.id,
        )
        s.add(user)
        s.add(ActivityItem(category="system", message=f"Technician account created: {data['full_name']} ({data['email']})"))
        s.flush()
        return {**ser_user(user), "technician_id": tech.id, "generated_password": otp}


def change_password(user_id: int, current_password: str, new_password: str) -> dict:
    if len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters")
    with session_scope() as s:
        user = s.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        if not verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        s.flush()
        return ser_user(user)


def update_profile(user_id: int, data: dict) -> dict:
    with session_scope() as s:
        user = s.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        if data.get("full_name"):
            user.full_name = data["full_name"]
        if "phone" in data:
            user.phone = data["phone"] or ""
        s.flush()
        return ser_user(user)


# ── Delete / status management ────────────────────────────────────────────────

def delete_lead(lead_id: str, reason: str, actor_role: str, actor_name: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise ValueError("A reason of at least 5 characters is required")
    with session_scope() as s:
        lead = s.get(Lead, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        lead_name = lead.name
        s.execute(update(Job).where(Job.lead_id == lead_id).values(lead_id=None))
        s.execute(update(ActivityItem).where(ActivityItem.lead_id == lead_id).values(lead_id=None))
        s.add(ActivityItem(
            category="system",
            message=f"Lead '{lead_name}' deleted by {actor_role} '{actor_name}'. Reason: {reason.strip()}",
        ))
        s.delete(lead)
        s.flush()
        return {"deleted": True, "id": lead_id}


def set_technician_status(tech_id: int, is_available: bool) -> dict:
    with session_scope() as s:
        tech = s.get(Technician, tech_id)
        if not tech:
            raise HTTPException(status_code=404, detail="Technician not found")
        tech.is_available = is_available
        # Also reflect status on linked user account sessions if deactivating
        if not is_available:
            user = s.scalar(select(User).where(User.technician_id == tech_id))
            if user:
                s.execute(delete(UserSession).where(UserSession.user_id == user.id))
        s.flush()
        return ser_technician(tech)


def delete_technician(tech_id: int) -> dict:
    with session_scope() as s:
        tech = s.get(Technician, tech_id)
        if not tech:
            raise HTTPException(status_code=404, detail="Technician not found")
        tech_name, tech_email = tech.name, tech.email
        s.execute(update(Job).where(Job.technician_id == tech_id).values(technician_id=None))
        user = s.scalar(select(User).where(User.technician_id == tech_id))
        if user:
            s.execute(delete(UserSession).where(UserSession.user_id == user.id))
            s.delete(user)
        s.add(ActivityItem(
            category="system",
            message=f"Technician '{tech_name}' ({tech_email}) and their account were permanently deleted.",
        ))
        s.delete(tech)
        s.flush()
        return {"deleted": True, "id": tech_id}


# ── Account self-deletion ─────────────────────────────────────────────────────

def _active_jobs_for_email(email: str, s) -> list:
    leads = s.scalars(select(Lead).where(Lead.email == email)).all()
    if not leads:
        return []
    lead_ids = [l.id for l in leads]
    return s.scalars(
        select(Job).where(
            Job.lead_id.in_(lead_ids),
            Job.status.in_(["scheduled", "in-progress"]),
        )
    ).all()


def request_account_deletion(user_id: int) -> dict:
    with session_scope() as s:
        user = s.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.role == "technician":
            # Check no active jobs before flagging
            active = s.scalars(
                select(Job).where(
                    Job.technician_id == user.technician_id,
                    Job.status.in_(["scheduled", "in-progress"]),
                )
            ).all() if user.technician_id else []
            if active:
                raise ValueError(
                    f"You still have {len(active)} scheduled or in-progress job(s). "
                    "Please complete or reassign them before requesting deletion."
                )
            user.delete_requested = True
            s.add(ActivityItem(
                category="system",
                message=f"Technician '{user.full_name}' ({user.email}) has requested account deletion — awaiting admin approval.",
            ))
            s.flush()
            return {"status": "pending", "message": "Your deletion request has been sent to the admin for approval."}

        else:  # role == "user"
            active = _active_jobs_for_email(user.email, s)
            if active:
                raise ValueError(
                    f"You have {len(active)} scheduled or active appointment(s). "
                    "All appointments must be completed or cancelled before you can delete your account."
                )
            s.execute(delete(UserSession).where(UserSession.user_id == user_id))
            s.add(ActivityItem(category="system", message=f"User account self-deleted: {user.email}"))
            s.delete(user)
            s.flush()
            return {"status": "deleted"}


def list_delete_requests() -> dict:
    with session_scope() as s:
        users = s.scalars(select(User).where(User.delete_requested == True)).all()
        result = []
        for u in users:
            entry = ser_user(u)
            if u.technician_id:
                active = s.scalars(
                    select(Job).where(
                        Job.technician_id == u.technician_id,
                        Job.status.in_(["scheduled", "in-progress"]),
                    )
                ).all()
                entry["active_jobs"] = len(active)
            else:
                entry["active_jobs"] = 0
            result.append(entry)
        return {"items": result}


def approve_delete_request(user_id: int) -> dict:
    with session_scope() as s:
        user = s.get(User, user_id)
        if not user or not user.delete_requested:
            raise HTTPException(status_code=404, detail="No pending delete request for this user")
        if user.technician_id:
            active = s.scalars(
                select(Job).where(
                    Job.technician_id == user.technician_id,
                    Job.status.in_(["scheduled", "in-progress"]),
                )
            ).all()
            if active:
                raise ValueError(f"Cannot approve: technician still has {len(active)} active/scheduled job(s).")
            s.execute(update(Job).where(Job.technician_id == user.technician_id).values(technician_id=None))
            tech = s.get(Technician, user.technician_id)
            if tech:
                s.delete(tech)
        s.execute(delete(UserSession).where(UserSession.user_id == user_id))
        s.add(ActivityItem(category="system", message=f"Admin approved account deletion for '{user.full_name}' ({user.email})."))
        s.delete(user)
        s.flush()
        return {"deleted": True, "id": user_id}


def reject_delete_request(user_id: int) -> dict:
    with session_scope() as s:
        user = s.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.delete_requested = False
        s.add(ActivityItem(category="system", message=f"Admin rejected deletion request for '{user.full_name}' ({user.email})."))
        s.flush()
        return ser_user(user)


# ── DB bootstrap ──────────────────────────────────────────────────────────────

def seed_initial_data() -> None:
    with session_scope() as s:
        # Demo user — always admin
        demo = s.scalar(select(User).where(User.email == settings.demo_user_email))
        if not demo:
            s.add(User(
                email=settings.demo_user_email,
                full_name=settings.demo_user_name,
                password_hash=hash_password(settings.demo_user_password),
                role="admin",
            ))
        elif demo.role != "admin":
            demo.role = "admin"

        # Technicians
        tech_count = s.scalar(select(func.count()).select_from(Technician)) or 0
        if not tech_count:
            for td in get_seed_technicians():
                s.add(Technician(**td))
            s.flush()

        # Leads
        lead_count = s.scalar(select(func.count()).select_from(Lead)) or 0
        if not lead_count:
            for ld in get_seed_leads():
                s.add(Lead(**ld))
            s.add(ActivityItem(category="system", message="Demo leads imported from seed data."))
            s.flush()

            # Jobs (need lead IDs and tech IDs)
            lead_ids = [l.id for l in s.scalars(select(Lead)).all()]
            tech_ids = [t.id for t in s.scalars(select(Technician)).all()]
            for jd in get_seed_jobs(lead_ids, tech_ids):
                s.add(Job(**jd))
