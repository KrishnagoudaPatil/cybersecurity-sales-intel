"""Single choke-point for every LLM call.

Guarantees that EVERY call is traced (request, response, model, prompt version,
latency, cost, decision) — you cannot call the model and forget to log it.

Runs in one of two modes:
  * live  — real Anthropic API (when ANTHROPIC_API_KEY is set)
  * mock  — deterministic, offline stand-in so evals, tracing and cost all work
            without a key. Mock responses are keyword-driven, not random, so eval
            numbers are reproducible in CI.
"""
from __future__ import annotations

import json
from typing import Callable, Optional

from app.config import get_settings
from app.llm.cost import cost_usd, estimate_tokens
from app.llm.tracing import Timer, log_call, new_trace_id


class LLMResult:
    def __init__(self, text: str, model: str, mode: str,
                 input_tokens: int, output_tokens: int, cost: float, latency_ms: float):
        self.text = text
        self.model = model
        self.mode = mode
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost = cost
        self.latency_ms = latency_ms


def _anthropic_call(model: str, prompt: str, max_tokens: int, temperature: float):
    import anthropic  # imported lazily so mock mode needs no SDK network setup
    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    return text, resp.usage.input_tokens, resp.usage.output_tokens


def call(
    *,
    feature: str,
    prompt: str,
    prompt_version: str,
    model: str,
    max_tokens: int = 512,
    temperature: float = 0.0,
    mock_fn: Optional[Callable[[str], str]] = None,
    decision: object = None,
) -> LLMResult:
    """Make a traced LLM call. `mock_fn(prompt)->str` supplies the offline response."""
    settings = get_settings()
    trace_id = new_trace_id()
    error = None
    text = ""

    with Timer() as t:
        try:
            if settings.llm_live:
                text, in_tok, out_tok = _anthropic_call(model, prompt, max_tokens, temperature)
                mode = "live"
            else:
                text = mock_fn(prompt) if mock_fn else ""
                mode = "mock"
                in_tok, out_tok = estimate_tokens(prompt), estimate_tokens(text)
        except Exception as e:  # noqa: BLE001 — trace the failure, then re-raise
            error = f"{type(e).__name__}: {e}"
            mode = "error"
            in_tok = estimate_tokens(prompt)
            out_tok = 0

    cost = cost_usd(model, in_tok, out_tok)
    log_call({
        "trace_id": trace_id,
        "feature": feature,
        "prompt_version": prompt_version,
        "model": model,
        "mode": mode,
        "input": prompt,
        "output": text,
        "decision": decision if decision is not None else _safe_json(text),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": cost,
        "latency_ms": t.ms,
        "error": error,
    })
    if error:
        raise RuntimeError(error)
    return LLMResult(text, model, mode, in_tok, out_tok, cost, t.ms)


def _safe_json(text: str):
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return None
