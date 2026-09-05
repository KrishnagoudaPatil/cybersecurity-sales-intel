"""FastAPI app — serves the real scored prospects from the Snowflake marts.

Data comes through the repository (local snapshot by default, or live Snowflake), so the
API code is identical regardless of backend. LLM summary/outreach run on demand.
"""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import REPO_ROOT, TRACES_DIR, get_settings
from app.llm.judgement import account_risk_summary, outreach_draft
from app.repo import get_repo

app = FastAPI(title="CyberShield Sales Intelligence API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    s = get_settings()
    return {"status": "ok", "data_backend": s.data_backend,
            "llm_mode": "live" if s.llm_live else "mock",
            "llm_provider": s.provider,
            "model_classify": s.model_for("classify"), "model_judge": s.model_for("judge")}


@app.get("/facets")
def facets():
    return get_repo().facets()


@app.get("/worklist")
def worklist(country: str | None = None, tier: str | None = None,
             size_band: str | None = None, min_score: float = 0.0, limit: int = 100):
    return get_repo().worklist(country=country, tier=tier, size_band=size_band,
                               min_score=min_score, limit=limit)


@app.get("/companies/{domain}")
def company_detail(domain: str):
    d = get_repo().company(domain)
    if not d:
        raise HTTPException(404, "company not found")
    return d


@app.post("/companies/{domain}/summary")
def company_summary(domain: str):
    d = get_repo().company(domain)
    if not d:
        raise HTTPException(404, "company not found")
    return {"company_domain": domain, "summary": account_risk_summary(d["company"])}


@app.post("/companies/{domain}/outreach")
def company_outreach(domain: str):
    d = get_repo().company(domain)
    if not d:
        raise HTTPException(404, "company not found")
    return outreach_draft(d["company"])


@app.get("/cost")
def cost_summary():
    tf = TRACES_DIR / "llm_calls.jsonl"
    if not tf.exists():
        return {"calls": 0, "total_cost_usd": 0.0, "by_feature": {}}
    by_feature: dict[str, dict] = {}
    total_cost, calls = 0.0, 0
    for line in tf.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        calls += 1
        total_cost += r.get("cost_usd", 0.0)
        f = by_feature.setdefault(r["feature"], {"calls": 0, "cost_usd": 0.0,
                                                 "input_tokens": 0, "output_tokens": 0})
        f["calls"] += 1
        f["cost_usd"] = round(f["cost_usd"] + r.get("cost_usd", 0.0), 6)
        f["input_tokens"] += r.get("input_tokens", 0)
        f["output_tokens"] += r.get("output_tokens", 0)
    return {"calls": calls, "total_cost_usd": round(total_cost, 6), "by_feature": by_feature}


# --- Optional: serve the built React SPA from the same origin (single-URL deploy) ---
from fastapi.staticfiles import StaticFiles  # noqa: E402

_dist = REPO_ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="spa")
