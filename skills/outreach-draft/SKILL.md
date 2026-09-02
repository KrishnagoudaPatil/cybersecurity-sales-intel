---
name: outreach-draft
version: 2.0.0
description: Draft a short, responsible first-touch cybersecurity email for a company, grounded ONLY in the security exposure observed on its internet footprint.
owner: sales-intelligence
inputs: [account_findings]
outputs: [outreach_draft]
models:
  judge: claude-sonnet-5                 # low volume, tone/judgement -> strong model
prompts:
  - outreach_draft (active: v2)          # prompts/outreach_draft/v2.txt
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
- Input: an `account_findings` dict shaped like a `FCT_ACCOUNT_SCORE` row
  (`company_domain`, `total_cves`, `exposed_db_services`, `eol_services`,
  `missing_header_ratio`, `risk_score`, `tier`, …).
- Output: `{ company_domain, subject, body, prompt_version, model }`.

## Procedure
1. Build a findings block (strongest exposure first) from the mart row.
2. Render `prompts/outreach_draft/v2.txt` (strong model, temp 0.5) via the traced client.
3. Split `Subject:` from body; return the structured draft.

## Worked example (invocation)
```python
from app.llm.judgement import outreach_draft
outreach_draft({"company_domain":"acme.io","total_cves":9,"tier":"A", ...})
```

## Guardrails
- **Responsible disclosure:** never include specific IPs or exploit detail; tone is
  helpful, not alarmist or threatening (enforced in the prompt).
- Never fabricate beyond the provided findings.
- Human-in-the-loop: drafts are surfaced for edit-then-send, never sent automatically.
- Cost: one strong-model call per draft; generate on demand, not across the whole book.

## Changelog
- 2.0.0 — repointed from synthetic firmographic signals to real observed security findings.
- 1.0.0 — initial (synthetic).
