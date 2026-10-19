@echo off
title Cai dat AI Shorts Generator
echo ==========================================================
echo        AI SHORTS GENERATOR - 1-CLICK SETUP (WINDOWS)
echo ==========================================================
powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [Loi] Qua trinh cai dat gap loi (Exit code %ERRORLEVEL%).
    pause
    exit /b %ERRORLEVEL%
)
pause
exit /b 0
