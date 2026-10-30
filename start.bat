@echo off
title SIEIS - Smart Indoor Environmental Intelligence System
cd /d "%~dp0"

echo ========================================================
echo   Starting SIEIS - Smart Indoor Environmental Intelligence
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    echo Python virtual environment not found. Attempting py launcher...
    py run.py
)

pause
