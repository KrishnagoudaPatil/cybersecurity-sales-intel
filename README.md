# Firmable — AI Sales Intelligence Platform (Take-Home)

A small but functional B2B sales-intelligence prototype for a **cybersecurity software
vendor**: it takes raw Australian company data, scores and prioritises the accounts most
likely to need cybersecurity software *right now*, surfaces the buying signals behind each
score, and drafts outreach — with a full **AI-native production harness** (skills, evals,
tracing, prompt versioning, cost model) around every LLM call.

> Built for the Firmable Senior Data Engineer take-home task.

## The core idea: a rule-vs-LLM split

The system deliberately does **not** use an LLM for everything.

| Layer | Tool | Why |
|-------|------|-----|
| ICP fit + firmographic scoring | **Deterministic rules** | Auditable, free, explainable to a rep |
| Hard buying signals (regulated industry, size, tech red-flags, hiring) | **Deterministic rules** | A rep must trust *why* an account ranks |
| Signal classification (messy text → structured signal) | **Cheap LLM (Haiku)** | Judgement over unstructured text; high volume |
| "Why now" summary + outreach draft | **Strong LLM (Sonnet)** | Tone + synthesis; low volume |
| Final score & tier | **Deterministic rules** | Never let a model pick the number |

Full rationale + cost model in [`docs/architecture.md`](docs/architecture.md).

## Quickstart

```bash
# 1. Backend (runs in MOCK mode with no API key — evals, traces, cost all still work)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.data_gen                 # generate the synthetic ANZ dataset
uvicorn app.api.main:app --reload      # http://localhost:8000

# 2. Frontend (separate terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173

# 3. Evals — one command, compares prompt v1 vs v2
./evals/run.sh

# 4. Live models: put a key in backend/.env (see backend/.env.example)
```

Single-URL / container deploy: see [`docs/deploy.md`](docs/deploy.md).

## Repository layout

```
backend/app/   FastAPI · scoring (rules) · signals (rule+LLM) · llm (client/tracing/cost/prompts)
frontend/      React + Vite UI (worklist, filters, account drawer, outreach)
skills/        versioned SKILL.md — account-scoring, outreach-draft
prompts/       versioned prompts (signal_classification v1/v2, account_summary, outreach_draft)
evals/         28 labelled examples + one-command harness + results.md
traces/        JSONL — one row per LLM call (request, response, model, version, latency, cost)
docs/          planning · architecture · how-you-build · deploy
data/          synthetic ANZ dataset (swap for the real Firmable file via loader.py)
```

## Docs
- [Planning](docs/planning.md) — the use cases and why
- [Architecture](docs/architecture.md) — how it fits together, rule-vs-LLM split, cost model
- [How I build](docs/how-you-build.md) — dev loop, where AI helped vs hurt, known weakness
- [Deploy](docs/deploy.md)
