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
    # Embeddings default to the LLM provider; set EMBEDDING_PROVIDER to mix, e.g. Gemini
    # embeddings with an Anthropic or OpenAI chat model (Anthropic has no embeddings API).
    embedding_provider: Literal["mock", "openai", "gemini"] | None = None
    llm_model: str | None = None
    embedding_model: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    # Extra Gemini keys, comma-separated, each from a different Google Cloud project (quotas are
    # per project). Embeddings switch to the next key when one hits its quota.
    gemini_api_keys: str | None = None
    anthropic_api_key: str | None = None
    embedding_dim: int = 1536

    # RAG: passages sent to the LLM, and minimum cosine similarity to count as relevant
    retrieval_k: int = 8
    retrieval_min_score: float = 0.62  # calibrated 2026-11-15, see .env.example
    # at most this many passages from one document, so a 89-chunk guide cannot crowd out the rest
    retrieval_max_per_doc: int = 3

    web_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
