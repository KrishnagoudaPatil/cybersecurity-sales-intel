# Architecture

## One-paragraph overview
Raw **Shodan scan data** lands in **Snowflake** as a single `VARIANT` column, and **dbt**
transforms it — through typed staging, a deterministic per-service signal layer, and
entity resolution — into two marts: a company dimension and a scored-prospect fact table.
A **FastAPI** backend serves that book as a ranked, filterable worklist to a **React** UI.
All scoring is **deterministic SQL** (auditable, and it runs where the 74 GB lives); an LLM
is used only where there is genuine language judgement (reading a raw service *banner* the
SQL rules can't parse, and writing the "why now" summary / outreach email). Every LLM call
goes through a single traced client, so observability, cost accounting and prompt
versioning are guaranteed, not optional.

```
Shodan NDJSON
   │  snowflake/loader/load_raw.py  (PUT → stage → COPY INTO)
   ▼
Snowflake  RAW.SCANS(v VARIANT)                          ELT: land raw, transform in-warehouse
   │  dbt
   ├─ staging      STG_SERVICES         (view)  typed 1-row-per-service, honeypots dropped
   ├─ intermediate INT_SERVICE_SIGNALS  (view)  per-service security findings  ← the "rules"
   ├─ intermediate INT_SERVICE_COMPANY  (view)  entity resolution → company_domain
   ├─ marts        DIM_COMPANY          (table) footprint, size band
   └─ marts        FCT_ACCOUNT_SCORE    (table) risk + fit → total_score → A–D tier
   │  export_marts.py  →  data/marts/*.json   (or DATA_BACKEND=snowflake: live query)
   ▼
backend/app  ── repo (LocalRepo | SnowflakeRepo) ── api (/worklist /companies/{d} /summary /outreach /cost)
             ── signals/classify (banner → service type, LLM, evaluated)
             ── llm/ client · tracing(JSONL) · cost · prompts(v1/v2) · judgement (summary/outreach)
                                        ▲ HTTP
   frontend/ (React + Vite): worklist · filters · account drawer · why-now · outreach
```

## Why Snowflake + dbt (ELT), not scripts
The dataset is ~13 GB zstd / ~74 GB uncompressed (~10M records). You do not process that in
Python on a laptop. The pattern is **ELT**: land the raw JSON untouched in a `VARIANT`
column (cheap, lossless, re-processable without re-loading), then push all the heavy
transformation into the warehouse where it parallelises. dbt gives that transformation
**structure** (staging → intermediate → marts), **lineage** (`ref()`/`source()`), and
**tests** (not-null / unique / accepted-values on the marts) — the difference between a pile
of SQL and a maintainable pipeline. Staging/intermediate are **views** (free, always fresh);
the marts are **tables** (materialised once, fast to serve and to snapshot).

## Key design decision: the rule-vs-LLM split
This is the most important call in the system. **SQL does the scoring; the LLM does the
language.**

| Concern | Owner | Why |
|---------|-------|-----|
| Per-service findings (CVEs, exposed DB/RDP, EOL, weak TLS, header hygiene) | **dbt SQL** | Derivable from structured fields; deterministic ⇒ reproducible ranking, and it scales to 74 GB in-warehouse |
| Entity resolution (host → `company_domain`) | **dbt SQL** | Must be auditable — a rep has to trust the attribution |
| Risk score, fit score, total, tier | **dbt SQL** | Never let a model "pick a number"; keep ranking defensible |
| Service type from a raw **banner** (free text) | **LLM (cheap, Haiku)** | Real judgement over unstructured text when `product`/`cpe`/`port`/`tags` are absent; high volume |
| "Why now" summary + outreach email | **LLM (strong, Sonnet)** | Tone & synthesis over the findings; low volume, on demand |

Consequence: if a rep asks "why is this an A?", the answer is a deterministic breakdown of
counted findings, not a model's opinion. The LLM never touches the score — it explains and
personalises what the SQL already decided.

## The scoring model (`fct_account_score.sql`)
Two independent 0–100 axes, blended:

- **Risk ("need")** — a weighted sum of the company's counted findings, capped at 100:
  `total_cves×15 + exposed_db×20 + exposed_remote×8 + eol×12 + self_signed×5 + weak_tls×5 +
  expired_cert×8 + header-hygiene×20`. Weights reflect how strong each signal is as evidence
  of exploitable need (a known CVE or an exposed database outweighs a missing header).
- **Fit** — `0.5 × target-geography (AU/NZ) + 0.5 × size band (from host_count)`, ×100. This
  narrows the ranked list to the vendor's addressable market.
- **Total** = `0.6 × risk + 0.4 × fit`; **tier** A ≥ 70 / B ≥ 50 / C ≥ 30 / D. Need is
  weighted above fit because the product question is *who needs it now*.

The weights are currently literals in the model. Promoting them to dbt `vars` (so they're
tunable without editing SQL) is a tracked improvement.

## Model routing
- `claude-haiku-4-5` — service-banner classification. High volume (one call per banner the
  SQL couldn't classify), cheap, fast, and the task (single-label classification into a
  6-way taxonomy) doesn't need a frontier model. Measured on the eval set at **100%**
  accuracy with prompt v2 (mock mode; see caveat in how-you-build).
- `claude-sonnet-5` — "why now" summaries and outreach. Low volume, on demand, higher value
  where tone and synthesis over the real findings matter.

## Cost model (tokens × volume × frequency)
Pricing lives in `llm/cost.py` (USD / 1M tokens — verify against current Anthropic pricing
before production use): Haiku ≈ $1 in / $5 out; Sonnet ≈ $3 in / $15 out.

**Banner classification (the volume driver)**
- Per call: ~300 in + ~25 out ≈ **$0.0004**.
- Crucially, this is **not** run per company or per record — only for services whose type
  the deterministic SQL cannot settle from `product`/`cpe`/`port`/`tags`. On this data most
  services are classified by rules for free; the LLM handles the residual of ambiguous
  banners.
- At full scale you cache by `hash(banner, prompt_version)`: identical banners (and the
  internet has vast numbers of identical ones) cost once, ever. Steady-state cost becomes a
  function of *distinct new banners*, not record count.

**Judgement (summary + outreach)**
- Per call: ~300 in + ~220 out ≈ **$0.0042** (Sonnet). A rep generating 50/day ≈ **$0.21/day**.
  Generated on demand only, never batched over the book.

**Production cost ceiling I'd set**
- Cache classification by `hash(banner, prompt_version)` → near-zero repeat cost.
- Classify only banners the SQL rules leave ambiguous — the LLM is a fallback, not the
  front door.
- Monthly budget cap with an 80% alert; hard stop that degrades to rules-only if hit.
- Keep judgement calls user-initiated (they cost ~10× a classification each).

## Observability
Every call appends one JSONL row (`traces/llm_calls.jsonl`): `ts, trace_id, feature,
prompt_version, model, mode, input, output, decision, input_tokens, output_tokens,
cost_usd, latency_ms, error`. The `/cost` endpoint aggregates it live, by feature. Because
logging lives *inside* `llm/client.call`, you cannot call the model and forget to trace it.

## Prompt versioning & evals
Prompts are files under `prompts/<feature>/<version>.txt`; the active version per feature is
pinned in `llm/prompts.py:ACTIVE`. The eval harness (`evals/run.sh`) runs the labelled set
of real Shodan banners through any version and reports accuracy / precision / recall / F1 +
a v1→v2 delta, writing `evals/results.md`. This is what lets us claim "v2 is better" with a
number, not a vibe (v1 50% → v2 100% accuracy on the current set).

## The app's two data backends
The API reads prospects through a repository interface with two implementations, chosen by
`DATA_BACKEND`:
- `local` (default) — `LocalRepo` reads the committed `data/marts/*.json` snapshot published
  by `export_marts.py`. Deploys anywhere, needs no Snowflake credentials or running
  warehouse, and costs nothing to demo.
- `snowflake` — `SnowflakeRepo` queries the marts live (needs credentials + a running
  warehouse; `snowflake-connector-python` runs on Python 3.14, so the app's own venv
  suffices). Chosen because the full marts could grow large enough that snapshotting the
  whole thing locally is impractical — at that point you query in place instead of exporting.

Same interface for both, so `api/main.py` is identical regardless of backend.

## Trade-offs & what I'd add next
- **Entity resolution is the weak point.** Hosts with no domain drop out, and a missing
  entry in the `infra_domains` seed can create a phantom company. TLS-certificate and
  ASN/org-based resolution are the top backlog items (see `improvements.md`).
- **Mock LLM mode** is deterministic and version-aware so evals run in CI without a key;
  live numbers require a real key (documented in `results.md`).
- **Sample, not the full file** — the pipeline is proven on a 1k sample; the full 74 GB path
  is external stage + Snowpipe + a bigger warehouse.
- **No orchestration yet** — load → dbt → export are run by hand; a real deployment schedules
  them (dbt Cloud / Airflow) with incremental models keyed on scan date.
