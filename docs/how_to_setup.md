# Setup Guide

Two ways to run the project: **Docker** (recommended, one command) or **local dev** (frontend + backend separately).

---

## Option 1 — Docker (recommended)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### Steps

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env — minimum required change:
#    Set POSTGRES_PASSWORD to anything (e.g. postgres)
#    Set LLM_PROVIDER=mock (no API key needed) or add a real key

# 3. Start everything
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

### Stop

```bash
docker compose down          # stop containers
docker compose down -v       # stop + delete database volume (full reset)
```

---

## Option 2 — Local Dev

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11+ |
| pip / venv | included with Python |
| Node.js | 18+ |
| PostgreSQL | 16+ (or use Docker just for the DB) |

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env file (from project root)
cp ../.env.example .env

# Edit .env — set POSTGRES_HOST=localhost and your DB credentials

# Run
uvicorn app:app --reload --port 8000
```

On first start the backend auto-creates all tables and seeds demo data.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

### Run PostgreSQL via Docker (if not installed locally)

```bash
docker run -d \
  --name pestguard-db \
  -e POSTGRES_DB=pestcontrol \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16-alpine
```

---

## Environment Variables

Copy `.env.example` to `.env` in the project root.

### Required

```env
LLM_PROVIDER=mock            # mock | anthropic | azure | openai

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=pestcontrol
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

AUTH_SECRET=change-me-to-a-long-random-string
```

### LLM Providers (pick one)

```env
# Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6

# Azure OpenAI
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://YOUR_RESOURCE.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-01

# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

> `LLM_PROVIDER=mock` works with no API key — the chat agent uses scripted responses and will simulate bookings when given an email, phone, and city.

### Communications (optional)

```env
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+15550000000

SENDGRID_API_KEY=SG....
FROM_EMAIL=noreply@yourdomain.com
```

Without these, SMS/email actions are logged to the console instead of sent.

### Demo account

```env
DEMO_USER_EMAIL=admin@pestguard.com
DEMO_USER_NAME=Admin
DEMO_USER_PASSWORD=demo1234
```

---

## Connect pgAdmin to Docker Postgres

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `pestcontrol` |
| Username | `postgres` |
| Password | value from `POSTGRES_PASSWORD` in `.env` |

---

## Re-seed demo data

```bash
# Truncate existing leads and jobs, then restart backend to re-seed
docker exec pestguard-db psql -U postgres -d pestcontrol -c "TRUNCATE leads, jobs CASCADE;"
docker compose restart backend
```

---

## First login

| Field | Value |
|---|---|
| Email | `admin@pestguard.com` |
| Password | `demo1234` |

The demo account always has the `admin` role. To test the technician flow, create a technician account from the **Admin** tab after logging in.
