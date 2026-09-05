"""Judgement LLM features on real data: account risk "why now" + outreach draft.

Both consume a `company` findings dict shaped like a FCT_ACCOUNT_SCORE row (so they plug
straight into the Snowflake-backed app). Low volume, higher value => STRONG model. Both
are traced and both have deterministic mock fallbacks so the app/demo work offline.
"""
from __future__ import annotations

from app.config import get_settings
from app.llm.client import call
from app.llm.prompts import render


def _findings_block(c: dict) -> str:
    lines = []
    order = [
        ("total_cves", "known CVE(s) across exposed services"),
        ("exposed_db_services", "database(s) exposed to the internet"),
        ("exposed_remote_services", "remote-access service(s) exposed (RDP/telnet/VNC/FTP)"),
        ("eol_services", "end-of-life software service(s)"),
        ("self_signed_services", "self-signed TLS certificate(s)"),
        ("weak_tls_services", "service(s) offering weak/legacy TLS"),
        ("expired_cert_services", "expired TLS certificate(s)"),
    ]
    for key, label in order:
        v = c.get(key) or 0
        if v:
            lines.append(f"- {v} {label}")
    ratio = c.get("missing_header_ratio") or 0
    if ratio:
        lines.append(f"- {round(ratio*100)}% of key HTTP security headers missing")
    return "\n".join(lines) or "- no significant exposure detected"


def account_risk_summary(company: dict) -> str:
    prompt, version = render(
        "account_risk_summary",
        company_domain=company["company_domain"],
        country=company.get("primary_country", "?"),
        host_count=company.get("host_count", 0),
        service_count=company.get("service_count", 0),
        findings=_findings_block(company),
    )
    res = call(feature="account_risk_summary", prompt=prompt, prompt_version=version,
               model=get_settings().model_for("judge"), max_tokens=200, temperature=0.3,
               mock_fn=lambda p: _mock_summary(company))
    return res.text.strip()


def outreach_draft(company: dict) -> dict:
    prompt, version = render(
        "outreach_draft",
        company_domain=company["company_domain"],
        findings=_findings_block(company),
    )
    model = get_settings().model_for("judge")
    res = call(feature="outreach_draft", prompt=prompt, prompt_version=version,
               model=model, max_tokens=320, temperature=0.5,
               mock_fn=lambda p: _mock_outreach(company))
    text = res.text.strip()
    subject, body = "Quick security question", text
    if text.lower().startswith("subject:"):
        first, _, rest = text.partition("\n")
        subject = first.split(":", 1)[1].strip()
        body = rest.strip()
    return {"company_domain": company["company_domain"], "subject": subject,
            "body": body, "prompt_version": version, "model": model}


def outreach_draft_for(domain: str) -> dict:
    """Draft an opener straight from a domain, fetching the findings row via the
    configured data backend (published snapshot by default, live Snowflake when
    DATA_BACKEND=snowflake). Saves the caller from hand-assembling a findings dict.
    """
    from app.repo import get_repo  # lazy: avoids import cost when unused
    rec = get_repo().company(domain)
    if not rec:
        raise ValueError(f"no account found for domain {domain!r}")
    return outreach_draft(rec["company"])


def _lead_finding(c: dict) -> str:
    if (c.get("total_cves") or 0) > 0:
        return f"{c['total_cves']} known CVEs on your public-facing services"
    if (c.get("exposed_db_services") or 0) > 0:
        return "a database exposed directly to the internet"
    if (c.get("eol_services") or 0) > 0:
        return "end-of-life software still running publicly"
    if (c.get("missing_header_ratio") or 0) >= 0.5:
        return "missing security headers across your web services"
    return "gaps in your external security posture"


def _mock_summary(c: dict) -> str:
    # Mirrors the v2 prompt's three-line "why now" brief (Risk / Why now / Opener) so the
    # offline stand-in is faithful to what the live model is asked to produce.
    lead = _lead_finding(c)
    return (f"Risk: {c['company_domain']} shows {lead} (risk score "
            f"{c.get('risk_score','?')}/100 across {c.get('host_count',0)} hosts).\n"
            f"Why now: internet-facing exposure like this is exactly what attackers scan for, "
            f"which puts them in-market for security help right now.\n"
            f"Opener: I noticed {lead} on {c['company_domain']}'s public footprint — worth a "
            f"quick external posture review this week?")


def _mock_outreach(c: dict) -> str:
    lead = _lead_finding(c)
    name = c["company_domain"].split(".")[0]
    return (f"Subject: {name}: security exposure noticed\n"
            f"Hi there,\n\nWhile researching {c['company_domain']} we noticed {lead}. Teams often can't see these external exposures "
            f"from the inside. We help close them fast, mapped to your risk.\n\n"
            f"Worth a quick 15-minute external posture review next week?\n\n"
            f"Best,\nAlex — CyberShield")
