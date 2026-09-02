"""Shared Snowflake connection helper (key-pair auth). Used by the export script and
the live (snowflake) data backend. Reads SNOWFLAKE_* from the repo .env.

Deliberately has NO app.config/pydantic dependency, so the export script can run in the
Snowflake (3.12) venv without the app's web dependencies installed.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    envf = REPO_ROOT / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)


def connect():
    import snowflake.connector  # lazy: only needed for the snowflake backend/export
    _load_env()
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "FIRMABLE"),
        private_key_file=str((REPO_ROOT / os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]).resolve()),
    )


def rows_as_dicts(cur) -> list[dict]:
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
