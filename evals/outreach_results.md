# Outreach Draft — Guardrail Eval Results

_Generated 2026-09-05 20:50 UTC · 21 hand-labelled accounts · mock mode._

> Feature: draft a <=110-word, responsible first-touch email that leads with an account's single most serious observed exposure. Generative, so we measure an **equivalent quality metric** — compliance with the skill's guardrails — rather than precision/recall.

> Deterministic **mock** mode by default (free, reproducible); `--live` measures the routed model. Each account is labelled with its strongest finding (`expected_lead`), which the draft must lead with.

**Fully-compliant drafts: 100.0%** · mean per-check pass rate: 100.0%

| guardrail check | pass rate |
|-----------------|----------:|
| leads with strongest finding | 100.0% |
| body <= 110 words | 100.0% |
| subject < 8 words | 100.0% |
| no specific IP (responsible disclosure) | 100.0% |
| no fabricated findings | 100.0% |
| has a call to action | 100.0% |
| no alarmist / threatening language | 100.0% |

## Known weaknesses

- No guardrail failures on the current labelled set in mock mode. The mock draft is a deterministic template, so this validates the *harness*; the informative run is `--live` against the routed model. Tone is checked only lexically (alarmist word-list) — a fuller check would use an LLM-as-judge rubric for tone and factual grounding, which is the next step here.
