---
name: service-classification
version: 1.0.0
description: Classify an internet-exposed service into a type (web/remote_access/database/mail/network_infra/unknown) from its raw banner, for cybersecurity prospecting.
owner: sales-intelligence
inputs: [banner]
outputs: [service_category]
models:
  classify: claude-haiku-4-5-20251001   # cheap, high-volume, one call per service
prompts:
  - service_classification (active: v2)  # prompts/service_classification/v2.txt
eval: evals/labelled_banners.jsonl (28 hand-labelled real banners); harness evals/run.sh
---

# service-classification

The LLM half of the rule-vs-LLM split on Shodan scan data. The dbt SQL rules classify a
service when structured fields (`product`, `cpe`, `port`, `tags`) are clear; this skill
reads the **raw free-text banner** when they are not.

## When to use (trigger conditions)
- A scanned service has a `banner` but no `product`/`cpe` (rules can't type it).
- Batch-typing the long tail of unidentified services before scoring.

Do NOT use it to score or rank (that's the deterministic dbt marts) — only to *identify
what a service is* from messy text.

## Inputs / outputs
- Input: `banner` (string) — the raw first response the service returned.
- Output: `{ "category": "web|remote_access|database|mail|network_infra|unknown",
  "confidence": 0.0-1.0 }`.

## Procedure
1. Render `prompts/service_classification/v2.txt` with the banner.
2. Call the cheap model (temperature 0) via the traced client.
3. Parse the JSON; fall back to `unknown` on any parse failure or off-taxonomy label.

## Worked example (invocation)
```python
from app.signals.classify import classify_banner
classify_banner("SSH-2.0-OpenSSH_8.9p1")          # -> {"category":"remote_access", ...}
classify_banner("RTSP/1.0 200 OK Server: Hipcam")  # -> {"category":"network_infra", ...}
```

## Evals
`./evals/run.sh` scores this feature on 28 hand-labelled real banners and compares
prompt v1 vs v2 (precision/recall/F1). Current mock-mode result: v1 50% → **v2 100%**
accuracy; results written to `evals/results.md`. Live mode measures the real model.

## Guardrails
- Beware look-alikes (encoded in v2): `RTSP/1.0` is a camera (network_infra) not web;
  `SMB` is file sharing not a database; `+OK` is POP mail.
- Never guess `web` purely from port 443 — classify from the banner; answer `unknown`
  when the banner is an error or too short.

## Changelog
- 1.0.0 — banner-based service classifier (v1 naive -> v2 taxonomy + look-alike rules).
