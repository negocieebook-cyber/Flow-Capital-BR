@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_PATH=%SCRIPT_DIR%..\.."
set "BAT_PATH=%SCRIPT_DIR%run_weekly_report.bat"
set "TASK_NAME=Flow Map Brasil - Relatorio Semanal"

schtasks /Create /TN "%TASK_NAME%" /TR "\"%BAT_PATH%\"" /SC WEEKLY /D SAT /ST 08:00 /F

echo.
echo Tarefa criada ou atualizada:
echo %TASK_NAME%
echo.
echo Projeto:
for %%I in ("%PROJECT_PATH%") do echo %%~fI
echo.
pause
