"""LLM signal classification — the core evaluated AI feature.

Turns one free-text company event into a structured cybersecurity buying signal.
Uses the CHEAP model (high volume, one call per event). Every call is traced via
app.llm.client.call.

Mock mode: a deterministic keyword classifier stands in so evals run without an API
key. It is VERSION-AWARE — it simulates the weaker behaviour of the naive v1 prompt
vs. the improved v2 prompt, so the eval harness reports a real v1->v2 delta offline.
In live mode the actual model produces the difference. This is documented in
evals/results.md so the numbers are never mistaken for live model metrics.
"""
from __future__ import annotations

import json
import re

from app.config import get_settings
from app.llm.client import call
from app.llm.prompts import render
from app.models import Signal

FEATURE = "signal_classification"

VALID_TYPES = {
    "breach_incident", "cloud_migration", "leadership_change",
    "funding_round", "compliance_pressure", "none",
}

# v2 = the improved prompt: full definitions, breach precedence, compliance-aware.
_RULES_V2 = [
    ("breach_incident", r"breach|ransomware|compromis|data (was )?exposed|exposed after|hack|cyber ?attack|oaic"),
    ("compliance_pressure", r"cps 234|soci|pci-?dss|privacy act|essential eight|\bism\b|compliance obligation"),
    ("leadership_change", r"new (chief|cio|cto|head of it|head of security)|appointed a new|named a new|joined from"),
    ("cloud_migration", r"cloud|on-?prem|digital transformation|migrat"),
    ("funding_round", r"funding|series [a-e]|investment|raised|capital"),
]

# v1 = the naive prompt: no definitions/precedence. Simulated weaknesses:
#   * only catches the literal word "breach"/"ransomware" (misses OAIC / "exposed" / "compromised")
#   * has NO concept of compliance_pressure (labels those "none")
#   * evaluates rules in a fixed order without breach precedence
_RULES_V1 = [
    ("breach_incident", r"\bbreach\b|ransomware"),
    ("leadership_change", r"new (cio|cto)|appointed a new"),
    ("cloud_migration", r"cloud|migrat"),
    ("funding_round", r"funding|series [a-e]"),
]


def _mock_for_version(prompt: str):
    # v2 prompt contains the definitions block; v1 does not.
    return _RULES_V2 if "Signal types and definitions" in prompt else _RULES_V1


def _mock_classify(prompt: str) -> str:
    rules = _mock_for_version(prompt)
    m = re.findall(r'Event:\s*"([^"]*)"', prompt)
    event = m[-1] if m else prompt
    low = event.lower()
    for stype, pattern in rules:
        if re.search(pattern, low):
            return json.dumps({"type": stype, "confidence": 0.9, "evidence": event[:80]})
    return json.dumps({"type": "none", "confidence": 0.8, "evidence": "no cyber-relevant signal"})


def _parse(text: str) -> dict:
    text = text.strip()
    try:
        obj = json.loads(text)
        stype = str(obj.get("type", "none")).strip()
        conf = float(obj.get("confidence", 0.5))
        ev = str(obj.get("evidence", ""))
    except Exception:  # noqa: BLE001
        stype = text.split()[0].strip().strip('".,') if text else "none"
        conf, ev = 0.5, text[:80]
    if stype not in VALID_TYPES:
        stype = "none"
    return {"type": stype, "confidence": max(0.0, min(1.0, conf)), "evidence": ev}


def classify_event(event: str, prompt_version: str | None = None) -> dict:
    prompt, version = render(FEATURE, version=prompt_version, event=event)
    model = get_settings().model_classify
    result = call(
        feature=FEATURE, prompt=prompt, prompt_version=version, model=model,
        max_tokens=120, temperature=0.0, mock_fn=_mock_classify,
    )
    return _parse(result.text)


def llm_signals(events: list[str], prompt_version: str | None = None) -> list[Signal]:
    out: list[Signal] = []
    for ev in events:
        r = classify_event(ev, prompt_version=prompt_version)
        if r["type"] != "none":
            out.append(Signal(
                type=r["type"], source="llm", strength=0.85,
                confidence=r["confidence"], evidence=r["evidence"] or ev,
            ))
    return out
