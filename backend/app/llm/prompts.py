"""Load versioned prompts from the prompts/ directory (files, not inline strings).

Layout:  prompts/<feature>/<version>.txt   e.g. prompts/signal_classification/v2.txt
`ACTIVE` pins which version each feature currently uses, so v1 vs v2 can be compared
by the eval harness. Prompts use Python str.format placeholders.
"""
from __future__ import annotations

from functools import lru_cache

from app.config import PROMPTS_DIR

# Which prompt version is live for each feature. Bump here to promote a new version.
ACTIVE = {
    "signal_classification": "v2",
    "account_summary": "v1",
    "outreach_draft": "v1",
}


@lru_cache
def load_prompt(feature: str, version: str | None = None) -> str:
    version = version or ACTIVE[feature]
    path = PROMPTS_DIR / feature / f"{version}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text()


def render(feature: str, version: str | None = None, **kwargs) -> tuple[str, str]:
    """Return (rendered_prompt, resolved_version)."""
    version = version or ACTIVE[feature]
    template = load_prompt(feature, version)
    return template.format(**kwargs), version
