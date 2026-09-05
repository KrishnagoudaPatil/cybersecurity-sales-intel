"""Eval harness for the account_risk_summary ("why now" brief) feature. One command.

Like the outreach eval, the summary is generative, so we measure an **equivalent quality
metric**: does the brief lead with the strongest finding, stay factually grounded (cite the
real risk score, never invent a finding), include a why-now timing rationale, stay
responsible (no leaked IPs), and give the rep an actionable opener. Reuses the same
hand-labelled account set as the outreach eval.

Deterministic mock mode by default (free, reproducible); `--live` measures the routed model.

Usage:
  python evals/summary_eval.py            # deterministic mock mode
  python evals/summary_eval.py --live     # measure the live routed model
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "evals"))

from outreach_eval import IPV4, LEAD_MARKERS, load_labelled  # noqa: E402 — shared helpers

RUNS = ROOT / "evals" / "runs"
RESULTS_MD = ROOT / "evals" / "summary_results.md"

WHY_NOW_MARKERS = ["why now", "in-market", "right now", "today", "this week", "now"]
ACTION_MARKERS = ["opener", "review", "posture", "worth", "call", "lead", "?"]
CHECKS = ["leads_with_strongest", "grounds_risk_score", "has_why_now",
          "no_fabrication", "no_specific_ip", "within_word_limit", "is_actionable"]


def score_summary(row: dict, text: str) -> dict:
    t = text.lower()
    lead = row["expected_lead"]

    leads = True if lead == "generic" else any(m in t for m in LEAD_MARKERS[lead])

    fab_forbidden = []
    if not row.get("total_cves"):
        fab_forbidden.append("cve")
    if not row.get("exposed_db_services"):
        fab_forbidden.append("database")
    if not row.get("eol_services"):
        fab_forbidden += ["end-of-life", "end of life"]
    allowed = set(LEAD_MARKERS.get(lead, []))
    no_fab = not any(p in t for p in fab_forbidden if p not in allowed)

    return {
        "leads_with_strongest": leads,
        "grounds_risk_score": str(int(row["risk_score"])) in text,   # cites the real number
        "has_why_now": any(m in t for m in WHY_NOW_MARKERS),
        "no_fabrication": no_fab,
        "no_specific_ip": not IPV4.search(text),
        "within_word_limit": len(text.split()) <= 120,
        "is_actionable": any(m in t for m in ACTION_MARKERS),
    }


def evaluate(data: list[dict], version: str, limit: int | None = None) -> dict:
    from app.llm.judgement import account_risk_summary
    if limit:
        data = data[:limit]
    rows, errors = [], []
    for ex in data:
        try:
            text = account_risk_summary(ex)
        except Exception as e:  # noqa: BLE001 — a rate-limit/transient error must not kill the run
            errors.append({"company_domain": ex["company_domain"], "error": str(e).splitlines()[0][:140]})
            continue
        checks = score_summary(ex, text)
        rows.append({"company_domain": ex["company_domain"], "expected_lead": ex["expected_lead"],
                     "words": len(text.split()), "checks": checks,
                     "failed": [c for c in CHECKS if not checks[c]]})
    n = len(rows) or 1  # guard div-by-zero when every call errored
    per_check = {c: round(sum(r["checks"][c] for r in rows) / n, 3) for c in CHECKS}
    overall = round(sum(all(r["checks"].values()) for r in rows) / n, 3)
    mean_check = round(sum(per_check.values()) / len(per_check), 3)
    return {"feature": "account_risk_summary", "version": version,
            "ts": datetime.now(timezone.utc).isoformat(), "n": len(rows), "n_errors": len(errors),
            "fully_compliant_rate": overall, "mean_check_pass_rate": mean_check,
            "per_check": per_check, "failures": [r for r in rows if r["failed"]], "errors": errors}


def print_report(res: dict, mode: str) -> None:
    print(f"\n=== Account Risk Summary — Quality Eval ({mode}) ===")
    print(f"Scored accounts: {res['n']}" + (f"  ·  errored (skipped): {res['n_errors']}" if res.get("n_errors") else ""))
    print(f"Fully-compliant briefs: {res['fully_compliant_rate']*100:.1f}%  ·  "
          f"mean per-check pass rate: {res['mean_check_pass_rate']*100:.1f}%\n")
    print(f"  {'check':<22}{'pass rate':>10}")
    for c in CHECKS:
        print(f"  {c:<22}{res['per_check'][c]*100:>9.1f}%")
    if res["failures"]:
        print("\nFailures:")
        for r in res["failures"]:
            print(f"  {r['company_domain']:<22} ({r['expected_lead']}) -> {', '.join(r['failed'])}")


def write_results_md(res: dict, mode: str) -> None:
    labels = {"leads_with_strongest": "leads with strongest finding",
              "grounds_risk_score": "cites the real risk score (grounding)",
              "has_why_now": "includes a why-now timing rationale",
              "no_fabrication": "no fabricated findings",
              "no_specific_ip": "no specific IP (responsible disclosure)",
              "within_word_limit": "<= 120 words",
              "is_actionable": "gives an actionable opener"}
    L = ["# Account Risk Summary — Quality Eval Results", "",
         f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
         f"{res['n']} hand-labelled accounts · {mode} mode._", "",
         "> Feature: a tight \"why now\" sales brief (Risk / Why now / Opener) grounded ONLY in "
         "observed findings. Generative, so we measure an **equivalent quality metric** — "
         "grounding + compliance — rather than precision/recall.", "",
         "> Deterministic **mock** mode by default (free, reproducible); `--live` measures the "
         "routed model. Reuses `evals/labelled_accounts.jsonl` (each account labelled with its "
         "strongest finding).", "",
         f"**Fully-compliant briefs: {res['fully_compliant_rate']*100:.1f}%** · "
         f"mean per-check pass rate: {res['mean_check_pass_rate']*100:.1f}%", "",
         "| quality check | pass rate |", "|---------------|----------:|"]
    for c in CHECKS:
        L.append(f"| {labels[c]} | {res['per_check'][c]*100:.1f}% |")
    L += ["", "## Known weaknesses", ""]
    if res["failures"]:
        for r in res["failures"]:
            L.append(f"- `{r['company_domain']}` ({r['expected_lead']}): failed "
                     f"{', '.join(r['failed'])} ({r['words']} words)")
    else:
        L.append("- No failures on the current labelled set in mock mode — the mock brief is a "
                 "deterministic template, so this validates the *harness*. The informative run "
                 "is `--live` against the routed model. `grounds_risk_score` is a substring "
                 "check; a fuller grounding test would use an LLM-as-judge to confirm each "
                 "claimed finding traces to the input.")
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
    (RUNS / f"account_risk_summary_{args.version}.json").write_text(json.dumps(res, indent=2))
    print_report(res, mode)
    write_results_md(res, mode)
    print(f"\nSaved artifact -> evals/runs/account_risk_summary_{args.version}.json  ·  "
          f"report -> evals/summary_results.md")


if __name__ == "__main__":
    main()
