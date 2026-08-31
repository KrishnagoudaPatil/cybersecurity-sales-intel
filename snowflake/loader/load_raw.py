"""Load raw Shodan NDJSON into Snowflake as VARIANT.

Creates FIRMABLE.RAW.SCANS(v VARIANT), stages the file, and loads it. Designed for the
dev sample now and the full 74GB later (same path; for the full file point at an external
stage / Snowpipe and scale the warehouse — see snowflake/README.md).

Auth: reads SNOWFLAKE_* from the repo .env. MFA-friendly (username_password_mfa) with
token caching, so you approve one push per token lifetime.

Usage:
  python snowflake/loader/load_raw.py data/raw/shodan_sample_1k.jsonl [--truncate]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import snowflake.connector

REPO = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    for line in (REPO / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def connect():
    _load_env()
    kwargs = dict(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        login_timeout=120,
    )
    key_path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
    if key_path:
        # Preferred: key-pair auth — no MFA, works headless in dbt/CI.
        kwargs["private_key_file"] = str((REPO / key_path).resolve())
    else:
        # Fallback: password + TOTP passcode (SNOWFLAKE_PASSCODE) for the first connect.
        kwargs["password"] = os.environ["SNOWFLAKE_PASSWORD"]
        kwargs["authenticator"] = "username_password_mfa"
        kwargs["client_request_mfa_token"] = True
        if os.environ.get("SNOWFLAKE_PASSCODE"):
            kwargs["passcode"] = os.environ["SNOWFLAKE_PASSCODE"]
    return snowflake.connector.connect(**kwargs)


DDL = [
    "create database if not exists FIRMABLE",
    "create schema if not exists FIRMABLE.RAW",
    "create schema if not exists FIRMABLE.DBT",
    "create table if not exists FIRMABLE.RAW.SCANS (v variant)",
    "create or replace file format FIRMABLE.RAW.FF_NDJSON type = json strip_outer_array = false",
    "create stage if not exists FIRMABLE.RAW.STG_SCANS file_format = FIRMABLE.RAW.FF_NDJSON",
]


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: load_raw.py <path-to-ndjson> [--truncate]")
    src = Path(sys.argv[1]).resolve()
    do_truncate = "--truncate" in sys.argv
    if not src.exists():
        sys.exit(f"file not found: {src}")

    con = connect()
    cur = con.cursor()
    try:
        print("Connected. Ensuring database/schema/stage…")
        for stmt in DDL:
            cur.execute(stmt)
        if do_truncate:
            cur.execute("truncate table FIRMABLE.RAW.SCANS")

        print(f"PUT {src.name} -> @STG_SCANS (auto-gzip)…")
        cur.execute(f"put 'file://{src}' @FIRMABLE.RAW.STG_SCANS auto_compress=true overwrite=true")

        print("COPY INTO FIRMABLE.RAW.SCANS…")
        cur.execute(
            "copy into FIRMABLE.RAW.SCANS from @FIRMABLE.RAW.STG_SCANS "
            f"file_format=FIRMABLE.RAW.FF_NDJSON pattern='.*{src.name}.*' on_error='skip_file'"
        )
        for row in cur.fetchall():
            print("  copy:", row)

        cur.execute("select count(*) from FIRMABLE.RAW.SCANS")
        print("Total rows in RAW.SCANS:", cur.fetchone()[0])
    finally:
        cur.close(); con.close()


if __name__ == "__main__":
    main()
