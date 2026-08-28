"""Central configuration. Reads from environment / .env; never hard-codes secrets."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
TRACES_DIR = REPO_ROOT / "traces"
PROMPTS_DIR = REPO_ROOT / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str = ""
    # Model routing: cheap model for high-volume classification, strong model for judgement.
    model_classify: str = "claude-haiku-4-5-20251001"
    model_judge: str = "claude-sonnet-5"

    # If no API key is present the LLM layer runs in deterministic MOCK mode so the
    # whole pipeline (evals, traces, cost) still works end-to-end offline.
    @property
    def llm_live(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
