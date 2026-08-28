#!/usr/bin/env bash
# One-command eval: compares prompt v1 vs v2 on the labelled set and writes results.md
set -euo pipefail
cd "$(dirname "$0")/.."
exec backend/.venv/bin/python evals/run.py "$@"
