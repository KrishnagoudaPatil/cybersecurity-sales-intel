# Firmable — Attack-Surface Sales Intelligence (Take-Home)

A B2B sales-intelligence prototype for a **cybersecurity software vendor**. It takes raw
**Shodan internet-scan data**, loads it into **Snowflake**, transforms it with **dbt** into
a book of scored companies, and prioritises the accounts with the strongest *observed*
security exposure — the businesses that most plausibly need cybersecurity software right
now. It surfaces the evidence behind each score (known CVEs, exposed databases, end-of-life
software, weak TLS, missing security headers) and drafts outreach — with a full
**AI-native production harness** (skills, evals, tracing, prompt versioning, cost model)
around every LLM call.

> Built for the Firmable Senior Data Engineer take-home task.

**Live demo:** https://cybersecurity-sales-intel-429721467276.asia-south1.run.app — the app
as one container on **Google Cloud Run**, querying **Snowflake** live and using Google
**Gemini** for the "why-now" summaries and outreach drafts.

## The premise: observed attack surface as buying intent

The dataset is Shodan's internet-wide scan export — one record per service observed on one
`IP:port` (banners, TLS, HTTP headers, detected software, known CVEs). Instead of guessing
who *might* need security software from firmographics, we read it off the internet directly:
a company running end-of-life software, an internet-exposed database, or a host with 16
known CVEs is a company with a demonstrable, evidenced need. That evidence is the score.

## The core idea: a rule-vs-LLM split

The system deliberately does **not** use an LLM for everything.

| Layer | Tool | Why |
|-------|------|-----|
| Per-service security signals (CVEs, exposed DB/RDP, EOL, weak TLS, header hygiene) | **dbt SQL (deterministic)** | Auditable, free, and scales to the full 74 GB in-warehouse |
| Entity resolution (host → company) | **dbt SQL (deterministic)** | Reproducible; a rep must trust the attribution |
| Risk score, fit score, tier | **dbt SQL (deterministic)** | Never let a model pick the number |
| Service classification from a raw banner (messy text → service type) | **Cheap LLM (Haiku / Gemini Flash)** — *evaluated* | Judgement over unstructured banners the SQL rules can't parse; high volume |
| "Why now" risk summary + outreach draft | **Strong LLM (Sonnet / Gemini)** | Tone + synthesis over the real findings; low volume, on demand |

The LLM provider is **pluggable** — Anthropic, Google Gemini, or a deterministic mock —
selected by `LLM_PROVIDER` (or auto-detected from whichever API key is set), behind a single
traced client. Full rationale + cost model in [`docs/architecture.md`](docs/architecture.md).

## Pipeline at a glance

```
Shodan NDJSON  ──►  Snowflake RAW.SCANS (VARIANT)   [loader: snowflake/loader/load_raw.py]
                        │
                        ▼  dbt
   staging (view)      STG_SERVICES          typed, one row per service, honeypots dropped
   intermediate (view) INT_SERVICE_SIGNALS   per-service security findings  (the "rules")
   intermediate (view) INT_SERVICE_COMPANY   entity resolution: host → company_domain
   marts (table)       DIM_COMPANY           company dimension (footprint, size band)
   marts (table)       FCT_ACCOUNT_SCORE     risk + fit → total_score → A–D tier
                        │
                        ▼  export_marts.py  (or live query)
   FastAPI + React  ── worklist · filters · account drawer · why-now · outreach
```

## Quickstart

The app runs on a **published snapshot of the marts** (`data/marts/*.json`, committed), so
you can demo it with no Snowflake account and no API key.

```bash
# 1. Backend — serves the real scored prospects from the mart snapshot.
#    No API key => LLM runs in deterministic MOCK mode (evals, traces, cost still work).
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.main:app --reload            # http://localhost:8000

# 2. Frontend (separate terminal)
cd frontend && npm install && npm run dev     # http://localhost:5173

# 3. Evals — one command, compares service-classification prompt v1 vs v2
./evals/run.sh

# 4. Live models: put GEMINI_API_KEY (free-tier) or ANTHROPIC_API_KEY in backend/.env
#    (see backend/.env.example). Provider auto-selects; force it with LLM_PROVIDER.
```

Rebuilding the data from Snowflake (optional — needs credentials; the Snowflake connector
and dbt both run on Python 3.14, so the app venv works) is documented in
[`snowflake/README.md`](snowflake/README.md):
`load_raw.py` lands the sample, `dbt build` builds the marts, `export_marts.py` republishes
the snapshot. Set `DATA_BACKEND=snowflake` to have the API query the marts live instead. The
full 74 GB load (split → S3 external stage → `COPY`) is `snowflake/loader/split_ndjson.py` +
`load_full_s3.sql`.

Single-URL / container deploy (Cloud Run): see [`docs/deploy.md`](docs/deploy.md).

## Repository layout

```
snowflake/     loaders — sample: load_raw.py (internal stage) · full 74 GB: split_ndjson.py
               + S3 external stage in load_full_s3.sql — plus dbt project (staging → marts)
backend/app/   FastAPI · repo (local snapshot | live Snowflake) · signals (banner classify)
               · llm (client/tracing/cost/prompts · judgement · pluggable providers) · snow · export_marts
frontend/      React + Vite UI (worklist, filters, account drawer, why-now, outreach)
skills/        versioned SKILL.md — service-classification, outreach-draft
prompts/       versioned prompts (service_classification v1/v2, account_risk_summary, outreach_draft)
evals/         28 hand-labelled real Shodan banners + one-command harness + results.md
traces/        JSONL — one row per LLM call (request, response, model, version, latency, cost)
data/marts/    published mart snapshot the local backend serves (companies.json, services.json)
docs/          planning · architecture · how-you-build · data_model · improvements · deploy
```

## Docs
- [Planning](docs/planning.md) — the use cases and why this data answers them
- [Architecture](docs/architecture.md) — pipeline, rule-vs-LLM split, pluggable providers, cost model
- [Data model](docs/data_model.md) — column dictionary (raw vs derived) for every layer
- [How I build](docs/how-you-build.md) — dev loop, where AI helped vs hurt, known weakness
- [Improvements](docs/improvements.md) — prioritised backlog (entity resolution first)
- [Deploy](docs/deploy.md) — single-container Cloud Run
