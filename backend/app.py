from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import get_engine, get_sessionmaker, setup_db
from models.model import Base
from routes.route import router
from services.service import seed_initial_data


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator:
    # 1. Run any PostgreSQL extension setup (uuid-ossp, pgcrypto, etc.)
    with get_sessionmaker()() as session:
        setup_db(session)

    # 2. Create all tables if they don't exist yet
    Base.metadata.create_all(get_engine())

    # 3. Seed demo data (no-ops if data already present)
    seed_initial_data()

    yield


app = FastAPI(
    title="PestGuard Pro — AI Automation Suite",
    description="AI agents for pest control: customer service, lead qualification, operations, and reporting.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
