@echo off
setlocal
cd /d "%~dp0"
title Materials DMP Portable

if not exist "MaterialsDMP.exe" (
    echo [ERROR] MaterialsDMP.exe is missing.
    pause
    exit /b 1
)

"%~dp0MaterialsDMP.exe"
if errorlevel 1 (
    echo.
    echo The platform stopped with an error. Keep this window open when asking for support.
    pause
)
