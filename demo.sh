#!/bin/bash
# PHQ Intelligence Bot — Demo Launcher
# Run from repo root: ./demo.sh

set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Setting up demo environment (one time)..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements-demo.txt -q
  echo "Done."
fi

.venv/bin/python scripts/run_demo.py
