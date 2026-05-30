# PestGuard Pro — AI Automation Suite

An end-to-end business automation platform for pest control companies. AI agents handle customer chat, lead qualification, job scheduling, and reporting — with full role-based access for admins and field technicians.

> **Setup guide →** [docs/how_to_setup.md](docs/how_to_setup.md)

---

## What it does

### AI Chat Agent
Customers chat on your website. The agent answers FAQs, provides pricing, checks availability, and books appointments — creating a Lead and Job automatically, no human needed.

### Lead Qualification
Every inbound lead is scored 0–100 across pest urgency, property type, location, and engagement. Leads are bucketed into **Hot** (call now), **Qualified** (schedule visit), or **Nurture** (email sequence).

### Job Operations
Jobs move through a pipeline: Scheduled → In-Progress → Completed. Admins can auto-assign the best technician by city and specialty, send appointment reminders, and trigger post-job follow-ups with one click.

### AI Reports
Generate weekly performance reports and upsell opportunity reports — written by the AI, based on real data from your database.

### Role-Based Access
| Role | Access |
|---|---|
| **Admin** | Full access — dashboard, leads, jobs, reports, admin panel |
| **Technician** | Their assigned jobs only — login via one-time password set by admin |
| **User** | Chat widget only |

---

## Key Features

- Multi-turn AI chat with tool use (pricing, availability, booking)
- Lead scoring with qualification reasons and next-step recommendations
- Job board with status pipeline and technician assignment
- Admin panel — create technician accounts with OTP, manage active/inactive status
- Duplicate lead detection by email and phone
- Address + postal code validation against served cities
- Chat history persisted per user in PostgreSQL
- Forced password change on first technician login
- Account deletion flow with admin approval for technicians
- Supports **Anthropic Claude**, **Azure OpenAI**, **OpenAI**, and a built-in mock for zero-cost testing

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy 2 |
| Database | PostgreSQL (Docker) |
| AI | Anthropic Claude API · OpenAI · Azure OpenAI |
| Frontend | React 18 · Vite |
| Auth | JWT bearer tokens · bcrypt · RBAC |
| Comms | Twilio (SMS) · SendGrid (email) — mocked without credentials |
| Container | Docker · Docker Compose |

---

## Demo login

| Field | Value |
|---|---|
| URL | `http://localhost` (Docker) or `http://localhost:5173` (local dev) |
| Email | `admin@pestguard.com` |
| Password | `demo1234` |

---

## Project structure

```
pest-control-ai/
├── backend/
│   ├── services/agents/      # AI agents (chat, qualification, operations, reporting)
│   ├── services/llm.py       # Unified LLM client (Anthropic + OpenAI + Azure + Mock)
│   ├── models/model.py       # Database models
│   ├── routes/route.py       # API endpoints
│   └── data/seed.py          # Demo data
├── frontend/src/
│   └── components/           # Dashboard, Leads, Jobs, Chat, Reports, Admin, Profile
├── docs/
│   └── how_to_setup.md       # Setup guide
├── docker-compose.yml
└── .env.example
```
