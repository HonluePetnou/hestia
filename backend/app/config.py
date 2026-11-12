"""Application settings, read from environment variables and the repo-root `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://hestia:hestia@localhost:5434/hestia"

    llm_provider: Literal["mock", "openai", "gemini", "anthropic"] = "mock"
    llm_model: str | None = None
    embedding_model: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    embedding_dim: int = 1536

    web_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
