"""Pydantic data models — the contract shared by data, scoring, signals, LLM and API."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EmployeeBand(str, Enum):
    micro = "1-9"
    small = "10-49"
    mid = "50-199"
    upper_mid = "200-499"
    large = "500-999"
    enterprise = "1000+"


class RevenueBand(str, Enum):
    lt1m = "<1M"
    m1_10 = "1M-10M"
    m10_50 = "10M-50M"
    m50_200 = "50M-200M"
    gt200 = "200M+"


class Company(BaseModel):
    """One ANZ business record. Mirrors the shape of Firmable's real profiles."""
    company_id: str
    abn: str = Field(..., description="11-digit Australian Business Number")
    company_name: str
    website: Optional[str] = None

    anzsic_code: str
    anzsic_division: str
    industry: str

    employee_count: int
    employee_band: EmployeeBand
    annual_revenue_aud: int
    revenue_band: RevenueBand
    founded_year: int

    state: str
    city: str

    tech_stack: list[str] = Field(default_factory=list)
    has_security_vendor: bool = False
    headcount_growth_12m_pct: float = 0.0
    security_job_postings: int = 0

    # Free-text, messy event feed — the raw material the LLM classifies into signals.
    recent_events: list[str] = Field(default_factory=list)


class Signal(BaseModel):
    """A structured buying signal attached to a company."""
    type: str                    # e.g. "breach_incident", "hiring_surge", "cloud_migration"
    source: str                  # "rule" or "llm"
    strength: float              # 0..1 contribution weight
    evidence: str                # human-readable justification
    confidence: float = 1.0      # 1.0 for rules; model-provided for LLM


class ScoreBreakdown(BaseModel):
    component: str
    points: float
    detail: str


class AccountScore(BaseModel):
    company_id: str
    company_name: str
    icp_fit: float               # 0..100 deterministic fit to ideal customer profile
    intent_score: float          # 0..100 from buying signals
    total_score: float           # blended 0..100
    tier: str                    # A / B / C / D
    signals: list[Signal] = Field(default_factory=list)
    breakdown: list[ScoreBreakdown] = Field(default_factory=list)


class OutreachDraft(BaseModel):
    company_id: str
    subject: str
    body: str
    prompt_version: str
    model: str
