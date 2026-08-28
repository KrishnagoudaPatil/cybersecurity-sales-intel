"""Generate a schema-faithful synthetic ANZ company dataset.

This stands in for Firmable's real file. Everything downstream reads through
loader.py, so swapping the real dataset in is a one-line change (see loader.py).

Deterministic: seeded RNG => identical output every run => reproducible evals.

Run:  python -m app.data_gen  [--n 600]
Output: data/companies.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from app.config import DATA_DIR
from app.models import Company, EmployeeBand, RevenueBand

SEED = 42

# (anzsic_code, division, industry label, data_sensitivity 0..1, regulated regime)
INDUSTRIES = [
    ("6220", "Financial and Insurance Services", "Banking & Finance", 0.95, "APRA CPS 234"),
    ("6420", "Financial and Insurance Services", "Insurance", 0.9, "APRA CPS 234"),
    ("8401", "Health Care and Social Assistance", "Hospitals & Health", 0.95, "Privacy Act / My Health"),
    ("8511", "Health Care and Social Assistance", "Medical Services", 0.85, "Privacy Act"),
    ("5910", "Information Media and Telecommunications", "Software & SaaS", 0.7, "Privacy Act"),
    ("5921", "Information Media and Telecommunications", "Data Processing & Hosting", 0.8, "Privacy Act"),
    ("4110", "Retail Trade", "Retail (Online)", 0.65, "PCI-DSS"),
    ("4260", "Retail Trade", "Retail (Store)", 0.4, "PCI-DSS"),
    ("7712", "Professional, Scientific and Technical", "Legal Services", 0.75, "Privacy Act"),
    ("6931", "Professional, Scientific and Technical", "Accounting", 0.7, "Privacy Act"),
    ("2211", "Manufacturing", "Manufacturing", 0.3, None),
    ("7000", "Rental, Hiring and Real Estate", "Real Estate", 0.35, "Privacy Act"),
    ("8010", "Education and Training", "Higher Education", 0.6, "Privacy Act"),
    ("7520", "Public Administration and Safety", "Government/Public Sector", 0.9, "ISM / Essential Eight"),
    ("4010", "Wholesale Trade", "Wholesale", 0.3, None),
    ("3600", "Electricity, Gas, Water", "Utilities/Critical Infra", 0.9, "SOCI Act"),
]

STATES = [
    ("NSW", ["Sydney", "Newcastle", "Wollongong"]),
    ("VIC", ["Melbourne", "Geelong", "Ballarat"]),
    ("QLD", ["Brisbane", "Gold Coast", "Cairns"]),
    ("WA", ["Perth", "Fremantle"]),
    ("SA", ["Adelaide"]),
    ("ACT", ["Canberra"]),
    ("TAS", ["Hobart"]),
]

SECURITY_VENDORS = ["CrowdStrike", "SentinelOne", "Okta", "Microsoft Defender", "Palo Alto", "Cloudflare"]
GENERIC_TECH = ["AWS", "Azure", "GCP", "Salesforce", "HubSpot", "Workday", "SAP", "Legacy on-prem", "WordPress"]

NAME_A = ["Coral", "Redgum", "Southern", "Apex", "Meridian", "Harbour", "Outback", "Bluestone",
          "Kanga", "Verdant", "Summit", "Tallow", "Wattle", "Reef", "Pinnacle", "Nimbus"]
NAME_B = ["Financial", "Health", "Digital", "Retail", "Data", "Legal", "Group", "Systems",
          "Logistics", "Partners", "Holdings", "Labs", "Networks", "Care", "Trade", "Energy"]
NAME_C = ["Pty Ltd", "Group", "Australia", "Co", "Ltd"]


def _emp_band(n: int) -> EmployeeBand:
    for hi, band in [(9, EmployeeBand.micro), (49, EmployeeBand.small), (199, EmployeeBand.mid),
                     (499, EmployeeBand.upper_mid), (999, EmployeeBand.large)]:
        if n <= hi:
            return band
    return EmployeeBand.enterprise


def _rev_band(r: int) -> RevenueBand:
    for hi, band in [(1_000_000, RevenueBand.lt1m), (10_000_000, RevenueBand.m1_10),
                     (50_000_000, RevenueBand.m10_50), (200_000_000, RevenueBand.m50_200)]:
        if r < hi:
            return band
    return RevenueBand.gt200


def _abn(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(11))


def _events(rng: random.Random, industry, sensitivity, regime, growth, sec_postings, has_vendor) -> list[str]:
    """Free-text event feed. Signals are intentionally buried in natural language."""
    ev: list[str] = []
    if rng.random() < 0.18:
        ev.append(rng.choice([
            "Reported a data breach affecting customer records last quarter.",
            "Disclosed a ransomware incident that disrupted operations for three days.",
            "Notified the OAIC of an eligible data breach involving personal information.",
            "Customer data exposed after a third-party vendor was compromised.",
        ]))
    if growth > 25:
        ev.append(rng.choice([
            f"Headcount grew {int(growth)}% year-on-year after strong demand.",
            f"Rapid expansion — team up {int(growth)}% in 12 months across offices.",
        ]))
    if sec_postings > 0:
        ev.append(rng.choice([
            f"Currently hiring for {sec_postings} security-related roles including a Head of Security.",
            f"Advertising {sec_postings} openings in IT security and compliance.",
        ]))
    if rng.random() < 0.3:
        ev.append(rng.choice([
            "Announced a migration of core systems to the cloud.",
            "Rolling out a company-wide move from on-prem to AWS.",
            "Completed a digital transformation program expanding online services.",
        ]))
    if rng.random() < 0.15:
        ev.append(rng.choice([
            "Appointed a new Chief Information Officer.",
            "Named a new CTO to lead technology strategy.",
            "New Head of IT joined from a major bank.",
        ]))
    if regime and rng.random() < 0.25:
        ev.append(f"Facing tighter {regime} compliance obligations this financial year.")
    if rng.random() < 0.2:
        ev.append(rng.choice([
            "Closed a Series B funding round to accelerate growth.",
            "Secured new investment to expand into new markets.",
        ]))
    if not ev:
        ev.append(rng.choice([
            "Published its quarterly business update.",
            "Opened a new office to serve regional customers.",
            "Launched a new product line for existing customers.",
        ]))
    return ev


def generate(n: int = 600) -> list[Company]:
    rng = random.Random(SEED)
    companies: list[Company] = []
    for i in range(n):
        anzsic, division, industry, sensitivity, regime = rng.choice(INDUSTRIES)
        state, cities = rng.choice(STATES)
        city = rng.choice(cities)

        emp = int(rng.choice([
            rng.randint(1, 9), rng.randint(10, 49), rng.randint(50, 199),
            rng.randint(50, 199), rng.randint(200, 499), rng.randint(200, 499),
            rng.randint(500, 999), rng.randint(1000, 6000),
        ]))
        revenue = emp * rng.randint(90_000, 320_000)
        growth = round(rng.choice([rng.uniform(-5, 10), rng.uniform(10, 30), rng.uniform(30, 90)]), 1)

        has_vendor = rng.random() < (0.65 if emp >= 500 else 0.30)
        tech = rng.sample(GENERIC_TECH, k=rng.randint(2, 4))
        if has_vendor:
            tech.append(rng.choice(SECURITY_VENDORS))
        sec_postings = rng.choice([0, 0, 0, 1, 2, rng.randint(1, 5)]) if emp >= 50 else 0

        name = f"{rng.choice(NAME_A)} {rng.choice(NAME_B)} {rng.choice(NAME_C)}"
        events = _events(rng, industry, sensitivity, regime, growth, sec_postings, has_vendor)

        companies.append(Company(
            company_id=f"AU{i:05d}",
            abn=_abn(rng),
            company_name=name,
            website=f"https://www.{name.split()[0].lower()}{name.split()[1].lower()}.com.au",
            anzsic_code=anzsic,
            anzsic_division=division,
            industry=industry,
            employee_count=emp,
            employee_band=_emp_band(emp),
            annual_revenue_aud=revenue,
            revenue_band=_rev_band(revenue),
            founded_year=rng.randint(1975, 2023),
            state=state,
            city=city,
            tech_stack=tech,
            has_security_vendor=has_vendor,
            headcount_growth_12m_pct=growth,
            security_job_postings=sec_postings,
            recent_events=events,
        ))
    return companies


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    args = ap.parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "companies.jsonl"
    rows = generate(args.n)
    with out.open("w") as f:
        for c in rows:
            f.write(c.model_dump_json() + "\n")
    print(f"Wrote {len(rows)} companies -> {out}")


if __name__ == "__main__":
    main()
