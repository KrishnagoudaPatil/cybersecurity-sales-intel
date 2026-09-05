"""Observability: one JSONL row per LLM call.

Schema (stable — depended on by evals and cost reports):
  ts, trace_id, feature, prompt_version, provider, model, mode,
  input, output, decision, input_tokens, output_tokens,
  cost_usd, latency_ms, error

The row is written in exactly one place — client.call's log_call({...}) — so this list
is the single definition of the shape. Adding a field is backward-compatible (readers key
by name); renaming or removing one breaks /cost and the eval harness, so treat those as a
deliberate contract change, not a side effect.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import TRACES_DIR

TRACE_FILE = TRACES_DIR / "llm_calls.jsonl"


def new_trace_id() -> str:
    return uuid.uuid4().hex[:12]


def log_call(record: dict[str, Any]) -> None:
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    record.setdefault("ts", datetime.now(timezone.utc).isoformat())
    record.setdefault("trace_id", new_trace_id())
    with TRACE_FILE.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


class Timer:
    def __enter__(self):
        self._t = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = round((time.perf_counter() - self._t) * 1000, 1)
