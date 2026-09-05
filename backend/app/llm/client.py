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
import time
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


# Gemini flash models are "thinking" models: they spend output tokens on internal
# reasoning BEFORE the visible answer. With a tight max_output_tokens the thinking eats
# the whole budget and the answer is truncated to garbage, so give generous headroom.
_GEMINI_THINKING_HEADROOM = 2048


def _gemini_call(model: str, prompt: str, max_tokens: int, temperature: float):
    from google import genai  # lazy: only needed when the gemini provider is active
    from google.genai import types
    client = genai.Client(api_key=get_settings().gemini_api_key)
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens + _GEMINI_THINKING_HEADROOM,
            temperature=temperature),
    )
    text = (resp.text or "").strip()
    um = getattr(resp, "usage_metadata", None)
    in_tok = getattr(um, "prompt_token_count", None) or estimate_tokens(prompt)
    # thinking tokens are billed as output too — count them so /cost is honest
    answer_tok = getattr(um, "candidates_token_count", None) or estimate_tokens(text)
    thoughts_tok = getattr(um, "thoughts_token_count", None) or 0
    return text, in_tok, answer_tok + thoughts_tok


_PROVIDERS = {"anthropic": _anthropic_call, "gemini": _gemini_call}

# Providers (esp. Gemini's free tier) throw intermittent 503/429 under load. These are
# safe to retry — the request never landed — so a short backoff hides the hiccup instead
# of failing the user's click.
_TRANSIENT = ("503", "429", "500", "unavailable", "overloaded",
              "rate limit", "resource_exhausted", "try again")


def _is_transient(err: Exception) -> bool:
    msg = str(err).lower()
    return any(sig in msg for sig in _TRANSIENT)


def _call_with_retry(provider, model, prompt, max_tokens, temperature, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return _PROVIDERS[provider](model, prompt, max_tokens, temperature)
        except Exception as e:  # noqa: BLE001
            last = e
            if i < attempts - 1 and _is_transient(e):
                time.sleep(0.8 * (2 ** i))   # 0.8s, then 1.6s
                continue
            raise
    raise last  # unreachable, but keeps type checkers happy


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
    provider = settings.provider
    trace_id = new_trace_id()
    error = None
    text = ""

    with Timer() as t:
        try:
            if provider in _PROVIDERS:
                text, in_tok, out_tok = _call_with_retry(provider, model, prompt, max_tokens, temperature)
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
        "provider": provider,
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
