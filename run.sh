#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi
[ -f data/demo.db ] || .venv/bin/python demo.py
.venv/bin/streamlit run app.py