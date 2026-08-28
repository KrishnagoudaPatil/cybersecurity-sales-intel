"""Orchestration layer between data/scoring/LLM and the API.

Scores the whole book once (rule signals + LLM-classified signals -> blended score),
caches it, and serves filtered/ranked worklists. Summaries and outreach are computed
lazily per account (they cost model calls).
"""
from __future__ import annotations

from functools import lru_cache

from app.loader import load_companies
from app.models import AccountScore, Company
from app.scoring.rules import score_account
from app.signals.classify import llm_signals
from app.signals.extract import rule_signals


class Book:
    def __init__(self) -> None:
        self.companies: dict[str, Company] = {}
        self.scores: dict[str, AccountScore] = {}
        self._build()

    def _build(self) -> None:
        for c in load_companies():
            self.companies[c.company_id] = c
            signals = rule_signals(c) + llm_signals(c.recent_events)
            self.scores[c.company_id] = score_account(c, signals)

    def worklist(self, *, industry: str | None = None, state: str | None = None,
                 tier: str | None = None, min_score: float = 0.0,
                 employee_band: str | None = None, limit: int = 50) -> list[AccountScore]:
        rows = []
        for cid, sc in self.scores.items():
            c = self.companies[cid]
            if industry and c.industry != industry:
                continue
            if state and c.state != state:
                continue
            if tier and sc.tier != tier:
                continue
            if employee_band and c.employee_band.value != employee_band:
                continue
            if sc.total_score < min_score:
                continue
            rows.append(sc)
        rows.sort(key=lambda s: s.total_score, reverse=True)
        return rows[:limit]

    def facets(self) -> dict:
        industries = sorted({c.industry for c in self.companies.values()})
        states = sorted({c.state for c in self.companies.values()})
        bands = sorted({c.employee_band.value for c in self.companies.values()})
        from collections import Counter
        tiers = Counter(s.tier for s in self.scores.values())
        return {"industries": industries, "states": states, "employee_bands": bands,
                "tiers": dict(sorted(tiers.items())), "total": len(self.companies)}


@lru_cache
def get_book() -> Book:
    return Book()
