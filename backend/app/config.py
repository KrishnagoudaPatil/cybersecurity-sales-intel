"""Central configuration. Reads from environment / .env; never hard-codes secrets."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
MARTS_DIR = DATA_DIR / "marts"      # published mart snapshot for the local backend
TRACES_DIR = REPO_ROOT / "traces"
PROMPTS_DIR = REPO_ROOT / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str = ""
    model_classify: str = "claude-haiku-4-5-20251001"  # cheap, high-volume classification
    model_judge: str = "claude-sonnet-5"               # strong, low-volume judgement

    # Where the app reads prospect data from:
    #   local     -> data/marts/*.json snapshot (default; deploys anywhere, no creds/cost)
    #   snowflake -> live queries against the marts (needs creds + a running warehouse,
    #                and the 3.12 venv with snowflake-connector)
    data_backend: str = "local"

    @property
    def llm_live(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
