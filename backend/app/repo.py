"""Prospect data access, with two interchangeable backends chosen by config.

  local     -> reads data/marts/*.json (published snapshot). Default.
  snowflake -> live queries against the marts.

Both expose the same interface: facets(), worklist(filters), company(domain).
"""
from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache

from app.config import MARTS_DIR, get_settings

# columns exposed on the worklist / detail (kept in sync across both backends)
_NUM = ("total_score", "risk_score", "fit_score", "missing_header_ratio")


class LocalRepo:
    """Serves the published JSON snapshot. Filtering/aggregation done in Python."""

    def __init__(self) -> None:
        cpath, spath = MARTS_DIR / "companies.json", MARTS_DIR / "services.json"
        if not cpath.exists():
            raise FileNotFoundError(
                f"{cpath} not found. Publish it with "
                f"`./.venv-snow/bin/python -m app.export_marts` (from backend/)."
            )
        self.companies = json.loads(cpath.read_text())
        services = json.loads(spath.read_text()) if spath.exists() else []
        self._by_domain = {}
        for s in services:
            self._by_domain.setdefault(s["company_domain"], []).append(s)

    def facets(self) -> dict:
        countries = sorted({c["primary_country"] for c in self.companies if c["primary_country"]})
        bands = sorted({c["size_band"] for c in self.companies if c.get("size_band")})
        tiers = Counter(c["tier"] for c in self.companies)
        return {"countries": countries, "size_bands": bands,
                "tiers": dict(sorted(tiers.items())), "total": len(self.companies)}

    def worklist(self, *, country=None, tier=None, size_band=None,
                 min_score=0.0, limit=100) -> list[dict]:
        rows = []
        for c in self.companies:
            if country and c["primary_country"] != country:
                continue
            if tier and c["tier"] != tier:
                continue
            if size_band and c.get("size_band") != size_band:
                continue
            if (c["total_score"] or 0) < min_score:
                continue
            rows.append(c)
        rows.sort(key=lambda c: c["total_score"] or 0, reverse=True)
        return rows[:limit]

    def company(self, domain: str) -> dict | None:
        c = next((x for x in self.companies if x["company_domain"] == domain), None)
        if not c:
            return None
        return {"company": c, "services": self._by_domain.get(domain, [])}


class SnowflakeRepo:
    """Live queries against the marts. Needs the 3.12 venv + creds + a warehouse."""

    _F = ("company_domain, tier, total_score, risk_score, fit_score, host_count, "
          "service_count, primary_country, total_cves, services_with_cve, "
          "exposed_db_services, exposed_remote_services, eol_services, self_signed_services, "
          "weak_tls_services, expired_cert_services, missing_header_ratio")
    _FCT = "FIRMABLE.DBT_MARTS.FCT_ACCOUNT_SCORE"
    _DIM = "FIRMABLE.DBT_MARTS.DIM_COMPANY"
    _SVC = "FIRMABLE.DBT_INTERMEDIATE.INT_SERVICE_COMPANY"

    def _q(self, sql, params=None):
        from app.snow import connect, rows_as_dicts
        con = connect(); cur = con.cursor()
        try:
            cur.execute(sql, params or {})
            return rows_as_dicts(cur)
        finally:
            cur.close(); con.close()

    def facets(self) -> dict:
        rows = self._q(f"select primary_country, size_band, tier from {self._FCT} "
                       f"join {self._DIM} using (company_domain)")
        return {"countries": sorted({r["primary_country"] for r in rows if r["primary_country"]}),
                "size_bands": sorted({r["size_band"] for r in rows if r["size_band"]}),
                "tiers": dict(sorted(Counter(r["tier"] for r in rows).items())),
                "total": len(rows)}

    def worklist(self, *, country=None, tier=None, size_band=None,
                 min_score=0.0, limit=100) -> list[dict]:
        where, params = ["f.total_score >= %(min_score)s"], {"min_score": min_score}
        if country:
            where.append("f.primary_country = %(country)s"); params["country"] = country
        if tier:
            where.append("f.tier = %(tier)s"); params["tier"] = tier
        if size_band:
            where.append("d.size_band = %(size_band)s"); params["size_band"] = size_band
        params["lim"] = limit
        return self._q(
            f"select {self._F}, d.size_band from {self._FCT} f join {self._DIM} d "
            f"using (company_domain) where {' and '.join(where)} "
            f"order by f.total_score desc limit %(lim)s", params)

    def company(self, domain: str) -> dict | None:
        c = self._q(f"select {self._F}, d.size_band, d.primary_hosting_org, d.distinct_ports "
                    f"from {self._FCT} f join {self._DIM} d using (company_domain) "
                    f"where company_domain = %(d)s", {"d": domain})
        if not c:
            return None
        svc = self._q(
            "select company_domain, ip, port, product, cve_count, has_known_cve, is_eol, "
            "is_self_signed, exposed_database, exposed_remote_access, weak_tls, cert_expired, "
            "is_http, (missing_hsts+missing_csp+missing_xfo+missing_xcto) as missing_headers "
            f"from {self._SVC} where company_domain = %(d)s", {"d": domain})
        return {"company": c[0], "services": svc}


@lru_cache
def get_repo():
    backend = get_settings().data_backend.lower()
    return SnowflakeRepo() if backend == "snowflake" else LocalRepo()
