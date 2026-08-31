# Architecture

## One-paragraph overview
A FastAPI backend scores a book of ANZ companies and serves a ranked, filterable
worklist to a React UI. Scoring is **deterministic**; an LLM is used only where there
is genuine language judgement (turning messy event text into structured signals, and
writing summaries/emails). Every LLM call goes through a single traced client, so
observability, cost accounting and prompt versioning are guaranteed, not optional.

```
data (JSONL)                 ┌───────────── backend/app ─────────────┐
  │  loader.py  ──► Company ──► signals/  ── rule_signals (deterministic)
  │                          │           └─ llm_signals ─► llm/client.call ─► Claude (Haiku)
  │                          ├─ scoring/  ── icp + rules ─► AccountScore
  │                          ├─ llm/      ── client · tracing(JSONL) · cost · prompts(v1/v2)
  │                          └─ api/      ── /worklist /companies/{id} /summary /outreach /cost
  └───────────────────────────────────────────────────────────────────┘
                                        ▲ HTTP
                             frontend/ (React + Vite): worklist · filters · account drawer
```

## Key design decision: the rule-vs-LLM split
This is the most important call in the system. **Rules do scoring; the LLM does language.**

| Concern | Owner | Why |
|---------|-------|-----|
| ICP fit, firmographic weighting | **Rule** | Must be auditable & explainable to a rep; changes rarely |
| Hard signals (regulated, hiring, no-vendor, legacy) | **Rule** | Derivable from structured fields; deterministic = reproducible ranking |
| Signal from free text (breach, cloud, leadership…) | **LLM (cheap)** | Real judgement over unstructured language; high volume → Haiku |
| "Why now" summary, outreach email | **LLM (strong)** | Tone & synthesis; low volume → Sonnet |
| Final score & tier | **Rule** | Never let a model "pick a number"; keep it defensible |

Consequence: if a rep asks "why is this an A?", the answer is a deterministic breakdown,
not a model's opinion. The model's inferences are visibly tagged `llm` in the UI so the
human can discount them.

## Model routing
- `claude-haiku-4-5` — signal classification. High volume (one call per event), cheap,
  fast, and the task (single-label classification with a tight schema) doesn't need a
  frontier model. Measured on our eval set at 96% accuracy with prompt v2.
- `claude-sonnet-5` — summaries and outreach. Low volume, on demand, higher value where
  tone and synthesis matter.

## Cost model (tokens × volume × frequency)
Pricing table lives in `llm/cost.py` (USD / 1M tokens — verify before production use):
Haiku ≈ $1 in / $5 out; Sonnet ≈ $3 in / $15 out.

**Signal classification (the volume driver)**
- Per call: ~450 in + ~25 out ≈ **$0.00058**.
- This prototype (600 companies × ~2.5 events ≈ 1,500 calls) ≈ **$0.87** per full re-score.
- At Firmable scale (1M companies × 2.5 events = 2.5M calls) ≈ **$1,450** per *full* re-score.
  You would never do that: re-classify only **changed events** (content-hash cache), which
  turns steady-state cost into a function of daily event volume, not book size — typically
  a rounding error by comparison.

**Judgement (summary + outreach)**
- Per call: ~250 in + ~200 out ≈ **$0.0038** (Sonnet). A rep generating 50/day ≈ **$0.19/day**.
  Generated on demand only, never batched over the book.

**Production cost ceiling I'd set**
- Cache classification by `hash(event_text, prompt_version)` → near-zero repeat cost.
- Only classify deltas (new/changed events), not the whole book.
- Monthly budget cap with an 80% alert; hard stop that degrades to rules-only scoring if hit.
- Keep judgement calls user-initiated (they cost 6× a classification each).

## Observability
Every call appends one JSONL row (`traces/llm_calls.jsonl`): `ts, trace_id, feature,
prompt_version, model, mode, input, output, decision, input_tokens, output_tokens,
cost_usd, latency_ms, error`. The `/cost` endpoint aggregates it live. Because logging
lives *inside* `llm/client.call`, you cannot call the model and forget to trace it.

## Prompt versioning & evals
Prompts are files under `prompts/<feature>/<version>.txt`; the active version per feature
is pinned in `llm/prompts.py:ACTIVE`. The eval harness (`evals/run.sh`) runs the labelled
set through any version and reports precision/recall/F1 + a v1→v2 delta, writing
`evals/results.md`. This is what lets us claim "v2 is better" with a number, not a vibe.

## Trade-offs & what I'd add next
- **Synthetic data** stands in for the real file (loader boundary isolates the swap).
- **Mock LLM mode** is deterministic and version-aware so evals run in CI without a key;
  live numbers require a real key (documented in results.md).
- No persistence/DB — the book is scored in memory at boot. Fine for a prototype; a real
  deployment would use a warehouse + incremental scoring.
- Next: content-hash caching, a proper labelled set (100+), confidence calibration,
  and CRM write-back.
