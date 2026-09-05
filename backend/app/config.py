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

    # LLM provider — pluggable behind the single traced choke-point (llm/client.call).
    #   auto (default) -> anthropic if its key is set, else gemini, else mock
    #   anthropic | gemini | mock -> force that provider
    llm_provider: str = "auto"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Per-provider model routing (classify = cheap/high-volume, judge = strong/low-volume).
    model_classify: str = "claude-haiku-4-5-20251001"
    model_judge: str = "claude-sonnet-5"
    gemini_model_classify: str = "gemini-3.6-flash"    # current flash model (free-tier)
    gemini_model_judge: str = "gemini-3.6-flash"       # verify latest id in Google AI Studio

    # Where the app reads prospect data from:
    #   local     -> data/marts/*.json snapshot (default; deploys anywhere, no creds/cost)
    #   snowflake -> live queries against the marts (needs creds + a running warehouse;
    #                snowflake-connector runs on 3.14, so the app venv works)
    data_backend: str = "local"

    @property
    def provider(self) -> str:
        """Resolve the active LLM provider (honours an explicit choice, else auto-detects)."""
        p = (self.llm_provider or "auto").lower()
        if p != "auto":
            return p
        if self.anthropic_api_key:
            return "anthropic"
        if self.gemini_api_key:
            return "gemini"
        return "mock"

    @property
    def llm_live(self) -> bool:
        return self.provider in ("anthropic", "gemini")

    def model_for(self, role: str) -> str:
        """Model id for a role ('classify' | 'judge') under the active provider."""
        if self.provider == "gemini":
            return self.gemini_model_classify if role == "classify" else self.gemini_model_judge
        return self.model_classify if role == "classify" else self.model_judge


@lru_cache
def get_settings() -> Settings:
    return Settings()
