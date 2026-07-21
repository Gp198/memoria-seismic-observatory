#!/usr/bin/env bash
set -euo pipefail
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
if [ ! -f "data/silver/events.csv" ] && [ ! -f "data/silver/events.parquet" ]; then
  python -m src.pipeline bootstrap-demo
fi
streamlit run app/streamlit_app.py
