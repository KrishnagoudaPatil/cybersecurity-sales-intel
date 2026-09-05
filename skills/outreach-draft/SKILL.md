---
name: outreach-draft
version: 2.2.0
description: Draft a short, responsible first-touch cybersecurity email for a company, grounded ONLY in the security exposure observed on its internet footprint.
owner: sales-intelligence
inputs: [account_findings]
outputs: [outreach_draft]
models:
  # Strong model for low-volume judgement. NOT hard-coded — resolved at runtime by
  # app.config.Settings.model_for("judge") under the active provider:
  #   anthropic -> claude-sonnet-5   |   gemini -> gemini-3.6-flash (free-tier demo)
  judge: model_for("judge")              # provider-routed; see docs/architecture.md cost model
prompts:
  - outreach_draft (active: v2)          # prompts/outreach_draft/v2.txt
eval: evals/labelled_accounts.jsonl (21 hand-labelled accounts); harness evals/outreach_eval.py
depends_on: [dbt marts: fct_account_score]
---

# outreach-draft

Writes a <=110-word, responsible cold email that leads with the single most serious
security exposure observed for an account.

## When to use (trigger conditions)
- A rep opens an A/B-tier account and wants a first-touch email to start from.
- Batch-drafting openers for a filtered worklist.

Do NOT auto-send — output is a **draft for human review** (see Guardrails).

## Inputs / outputs
- Input: **just a domain** (recommended) — the findings row is fetched for you via the
  configured data backend (published snapshot by default, live Snowflake when
  `DATA_BACKEND=snowflake`). No hand-assembled dict required.
- Advanced: you may still pass an `account_findings` dict shaped like a
  `FCT_ACCOUNT_SCORE` row (`company_domain`, `total_cves`, `exposed_db_services`,
  `eol_services`, `missing_header_ratio`, `risk_score`, `tier`, …) when you already
  have the row in hand.
- Output: `{ company_domain, subject, body, prompt_version, model }`.

## Procedure
1. Resolve the findings row for the domain via `get_repo().company(domain)` (backend
   picked by `DATA_BACKEND`), or accept a caller-supplied findings dict.
2. Build a findings block (strongest exposure first) from that row.
3. Render `prompts/outreach_draft/v2.txt` (strong model, temp 0.5) via the traced client.
4. Split `Subject:` from body; return the structured draft.

## Worked example (invocation)
```python
# Recommended — pass a domain; the row is fetched from the configured backend.
from app.llm.judgement import outreach_draft_for
outreach_draft_for("acme.io")

# Advanced — pass a findings row you already have.
from app.llm.judgement import outreach_draft
outreach_draft({"company_domain": "acme.io", "total_cves": 9, "tier": "A", ...})
```

## Evals
`backend/.venv/bin/python evals/outreach_eval.py` scores every draft against the guardrails
below on 21 hand-labelled accounts — leads-with-strongest-finding, ≤110 words, subject
<8 words, no leaked IPs, no fabricated findings, has a CTA, non-alarmist tone — and writes
`evals/outreach_results.md`. This is guardrail-compliance (an **equivalent quality metric**
for a generative feature), not precision/recall. Deterministic mock mode by default (free,
reproducible; validates the harness); `--live` measures the routed model. Known limitation:
tone is only checked lexically — a fuller check would use an LLM-as-judge rubric.

## Guardrails
- **Responsible disclosure:** never include specific IPs or exploit detail; tone is
  helpful, not alarmist or threatening (enforced in the prompt).
- Never fabricate beyond the provided findings.
- Human-in-the-loop: drafts are surfaced for edit-then-send, never sent automatically.
- Cost: one strong-model call per draft; generate on demand, not across the whole book.

## Changelog
- 2.2.0 — added a guardrail-compliance eval (`evals/outreach_eval.py`, 21 labelled accounts):
  measures leads-with-strongest, word/subject limits, no-IP, no-fabrication, CTA, and tone.
- 2.1.1 — frontmatter `models` now reflects real provider-routing (`model_for("judge")`)
  instead of a hard-coded `claude-sonnet-5`, matching how the model is chosen at runtime.
- 2.1.0 — added `outreach_draft_for(domain)`: fetches the findings row from the configured
  backend (snapshot or live Snowflake), so callers pass only a domain.
- 2.0.0 — grounded outreach on real observed security findings.
- 1.0.0 — initial (synthetic).
