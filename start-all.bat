@echo off
title AI Idea Researcher — Full Stack
echo.
echo  ============================================
echo   AI Idea Researcher — Starting All Services
echo  ============================================
echo.

:: ─── Backend ───────────────────────────────────
echo [1/4] Starting Backend...
cd /d "%~dp0Backend"

:: Activate venv if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Start backend in new window
start "Backend API" cmd /k "title Backend API — localhost:8000 && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo      Backend starting on http://localhost:8000

:: Wait for backend to boot
echo [2/4] Waiting for backend to boot...
timeout /t 4 /nobreak >nul

:: ─── Website ───────────────────────────────────
echo [3/4] Starting Website...
cd /d "%~dp0Website"

:: Start website in new window
start "Website Dev" cmd /k "title Website — localhost:4321 && npm run dev"
echo      Website starting on http://localhost:4321

:: Wait for website to boot
timeout /t 5 /nobreak >nul

:: ─── Open Browsers ─────────────────────────────
echo [4/4] Opening browsers...
start http://localhost:8000/docs
start http://localhost:4321/dashboard

echo.
echo  ============================================
echo   All services running!
echo   Backend API docs : http://localhost:8000/docs
echo   Website dashboard: http://localhost:4321/dashboard
echo   Server Status    : http://localhost:4321/dashboard/status
echo   AI Research Chat : http://localhost:4321/dashboard/chat
echo  ============================================
echo.
echo  Close this window or press Ctrl+C to stop all.
pause
