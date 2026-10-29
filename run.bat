@echo off
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)
if not exist data\demo.db .venv\Scripts\python demo.py
.venv\Scripts\streamlit run app.py