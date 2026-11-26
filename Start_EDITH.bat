@echo off
title EDITH - Personal AI Assistant

cd /d "%~dp0"

echo.
echo ========================================
echo          EDITH v0.1 STARTUP
echo ========================================
echo.

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Python virtual environment not found!
    echo Expected: %PYTHON%
    pause
    exit /b 1
)

echo [1/2] Virtual environment found.
echo [2/2] Starting EDITH...
echo.

"%PYTHON%" -m app.main

echo.
echo ========================================
echo EDITH process has stopped.
echo ========================================
pause