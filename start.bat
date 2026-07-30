@echo off
setlocal enabledelayedexpansion
title Materials DMP

:: === Ensure we're in the script's directory ===
cd /d "%~dp0"

echo.
echo ============================================
echo   Materials DMP - Startup
echo ============================================
echo.

:: === Check Python ===
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: === Check Node.js ===
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 20+
    echo Download: https://nodejs.org/
    pause
    exit /b 1
)

echo [1/5] Setting up Python virtual environment...
if not exist "venv\" (
    python -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

echo [2/5] Installing backend dependencies...
call venv\Scripts\activate.bat

:: Clear any proxy settings that may interfere with pip
set ALL_PROXY=
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set SOCKS_PROXY=
set socks_proxy=

pip install --proxy="" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -q -r backend\requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install backend dependencies
    pause
    exit /b 1
)

echo [3/5] Initializing database...
cd backend
python -m scripts.init_roles
python -m scripts.seed_data
cd ..
if !errorlevel! neq 0 (
    echo [WARNING] Database init had issues, but continuing...
)

echo [4/5] Installing frontend dependencies...
cd frontend
call npm config set registry https://registry.npmmirror.com
call npm install
cd ..
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install frontend dependencies
    pause
    exit /b 1
)

echo [5/5] Starting services...
echo.
echo ============================================
echo   Backend API:  http://localhost:8000
echo   API Docs:    http://localhost:8000/api/v1/docs
echo   Frontend:    http://localhost:5173
echo   Login:       admin / admin123
echo ============================================
echo.

:: Start backend in a new window (keep window open with /k so errors are visible)
echo Starting backend...
start "Materials-DMP-Backend" cmd /k "cd /d %~dp0backend && echo Backend starting... && title Backend - Materials DMP && ..\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: Wait for backend to be ready
echo Waiting for backend (up to 15s)...
python -c "import urllib.request, time; [time.sleep(2) or urllib.request.urlopen('http://localhost:8000/health') for _ in range(8)]" 2>nul
if !errorlevel! neq 0 (
    echo [WARNING] Backend did not respond. Check the "Backend - Materials DMP" window.
)

:: Start frontend
echo Starting frontend...
cd frontend
call npm run dev

pause
