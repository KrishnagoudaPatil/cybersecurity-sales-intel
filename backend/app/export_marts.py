"""Publish the Snowflake marts to a local JSON snapshot the `local` backend serves.

Run in the 3.12 venv (has snowflake-connector):
    ./.venv-snow/bin/python -m app.export_marts     # from backend/, or set PYTHONPATH

Writes data/marts/companies.json and data/marts/services.json. For the full 74GB dataset
these can get large — that is exactly when you switch the app to DATA_BACKEND=snowflake
(live queries) instead of snapshotting. A `--limit-services` cap keeps the snapshot lean.
"""
from __future__ import annotations

import argparse
import json

from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from app.snow import connect, rows_as_dicts

def _json_default(o):
    if isinstance(o, Decimal):
        f = float(o); return int(f) if f.is_integer() else f
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return str(o)


MARTS_DIR = Path(__file__).resolve().parents[2] / "data" / "marts"

COMPANIES_SQL = """
select f.company_domain, f.tier, f.total_score, f.risk_score, f.fit_score,
       f.host_count, f.service_count, f.primary_country,
       f.total_cves, f.services_with_cve, f.exposed_db_services, f.exposed_remote_services,
       f.eol_services, f.self_signed_services, f.weak_tls_services, f.expired_cert_services,
       f.missing_header_ratio,
       d.company_name, d.attribution_confidence,
       d.size_band, d.primary_hosting_org, d.distinct_ports, d.last_seen
from FIRMABLE.DBT_MARTS.FCT_ACCOUNT_SCORE f
join FIRMABLE.DBT_MARTS.DIM_COMPANY d using (company_domain)
order by f.total_score desc
"""

SERVICES_SQL = """
select company_domain, ip, port, product,
       cve_count, has_known_cve, is_eol, is_self_signed,
       exposed_database, exposed_remote_access, weak_tls, cert_expired, is_http,
       (missing_hsts + missing_csp + missing_xfo + missing_xcto) as missing_headers
from FIRMABLE.DBT_INTERMEDIATE.INT_SERVICE_COMPANY
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-services", type=int, default=0, help="0 = all")
    args = ap.parse_args()

    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    con = connect(); cur = con.cursor()
    try:
        cur.execute(COMPANIES_SQL)
        companies = rows_as_dicts(cur)
        (MARTS_DIR / "companies.json").write_text(json.dumps(companies, default=_json_default))

        sql = SERVICES_SQL + (f" limit {args.limit_services}" if args.limit_services else "")
        cur.execute(sql)
        services = rows_as_dicts(cur)
        (MARTS_DIR / "services.json").write_text(json.dumps(services, default=_json_default))
    finally:
        cur.close(); con.close()
    print(f"Published {len(companies)} companies, {len(services)} services -> {MARTS_DIR}")


if __name__ == "__main__":
    main()
