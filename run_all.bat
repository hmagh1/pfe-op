@echo off
title MAF WebApp Launcher

echo ==============================
echo   MAF FULL STACK START
echo ==============================

REM ==============================
REM BACKEND SETUP
REM ==============================
echo.
echo [1/4] Setup Backend...

cd backend

IF NOT EXIST venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

echo Installing Python dependencies...
pip install --upgrade pip >nul
pip install fastapi uvicorn pandas openpyxl numpy scikit-learn python-multipart >nul

echo Backend ready.

REM ==============================
REM FRONTEND SETUP
REM ==============================
echo.
echo [2/4] Setup Frontend...

cd ..\frontend

IF NOT EXIST node_modules (
    echo Installing frontend dependencies...
    npm install
)

echo Frontend ready.

REM ==============================
REM START BACKEND
REM ==============================
echo.
echo [3/4] Starting Backend...

cd ..\backend
start cmd /k "venv\Scripts\activate && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 18000"

REM ==============================
REM START FRONTEND
REM ==============================
echo.
echo [4/4] Starting Frontend...

cd ..\frontend
start cmd /k "npm run dev"

echo.
echo ==============================
echo   ALL SERVICES STARTED
echo ==============================

echo Backend: http://127.0.0.1:18000/docs
echo Frontend: http://127.0.0.1:15173

pause