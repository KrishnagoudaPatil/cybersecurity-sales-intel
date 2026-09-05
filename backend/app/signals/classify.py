"""LLM service classification — the core EVALUATED AI feature (real-data version).

Reads a raw service `banner` (free text) and classifies the service into one category.
This is the genuine rule-vs-LLM boundary on the Shodan data: the dbt SQL rules classify
a service when structured fields (product / cpe / port / tags) are clear; the LLM reads
the messy banner when they are absent. Every call is traced via app.llm.client.call.

Mock mode: a deterministic, VERSION-AWARE keyword classifier stands in so evals run with
no API key. v1 simulates a naive prompt (no network-infra knowledge); v2 simulates the
improved prompt. This yields a real v1->v2 delta offline; live mode uses the real model.
"""
from __future__ import annotations

import json
import re

from app.config import get_settings
from app.llm.client import call
from app.llm.prompts import render

FEATURE = "service_classification"

CLASSES = {"web", "remote_access", "database", "mail", "network_infra", "unknown"}

# v2 = improved prompt: full taxonomy incl. network_infra + look-alike handling.
# Ordered by precedence.
_RULES_V2 = [
    ("unknown",        r"^ssl error|unrecognized_name|^\W*$"),
    ("web",            r"^http/"),
    ("mail",           r"esmtp|\bsmtp\b|^\+ok|\bimap\b|dovecot"),
    ("remote_access",  r"^ssh-2\.0|^\bftp\b|220.*\bftp\b|ansi color|^rfb |telnet"),
    ("database",       r"mysql|mariadb|mongodb|redis|postgres|mssql|\bsql server\b"),
    ("network_infra",  r"rtsp/|sip/2\.0|powerdns|resolver|\bbind\b|named|ntp |stratum|pptp|cisco|portmap|\bsmb\b|dns"),
]

# v1 = naive prompt: only the "obvious" services, NO network-infra concept, weak on
# POP mail / telnet / bare tokens (simulated weaknesses).
_RULES_V1 = [
    ("web",            r"http"),
    ("remote_access",  r"ssh"),
    ("database",       r"mysql|mariadb"),
    ("mail",           r"smtp"),
]


def _rules_for(prompt: str):
    return _RULES_V2 if "Categories (choose the single best)" in prompt else _RULES_V1


def _mock_classify(prompt: str) -> str:
    rules = _rules_for(prompt)
    m = re.findall(r'Banner:\s*"([^"]*)"', prompt)
    banner = (m[-1] if m else prompt).lower()
    for cat, pattern in rules:
        if re.search(pattern, banner):
            return json.dumps({"category": cat, "confidence": 0.9})
    return json.dumps({"category": "unknown", "confidence": 0.6})


def _parse(text: str) -> dict:
    text = text.strip()
    try:
        obj = json.loads(text)
        cat = str(obj.get("category", "unknown")).strip()
        conf = float(obj.get("confidence", 0.5))
    except Exception:  # noqa: BLE001 — v1 may return a bare label
        cat = text.split()[0].strip().strip('".,').lower() if text else "unknown"
        conf = 0.5
    if cat not in CLASSES:
        cat = "unknown"
    return {"category": cat, "confidence": max(0.0, min(1.0, conf))}


def classify_banner(banner: str, prompt_version: str | None = None) -> dict:
    """Classify one service banner. Returns {category, confidence}. Traced + costed."""
    prompt, version = render(FEATURE, version=prompt_version, banner=banner)
    result = call(
        feature=FEATURE, prompt=prompt, prompt_version=version,
        model=get_settings().model_for("classify"), max_tokens=40, temperature=0.0,
        mock_fn=_mock_classify,
    )
    return _parse(result.text)
