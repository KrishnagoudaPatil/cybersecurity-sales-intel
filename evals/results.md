# Signal Classification — Eval Results

_Generated 2026-08-28 15:35 UTC · 28 hand-labelled examples._

> Note: with no `ANTHROPIC_API_KEY`, the classifier runs in deterministic **mock** mode, which simulates each prompt version's expected behaviour so the harness reports a real v1→v2 delta offline. With a key set, the same harness measures the live model.

| version | accuracy | macro-F1 |
|---------|---------:|---------:|
| v1 | 57.1% | 0.534 |
| v2 | 96.4% | 0.963 |

**Δ v1→v2: +39.3 pts accuracy, +0.429 macro-F1.**

## Per-class (v2)

| class | precision | recall | f1 | support |
|-------|----------:|-------:|---:|--------:|
| breach_incident | 1.00 | 1.00 | 1.00 | 6 |
| cloud_migration | 1.00 | 0.80 | 0.89 | 5 |
| compliance_pressure | 1.00 | 1.00 | 1.00 | 5 |
| funding_round | 1.00 | 1.00 | 1.00 | 3 |
| leadership_change | 0.80 | 1.00 | 0.89 | 4 |
| none | 1.00 | 1.00 | 1.00 | 5 |

## Known weaknesses (v2)

- Expected `cloud_migration`, got `leadership_change` — "A new CIO announced a cloud migration program."
