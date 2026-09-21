@echo off
title AI Idea Researcher - Backend
cd /d "%~dp0"

echo ============================================
echo   AI Idea Researcher API
echo ============================================
echo.

:: Check if venv exists
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    echo.
)

:: Activate venv
call .venv\Scripts\activate.bat

:: Install dependencies if needed
if not exist ".venv\Lib\site-packages\fastapi" (
    echo Installing dependencies...
    pip install -r requirements.txt
    echo.
)

echo Starting server on http://localhost:8000
echo Press Ctrl+C to stop.
echo.
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
