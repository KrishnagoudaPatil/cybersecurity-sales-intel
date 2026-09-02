"""Eval harness for service-banner classification. One command, no external deps.

Runs the classifier over the hand-labelled banner set for one or more prompt versions,
computes per-class precision/recall/F1 + macro-F1 + accuracy, prints a v1-vs-v2
comparison, saves a JSON artifact per version, and regenerates evals/results.md.

Usage:
  python evals/run.py                 # compare v1 vs v2
  python evals/run.py --version v2    # single version
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.signals.classify import CLASSES, classify_banner  # noqa: E402

LABELLED = ROOT / "evals" / "labelled_banners.jsonl"
RUNS = ROOT / "evals" / "runs"
RESULTS_MD = ROOT / "evals" / "results.md"
COMPARE = ["v1", "v2"]
CLASS_LIST = sorted(CLASSES)


def load_labelled() -> list[dict]:
    return [json.loads(l) for l in LABELLED.read_text().splitlines() if l.strip()]


def evaluate(version: str, data: list[dict]) -> dict:
    rows = []
    for ex in data:
        pred = classify_banner(ex["banner"], prompt_version=version)["category"]
        rows.append({"banner": ex["banner"][:60], "expected": ex["expected"],
                     "predicted": pred, "correct": pred == ex["expected"]})

    per_class = {}
    for cls in CLASS_LIST:
        tp = sum(r["predicted"] == cls and r["expected"] == cls for r in rows)
        fp = sum(r["predicted"] == cls and r["expected"] != cls for r in rows)
        fn = sum(r["predicted"] != cls and r["expected"] == cls for r in rows)
        support = sum(r["expected"] == cls for r in rows)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[cls] = {"precision": round(prec, 3), "recall": round(rec, 3),
                          "f1": round(f1, 3), "support": support}

    labelled = [c for c in CLASS_LIST if per_class[c]["support"] > 0]
    macro_f1 = round(sum(per_class[c]["f1"] for c in labelled) / len(labelled), 3)
    accuracy = round(sum(r["correct"] for r in rows) / len(rows), 3)
    return {"version": version, "ts": datetime.now(timezone.utc).isoformat(),
            "n": len(rows), "accuracy": accuracy, "macro_f1": macro_f1,
            "per_class": per_class, "errors": [r for r in rows if not r["correct"]]}


def save_run(res: dict) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"service_classification_{res['version']}.json").write_text(json.dumps(res, indent=2))


def print_report(results: list[dict]) -> None:
    print("\n=== Service Classification — Eval Report ===")
    print(f"Labelled banners: {results[0]['n']}\n")
    print(f"{'version':<8}{'accuracy':>10}{'macro_f1':>10}")
    print("-" * 28)
    for r in results:
        print(f"{r['version']:<8}{r['accuracy']*100:>9.1f}%{r['macro_f1']:>10.3f}")
    if len(results) >= 2:
        print(f"\nΔ {results[0]['version']}→{results[-1]['version']}: "
              f"accuracy {(results[-1]['accuracy']-results[0]['accuracy'])*100:+.1f} pts, "
              f"macro-F1 {results[-1]['macro_f1']-results[0]['macro_f1']:+.3f}")
    latest = results[-1]
    print(f"\nPer-class ({latest['version']}):")
    print(f"  {'class':<16}{'prec':>7}{'recall':>8}{'f1':>7}{'support':>9}")
    for cls, m in latest["per_class"].items():
        if m["support"]:
            print(f"  {cls:<16}{m['precision']:>7.2f}{m['recall']:>8.2f}{m['f1']:>7.2f}{m['support']:>9}")
    if latest["errors"]:
        print(f"\nRemaining errors in {latest['version']}:")
        for e in latest["errors"]:
            print(f"  expected {e['expected']:<14} got {e['predicted']:<14} | {e['banner']}")


def write_results_md(results: list[dict]) -> None:
    L = ["# Service Classification — Eval Results", "",
         f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
         f"{results[0]['n']} hand-labelled real Shodan banners._", "",
         "> Feature: classify a raw service **banner** into "
         "`web / remote_access / database / mail / network_infra / unknown`. This is the "
         "LLM half of the rule-vs-LLM split — it reads free-text banners when the dbt SQL "
         "rules have no structured `product`/`cpe`/`tag` to go on.",
         "",
         "> With no `ANTHROPIC_API_KEY` the classifier runs in deterministic **mock** mode, "
         "version-aware so the harness reports a real v1→v2 delta offline; with a key the "
         "same harness measures the live model.", "",
         "| version | accuracy | macro-F1 |", "|---------|---------:|---------:|"]
    for r in results:
        L.append(f"| {r['version']} | {r['accuracy']*100:.1f}% | {r['macro_f1']:.3f} |")
    if len(results) >= 2:
        L.append(f"\n**Δ {results[0]['version']}→{results[-1]['version']}: "
                 f"{(results[-1]['accuracy']-results[0]['accuracy'])*100:+.1f} pts accuracy, "
                 f"{results[-1]['macro_f1']-results[0]['macro_f1']:+.3f} macro-F1.**")
    latest = results[-1]
    L += ["", f"## Per-class ({latest['version']})", "",
          "| class | precision | recall | f1 | support |",
          "|-------|----------:|-------:|---:|--------:|"]
    for cls, m in latest["per_class"].items():
        if m["support"]:
            L.append(f"| {cls} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | {m['support']} |")
    L += ["", f"## Known weaknesses ({latest['version']})", ""]
    if latest["errors"]:
        for e in latest["errors"]:
            L.append(f"- Expected `{e['expected']}`, got `{e['predicted']}` — \"{e['banner']}\"")
    else:
        L.append("- No errors on the current 28-banner set. It's small and hand-built; real "
                 "banners are messier (truncation, binary, TLS-wrapped). Next: grow to 100+, "
                 "add per-protocol adversarial cases, and calibrate confidence.")
    RESULTS_MD.write_text("\n".join(L) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version")
    args = ap.parse_args()
    data = load_labelled()
    versions = [args.version] if args.version else COMPARE
    results = [evaluate(v, data) for v in versions]
    for r in results:
        save_run(r)
    print_report(results)
    write_results_md(results)
    print("\nSaved artifacts -> evals/runs/  ·  report -> evals/results.md")


if __name__ == "__main__":
    main()
