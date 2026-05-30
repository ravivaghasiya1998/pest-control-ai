from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    __abstract__ = True

    @classmethod
    def get(cls, db: Session, ident):
        return db.get(cls, ident=ident)

    @classmethod
    def get_or_404(cls, db: Session, ident, detail: str | None = None):
        from fastapi import HTTPException
        obj = db.get(cls, ident=ident)
        if obj is None:
            raise HTTPException(status_code=404, detail=detail or f"{cls.__name__} not found")
        return obj

    @classmethod
    def select(cls):
        return select(cls)

    @classmethod
    def count(cls):
        return select(func.count()).select_from(cls)

    @classmethod
    def insert(cls, returning_full_model: bool = True):
        query = insert(cls)
        if returning_full_model:
            query = query.returning(cls)
        return query

    @classmethod
    def update(cls):
        return update(cls)

    @classmethod
    def delete(cls):
        return delete(cls)

    @classmethod
    def upsert(cls, query):
        """INSERT … ON CONFLICT DO UPDATE (upsert) using primary key as conflict target."""
        index_elements = inspect(cls).primary_key
        set_columns = {
            col.name: col
            for col in query.excluded
            if not col.primary_key and col.name not in [c.name for c in index_elements]
        }
        return query.on_conflict_do_update(index_elements=index_elements, set_=set_columns)


# ── Auth ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")          # admin / technician / user
    phone: Mapped[str] = mapped_column(String(50), default="")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    delete_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    technician_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("technicians.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="sessions")


# ── Core business entities ────────────────────────────────────────────────────

class Lead(Base):
    """Inbound inquiry — pre-sale prospect."""
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str] = mapped_column(String(50), default="")
    address: Mapped[str] = mapped_column(String(512), default="")
    city: Mapped[str] = mapped_column(String(120), index=True)

    property_type: Mapped[str] = mapped_column(String(60))   # residential / commercial / multi-family
    pest_type: Mapped[str] = mapped_column(String(120))      # termites / roaches / bedbugs / rodents / ants / wasps
    pest_description: Mapped[str] = mapped_column(Text, default="")
    urgency: Mapped[str] = mapped_column(String(30), default="medium")  # low / medium / high / emergency
    source: Mapped[str] = mapped_column(String(60), default="website")  # website / phone / chat / referral

    status: Mapped[str] = mapped_column(String(40), default="new", index=True)
    # new / qualified / hot / nurture / converted / lost

    qualification: Mapped[dict] = mapped_column(JSON, default=dict)
    outreach: Mapped[dict] = mapped_column(JSON, default=dict)

    is_repeat_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    annual_value: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    jobs: Mapped[list["Job"]] = relationship(back_populates="lead")
    activities: Mapped[list["ActivityItem"]] = relationship(back_populates="lead")


class Customer(Base):
    """Existing paying customer (created when a lead converts)."""
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(50), default="")
    address: Mapped[str] = mapped_column(String(512), default="")
    city: Mapped[str] = mapped_column(String(120))
    property_type: Mapped[str] = mapped_column(String(60))

    contract_type: Mapped[str] = mapped_column(String(40), default="one-off")
    # one-off / monthly / quarterly / annual
    contract_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contract_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lifetime_value: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    jobs: Mapped[list["Job"]] = relationship(back_populates="customer")


class Technician(Base):
    __tablename__ = "technicians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(50))
    service_areas: Mapped[list[str]] = mapped_column(JSON, default=list)
    specialties: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    jobs: Mapped[list["Job"]] = relationship(back_populates="technician")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), nullable=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    technician_id: Mapped[int | None] = mapped_column(ForeignKey("technicians.id"), nullable=True)

    service_type: Mapped[str] = mapped_column(String(120))
    pest_type: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(512))
    city: Mapped[str] = mapped_column(String(120))

    status: Mapped[str] = mapped_column(String(40), default="scheduled", index=True)
    # scheduled / in-progress / completed / cancelled

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    price: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")

    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_up_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    review_requested: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    lead: Mapped["Lead | None"] = relationship(back_populates="jobs")
    customer: Mapped["Customer | None"] = relationship(back_populates="jobs")
    technician: Mapped["Technician | None"] = relationship(back_populates="jobs")


# ── Chat (Customer Service Agent) ────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    visitor_name: Mapped[str] = mapped_column(String(255), default="Visitor")
    visitor_email: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active / closed / converted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# ── Reports ──────────────────────────────────────────────────────────────────

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(40))  # weekly / upsell / custom
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    generated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


# ── Activity log ─────────────────────────────────────────────────────────────

class ActivityItem(Base):
    __tablename__ = "activity_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    category: Mapped[str] = mapped_column(String(60))
    # system / qualification / outreach / scheduling / comms / chat / report
    message: Mapped[str] = mapped_column(Text)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    lead: Mapped["Lead | None"] = relationship(back_populates="activities")
