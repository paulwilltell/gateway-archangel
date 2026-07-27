from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Gateway"
    app_tagline: str = "Human voices. Scripture-measured analysis."
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    public_base_url: str = "http://127.0.0.1:8000"
    secret_key: str = "change-me-before-production"

    database_url: str = f"sqlite:///{BASE_DIR / 'gateway.db'}"
    seed_demo_data: bool = True

    # Canonical corpus and research connectors
    corpus_version: str = "kjv-1769-full-2026-07"
    corpus_seed_path: str = str(BASE_DIR / "app" / "data" / "kjv_full.json")
    source_registry_path: str = str(BASE_DIR / "app" / "data" / "source_registry.json")

    api_bible_api_key: str | None = None
    api_bible_base_url: str = "https://rest.api.bible/v1"
    api_bible_kjv_id: str = "de4e12af7f28f599-01"

    bible_brain_api_key: str | None = None
    bible_brain_base_url: str = "https://4.dbt.io/api"

    sefaria_base_url: str = "https://www.sefaria.org/api"

    # The default analyzer is deterministic and requires no external model.
    archangel_analyzer: Literal["heuristic", "anthropic", "openai", "local_openai_compatible"] = "heuristic"
    archangel_engine_version: str = "archangel-foundation-0.1.0"
    archangel_strict_corpus_only: bool = True
    archangel_model: str | None = None
    # Analysis prompts carry evidence, context windows, counterpassages, and
    # lexical data, so a thorough pass legitimately takes minutes. Analysis
    # runs in a background task, so a generous ceiling costs the reader
    # nothing; too tight a value silently degrades every post to the
    # deterministic analyzer.
    analysis_timeout_seconds: float = 240.0

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"

    local_llm_base_url: str = "http://127.0.0.1:11434/v1"
    local_llm_api_key: str = "local-development"
    local_llm_model: str | None = None

    # Safety boundaries. Numbers are configurable for non-US deployments.
    safety_country: str = "US"
    emergency_number: str = "911"
    crisis_number: str = "988"
    poison_control_number: str = "1-800-222-1222"

    max_post_chars: int = Field(default=8_000, ge=200, le=50_000)
    max_reply_chars: int = Field(default=4_000, ge=100, le=20_000)

    # Open-platform protections: per-client sliding-window rate limits and the
    # shared secret that guards moderation actions (content removal/restore).
    moderation_token: str | None = None
    rate_limit_window_seconds: int = Field(default=600, ge=10, le=86_400)
    rate_limit_posts_per_window: int = Field(default=5, ge=1, le=1_000)
    rate_limit_replies_per_window: int = Field(default=20, ge=1, le=5_000)
    rate_limit_reports_per_window: int = Field(default=10, ge=1, le=1_000)
    rate_limit_chat_per_window: int = Field(default=20, ge=1, le=5_000)

    # Community data is never automatically used to update model weights.
    training_data_mode: Literal["off", "consent_reviewed_only"] = "consent_reviewed_only"
    training_policy_version: str = "gateway-training-consent-v1"
    enable_private_content_training: bool = False
    training_retention_days: int = Field(default=30, ge=1, le=3650)

    pii_hash_salt: str = "replace-me"
    field_encryption_key: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
