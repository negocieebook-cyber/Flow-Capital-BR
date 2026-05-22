@echo off
cd /d C:\flow-map-brasil
call .venv\Scripts\activate
python -m app.main --mode weekly >> logs\weekly_report.log 2>&1
