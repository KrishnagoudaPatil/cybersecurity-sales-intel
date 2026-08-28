---
name: outreach-draft
version: 1.0.0
description: Draft a short, personalised first-touch cybersecurity sales email for an ANZ account, grounded in its detected buying signals.
owner: sales-intelligence
inputs: [company_record, account_score]
outputs: [outreach_draft]
models:
  judge: claude-sonnet-5                 # low volume, tone/judgement -> strong model
prompts:
  - outreach_draft (active: v1)          # prompts/outreach_draft/v1.txt
depends_on: [account-scoring]
---

# outreach-draft

Writes a <=120-word, Australian-English cold email that leads with the single
strongest buying signal for an account.

## When to use (trigger conditions)
- A rep opens an A/B-tier account and wants a first-touch email to start from.
- Batch-drafting opener emails for a filtered worklist.

Do NOT use for scoring or prioritisation (that's `account-scoring`), and do NOT
auto-send — output is a **draft for human review** (see Guardrails).

## Inputs
- `Company` record + the `AccountScore` from `account-scoring` (for its `signals`).

## Outputs
```json
{ "company_id":"AU00042", "subject":"...", "body":"...",
  "prompt_version":"v1", "model":"claude-sonnet-5" }
```

## Procedure
1. Build a signals block from `account_score.signals` (strongest first).
2. Render `prompts/outreach_draft/v1.txt` with company + regime + signals.
3. Call the strong model (temperature 0.5) via the traced client.
4. Split `Subject:` line from body; return structured draft.

## Worked example (invocation)
```bash
curl -X POST "localhost:8000/companies/AU00042/outreach"
```
```python
from app.llm.judgement import outreach_draft
draft = outreach_draft(company, score)
```

## Guardrails
- Never fabricate facts beyond the provided signals (prompt enforces this).
- Human-in-the-loop: drafts are surfaced in the UI for edit-then-send, never sent
  automatically.
- Cost: ~1 strong-model call per draft; drafts are generated on demand, not for the
  whole book — keep it that way (see docs/architecture.md cost model).

## Changelog
- 1.0.0 — initial version.
