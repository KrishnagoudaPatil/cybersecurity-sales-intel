"""Eval harness for signal classification. One command, no external deps.

Runs the classifier over the hand-labelled set for one or more prompt versions,
computes per-class precision/recall/F1 + macro-F1 + accuracy, prints a comparison,
saves a JSON artifact per version under evals/runs/, and regenerates evals/results.md.

Usage:
  python evals/run.py                 # compare all versions in COMPARE (v1 vs v2)
  python evals/run.py --version v2    # single version, diffed vs its last saved run
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.signals.classify import VALID_TYPES, classify_event  # noqa: E402

LABELLED = ROOT / "evals" / "labelled_signals.jsonl"
RUNS = ROOT / "evals" / "runs"
RESULTS_MD = ROOT / "evals" / "results.md"
COMPARE = ["v1", "v2"]
CLASSES = sorted(VALID_TYPES)


def load_labelled() -> list[dict]:
    return [json.loads(l) for l in LABELLED.read_text().splitlines() if l.strip()]


def evaluate(version: str, data: list[dict]) -> dict:
    rows = []
    for ex in data:
        pred = classify_event(ex["event"], prompt_version=version)["type"]
        rows.append({"event": ex["event"], "expected": ex["expected"], "predicted": pred,
                     "correct": pred == ex["expected"]})

    # per-class precision/recall/f1
    per_class = {}
    for cls in CLASSES:
        tp = sum(r["predicted"] == cls and r["expected"] == cls for r in rows)
        fp = sum(r["predicted"] == cls and r["expected"] != cls for r in rows)
        fn = sum(r["predicted"] != cls and r["expected"] == cls for r in rows)
        support = sum(r["expected"] == cls for r in rows)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[cls] = {"precision": round(prec, 3), "recall": round(rec, 3),
                          "f1": round(f1, 3), "support": support}

    labelled_classes = [c for c in CLASSES if per_class[c]["support"] > 0]
    macro_f1 = round(sum(per_class[c]["f1"] for c in labelled_classes) / len(labelled_classes), 3)
    accuracy = round(sum(r["correct"] for r in rows) / len(rows), 3)
    return {
        "version": version,
        "ts": datetime.now(timezone.utc).isoformat(),
        "n": len(rows),
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "errors": [r for r in rows if not r["correct"]],
    }


def save_run(res: dict) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"signal_classification_{res['version']}.json").write_text(json.dumps(res, indent=2))


def fmt_pct(x: float) -> str:
    return f"{x*100:5.1f}%"


def print_report(results: list[dict]) -> None:
    print("\n=== Signal Classification — Eval Report ===")
    print(f"Labelled examples: {results[0]['n']}\n")
    hdr = f"{'version':<8}{'accuracy':>10}{'macro_f1':>10}"
    print(hdr); print("-" * len(hdr))
    for r in results:
        print(f"{r['version']:<8}{fmt_pct(r['accuracy']):>10}{r['macro_f1']:>10.3f}")
    if len(results) >= 2:
        d_acc = results[-1]["accuracy"] - results[0]["accuracy"]
        d_f1 = results[-1]["macro_f1"] - results[0]["macro_f1"]
        print(f"\nΔ {results[0]['version']}→{results[-1]['version']}: "
              f"accuracy {d_acc*100:+.1f} pts, macro-F1 {d_f1:+.3f}")

    latest = results[-1]
    print(f"\nPer-class ({latest['version']}):")
    print(f"  {'class':<22}{'prec':>7}{'recall':>8}{'f1':>7}{'support':>9}")
    for cls, m in latest["per_class"].items():
        if m["support"]:
            print(f"  {cls:<22}{m['precision']:>7.2f}{m['recall']:>8.2f}{m['f1']:>7.2f}{m['support']:>9}")
    if latest["errors"]:
        print(f"\nRemaining errors in {latest['version']}:")
        for e in latest["errors"]:
            print(f"  expected {e['expected']:<20} got {e['predicted']:<20} | {e['event'][:60]}")


def write_results_md(results: list[dict]) -> None:
    lines = ["# Signal Classification — Eval Results", ""]
    lines.append(f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
                 f"{results[0]['n']} hand-labelled examples._")
    lines.append("")
    lines.append("> Note: with no `ANTHROPIC_API_KEY`, the classifier runs in deterministic "
                 "**mock** mode, which simulates each prompt version's expected behaviour so "
                 "the harness reports a real v1→v2 delta offline. With a key set, the same "
                 "harness measures the live model.")
    lines.append("")
    lines.append("| version | accuracy | macro-F1 |")
    lines.append("|---------|---------:|---------:|")
    for r in results:
        lines.append(f"| {r['version']} | {r['accuracy']*100:.1f}% | {r['macro_f1']:.3f} |")
    if len(results) >= 2:
        d_acc = (results[-1]["accuracy"] - results[0]["accuracy"]) * 100
        d_f1 = results[-1]["macro_f1"] - results[0]["macro_f1"]
        lines.append(f"\n**Δ {results[0]['version']}→{results[-1]['version']}: "
                     f"{d_acc:+.1f} pts accuracy, {d_f1:+.3f} macro-F1.**")
    latest = results[-1]
    lines += ["", f"## Per-class ({latest['version']})", "",
              "| class | precision | recall | f1 | support |",
              "|-------|----------:|-------:|---:|--------:|"]
    for cls, m in latest["per_class"].items():
        if m["support"]:
            lines.append(f"| {cls} | {m['precision']:.2f} | {m['recall']:.2f} | "
                         f"{m['f1']:.2f} | {m['support']} |")
    lines += ["", f"## Known weaknesses ({latest['version']})", ""]
    if latest["errors"]:
        for e in latest["errors"]:
            lines.append(f"- Expected `{e['expected']}`, got `{e['predicted']}` — \"{e['event']}\"")
    else:
        lines.append("- No errors on the current labelled set. This set is small (28) and "
                     "hand-built; real-world text will be messier. Next: expand to 100+ examples, "
                     "add adversarial/ambiguous cases, and track confidence calibration.")
    RESULTS_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", help="evaluate a single version (else compare v1 vs v2)")
    args = ap.parse_args()
    data = load_labelled()

    versions = [args.version] if args.version else COMPARE
    results = []
    for v in versions:
        res = evaluate(v, data)
        save_run(res)
        results.append(res)

    print_report(results)
    write_results_md(results)
    print(f"\nSaved artifacts -> evals/runs/  ·  report -> evals/results.md")


if __name__ == "__main__":
    main()
