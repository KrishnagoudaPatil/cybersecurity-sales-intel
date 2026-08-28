"""Judgement LLM features: account "why now" summary + outreach draft.

Low volume, higher value => STRONG model (Sonnet). Both are traced and both have
deterministic mock fallbacks so the app and demo work offline.
"""
from __future__ import annotations

from app.config import get_settings
from app.llm.client import call
from app.llm.prompts import render
from app.models import AccountScore, Company, OutreachDraft
from app.scoring.icp import COMPLIANCE_REGIME


def _signals_block(score: AccountScore) -> str:
    if not score.signals:
        return "- (no strong signals detected)"
    return "\n".join(f"- {s.type} [{s.source}, conf {s.confidence:.2f}]: {s.evidence}"
                     for s in score.signals)


def _mock_summary(prompt: str) -> str:
    # Deterministic, grounded stand-in built from the prompt's own fields.
    import re
    name = re.search(r"Company:\s*(.+)", prompt)
    industry = re.search(r"Industry:\s*(.+?)\s*\|", prompt)
    n = name.group(1).strip() if name else "This company"
    ind = industry.group(1).strip() if industry else "its sector"
    lead = "a disclosed security incident" if "breach" in prompt.lower() else \
           "recent buying signals" if "signal" in prompt.lower() else "its risk profile"
    return (f"{n} is a strong cybersecurity prospect: as a {ind} operator it faces elevated "
            f"regulatory and data-protection pressure, and {lead} suggest it is evaluating its "
            f"security posture now. Lead with the compliance angle and the specific signal above.")


def _mock_outreach(prompt: str) -> str:
    import re
    name = re.search(r"to\s+(.+?)\.", prompt)
    n = name.group(1).strip() if name else "your team"
    strongest = "your recent security incident" if "breach" in prompt.lower() else \
                "your compliance obligations" if "compliance" in prompt.lower() else \
                "your rapid growth"
    return (f"Subject: Cyber posture for {n.split()[0]}\n"
            f"Hi there,\n\nGiven {strongest}, teams like {n} are reassessing how they detect and "
            f"contain threats before they hit customers. We help Australian mid-market firms close "
            f"that gap fast, mapped to your regulatory obligations.\n\nWorth a 15-minute call next "
            f"week to see if it's relevant?\n\nBest,\nAlex — Sales, CyberShield AU")


def account_summary(company: Company, score: AccountScore) -> str:
    prompt, version = render(
        "account_summary",
        company_name=company.company_name, industry=company.industry,
        employees=company.employee_count, state=company.state,
        regime=COMPLIANCE_REGIME.get(company.industry, "none"),
        signals=_signals_block(score),
    )
    res = call(feature="account_summary", prompt=prompt, prompt_version=version,
               model=get_settings().model_judge, max_tokens=200, temperature=0.3,
               mock_fn=_mock_summary)
    return res.text.strip()


def outreach_draft(company: Company, score: AccountScore) -> OutreachDraft:
    prompt, version = render(
        "outreach_draft",
        company_name=company.company_name, industry=company.industry,
        employees=company.employee_count, state=company.state,
        regime=COMPLIANCE_REGIME.get(company.industry, "none"),
        signals=_signals_block(score),
    )
    model = get_settings().model_judge
    res = call(feature="outreach_draft", prompt=prompt, prompt_version=version,
               model=model, max_tokens=350, temperature=0.5, mock_fn=_mock_outreach)
    text = res.text.strip()
    subject, body = "Quick question", text
    if text.lower().startswith("subject:"):
        first, _, rest = text.partition("\n")
        subject = first.split(":", 1)[1].strip()
        body = rest.strip()
    return OutreachDraft(company_id=company.company_id, subject=subject, body=body,
                         prompt_version=version, model=model)
