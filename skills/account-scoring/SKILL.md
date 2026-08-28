---
name: account-scoring
version: 1.1.0
description: Score an ANZ company for cybersecurity-software sales fit and buying intent, returning a 0-100 score, tier (A-D), and the signals behind it.
owner: sales-intelligence
inputs: [company_record]
outputs: [account_score]
models:
  classify: claude-haiku-4-5-20251001   # cheap, high-volume signal classification
  judge: claude-sonnet-5                 # only if a narrative "why now" is also requested
prompts:
  - signal_classification (active: v2)   # prompts/signal_classification/v2.txt
depends_on: [signal-classification]
---

# account-scoring

Turns one company record into a prioritised, explainable cybersecurity-sales score.

## When to use (trigger conditions)
- A new or updated company record enters the book and needs (re)prioritising.
- A rep filters a territory/segment and wants it ranked by likelihood-to-buy.
- Nightly batch re-scoring of the whole dataset.

Do NOT use this to *write outreach* — that's the `outreach-draft` skill, which consumes this skill's output.

## The rule-vs-LLM split (important)
Scoring is **deterministic**. The only LLM step is classifying the free-text
`recent_events` feed into structured signals (the `signal-classification` dependency).
Once signals exist, ICP fit + intent are pure arithmetic — so ranking is auditable
and reproducible. Never ask the model to "pick the score".

## Inputs
A `Company` record (see backend/app/models.py). Minimum fields used:
`industry, employee_band, annual_revenue_aud, has_security_vendor,
headcount_growth_12m_pct, security_job_postings, tech_stack, recent_events`.

## Outputs
An `AccountScore`:
```json
{
  "company_id": "AU00042",
  "icp_fit": 90.0,          // 0-100, deterministic ICP fit
  "intent_score": 96.0,     // 0-100, from buying signals
  "total_score": 93.4,      // 0.45*icp_fit + 0.55*intent
  "tier": "A",              // A>=75, B>=55, C>=35, else D
  "signals": [ {"type":"breach_incident","source":"llm","evidence":"..."} ],
  "breakdown": [ {"component":"industry_fit","points":50.0,"detail":"..."} ]
}
```

## Procedure
1. Extract **rule signals** deterministically (regulated industry, hiring surge,
   security hiring, missing security vendor, legacy tech).
2. Extract **LLM signals**: for each `recent_events` string, invoke
   `signal-classification` (cheap model, prompt v2) → drop `none`.
3. Compute `icp_fit` (industry × size × budget) and `intent_score` (sum of weighted
   signal contributions, capped at 100).
4. Blend → `total_score`, assign `tier`.

## Worked example (invocation)
```bash
# Python
python - <<'PY'
from app.loader import load_companies
from app.signals.extract import rule_signals
from app.signals.classify import llm_signals
from app.scoring.rules import score_account
c = load_companies()[42]
score = score_account(c, rule_signals(c) + llm_signals(c.recent_events))
print(score.tier, score.total_score, [s.type for s in score.signals])
PY

# HTTP
curl "localhost:8000/worklist?industry=Banking%20%26%20Finance&tier=A&limit=5"
```

## Guardrails
- If `recent_events` is empty, still score on rules alone (never fail).
- Signal weights live in `backend/app/scoring/rules.py`; ICP weights in
  `backend/app/scoring/icp.py`. Change config, not logic.

## Changelog
- 1.1.0 — signal classification prompt promoted v1→v2 (+39 pts accuracy on eval set).
- 1.0.0 — initial rule+LLM blend.
