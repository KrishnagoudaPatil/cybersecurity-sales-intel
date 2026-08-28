"""Token + cost accounting.

Pricing is kept as an explicit, editable table (USD per 1M tokens). Verify against
current Anthropic pricing before relying on absolute figures — the point is the
*method* (per-task model routing + tokens x volume x frequency), documented in
docs/architecture.md. Cheap model for high-volume classification, strong model for
low-volume judgement.
"""
from __future__ import annotations

# USD per 1,000,000 tokens (input, output).
PRICING = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
}
_DEFAULT = (1.00, 5.00)


def estimate_tokens(text: str) -> int:
    """Rough token estimate for mock mode / pre-flight (≈3.8 chars/token)."""
    if not text:
        return 0
    return max(1, round(len(text) / 3.8))


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    in_rate, out_rate = PRICING.get(model, _DEFAULT)
    return round(in_rate * input_tokens / 1e6 + out_rate * output_tokens / 1e6, 6)
