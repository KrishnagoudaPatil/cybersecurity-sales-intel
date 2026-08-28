"""Buying-signal extraction.

TWO sources, by design (this is the rule-vs-LLM split in miniature):

1. RULE signals  -> derived from structured fields with hard, auditable logic
   (regulated industry, headcount growth, security hiring, missing security vendor,
   company-size sweet spot). Free, instant, deterministic.

2. LLM signals   -> classified from the messy free-text `recent_events` feed, where
   the signal is buried in natural language (a breach disclosure, a cloud migration,
   a leadership change). This is genuine judgement over unstructured text, so it goes
   to a cheap model. See app/signals/classify.py.

Keeping them separate means a rep can see exactly which signals are hard facts vs.
model inferences, and we can eval the LLM half independently.
"""
from __future__ import annotations

from app.models import Company, Signal
from app.scoring.icp import COMPLIANCE_REGIME


def rule_signals(c: Company) -> list[Signal]:
    sigs: list[Signal] = []

    regime = COMPLIANCE_REGIME.get(c.industry)
    if regime:
        sigs.append(Signal(
            type="regulated_industry", source="rule", strength=0.8,
            evidence=f"Operates in {c.industry}, subject to {regime}.",
        ))

    if c.headcount_growth_12m_pct >= 25:
        sigs.append(Signal(
            type="hiring_surge", source="rule",
            strength=min(1.0, 0.4 + c.headcount_growth_12m_pct / 100),
            evidence=f"Headcount up {c.headcount_growth_12m_pct:.0f}% in 12 months — expanding attack surface.",
        ))

    if c.security_job_postings > 0:
        sigs.append(Signal(
            type="security_hiring", source="rule",
            strength=min(1.0, 0.5 + 0.15 * c.security_job_postings),
            evidence=f"{c.security_job_postings} open security role(s) — actively investing in security.",
        ))

    # Mid/upper-mid firm with sensitive posture but NO security vendor in the stack.
    if not c.has_security_vendor and 50 <= c.employee_count <= 999:
        sigs.append(Signal(
            type="no_security_vendor", source="rule", strength=0.7,
            evidence="No known security vendor in tech stack despite mid-market size — likely a gap.",
        ))

    if "Legacy on-prem" in c.tech_stack:
        sigs.append(Signal(
            type="legacy_tech", source="rule", strength=0.4,
            evidence="Runs legacy on-prem systems — higher exposure to unpatched vulnerabilities.",
        ))

    return sigs


# Canonical set of signal types the LLM classifier may emit from free text.
LLM_SIGNAL_TYPES = [
    "breach_incident",      # disclosed breach / ransomware / data exposure
    "cloud_migration",      # moving to cloud / digital transformation -> new attack surface
    "leadership_change",    # new CIO/CTO/Head of IT -> budget reset, new initiatives
    "funding_round",        # fresh capital -> ability to spend
    "compliance_pressure",  # explicit regulatory obligation mentioned
    "none",                 # no cyber-relevant signal
]
