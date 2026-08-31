"""FastAPI app — the product surface a salesperson (via the React UI) hits."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import TRACES_DIR, get_settings
from app.llm.judgement import account_summary, outreach_draft
from app.service import get_book

app = FastAPI(title="Firmable Sales Intelligence API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
def health():
    s = get_settings()
    return {"status": "ok", "llm_mode": "live" if s.llm_live else "mock",
            "model_classify": s.model_classify, "model_judge": s.model_judge}


@app.get("/facets")
def facets():
    return get_book().facets()


@app.get("/worklist")
def worklist(industry: str | None = None, state: str | None = None,
             tier: str | None = None, min_score: float = 0.0,
             employee_band: str | None = None, limit: int = 50):
    return get_book().worklist(industry=industry, state=state, tier=tier,
                               min_score=min_score, employee_band=employee_band, limit=limit)


@app.get("/companies/{company_id}")
def company_detail(company_id: str):
    book = get_book()
    if company_id not in book.companies:
        raise HTTPException(404, "company not found")
    return {"company": book.companies[company_id], "score": book.scores[company_id]}


@app.post("/companies/{company_id}/summary")
def company_summary(company_id: str):
    book = get_book()
    if company_id not in book.companies:
        raise HTTPException(404, "company not found")
    text = account_summary(book.companies[company_id], book.scores[company_id])
    return {"company_id": company_id, "summary": text}


@app.post("/companies/{company_id}/outreach")
def company_outreach(company_id: str):
    book = get_book()
    if company_id not in book.companies:
        raise HTTPException(404, "company not found")
    return outreach_draft(book.companies[company_id], book.scores[company_id])


@app.get("/cost")
def cost_summary():
    """Aggregate spend + volume from the trace log — powers the cost dashboard."""
    tf = TRACES_DIR / "llm_calls.jsonl"
    if not tf.exists():
        return {"calls": 0, "total_cost_usd": 0.0, "by_feature": {}}
    by_feature: dict[str, dict] = {}
    total_cost = 0.0
    calls = 0
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
# If frontend/dist exists (i.e. `npm run build` was run), mount it at / so the whole
# app is one URL. In dev we skip this and use the Vite proxy instead.
from app.config import REPO_ROOT  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_dist = REPO_ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="spa")
