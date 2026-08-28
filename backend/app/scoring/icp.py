"""Ideal Customer Profile (ICP) for a cybersecurity software vendor, as data.

Kept as an explicit, tunable config object so a sales/RevOps user could adjust
weights without touching logic. This is deliberately DETERMINISTIC: ICP fit must
be auditable and explainable to a rep ("you rank high because you're a regulated
mid-market firm in finance"). No LLM involved.
"""
from __future__ import annotations

# Industries weighted by cyber risk + regulatory pressure + typical willingness to buy.
INDUSTRY_FIT = {
    "Banking & Finance": 1.0,
    "Insurance": 0.95,
    "Hospitals & Health": 1.0,
    "Medical Services": 0.85,
    "Government/Public Sector": 0.95,
    "Utilities/Critical Infra": 1.0,
    "Software & SaaS": 0.8,
    "Data Processing & Hosting": 0.9,
    "Legal Services": 0.8,
    "Accounting": 0.75,
    "Retail (Online)": 0.7,
    "Higher Education": 0.7,
    "Retail (Store)": 0.45,
    "Real Estate": 0.4,
    "Wholesale": 0.35,
    "Manufacturing": 0.4,
}

# Mid-market is the sweet spot: big enough to have budget + data to protect,
# small enough to lack a mature in-house security team.
EMPLOYEE_FIT = {
    "1-9": 0.15,
    "10-49": 0.45,
    "50-199": 0.9,
    "200-499": 1.0,
    "500-999": 0.85,
    "1000+": 0.6,
}

# Regulated verticals carry compliance regimes that force cyber spend.
COMPLIANCE_REGIME = {
    "Banking & Finance": "APRA CPS 234",
    "Insurance": "APRA CPS 234",
    "Hospitals & Health": "Privacy Act / My Health Records",
    "Medical Services": "Privacy Act",
    "Government/Public Sector": "ISM / Essential Eight",
    "Utilities/Critical Infra": "SOCI Act",
    "Retail (Online)": "PCI-DSS",
    "Retail (Store)": "PCI-DSS",
    "Legal Services": "Privacy Act",
    "Accounting": "Privacy Act",
}

# Blend of the two halves of the score. ICP = "should we sell to them at all".
# Intent = "are they in-market right now". Weighted toward intent for prioritisation.
ICP_WEIGHT = 0.45
INTENT_WEIGHT = 0.55

TIER_CUTOFFS = [(75, "A"), (55, "B"), (35, "C")]  # else D
