from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ── Auth ──────────────────────────────────────────────────────────────────────

class AuthRegisterRequest(BaseModel):
    email: str
    full_name: str
    password: str


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class UserSchema(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    phone: str
    must_change_password: bool
    delete_requested: bool = False
    created_at: str


class CreateTechnicianRequest(BaseModel):
    full_name: str
    email: str
    phone: str = ""
    service_areas: list[str] = []
    specialties: list[str] = []


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None


class DeleteLeadRequest(BaseModel):
    reason: str


class TechnicianStatusRequest(BaseModel):
    is_available: bool


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserSchema


# ── Leads ─────────────────────────────────────────────────────────────────────

class LeadCreateRequest(BaseModel):
    name: str
    email: str
    phone: str = ""
    address: str = ""
    city: str
    property_type: str
    pest_type: str
    pest_description: str = ""
    urgency: str = "medium"
    source: str = "website"
    is_repeat_customer: bool = False


class LeadSchema(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    address: str
    city: str
    property_type: str
    pest_type: str
    pest_description: str
    urgency: str
    source: str
    status: str
    qualification: dict
    outreach: dict
    is_repeat_customer: bool
    annual_value: int
    created_at: str
    updated_at: str


class LeadsResponse(BaseModel):
    items: list[LeadSchema]
    count: int


class LeadResponse(BaseModel):
    lead: LeadSchema


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    lead_id: str | None = None
    customer_id: str | None = None
    technician_id: int | None = None
    service_type: str
    pest_type: str
    address: str
    city: str
    scheduled_at: str | None = None
    price: float = 0.0
    notes: str = ""


class JobUpdateRequest(BaseModel):
    status: str | None = None
    technician_id: int | None = None
    scheduled_at: str | None = None
    completed_at: str | None = None
    price: float | None = None
    notes: str | None = None
    reminder_sent: bool | None = None
    follow_up_sent: bool | None = None


class JobSchema(BaseModel):
    id: str
    lead_id: str | None
    customer_id: str | None
    technician_id: int | None
    technician_name: str | None
    service_type: str
    pest_type: str
    address: str
    city: str
    status: str
    scheduled_at: str | None
    completed_at: str | None
    price: float
    notes: str
    reminder_sent: bool
    follow_up_sent: bool
    review_requested: bool
    created_at: str


class JobsResponse(BaseModel):
    items: list[JobSchema]
    count: int


class JobResponse(BaseModel):
    job: JobSchema


# ── Technicians ───────────────────────────────────────────────────────────────

class TechnicianSchema(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    service_areas: list[str]
    specialties: list[str]
    is_available: bool


class TechniciansResponse(BaseModel):
    items: list[TechnicianSchema]


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    visitor_name: str = "Visitor"
    visitor_email: str = ""


class MessageSchema(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class ConversationSchema(BaseModel):
    id: str
    visitor_name: str
    visitor_email: str
    status: str
    messages: list[MessageSchema]
    created_at: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    booked_leads: list[dict] = []


# ── Reports ───────────────────────────────────────────────────────────────────

class ReportGenerateRequest(BaseModel):
    report_type: str = "weekly"
    question: str = ""


class ReportSchema(BaseModel):
    id: int
    report_type: str
    title: str
    content: dict
    generated_at: str


class ReportsResponse(BaseModel):
    items: list[ReportSchema]


# ── Dashboard ─────────────────────────────────────────────────────────────────

class MetricCard(BaseModel):
    label: str
    value: Any
    hint: str = ""
    trend: str = ""


class DashboardResponse(BaseModel):
    metrics: list[MetricCard]
    recent_activity: list[dict]
    top_leads: list[LeadSchema]
    upcoming_jobs: list[JobSchema]
    system_summary: dict


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    provider: str = ""
