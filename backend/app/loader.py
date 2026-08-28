"""Dataset loader — the single swap point between synthetic and real data.

To use Firmable's real file instead of the synthetic one:
  1. Drop it at data/companies.jsonl (or point DATASET_PATH at it), and
  2. adjust `from_raw()` to map the real column names onto the Company model.
Nothing else downstream changes.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.config import DATA_DIR
from app.models import Company

DATASET_PATH = DATA_DIR / "companies.jsonl"


def load_companies(path: Path | None = None) -> list[Company]:
    p = path or DATASET_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Run `python -m app.data_gen` to generate the synthetic dataset."
        )
    out: list[Company] = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(Company.model_validate_json(line))
    return out


def from_raw(row: dict) -> Company:
    """Map a raw external record onto Company. Adjust field names for the real file."""
    return Company.model_validate(row)
