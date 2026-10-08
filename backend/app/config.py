"""Application configuration via pydantic-settings."""

import os
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Materials DMP"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret-key"

    # Database
    # SQLite remains the zero-config local default. DATABASE_URL takes
    # precedence when an external database is configured.
    USE_SQLITE: bool = True
    SQLITE_PATH: Path = Path(__file__).parent.parent / "materials_dmp.db"
    DATABASE_URL: str | None = None

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "materials"
    POSTGRES_PASSWORD: str = "materials_secret"
    POSTGRES_DB: str = "materials_dmp"

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgres://"):
                return self.DATABASE_URL.replace(
                    "postgres://", "postgresql+psycopg://", 1
                )
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace(
                    "postgresql://", "postgresql+psycopg://", 1
                )
            return self.DATABASE_URL
        if os.getenv("VERCEL"):
            raise ValueError("DATABASE_URL is required when deploying to Vercel")
        if self.USE_SQLITE:
            return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"
        return (
            "postgresql+asyncpg://"
            f"{quote_plus(self.POSTGRES_USER)}:"
            f"{quote_plus(self.POSTGRES_PASSWORD)}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    # JWT Auth
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # AI Assistant
    # LLM_* is the provider-neutral production configuration. DEEPSEEK_*
    # remains as a backwards-compatible fallback for existing deployments.
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str | None = None
    LLM_MODEL: str | None = None
    LLM_PROXY: str | None = None
    LLM_TIMEOUT_SECONDS: float = Field(default=150.0, gt=0)
    LLM_MAX_TOKENS: int = Field(default=4096, ge=1)
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOOL_ROUNDS: int = Field(default=4, ge=1, le=10)
    LLM_THINKING_MODE: str | None = None
    LLM_EXTRA_BODY: dict[str, Any] = Field(default_factory=dict)

    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_PROXY: str | None = None
    ASSISTANT_ACTION_EXPIRE_MINUTES: int = 10
    ASSISTANT_BACKUP_RETENTION_HOURS: int = 24

    @property
    def assistant_api_key(self) -> str | None:
        return self.LLM_API_KEY or self.DEEPSEEK_API_KEY

    @property
    def assistant_base_url(self) -> str:
        return (self.LLM_BASE_URL or self.DEEPSEEK_BASE_URL).rstrip("/")

    @property
    def assistant_model(self) -> str:
        return self.LLM_MODEL or self.DEEPSEEK_MODEL

    @property
    def assistant_proxy(self) -> str | None:
        return self.LLM_PROXY or self.DEEPSEEK_PROXY

    @property
    def assistant_is_configured(self) -> bool:
        # Local OpenAI-compatible servers often do not require an API key.
        # A generic base URL therefore counts as an explicit configuration.
        return bool(
            self.LLM_BASE_URL
            or self.LLM_API_KEY
            or self.DEEPSEEK_API_KEY
        )

    # File Storage
    STORAGE_BACKEND: str = "local"
    STORAGE_ROOT: Path = Path(__file__).parent.parent / "storage"

    @property
    def storage_backend(self) -> str:
        if os.getenv("VERCEL") and self.STORAGE_BACKEND == "local":
            return "vercel_blob"
        return self.STORAGE_BACKEND

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
