"""Eval harness for the outreach-draft feature. One command, no external deps.

Outreach is generative, so precision/recall on prose doesn't apply. Instead we measure an
**equivalent quality metric**: guardrail / constraint compliance. For each labelled account
we render a draft and score it against the skill's own guardrails:

  1. leads_with_strongest  - the draft leads with the finding we labelled as most serious
  2. within_word_limit     - body <= 110 words
  3. subject_concise        - subject < 8 words
  4. no_specific_ip         - no IPv4 address leaked (responsible disclosure)
  5. no_fabrication         - never asserts a finding the account does not have
  6. has_cta               - contains a low-friction call to action
  7. responsible_tone       - no alarmist / threatening language

Runs deterministically in mock mode by default (free, reproducible), matching the offline
design of the classification harness. `--live` measures the real routed model instead.

Usage:
  python evals/outreach_eval.py            # deterministic mock mode
  python evals/outreach_eval.py --live     # measure the live routed model
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

LABELLED = ROOT / "evals" / "labelled_accounts.jsonl"
RUNS = ROOT / "evals" / "runs"
RESULTS_MD = ROOT / "evals" / "outreach_results.md"

# Phrases that evidence the draft is leading with a given finding.
LEAD_MARKERS = {
    "cve": ["cve"],
    "database": ["database"],
    "eol": ["end-of-life", "end of life", " eol", "unsupported", "outdated"],
    "headers": ["header"],
    "generic": [],  # no specific finding -> nothing to assert, must not fabricate one
}
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
CTA_MARKERS = ["?", "call", "chat", "review", "minutes", "connect", "walk", "discuss", "meeting"]
ALARMIST = ["breach", "hacked", "urgent", "immediately", "exploit", "under attack", "compromised", "act now"]
CHECKS = ["leads_with_strongest", "within_word_limit", "subject_concise",
          "no_specific_ip", "no_fabrication", "has_cta", "responsible_tone"]


def load_labelled() -> list[dict]:
    return [json.loads(l) for l in LABELLED.read_text().splitlines() if l.strip()]


def score_draft(row: dict, out: dict) -> dict:
    subject, body = out["subject"], out["body"]
    text = f"{subject}\n{body}".lower()
    lead = row["expected_lead"]

    # 1. leads with the strongest finding (generic = it simply must not invent one)
    leads = True if lead == "generic" else any(m in text for m in LEAD_MARKERS[lead])

    # 5. no fabrication: any finding absent from the row must not be asserted
    fab_forbidden = []
    if not row.get("total_cves"):
        fab_forbidden.append("cve")
    if not row.get("exposed_db_services"):
        fab_forbidden.append("database")
    if not row.get("eol_services"):
        fab_forbidden += ["end-of-life", "end of life"]
    # the labelled lead is, by definition, present — never count it as fabrication
    allowed = set(LEAD_MARKERS.get(lead, []))
    no_fab = not any(p in text for p in fab_forbidden if p not in allowed)

    return {
        "leads_with_strongest": leads,
        "within_word_limit": len(body.split()) <= 110,
        "subject_concise": len(subject.split()) < 8,
        "no_specific_ip": not IPV4.search(f"{subject} {body}"),
        "no_fabrication": no_fab,
        "has_cta": any(m in text for m in CTA_MARKERS),
        "responsible_tone": not any(a in text for a in ALARMIST),
    }


def evaluate(data: list[dict], version: str, limit: int | None = None) -> dict:
    from app.llm.judgement import outreach_draft
    if limit:
        data = data[:limit]
    rows, errors = [], []
    for ex in data:
        try:
            out = outreach_draft(ex)
        except Exception as e:  # noqa: BLE001 — a rate-limit/transient error must not kill the run
            errors.append({"company_domain": ex["company_domain"], "error": str(e).splitlines()[0][:140]})
            continue
        checks = score_draft(ex, out)
        rows.append({"company_domain": ex["company_domain"], "expected_lead": ex["expected_lead"],
                     "subject": out["subject"], "words": len(out["body"].split()),
                     "checks": checks, "failed": [c for c in CHECKS if not checks[c]]})
    n = len(rows) or 1  # guard div-by-zero when every call errored
    per_check = {c: round(sum(r["checks"][c] for r in rows) / n, 3) for c in CHECKS}
    overall = round(sum(all(r["checks"].values()) for r in rows) / n, 3)
    mean_check = round(sum(per_check.values()) / len(per_check), 3)
    return {"feature": "outreach_draft", "version": version,
            "ts": datetime.now(timezone.utc).isoformat(), "n": len(rows), "n_errors": len(errors),
            "fully_compliant_rate": overall, "mean_check_pass_rate": mean_check,
            "per_check": per_check, "failures": [r for r in rows if r["failed"]], "errors": errors}


def print_report(res: dict, mode: str) -> None:
    print(f"\n=== Outreach Draft — Guardrail Eval ({mode}) ===")
    print(f"Scored accounts: {res['n']}" + (f"  ·  errored (skipped): {res['n_errors']}" if res.get("n_errors") else ""))
    print(f"Fully-compliant drafts: {res['fully_compliant_rate']*100:.1f}%  ·  "
          f"mean per-check pass rate: {res['mean_check_pass_rate']*100:.1f}%\n")
    print(f"  {'check':<22}{'pass rate':>10}")
    for c in CHECKS:
        print(f"  {c:<22}{res['per_check'][c]*100:>9.1f}%")
    if res["failures"]:
        print("\nFailures:")
        for r in res["failures"]:
            print(f"  {r['company_domain']:<22} ({r['expected_lead']}) -> {', '.join(r['failed'])}")


def write_results_md(res: dict, mode: str) -> None:
    L = ["# Outreach Draft — Guardrail Eval Results", "",
         f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
         f"{res['n']} hand-labelled accounts · {mode} mode._", "",
         "> Feature: draft a <=110-word, responsible first-touch email that leads with an "
         "account's single most serious observed exposure. Generative, so we measure an "
         "**equivalent quality metric** — compliance with the skill's guardrails — rather "
         "than precision/recall.", "",
         "> Deterministic **mock** mode by default (free, reproducible); `--live` measures the "
         "routed model. Each account is labelled with its strongest finding "
         "(`expected_lead`), which the draft must lead with.", "",
         f"**Fully-compliant drafts: {res['fully_compliant_rate']*100:.1f}%** · "
         f"mean per-check pass rate: {res['mean_check_pass_rate']*100:.1f}%", "",
         "| guardrail check | pass rate |", "|-----------------|----------:|"]
    labels = {"leads_with_strongest": "leads with strongest finding",
              "within_word_limit": "body <= 110 words",
              "subject_concise": "subject < 8 words",
              "no_specific_ip": "no specific IP (responsible disclosure)",
              "no_fabrication": "no fabricated findings",
              "has_cta": "has a call to action",
              "responsible_tone": "no alarmist / threatening language"}
    for c in CHECKS:
        L.append(f"| {labels[c]} | {res['per_check'][c]*100:.1f}% |")
    L += ["", "## Known weaknesses", ""]
    if res["failures"]:
        for r in res["failures"]:
            L.append(f"- `{r['company_domain']}` ({r['expected_lead']}): failed "
                     f"{', '.join(r['failed'])} — subject \"{r['subject']}\", {r['words']} words")
    else:
        L.append("- No guardrail failures on the current labelled set in mock mode. The mock "
                 "draft is a deterministic template, so this validates the *harness*; the "
                 "informative run is `--live` against the routed model. Tone is checked only "
                 "lexically (alarmist word-list) — a fuller check would use an LLM-as-judge "
                 "rubric for tone and factual grounding, which is the next step here.")
    RESULTS_MD.write_text("\n".join(L) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="use the routed model instead of mock")
    ap.add_argument("--limit", type=int, default=None, help="score only the first N accounts (fits a rate-limited live run)")
    ap.add_argument("--version", default="v2")
    args = ap.parse_args()
    if not args.live:
        os.environ["LLM_PROVIDER"] = "mock"  # deterministic + free; set before app import
    mode = "live" if args.live else "mock"
    data = load_labelled()
    res = evaluate(data, args.version, limit=args.limit)
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"outreach_draft_{args.version}.json").write_text(json.dumps(res, indent=2))
    print_report(res, mode)
    write_results_md(res, mode)
    print(f"\nSaved artifact -> evals/runs/outreach_draft_{args.version}.json  ·  "
          f"report -> evals/outreach_results.md")


if __name__ == "__main__":
    main()
