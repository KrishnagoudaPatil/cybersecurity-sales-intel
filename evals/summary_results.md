# Account Risk Summary — Quality Eval Results

_Generated 2026-09-05 20:50 UTC · 21 hand-labelled accounts · mock mode._

> Feature: a tight "why now" sales brief (Risk / Why now / Opener) grounded ONLY in observed findings. Generative, so we measure an **equivalent quality metric** — grounding + compliance — rather than precision/recall.

> Deterministic **mock** mode by default (free, reproducible); `--live` measures the routed model. Reuses `evals/labelled_accounts.jsonl` (each account labelled with its strongest finding).

**Fully-compliant briefs: 100.0%** · mean per-check pass rate: 100.0%

| quality check | pass rate |
|---------------|----------:|
| leads with strongest finding | 100.0% |
| cites the real risk score (grounding) | 100.0% |
| includes a why-now timing rationale | 100.0% |
| no fabricated findings | 100.0% |
| no specific IP (responsible disclosure) | 100.0% |
| <= 120 words | 100.0% |
| gives an actionable opener | 100.0% |

## Known weaknesses

- No failures on the current labelled set in mock mode — the mock brief is a deterministic template, so this validates the *harness*. The informative run is `--live` against the routed model. `grounds_risk_score` is a substring check; a fuller grounding test would use an LLM-as-judge to confirm each claimed finding traces to the input.
