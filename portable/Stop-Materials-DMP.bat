@echo off
taskkill /IM MaterialsDMP.exe /T >nul 2>&1
if errorlevel 1 (
    echo Materials DMP is not running.
) else (
    echo Materials DMP has been stopped.
)
pause
