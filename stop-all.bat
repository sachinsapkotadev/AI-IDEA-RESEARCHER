@echo off
title Stopping All Services
echo.
echo  Stopping AI Idea Researcher services...
echo.

:: Kill backend
taskkill /FI "TITLE eq Backend API" /T /F >nul 2>&1
echo  Backend stopped.

:: Kill website
taskkill /FI "TITLE eq Website Dev" /T /F >nul 2>&1
echo  Website stopped.

:: Kill any leftover uvicorn/node
taskkill /IM "uvicorn.exe" /F >nul 2>&1
taskkill /IM "node.exe" /F >nul 2>&1

echo.
echo  All services stopped.
timeout /t 2 /nobreak >nul
