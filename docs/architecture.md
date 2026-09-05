# Architecture

## One-paragraph overview
Raw **Shodan scan data** lands in **Snowflake** as a single `VARIANT` column, and **dbt**
transforms it — through typed staging, a deterministic per-service signal layer, and
entity resolution — into two marts: a company dimension and a scored-prospect fact table.
A **FastAPI** backend serves that book as a ranked, filterable worklist to a **React** UI.
All scoring is **deterministic SQL** (auditable, and it runs where the 74 GB lives); an LLM
is used only where there is genuine language judgement (writing the "why now" summary and
the outreach email over the findings the SQL produced). Every LLM call
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
             ── llm/ client (provider dispatch: anthropic|gemini|mock) · tracing(JSONL) · cost · prompts(v1/v2) · judgement
                                        ▲ HTTP
   frontend/ (React + Vite): worklist · filters · account drawer · why-now · outreach
```

## Why Snowflake + dbt (ELT), not scripts
The dataset is ~13 GB zstd / ~74 GB uncompressed (~10M records). The pattern is **ELT**: land the raw JSON untouched in a `VARIANT`
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
| "Why now" summary + outreach email | **LLM (strong, Sonnet / Gemini)** | Tone & synthesis over the findings; low volume, on demand |

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

## Model routing & pluggable providers
Every model call goes through one client (`llm/client.py`), which dispatches to a
**pluggable provider** — Anthropic, Google **Gemini**, or a deterministic **mock** — chosen
by `LLM_PROVIDER` (or auto-detected: Anthropic if its key is set, else Gemini, else mock).
Two logical roles are each routed to a per-provider model via `Settings.model_for(role)`:

- **judge** — "why now" summaries and outreach. Low volume, on demand, higher value:
  `claude-sonnet-5` or a strong Gemini model, where tone and synthesis over the real
  findings matter. This is the only tier a live feature uses today.
- **classify** — the cheap/high-volume tier (`claude-haiku-4-5` / `gemini-3.6-flash`),
  retained in the routing config for future high-volume LLM work (buying-signal narration,
  or banner-based data enrichment); no live feature exercises it today.

Transient provider errors (HTTP 429/503 — common on Gemini's free tier) are retried with
backoff inside the client, so a hiccup doesn't fail the user's click. The deployed demo runs
on **Gemini, live**.

## Cost model (tokens × volume × frequency)
Pricing lives in `llm/cost.py` (USD / 1M tokens — verify against current provider pricing
before production use): Anthropic Haiku ≈ $1 in / $5 out, Sonnet ≈ $3 in / $15 out; Gemini
Flash is free-tier at demo volumes (so the deployed demo's live LLM cost is ~$0).

**Judgement (summary + outreach) — the only live LLM cost**
- Per call: ~300 in + ~220 out ≈ **$0.0042** (Sonnet); ~$0 on Gemini free-tier.
- Generated **on demand only** (a rep clicks *Summary* or *Outreach* on one account), never
  batched across the book. A rep generating 50/day ≈ **$0.21/day** on Sonnet.
- Because it's low-volume and human-triggered, spend scales with rep activity, not with the
  74 GB of data — the deterministic SQL already did the whole-book work for free.

**Production cost ceiling I'd set**
- Keep judgement on demand only; never batch it across the whole book.
- Monthly budget cap with an 80% alert; hard stop that degrades to rules-only (no LLM) if hit.
- If a high-volume LLM feature is later added (banner-based enrichment or buying-signal
  narration), route it to the cheap tier and cache by `hash(input, prompt_version)` so
  identical inputs cost once — steady-state cost becomes a function of *distinct new inputs*,
  not record count.
- Keep judgement calls user-initiated (one click = one call), so spend tracks rep activity,
  not the size of the book.

## Observability & cost tracing
Every call appends one JSONL row to `traces/llm_calls.jsonl`, and the `/cost` endpoint reads
that file back to aggregate spend + tokens **by feature**, live. Because the write lives
*inside* `llm/client.call` — the single choke-point every feature goes through — a feature
cannot call a model without tracing it, and every row comes out the same shape.

**The trace schema (one stable contract).** Each row is: `ts, trace_id, feature,
prompt_version, provider, model, mode, input, output, decision, input_tokens, output_tokens,
cost_usd, latency_ms, error`. It's a genuine contract because **two independent readers**
depend on it — the `/cost` aggregation and the eval harness — so it's maintained deliberately,
not incidentally:
- **One writer.** The row is built in exactly one place (`client.call`'s `log_call({…})`),
  never emitted ad-hoc elsewhere, so there is a single definition to change.
- **Declared, not implicit.** `llm/tracing.py`'s module docstring pins the field list as
  "stable — depended on by evals and cost reports"; that comment is the source of truth a
  change is checked against.
- **Additive by default.** Readers key on fields by name (`r["feature"]`, `r.get("cost_usd")`),
  so adding a field is backward-compatible; only *renaming or removing* one breaks a reader —
  which is exactly what the docstring guards as a deliberate schema change.

**On Cloud Run the traces are ephemeral.** The
JSONL is written to the container's local filesystem, and Cloud Run instances are stateless
and scale to zero, so a cold start, a redeploy, or a second instance each starts with an empty
file. `/cost` on the live URL therefore reads back near-zero rather than a running history —
it reflects one warm instance's lifetime, not all-time spend. That's fine for a demo but is
**not** durable observability. The production fix is a one-line change *at the same
choke-point*: instead of (or alongside) the local file, have `log_call` emit each row as a
structured log to **Cloud Logging** (stdout on Cloud Run is captured automatically and is
queryable in Logs Explorer) and/or stream it to **BigQuery / a GCS bucket**, then point `/cost`
at that store. The call sites and the schema above stay identical — only the sink changes.

## Prompt versioning & evals
Prompts are files under `prompts/<feature>/<version>.txt`; the active version per feature is
pinned in `llm/prompts.py:ACTIVE`. The two live LLM features are judgement (generative), so
each is measured by an *equivalent quality metric* — grounding + guardrail compliance —
across 21 hand-labelled accounts in `evals/labelled_accounts.jsonl`:
- `evals/summary_eval.py` — the "why now" brief: leads-with-strongest, cites the real risk
  score (grounding), why-now rationale, no fabrication, actionable opener → `summary_results.md`.
- `evals/outreach_eval.py` — the opener email: leads-with-strongest, ≤110 words, no leaked
  IPs, no fabrication, CTA, non-alarmist tone → `outreach_results.md`.

Both run deterministically in mock mode (free, reproducible), which validates the harness and
gives a stable regression signal; `--live` measures the routed model for the real numbers. A
deliberately bad draft fails 6 of 7 checks, so the guardrails bite rather than pass vacuously.

## The app's two data backends
The API reads prospects through a repository interface with two implementations, chosen by
`DATA_BACKEND`:
- `local` (default) — `LocalRepo` reads the committed `data/marts/*.json` snapshot published
  by `export_marts.py`. Deploys anywhere, needs no Snowflake credentials or running
  warehouse, and costs nothing to demo.
- `snowflake` — `SnowflakeRepo` queries the marts live (needs credentials + a running
  warehouse; `snowflake-connector-python` runs on Python 3.14, so the app's own venv
  suffices). Chosen because the full marts could grow large enough that snapshotting the
  whole thing locally is impractical — at that point the API queries in place instead of exporting.

Same interface for both, so `api/main.py` is identical regardless of backend.

## Deployment
One container: a multi-stage Dockerfile builds the React SPA, and the FastAPI backend serves
it, so UI and API share one origin (no CORS) on `$PORT` (8080). Deployed to **Google Cloud
Run** (`gcloud run deploy --source .` → Cloud Build), which gives a single HTTPS URL and
scales to zero when idle. The LLM key is injected from Secret Manager and `DATA_BACKEND`
selects local snapshot vs live Snowflake — the live demo runs `snowflake` + Gemini. See
`deploy.md`.

## Trade-offs & what I'd add next
- **Entity resolution is the weak point.** Hosts with no domain drop out, and a missing
  entry in the `infra_domains` seed can create a phantom company. TLS-certificate and
  ASN/org-based resolution are the top backlog items (see `improvements.md`).
- **Mock LLM mode** is deterministic so evals run in CI without a key; live numbers require a
  real key (documented in `summary_results.md` / `outreach_results.md`).