from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from schemas.schema import (
    AuthLoginRequest, AuthRegisterRequest, AuthResponse, ChangePasswordRequest,
    ChatMessageRequest, ChatResponse, CreateTechnicianRequest, DashboardResponse,
    DeleteLeadRequest, HealthResponse, JobCreateRequest, JobResponse, JobsResponse,
    JobUpdateRequest, LeadCreateRequest, LeadResponse, LeadsResponse,
    ReportGenerateRequest, ReportsResponse, TechnicianStatusRequest,
    TechniciansResponse, UpdateProfileRequest, UserSchema,
)
from services.service import (
    approve_delete_request, auto_assign_jobs, change_password, chat_message,
    create_job, create_lead, create_technician_account, delete_lead,
    delete_technician, generate_report, get_conversation, get_current_user,
    get_dashboard, get_lead, list_delete_requests, list_jobs, list_leads,
    list_reports, list_technicians, login_user, qualify_all_leads,
    qualify_lead_service, register_user, reject_delete_request,
    request_account_deletion, send_followups, send_reminders,
    set_technician_status, update_job, update_profile,
)

router = APIRouter(prefix="/api", tags=["pest-control-ai"])
bearer = HTTPBearer(auto_error=False)


def auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return get_current_user(credentials.credentials)


def require_admin(user=Depends(auth)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "provider": settings.llm_provider}


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=UserSchema)
def register(payload: AuthRegisterRequest):
    try:
        return register_user(payload.email, payload.full_name, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: AuthLoginRequest):
    try:
        return login_user(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.get("/auth/me", response_model=UserSchema)
def me(user=Depends(auth)):
    from services.service import ser_user
    return ser_user(user)


@router.post("/auth/change-password", response_model=UserSchema)
def change_password_route(payload: ChangePasswordRequest, user=Depends(auth)):
    try:
        return change_password(user.id, payload.current_password, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/auth/profile", response_model=UserSchema)
def update_profile_route(payload: UpdateProfileRequest, user=Depends(auth)):
    return update_profile(user.id, payload.model_dump(exclude_none=True))


@router.delete("/auth/account")
def delete_account_route(user=Depends(auth)):
    try:
        return request_account_deletion(user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.post("/admin/create-technician", response_model=dict)
def create_technician_route(payload: CreateTechnicianRequest, _=Depends(require_admin)):
    try:
        return create_technician_account(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/admin/delete-requests")
def list_delete_requests_route(_=Depends(require_admin)):
    return list_delete_requests()


@router.post("/admin/delete-requests/{user_id}/approve")
def approve_delete_route(user_id: int, _=Depends(require_admin)):
    try:
        return approve_delete_request(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/admin/delete-requests/{user_id}/reject")
def reject_delete_route(user_id: int, _=Depends(require_admin)):
    return reject_delete_request(user_id)


@router.patch("/admin/technicians/{tech_id}/status")
def tech_status_route(tech_id: int, payload: TechnicianStatusRequest, _=Depends(require_admin)):
    return set_technician_status(tech_id, payload.is_available)


@router.delete("/admin/technicians/{tech_id}")
def delete_tech_route(tech_id: int, _=Depends(require_admin)):
    return delete_technician(tech_id)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard(_=Depends(auth)):
    return get_dashboard()


# ── Leads ─────────────────────────────────────────────────────────────────────

@router.get("/leads", response_model=LeadsResponse)
def leads(status: str | None = None, city: str | None = None, _=Depends(auth)):
    return list_leads(status=status, city=city)


@router.post("/leads", response_model=dict)
def create_lead_route(payload: LeadCreateRequest, _=Depends(auth)):
    return create_lead(payload.model_dump())


@router.get("/leads/{lead_id}", response_model=LeadResponse)
def get_lead_route(lead_id: str, _=Depends(auth)):
    return {"lead": get_lead(lead_id)}


@router.post("/leads/{lead_id}/qualify", response_model=LeadResponse)
def qualify_lead_route(lead_id: str, _=Depends(auth)):
    return qualify_lead_service(lead_id)


@router.post("/leads/qualify-all")
def qualify_all_route(_=Depends(auth)):
    return qualify_all_leads()


@router.delete("/leads/{lead_id}")
def delete_lead_route(lead_id: str, payload: DeleteLeadRequest, user=Depends(auth)):
    if user.role not in ("admin", "technician"):
        raise HTTPException(status_code=403, detail="Not allowed")
    try:
        return delete_lead(lead_id, payload.reason, user.role, user.full_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Jobs ──────────────────────────────────────────────────────────────────────

@router.get("/jobs", response_model=JobsResponse)
def jobs(status: str | None = None, city: str | None = None, user=Depends(auth)):
    tech_id = user.technician_id if user.role == "technician" else None
    return list_jobs(status=status, city=city, technician_id=tech_id)


@router.post("/jobs", response_model=JobResponse)
def create_job_route(payload: JobCreateRequest, _=Depends(auth)):
    return create_job(payload.model_dump())


@router.patch("/jobs/{job_id}", response_model=JobResponse)
def update_job_route(job_id: str, payload: JobUpdateRequest, _=Depends(auth)):
    return update_job(job_id, payload.model_dump(exclude_none=True))


# ── Operations ────────────────────────────────────────────────────────────────

@router.post("/operations/assign")
def assign_route(_=Depends(auth)):
    return auto_assign_jobs()


@router.post("/operations/reminders")
def reminders_route(_=Depends(auth)):
    return send_reminders()


@router.post("/operations/followups")
def followups_route(_=Depends(auth)):
    return send_followups()


# ── Technicians ───────────────────────────────────────────────────────────────

@router.get("/technicians", response_model=TechniciansResponse)
def technicians(_=Depends(auth)):
    return list_technicians()


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.post("/chat/message", response_model=ChatResponse)
def chat(payload: ChatMessageRequest):
    return chat_message(
        session_id=payload.session_id,
        user_message=payload.message,
        visitor_name=payload.visitor_name,
        visitor_email=payload.visitor_email,
    )


@router.get("/chat/{session_id}")
def get_chat(session_id: str):
    return get_conversation(session_id)


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get("/reports", response_model=ReportsResponse)
def reports(_=Depends(auth)):
    return list_reports()


@router.post("/reports/generate")
def generate_report_route(payload: ReportGenerateRequest, user=Depends(auth)):
    return generate_report(
        report_type=payload.report_type,
        user_id=user.id,
        question=payload.question,
    )
