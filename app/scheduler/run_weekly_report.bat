@echo off
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\.."

if not exist "logs" mkdir "logs"

call ".venv\Scripts\activate.bat"
python -m app.main --mode weekly >> "logs\weekly_report.log" 2>&1
