"""
Billhound application settings via pydantic-settings.
All configuration sourced from environment variables with .env fallback.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Application --
    app_name: str = "billhound"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # -- Database --
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL async connection string",
        examples=["postgresql+asyncpg://postgres:postgres@localhost:5432/billhound"],
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    # -- Encryption --
    encryption_key: SecretStr = Field(
        ...,
        description="32-byte hex-encoded AES-256 key",
    )

    # -- Telegram --
    telegram_bot_token: SecretStr = Field(default=SecretStr(""))

    # -- OAuth --
    gmail_client_id: str = ""
    gmail_client_secret: SecretStr = Field(default=SecretStr(""))
    outlook_client_id: str = ""
    outlook_client_secret: SecretStr = Field(default=SecretStr(""))
    oauth_redirect_base_url: str = "http://localhost:8080"

    # -- LLM --
    llm_provider: Literal["openai", "anthropic", "gemini"] = "openai"
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_model: str = "gpt-4o-mini"

    # -- Subscription Detection --
    confidence_threshold: float = 0.70
    renewal_alert_days: list[int] = Field(default=[7, 3, 1])

    # -- Scheduler --
    scan_interval_minutes: int = 60

    # -- Playwright / Automation --
    playwright_headless: bool = True
    playwright_timeout_ms: int = 30_000
    screenshot_dir: str = "data/screenshots"

    # -- ACP (Virtuals Agent Commerce Protocol) --
    acp_enabled: bool = False
    acp_wallet_private_key: SecretStr = Field(default=SecretStr(""))
    acp_agent_wallet_address: str = ""
    acp_entity_id: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_database_url(cls, values: dict) -> dict:
        """Auto-convert Railway's postgresql:// to postgresql+asyncpg://.

        Railway (and most PaaS) provide DATABASE_URL as a standard
        ``postgresql://`` URI. SQLAlchemy async requires the asyncpg
        driver prefix. This validator transparently rewrites the scheme
        so users never have to edit the URL manually.
        """
        url = values.get("database_url") or values.get("DATABASE_URL")
        if isinstance(url, str):
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            values["database_url"] = url
        return values


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
