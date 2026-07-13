"""Application configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EGSD_", env_file=".env", extra="ignore")

    # Default to a local SQLite file so the walking skeleton runs with no external services.
    # Production uses PostgreSQL, e.g. postgresql+psycopg://egsd:egsd@db:5432/egsd
    database_url: str = "sqlite:///./egsd.db"

    # In dev mode the schema is created on startup; in production use `alembic upgrade head`.
    auto_create_schema: bool = True

    app_title: str = "e-GSD — validated core"


settings = Settings()
