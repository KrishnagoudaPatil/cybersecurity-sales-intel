# Service Classification — Eval Results

_Generated 2026-09-02 17:11 UTC · 28 hand-labelled real Shodan banners._

> Feature: classify a raw service **banner** into `web / remote_access / database / mail / network_infra / unknown`. This is the LLM half of the rule-vs-LLM split — it reads free-text banners when the dbt SQL rules have no structured `product`/`cpe`/`tag` to go on.

> With no `ANTHROPIC_API_KEY` the classifier runs in deterministic **mock** mode, version-aware so the harness reports a real v1→v2 delta offline; with a key the same harness measures the live model.

| version | accuracy | macro-F1 |
|---------|---------:|---------:|
| v1 | 50.0% | 0.631 |
| v2 | 100.0% | 1.000 |

**Δ v1→v2: +50.0 pts accuracy, +0.369 macro-F1.**

## Per-class (v2)

| class | precision | recall | f1 | support |
|-------|----------:|-------:|---:|--------:|
| database | 1.00 | 1.00 | 1.00 | 2 |
| mail | 1.00 | 1.00 | 1.00 | 3 |
| network_infra | 1.00 | 1.00 | 1.00 | 11 |
| remote_access | 1.00 | 1.00 | 1.00 | 6 |
| unknown | 1.00 | 1.00 | 1.00 | 3 |
| web | 1.00 | 1.00 | 1.00 | 3 |

## Known weaknesses (v2)

- No errors on the current 28-banner set. It's small and hand-built; real banners are messier (truncation, binary, TLS-wrapped). Next: grow to 100+, add per-protocol adversarial cases, and calibrate confidence.
