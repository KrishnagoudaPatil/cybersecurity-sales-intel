"""Deterministic account scoring engine.

Produces an AccountScore from (a) ICP fit and (b) intent derived from buying signals.
Everything here is pure, deterministic and explainable — no LLM. The LLM's only role
upstream is to turn free text into structured Signals; once we have Signals, scoring
is rules. That keeps ranking auditable and reproducible.
"""
from __future__ import annotations

from app.models import AccountScore, Company, ScoreBreakdown, Signal
from app.scoring.icp import (
    EMPLOYEE_FIT,
    ICP_WEIGHT,
    INDUSTRY_FIT,
    INTENT_WEIGHT,
    TIER_CUTOFFS,
)

# How much each signal type contributes to the 0..100 intent score (before its own
# per-instance strength/confidence). Tuned so a single strong signal can't max it out.
SIGNAL_INTENT_WEIGHT = {
    "breach_incident": 45,
    "compliance_pressure": 30,
    "regulated_industry": 25,
    "security_hiring": 30,
    "hiring_surge": 22,
    "cloud_migration": 25,
    "no_security_vendor": 28,
    "leadership_change": 18,
    "funding_round": 15,
    "legacy_tech": 12,
    "none": 0,
}


def icp_fit(c: Company) -> tuple[float, list[ScoreBreakdown]]:
    industry = INDUSTRY_FIT.get(c.industry, 0.4)
    size = EMPLOYEE_FIT.get(c.employee_band.value, 0.4)
    # Revenue acts as a light budget-capacity multiplier.
    budget = min(1.0, 0.5 + c.annual_revenue_aud / 200_000_000)

    fit = 100 * (0.5 * industry + 0.35 * size + 0.15 * budget)
    breakdown = [
        ScoreBreakdown(component="industry_fit", points=round(50 * industry, 1),
                       detail=f"{c.industry} (weight {industry})"),
        ScoreBreakdown(component="size_fit", points=round(35 * size, 1),
                       detail=f"{c.employee_band.value} employees (weight {size})"),
        ScoreBreakdown(component="budget_capacity", points=round(15 * budget, 1),
                       detail=f"${c.annual_revenue_aud/1e6:.1f}M revenue"),
    ]
    return round(fit, 1), breakdown


def intent_score(signals: list[Signal]) -> tuple[float, list[ScoreBreakdown]]:
    total = 0.0
    breakdown: list[ScoreBreakdown] = []
    for s in signals:
        base = SIGNAL_INTENT_WEIGHT.get(s.type, 10)
        pts = base * s.strength * s.confidence
        total += pts
        breakdown.append(ScoreBreakdown(
            component=f"signal:{s.type}", points=round(pts, 1),
            detail=f"[{s.source}] {s.evidence}",
        ))
    return round(min(100.0, total), 1), breakdown


def tier_for(total: float) -> str:
    for cutoff, tier in TIER_CUTOFFS:
        if total >= cutoff:
            return tier
    return "D"


def score_account(c: Company, signals: list[Signal]) -> AccountScore:
    fit, fit_bd = icp_fit(c)
    intent, intent_bd = intent_score(signals)
    total = round(ICP_WEIGHT * fit + INTENT_WEIGHT * intent, 1)
    return AccountScore(
        company_id=c.company_id,
        company_name=c.company_name,
        icp_fit=fit,
        intent_score=intent,
        total_score=total,
        tier=tier_for(total),
        signals=signals,
        breakdown=fit_bd + intent_bd,
    )
