from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── PostgreSQL connection vars ────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "pestcontrol"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── LLM provider: "anthropic" | "azure" | "openai" | "mock" ─────────────
    llm_provider: str = "mock"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-02-01"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # ── Auth ──────────────────────────────────────────────────────────────────
    auth_secret: str = "change-me-in-production-use-long-random-string"
    auth_token_ttl_hours: int = 24

    # ── CORS ──────────────────────────────────────────────────────────────────
    frontend_origin: str = "http://localhost:5173"

    # ── Demo credentials ──────────────────────────────────────────────────────
    demo_user_email: str = "admin@pestguard.com"
    demo_user_name: str = "Admin"
    demo_user_password: str = "demo1234"

    # ── Communications (mocked; swap for real keys when ready) ───────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = "+15550000000"
    sendgrid_api_key: str = ""
    from_email: str = "noreply@pestguard.com"

    # ── Database pool & behaviour ─────────────────────────────────────────────
    debug_sql_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_pool_use_lifo: bool = True
    postgres_extensions: list[str] = []   # e.g. ["uuid-ossp", "pgcrypto"]

    # ── Business settings ─────────────────────────────────────────────────────
    business_name: str = "PestGuard Pro"
    service_areas: list[str] = ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne", "Stuttgart"]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
