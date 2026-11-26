@echo off
title EDITH - Personal AI Assistant

cd /d "%~dp0"

set "HIDDEN_MODE="
if /I "%~1"=="hidden" set "HIDDEN_MODE=1"

if not defined HIDDEN_MODE goto hidden_setup_done
set "LOG_DIR=%LOCALAPPDATA%\EDITH\logs"
set "LOG_FILE=%LOCALAPPDATA%\EDITH\logs\edith.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
:hidden_setup_done

echo.
echo ========================================
echo          EDITH v0.1 STARTUP
echo ========================================
echo.

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    if defined HIDDEN_MODE (
        >>"%LOG_FILE%" echo [ERROR] Python virtual environment not found: %PYTHON%
        exit /b 1
    )
    echo [ERROR] Python virtual environment not found!
    echo Expected: %PYTHON%
    pause
    exit /b 1
)

echo [1/2] Virtual environment found.
echo [2/2] Starting EDITH...
echo.

if defined HIDDEN_MODE goto run_hidden

"%PYTHON%" -m app.main

set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo ========================================
echo EDITH process has stopped.
echo ========================================
pause
exit /b %EXIT_CODE%

:run_hidden
echo [%date% %time%] Starting EDITH in hidden mode.>>"%LOG_FILE%"
"%PYTHON%" -m app.main >>"%LOG_FILE%" 2>&1
exit /b %ERRORLEVEL%